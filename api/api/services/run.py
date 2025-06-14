import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Iterable, Optional

from fastapi import Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sentry_sdk import new_scope

from api.services.analytics import AnalyticsService
from api.services.groups import GroupService
from api.services.internal_tasks.moderation_service import capture_content_moderation_error
from core.domain.agent_run import AgentRun
from core.domain.analytics_events.analytics_events import RanTaskEventProperties, RunTrigger, SourceType
from core.domain.error_response import ErrorResponse
from core.domain.errors import (
    BadRequestError,
    DefaultError,
    InternalError,
)
from core.domain.events import EventRouter, StoreTaskRunEvent
from core.domain.message import Messages
from core.domain.run_output import RunOutput
from core.domain.task_run_builder import TaskRunBuilder
from core.domain.task_run_reply import RunReply
from core.domain.task_variant import SerializableTaskVariant
from core.domain.tool_call import ToolCall, ToolCallOutput, ToolCallRequestWithID
from core.domain.types import CacheUsage
from core.domain.users import UserIdentifier
from core.providers.base.provider_error import ContentModerationError, ProviderError
from core.runners.abstract_runner import AbstractRunner
from core.runners.workflowai.workflowai_runner import WorkflowAIRunner
from core.storage import TenantTuple
from core.storage.azure.azure_blob_file_storage import FileStorage
from core.storage.backend_storage import BackendStorage


def _format_model(model: BaseModel, exclude_none: bool = True) -> str:
    return f"data: {model.model_dump_json(exclude_none=exclude_none)}\n\n"


class RunService:
    """The run service is on the critical path so should be thoroughly tested and as efficient as possible"""

    def __init__(
        self,
        storage: BackendStorage,
        event_router: EventRouter,
        group_service: GroupService,
        analytics_service: AnalyticsService,
        user: UserIdentifier | None,
    ):
        self._storage = storage

        self._event_router = event_router
        self._logger = logging.getLogger(self.__class__.__name__)
        self.group_service = group_service
        self.analytics_service = analytics_service
        self.user = user

    async def stream_run(
        self,
        builder: TaskRunBuilder,
        runner: AbstractRunner[Any],
        cache: CacheUsage,
        trigger: RunTrigger,
        chunk_serializer: Callable[[str, RunOutput], BaseModel | None],
        serializer: Callable[[AgentRun], BaseModel | None],
        source: SourceType | None,
        store_inline: bool = False,
        file_storage: FileStorage | None = None,
    ) -> AsyncGenerator[str, None]:
        try:
            chunk: RunOutput | None = None
            async for chunk in self.stream_from_builder(
                builder=builder,
                runner=runner,
                cache=cache,
                trigger=trigger,
                user=self.user,
                store_inline=store_inline,
                source=source,
                file_storage=file_storage,
            ):
                if chunk and (serialized := chunk_serializer(builder.id, chunk)):
                    yield _format_model(serialized)

            # TODO: We are streaming one too many chunks here. Both the abstract provider and below
            # Stream the final chunk which leads to duplicate final chunks
            if run := builder.task_run:
                if final_chunk := serializer(run):
                    yield _format_model(final_chunk)
        except ContentModerationError as e:
            yield _format_model(e.error_response(), exclude_none=True)
            capture_content_moderation_error(e, self._storage.tenant, builder.task.name)
        except ProviderError as e:
            e.capture_if_needed()
            yield _format_model(e.error_response(), exclude_none=True)
        except DefaultError as e:
            e.capture_if_needed()
            yield _format_model(e.error_response(), exclude_none=True)
        except Exception as e:
            with new_scope() as scope:
                scope.set_level("fatal")
                self._logger.exception("Unknown error in stream run", exc_info=e)
            yield _format_model(ErrorResponse.internal_error())

    async def prepare_builder(
        self,
        task_input: dict[str, Any] | Messages,
        runner: AbstractRunner[Any],
        task_run_id: Optional[str],
        metadata: Optional[dict[str, Any]],
        start_time: float,
        author_tenant: TenantTuple | None,
        private_fields: set[str] | None,
        is_different_version: bool,
        conversation_id: str | None,
    ):
        builder = await runner.task_run_builder(
            input=task_input,
            task_run_id=task_run_id,
            metadata=metadata,
            private_fields=private_fields,
            start_time=start_time,
            conversation_id=conversation_id,
        )
        builder.author_uid = author_tenant[1] if author_tenant else None
        builder.author_tenant = author_tenant[0] if author_tenant else None
        builder.version_changed = is_different_version
        return builder

    # TODO: remove this function and use a combo prepare_builder + run_from_builder + stream
    # when we have removed the deprecated endpoint
    async def run(
        self,
        task_input: dict[str, Any] | Messages,
        runner: AbstractRunner[Any],
        task_run_id: Optional[str],
        stream_serializer: Callable[[str, RunOutput], BaseModel | None] | None,
        cache: CacheUsage,
        metadata: Optional[dict[str, Any]],
        trigger: RunTrigger,
        serializer: Callable[[AgentRun], BaseModel],
        start_time: float,
        author_tenant: TenantTuple | None = None,
        stream_last_chunk: bool = False,
        store_inline: bool = False,
        private_fields: set[str] | None = None,
        conversation_id: str | None = None,
        # Deprecated: we should not need the source here but we need it when storing inline for
        # the old run endpoint
        source: SourceType | None = None,
        is_different_version: bool = False,
        file_storage: FileStorage | None = None,
    ) -> Response:
        builder = await self.prepare_builder(
            task_input=task_input,
            runner=runner,
            task_run_id=task_run_id,
            metadata=metadata,
            private_fields=private_fields,
            start_time=start_time,
            author_tenant=author_tenant,
            is_different_version=is_different_version,
            conversation_id=conversation_id,
        )
        if stream_serializer:
            return StreamingResponse(
                self.stream_run(
                    builder=builder,
                    runner=runner,
                    cache=cache,
                    trigger=trigger,
                    chunk_serializer=stream_serializer,
                    serializer=serializer if stream_last_chunk else lambda _: None,
                    store_inline=store_inline,
                    source=source,
                    file_storage=file_storage,
                ),
                media_type="text/event-stream",
            )

        task_run = await self.run_from_builder(
            builder=builder,
            runner=runner,
            cache=cache,
            trigger=trigger,
            store_inline=store_inline,
            source=source,
            file_storage=file_storage,
        )
        return JSONResponse(content=serializer(task_run).model_dump(mode="json"))

    def _combine_tool_calls(
        self,
        requests: Iterable[ToolCallRequestWithID] | None,
        outputs: Iterable[ToolCallOutput] | None,
    ) -> list[ToolCall] | None:
        if not outputs:
            return None
        if not requests:
            raise BadRequestError("Cannot reply with tool calls to a run without tool calls", capture=True)
        return ToolCall.combine(requests, outputs)

    async def reply(
        self,
        runner: AbstractRunner[Any],
        to_run: AgentRun,
        user_message: str | None,
        tool_calls: Iterable[ToolCallOutput] | None,
        metadata: dict[str, Any] | None,
        serializer: Callable[[AgentRun], BaseModel],
        start_time: float,
        stream_serializer: Callable[[str, RunOutput], BaseModel] | None = None,
        is_different_version: bool = False,
    ):
        if to_run.status != "success":
            raise BadRequestError("Cannot reply to a non-successful run", capture=True)
        if not to_run.llm_completions:
            raise InternalError("No LLM completions found in previous run", extra={"run_id": to_run.id})
        # We get the last completion
        previous_completion = to_run.llm_completions[-1]
        # Annoying to cast here but run_by_id will have standardized the messages
        # We can't use `llm_completions_by_id` because we need the task input and the tool calls
        try:
            messages = previous_completion.to_messages()
        except Exception:
            raise InternalError("Failed to parse previous messages", extra={"run_id": to_run.id})

        # Now we can build the task run reply object with the previous data
        reply = RunReply(
            previous_run_id=to_run.id,
            previous_messages=messages,
            user_message=user_message,
            tool_calls=self._combine_tool_calls(to_run.tool_call_requests, tool_calls),
        )

        builder = await runner.task_run_builder(
            input=runner.task.validate_input(to_run.task_input),
            metadata=metadata,
            reply=reply,
            start_time=start_time,
        )
        builder.version_changed = is_different_version
        if stream_serializer:
            return StreamingResponse(
                self.stream_run(
                    builder=builder,
                    runner=runner,
                    cache="never",
                    trigger="user",
                    chunk_serializer=stream_serializer,
                    serializer=serializer,
                    store_inline=False,
                    source=None,  # see comment above, not needed when not storing inline
                    file_storage=None,  # same
                ),
                media_type="text/event-stream",
            )

        task_run = await self.run_from_builder(
            builder=builder,
            runner=runner,
            cache="never",
            trigger="user",
            store_inline=False,
            source=None,  # see comment above, not needed when not storing inline
        )

        return JSONResponse(content=serializer(task_run).model_dump(mode="json", exclude_none=True))

    async def _store_task_run(
        self,
        task: SerializableTaskVariant,
        run: AgentRun,
        trigger: RunTrigger | None,
        user: UserIdentifier | None = None,
        store_inline: bool = True,
        source: SourceType | None = None,
        file_storage: FileStorage | None = None,
    ):
        # if the run was cached, we don't need to store it but we still send the analytics
        if run.from_cache:
            self._send_run_analytics(run, trigger)
            return run

        if store_inline:
            self._logger.warning(
                "Storing runs inline is deprecated and will be removed in a future release",
                extra={"task_id": task.id, "task_uid": task.task_uid, "run_id": run.id, "tenant": self._storage.tenant},
            )

            # Soon we will no longer store runs inline + this class will be removed
            # For now, let's just use the runs service static method to store the run
            from api.services.runs.runs_service import RunsService

            if not file_storage:
                raise InternalError("File storage is required to store runs inline")

            return await RunsService.store_task_run_fn(
                self._storage,
                file_storage,
                self._event_router,
                self.analytics_service.send_event,
                # TODO: inject
                WorkflowAIRunner.provider_factory,
                task,
                run,
                user,
                trigger,
                source=source,
            )

        task_run = run
        # We can't send the analytics now since we want data in analytics that is
        # set when the run is stored (e.g. group iteration)
        self._event_router(StoreTaskRunEvent(task=task, run=task_run, trigger=trigger))

        return task_run

    def _send_run_analytics(self, run: AgentRun, trigger: RunTrigger | None):
        self.analytics_service.send_event(lambda: RanTaskEventProperties.from_task_run(run, trigger=trigger))

    @asynccontextmanager
    async def _wrap_run(
        self,
        builder: TaskRunBuilder,
        store_inline: bool,
        trigger: RunTrigger | None,
        source: SourceType | None,
        file_storage: FileStorage | None,
    ):
        try:
            yield
        except ProviderError as e:
            failed_run = builder.build(
                output=RunOutput(e.partial_output),
                error=e.error_response().error,
            )
            if e.store_task_run:
                await self._store_task_run(
                    task=builder.task,
                    run=failed_run,
                    trigger=trigger,
                    store_inline=store_inline,
                    source=source,
                    file_storage=file_storage,
                )
                e.task_run_id = failed_run.id
            else:
                self._send_run_analytics(failed_run, trigger=trigger)
            raise e

    async def run_from_builder(
        self,
        builder: TaskRunBuilder,
        runner: AbstractRunner[Any],
        cache: CacheUsage = "auto",
        trigger: RunTrigger | None = None,
        store_inline: bool = True,
        source: SourceType | None = None,
        file_storage: FileStorage | None = None,
    ) -> AgentRun:
        async with self._wrap_run(
            builder,
            trigger=trigger,
            store_inline=store_inline,
            source=source,
            file_storage=file_storage,
        ):
            task_run = await runner.run(builder, cache=cache)

        return await self._store_task_run(
            task=builder.task,
            run=task_run,
            trigger=trigger,
            store_inline=store_inline,
            source=source,
            file_storage=file_storage,
        )

    async def stream_from_builder(
        self,
        builder: TaskRunBuilder,
        runner: AbstractRunner[Any],
        cache: CacheUsage = "auto",
        trigger: RunTrigger | None = None,
        user: UserIdentifier | None = None,
        store_inline: bool = True,
        source: SourceType | None = None,
        file_storage: FileStorage | None = None,
    ) -> AsyncGenerator[RunOutput, None]:
        chunk: RunOutput | None = None

        async with self._wrap_run(
            builder,
            trigger=trigger,
            store_inline=store_inline,
            source=source,
            file_storage=file_storage,
        ):
            async for chunk in runner.stream(builder, cache=cache):
                yield chunk
            if not chunk:
                return
            task_run = builder.build(chunk)

        task_run = await self._store_task_run(
            task=builder.task,
            run=task_run,
            trigger=trigger,
            user=user,
            store_inline=store_inline,
            source=source,
            file_storage=file_storage,
        )
        # hack to update the builder task run so that it can be used
        # outside of the stream
        builder._task_run = task_run  # pyright: ignore [reportPrivateUsage]
