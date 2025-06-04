import asyncio
import logging
from collections.abc import Callable
from typing import Any, Literal, cast

from pydantic import BaseModel, ValidationError

from api.services._utils import apply_reviews
from api.services.analytics import AnalyticsService
from api.services.runs._run_conversation_handler import RunConversationHandler
from api.services.runs._run_file_handler import FileHandler
from api.services.runs._stored_message import StoredMessages
from core.domain.agent_run import AgentRun
from core.domain.analytics_events.analytics_events import (
    EventProperties,
    RanTaskEventProperties,
    RunTrigger,
    SourceType,
)
from core.domain.errors import InternalError
from core.domain.events import Event, EventRouter, RunCreatedEvent
from core.domain.llm_completion import LLMCompletion
from core.domain.llm_usage import LLMUsage
from core.domain.models import Model, Provider
from core.domain.page import Page
from core.domain.task_run_query import SerializableTaskRunField, SerializableTaskRunQuery
from core.domain.task_variant import SerializableTaskVariant
from core.domain.users import UserIdentifier
from core.providers.base.models import StandardMessage
from core.providers.factory.abstract_provider_factory import AbstractProviderFactory
from core.storage import ObjectNotFoundException, TaskTuple
from core.storage.abstract_storage import AbstractStorage
from core.storage.azure.azure_blob_file_storage import FileStorage
from core.storage.backend_storage import BackendStorage
from core.utils.coroutines import capture_errors
from core.utils.dicts import delete_at_keypath

from ._run_previews import assign_run_previews

_logger = logging.getLogger("RunsService")


class LLMCompletionTypedMessages(BaseModel):
    messages: list[StandardMessage]
    response: str | None = None
    usage: LLMUsage
    duration_seconds: float | None = None
    provider_config_id: str | None = None
    provider: Provider | None = None
    model: Model | None = None
    cost_usd: float | None = None

    @classmethod
    def from_domain(cls, messages: list[StandardMessage], c: LLMCompletion):
        return cls(
            messages=messages,
            response=c.response,
            usage=c.usage,
            duration_seconds=c.duration_seconds,
            provider_config_id=c.config_id,
            provider=c.provider,
            model=c.model,
            cost_usd=c.usage.cost_usd,
        )


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

    def _sanitize_run(self, run: AgentRun) -> AgentRun:
        if run.llm_completions:
            for c in run.llm_completions:
                c.messages = self._sanitize_llm_messages(c.provider, c.messages)

        return run

    async def list_runs(self, task_uid: int, query: SerializableTaskRunQuery) -> Page[AgentRun]:
        storage = self._storage.task_runs

        res = [self._sanitize_run(a) async for a in storage.fetch_task_run_resources(task_uid, query)]
        await apply_reviews(self._storage.reviews, query.task_id, res, _logger)
        return Page(items=res)

    # TODO[test]: add tests for max wait ms
    async def run_by_id(
        self,
        task_id: TaskTuple,
        id: str,
        include: set[SerializableTaskRunField] | None = None,
        exclude: set[SerializableTaskRunField] | None = None,
        max_wait_ms: int | None = None,
        retry_delay_ms: int = 100,
    ) -> AgentRun:
        async def _find_run():
            raw = await self._storage.task_runs.fetch_task_run_resource(task_id, id, exclude=exclude, include=include)
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
        is_active: bool | None = None,
        exclude_fields: set[SerializableTaskRunField] = {"llm_completions"},
    ) -> AgentRun:
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
            exclude_fields=exclude_fields,
            limit=1,
            status=status,
            is_active=is_active,
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

        llm_completions_typed = [
            LLMCompletionTypedMessages.from_domain(self._sanitize_llm_messages_typed(c.provider, c.messages), c)
            for c in run.llm_completions
        ]

        return LLMCompletionsResponse(completions=llm_completions_typed)

    @classmethod
    async def _compute_cost(cls, task_run: AgentRun, provider_factory: AbstractProviderFactory):
        """Make sure the cost is computed for a task run for each completion. This function relies solely
        on the completions and not on the input / output"""
        # TODO: refactor to make that clear when we remove the provider for pricing
        if not task_run.llm_completions:
            _logger.warning("no completions found for task run", extra={"task_run": task_run})
            return

        try:
            model = Model(task_run.group.properties.model)
        except ValueError:
            _logger.warning(
                "invalid model in task run",
                extra={"task_run_id": task_run.id},
            )
            return

        async with asyncio.TaskGroup() as tg:
            for completion in task_run.llm_completions:
                provider = provider_factory.get_provider(completion.provider)
                tg.create_task(provider.finalize_completion(model, completion, timeout=None))

        task_run.cost_usd = sum(c.usage.cost_usd for c in task_run.llm_completions if c.usage and c.usage.cost_usd)

    @classmethod
    def _strip_private_fields(cls, task_run: AgentRun):
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
    def _strip_llm_completions(cls, completions: list[LLMCompletion] | None):
        """Remove potentially private LLM data from LLM completions"""
        if not completions:
            return

        for completion in completions:
            completion.messages = []
            completion.response = None

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
        task_run: AgentRun,
        user_identifier: UserIdentifier | None = None,
        trigger: RunTrigger | None = None,
        source: SourceType | None = None,
    ) -> AgentRun:
        # Strip private fields before storing files in case one of the files contains private data
        task_run = cls._strip_private_fields(task_run)

        # Compute cost, no need to download files before hand. Cost is computed based on the completions
        try:
            await cls._compute_cost(task_run, provider_factory)
        except Exception as e:
            _logger.exception("error computing cost for task run", exc_info=e, extra={"task_run": task_run})

        messages: StoredMessages | None = None
        if task_variant.input_schema.uses_messages:
            try:
                messages = StoredMessages.model_validate(task_run.task_input)
            except ValidationError:
                _logger.exception("error validating messages for task run", extra={"task_run": task_run})

        if messages:
            with capture_errors(logger=_logger, msg="Could not handle conversation"):
                conversation_handler = RunConversationHandler(
                    task_uid=task_variant.task_uid,
                    schema_id=task_variant.task_schema_id,
                    kv_storage=storage.kv,
                )
                await conversation_handler.handle_run(task_run, messages)

        # Replace base64 and outside urls with storage urls in payloads
        file_handler = FileHandler(file_storage, f"{storage.tenant}/{task_run.task_id}")
        await file_handler.handle_run(task_run, task_variant, messages)

        # Removing LLM completions if there are private fields
        if task_run.private_fields:
            cls._strip_llm_completions(task_run.llm_completions)

        with capture_errors(logger=_logger, msg="Could not assign run previews"):
            assign_run_previews(task_run, messages)

        if messages:
            task_run.task_input = messages.dump_for_input()

        stored = await storage.store_task_run_resource(task_variant, task_run, user_identifier, source)

        event_router(RunCreatedEvent(run=stored))
        analytics_handler(lambda: RanTaskEventProperties.from_task_run(stored, trigger))
        return stored

    async def store_task_run(
        self,
        task_variant: SerializableTaskVariant,
        task_run: AgentRun,
        user_identifier: UserIdentifier | None = None,
        trigger: RunTrigger | None = None,
        user_source: SourceType | None = None,
    ) -> AgentRun:
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
