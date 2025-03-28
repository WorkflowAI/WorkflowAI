import asyncio
import logging
from collections.abc import Callable
from typing import Any, Literal, TypeVar, cast

from pydantic import BaseModel
from pymongo.errors import DocumentTooLarge

from api.services._utils import apply_reviews
from api.services.analytics import AnalyticsService
from core.domain.analytics_events.analytics_events import (
    EventProperties,
    RanTaskEventProperties,
    RunTrigger,
    SourceType,
)
from core.domain.errors import InternalError, InvalidFileError
from core.domain.events import Event, EventRouter, RunCreatedEvent
from core.domain.llm_usage import LLMUsage
from core.domain.models import Model, Provider
from core.domain.models.utils import get_model_data
from core.domain.page import Page
from core.domain.task_run import SerializableTaskRun
from core.domain.task_run_query import SerializableTaskRunField, SerializableTaskRunQuery
from core.domain.task_variant import SerializableTaskVariant
from core.domain.users import UserIdentifier
from core.providers.base.models import StandardMessage
from core.providers.factory.abstract_provider_factory import AbstractProviderFactory
from core.runners.workflowai.utils import (
    FileWithKeyPath,
    download_file,
    extract_files,
    is_schema_containing_legacy_file,
)
from core.storage import ObjectNotFoundException, TaskTuple
from core.storage.abstract_storage import AbstractStorage
from core.storage.azure.azure_blob_file_storage import CouldNotStoreFileError, FileStorage
from core.storage.backend_storage import BackendStorage
from core.storage.file_storage import FileData
from core.utils.dicts import InvalidKeyPathError, delete_at_keypath, set_at_keypath
from core.utils.models.dumps import safe_dump_pydantic_model

# TODO: move to __init__ when we have removed classmethods
_logger = logging.getLogger("RunsService")

_R = TypeVar("_R", bound=BaseModel)


class LLMCompletionTypedMessages(BaseModel):
    messages: list[StandardMessage]
    response: str | None = None
    usage: LLMUsage
    duration_seconds: float | None = None


class LLMCompletionsResponse(BaseModel):
    completions: list[LLMCompletionTypedMessages]


class RunsService:
    def __init__(
        self,
        storage: BackendStorage,
        provider_factory: AbstractProviderFactory,
        event_router: EventRouter,
        analytics_service: AnalyticsService,
        file_storage: FileStorage,
    ):
        self._storage = storage
        self._provider_factory = provider_factory
        self._event_router = event_router
        self._analytics_service = analytics_service
        self._file_storage = file_storage

    def _sanitize_llm_messages(self, provider: Provider, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert provider messages to the openai format so that it's properly displayed in the UI"""
        try:
            provider_obj = self._provider_factory.get_provider(provider)
            return cast(list[dict[str, Any]], provider_obj.standardize_messages(messages))
        except Exception:
            _logger.exception(
                "Error sanitizing messages for provider",
                extra={
                    "provider": provider,
                    "messages": messages,
                },
            )
            return messages

    def _sanitize_run(self, run: SerializableTaskRun) -> SerializableTaskRun:
        if run.llm_completions:
            for c in run.llm_completions:
                c.messages = self._sanitize_llm_messages(c.provider, c.messages)

        return run

    async def list_runs(self, task_uid: int, query: SerializableTaskRunQuery) -> Page[SerializableTaskRun]:
        storage = self._storage.task_runs

        res = [self._sanitize_run(a) async for a in storage.fetch_task_run_resources(task_uid, query)]
        await apply_reviews(self._storage.reviews, query.task_id, res, _logger)
        return Page(items=res)

    # TODO[test]: add tests for max wait ms
    async def run_by_id(
        self,
        task_id: TaskTuple,
        id: str,
        exclude: set[SerializableTaskRunField] | None = None,
        max_wait_ms: int | None = None,
        retry_delay_ms: int = 100,
    ) -> SerializableTaskRun:
        async def _find_run():
            raw = await self._storage.task_runs.fetch_task_run_resource(task_id, id, exclude=exclude)
            run = self._sanitize_run(raw)
            await apply_reviews(self._storage.reviews, task_id[0], [run], _logger)
            return run

        if not max_wait_ms:
            return await _find_run()

        max_retries = int(max_wait_ms / retry_delay_ms) if max_wait_ms else 1
        # If we retry immediately after a run returns, the run might not have been saved yet
        # So we allow to wait for a bit
        for i in range(max_retries):
            try:
                return await _find_run()
            except ObjectNotFoundException:
                if i == max_retries - 1:
                    raise ObjectNotFoundException(f"Run {id} not found after {max_wait_ms}ms", extra={"run_id": id})
                await asyncio.sleep(retry_delay_ms / 1000)

        # We are raising above so this should never be reached
        raise InternalError("We should never reach this point", extra={"run_id": id})

    async def latest_run(
        self,
        task_uid: TaskTuple,
        schema_id: int | None,
        is_success: bool | None,
    ) -> SerializableTaskRun:
        """Returns the latest successful run for a task and optionally a schema"""

        status: set[Literal["success", "failure"]] | None = None
        match is_success:
            case True:
                status = {"success"}
            case False:
                status = {"failure"}
            case None:
                pass

        q = SerializableTaskRunQuery(
            task_id=task_uid[0],
            task_schema_id=schema_id,
            exclude_fields={"llm_completions"},
            limit=1,
            status=status,
        )
        try:
            return await anext(self._storage.task_runs.fetch_task_run_resources(task_uid=task_uid[1], query=q))
        except StopAsyncIteration:
            raise ObjectNotFoundException(f"No run found for task {task_uid} and schema {schema_id}")

    def _sanitize_llm_messages_typed(
        self,
        provider: Provider,
        messages: list[dict[str, Any]],
    ) -> list[StandardMessage]:
        provider_obj = self._provider_factory.get_provider(provider)
        return provider_obj.standardize_messages(messages)

    async def llm_completions_by_id(self, task_id: TaskTuple, id: str) -> LLMCompletionsResponse:
        run = await self._storage.task_runs.fetch_task_run_resource(
            task_id,
            id,
            include={"llm_completions", "metadata", "group.properties"},
        )

        if not run.llm_completions:
            return LLMCompletionsResponse(completions=[])

        llm_completions_typed: list[LLMCompletionTypedMessages] = []

        for c in run.llm_completions:
            t: LLMCompletionTypedMessages = LLMCompletionTypedMessages(
                messages=self._sanitize_llm_messages_typed(c.provider, c.messages),
                response=c.response,
                usage=c.usage,
                duration_seconds=c.duration_seconds,
            )
            llm_completions_typed.append(t)
        return LLMCompletionsResponse(completions=llm_completions_typed)

    @classmethod
    async def _apply_files(
        cls,
        payload: dict[str, Any],
        files: list[FileWithKeyPath],
        include: set[str] | None,
        exclude: set[str] | None,
    ):
        for file in files:
            if not file.url:
                file.url = file.storage_url
            try:
                set_at_keypath(
                    payload,
                    file.key_path,
                    file.model_dump(include=include, exclude_none=True, exclude=exclude),
                )
            except InvalidKeyPathError as e:
                _logger.exception(
                    "Error setting file in task run input",
                    extra={"file": file.model_dump(exclude={"data"})},
                    exc_info=e,
                )
                continue

    # TODO: merge with instance method when workflowai.py is removed
    # Staticmethod is only used as a bridge to avoid adding a new dependency on workflowai.py
    @classmethod
    async def _store_files(
        cls,
        file_storage: FileStorage,
        folder_path: str,
        files: list[FileWithKeyPath],
    ) -> list[FileWithKeyPath]:
        for file in files:
            bts = file.content_bytes()
            if not bts:
                # Skipping, only reason a file might not have data is if it's private
                continue

            try:
                file.storage_url = await file_storage.store_file(
                    FileData(contents=bts, content_type=file.content_type),
                    folder_path=folder_path,
                )
            except CouldNotStoreFileError as e:
                _logger.exception(
                    "Error storing file",
                    extra={"file": file.model_dump(exclude={"data"})},
                    exc_info=e,
                )
                continue

        return files

    @classmethod
    async def _download_files_if_needed(cls, files: list[FileWithKeyPath]):
        try:
            async with asyncio.TaskGroup() as tg:
                for file in files:
                    if file.url and not file.data:
                        tg.create_task(download_file(file))
        except* InvalidFileError as e:
            # We fail silently here, that can happen if the file is not found
            # Usually we should return an error before, for example when the file fails to be downloaded
            # from either us or the provider
            _logger.exception("error downloading file", exc_info=e)

    @classmethod
    def _provider_for_pricing_task_run(cls, task_run: SerializableTaskRun, model: Model):
        if task_run.group.properties.provider:
            try:
                return Provider(task_run.group.properties.provider)
            except ValueError:
                _logger.warning(
                    "invalid provider in task run",
                    extra={"task_run_id": task_run.id, "task_run": safe_dump_pydantic_model(task_run)},
                )
                # Skipping will use the fallback provider
        return get_model_data(model).provider_for_pricing

    @classmethod
    async def _compute_cost(cls, task_run: SerializableTaskRun, provider_factory: AbstractProviderFactory):
        if not task_run.llm_completions:
            _logger.warning("no completions found for task run", extra={"task_run": task_run})
            return

        try:
            model = Model(task_run.group.properties.model)
        except ValueError:
            _logger.warning(
                "invalid model in task run",
                extra={"task_run_id": task_run.id, "task_run": safe_dump_pydantic_model(task_run)},
            )
            return

        provider = provider_factory.get_provider(cls._provider_for_pricing_task_run(task_run, model))

        await provider.finalize_completions(model, task_run.llm_completions)

        task_run.cost_usd = sum(c.usage.cost_usd for c in task_run.llm_completions if c.usage and c.usage.cost_usd)

    @classmethod
    def _strip_private_fields(cls, task_run: SerializableTaskRun):
        if not task_run.private_fields:
            return task_run

        # Sorting to strip root keys before leaf ones
        # e-g task_input before task_input.hello
        fields = list(task_run.private_fields)
        fields.sort()

        for field in fields:
            if field.startswith("task_input"):
                # 11 = len("task_input."")
                no_prefix = field[11:]
                if not no_prefix:
                    # No key path -> we strip the entire task input
                    task_run.task_input = {}
                else:
                    task_run.task_input = delete_at_keypath(task_run.task_input, no_prefix.split("."))
            elif field.startswith("task_output"):
                # 12 = len("task_output.")
                no_prefix = field[12:]
                if not no_prefix:
                    # No key path -> we strip the entire task output
                    task_run.task_output = {}
                else:
                    task_run.task_output = delete_at_keypath(task_run.task_output, no_prefix.split("."))
            else:
                _logger.warning("unknown private field", extra={"field": field})

        return task_run

    @classmethod
    def _strip_llm_completions(cls, task_run: SerializableTaskRun):
        if not task_run.llm_completions:
            return task_run

        for completion in task_run.llm_completions:
            completion.messages = []
            completion.response = None
        return task_run

    # TODO: the below functions are not optimized, we are extracting and applying files twice and iterating over the
    # files multiple times
    # It's ok for now since this will run in the background
    @classmethod
    async def _extract_download_and_apply_files(cls, schema: dict[str, Any], payload: dict[str, Any]):
        # In legacy tasks, the files are stored directly in the payload
        if is_schema_containing_legacy_file(schema):
            return False

        # Otherwise we extract all the files
        _, _, files = extract_files(schema, payload)
        if not files:
            return False

        # Download them
        await cls._download_files_if_needed(files)
        # And set them in the payload
        # Files will be applied with all their fields
        await cls._apply_files(payload, files, include=None, exclude={"key_path"})

        return True

    @classmethod
    async def _extract_and_store_files(
        cls,
        schema: dict[str, Any],
        payload: dict[str, Any],
        file_storage: FileStorage,
        folder_path: str,
    ):
        _, _, files = extract_files(schema, payload)
        await cls._store_files(file_storage, folder_path, files)
        # Data is stripped from the files
        await cls._apply_files(payload, files, {"content_type", "url", "storage_url"}, exclude={"key_path"})

    # TODO: merge with instance method when workflowai.py is removed
    # Staticmethod is only used as a bridge to avoid adding a new dependency on workflowai.py
    @classmethod
    async def store_task_run_fn(
        cls,
        storage: AbstractStorage,
        file_storage: FileStorage,
        event_router: Callable[[Event], None],
        analytics_handler: Callable[[Callable[[], EventProperties]], None],
        provider_factory: AbstractProviderFactory,
        task_variant: SerializableTaskVariant,
        task_run: SerializableTaskRun,
        user_identifier: UserIdentifier | None = None,
        trigger: RunTrigger | None = None,
        source: SourceType | None = None,
    ) -> SerializableTaskRun:
        # Extract data of files in the task run input only, download files if needed
        should_store_files = await cls._extract_download_and_apply_files(
            schema=task_variant.input_schema.json_schema,
            payload=task_run.task_input,
        )

        # Compute cost
        try:
            await cls._compute_cost(task_run, provider_factory)
        except Exception as e:
            _logger.exception("error computing cost for task run", exc_info=e, extra={"task_run": task_run})

        # Strip private fields before storing files in case one of the files contains private data
        task_run = cls._strip_private_fields(task_run)
        # Upload files to Azure Blob Storage
        folder_path = f"{storage.tenant}/{task_run.task_id}"
        # Re-extracting files as some data might have been stripped
        if should_store_files:
            await cls._extract_and_store_files(
                schema=task_variant.input_schema.json_schema,
                payload=task_run.task_input,
                file_storage=file_storage,
                folder_path=folder_path,
            )
        # Removing LLM completions if there are private fields
        # TODO: be more granular
        if task_run.private_fields and task_run.llm_completions:
            task_run = cls._strip_llm_completions(task_run)

        try:
            # Store task run
            stored = await storage.store_task_run_resource(task_variant, task_run, user_identifier, source)
        except DocumentTooLarge:
            _logger.warning("task run document too large", extra={"task_run_id": task_run.id})
            task_run = cls._strip_llm_completions(task_run)
            stored = await storage.store_task_run_resource(task_variant, task_run, user_identifier, source)

        event_router(RunCreatedEvent(run=stored))
        analytics_handler(lambda: RanTaskEventProperties.from_task_run(stored, trigger))
        return stored

    async def store_task_run(
        self,
        task_variant: SerializableTaskVariant,
        task_run: SerializableTaskRun,
        user_identifier: UserIdentifier | None = None,
        trigger: RunTrigger | None = None,
        user_source: SourceType | None = None,
    ) -> SerializableTaskRun:
        return await self.store_task_run_fn(
            self._storage,
            self._file_storage,
            self._event_router,
            self._analytics_service.send_event,
            self._provider_factory,
            task_variant,
            task_run,
            user_identifier,
            trigger,
            user_source,
        )
