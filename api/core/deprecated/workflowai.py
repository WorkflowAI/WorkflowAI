import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from functools import wraps
from typing import Any, AsyncGenerator, Optional, Protocol, TypeVar

from core.domain.analytics_events.analytics_events import (
    RunTrigger,
    SourceType,
)
from core.domain.deprecated.task import Task, TaskInput, TaskOutput
from core.domain.errors import (
    MissingContextWorklowAI,
)
from core.domain.run_output import RunOutput
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_run import SerializableTaskRun
from core.domain.task_run_builder import TaskRunBuilder
from core.domain.types import CacheUsage
from core.domain.users import UserIdentifier
from core.domain.version_reference import VersionReference
from core.runners.abstract_runner import AbstractRunner, CacheFetcher
from core.runners.workflowai.workflowai_runner import WorkflowAIRunner
from core.storage.abstract_storage import AbstractStorage
from core.storage.file_storage import FileStorage
from core.storage.noop_storage import NoopStorage
from core.utils.no_op import NoopFileStorage

_wai_context: ContextVar[Optional["WorkflowAI"]] = ContextVar("_wai_context", default=None)


_WAI_METHOD = TypeVar("_WAI_METHOD", bound=Callable[..., Any])


def _add_wai_to_ctx(fn: _WAI_METHOD) -> _WAI_METHOD:
    @wraps(fn)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        wai = args[0]
        if not isinstance(wai, WorkflowAI):
            raise ValueError("First argument must be a WorkflowAI instance")
        _wai_context.set(wai)
        return fn(*args, **kwargs)

    return wrapped  # type: ignore


class _RunServiceProt(Protocol):
    async def run_from_builder(
        self,
        builder: TaskRunBuilder,
        runner: AbstractRunner[Any],
        cache: CacheUsage = "auto",
        trigger: RunTrigger | None = None,
        store_inline: bool = True,
        source: SourceType | None = None,
        file_storage: FileStorage | None = None,
    ) -> SerializableTaskRun: ...

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
    ) -> AsyncGenerator[RunOutput, None]: ...


# TODO: We should remove this class little by little
# It was built as a central point to handle the CLI and the API
# Since we are moving towards a pure API approach, it should be replaced by services
class WorkflowAI:
    """
    A hub for all workflow ai operations, responsible for running tasks, storing results, and managing runners
    and evaluators.
    """

    def __init__(
        self,
        run_service: _RunServiceProt,
        storage: AbstractStorage | None = None,
        file_storage: FileStorage | None = None,
        cache_fetcher: CacheFetcher | None = None,
    ):
        self._run_service = run_service
        self.storage: AbstractStorage = storage or NoopStorage()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._file_storage: FileStorage = file_storage or NoopFileStorage()
        self._cache_fetcher = cache_fetcher

    @classmethod
    def from_ctx(cls) -> "WorkflowAI":
        wai = _wai_context.get()
        if not wai:
            raise MissingContextWorklowAI("No WorkflowAI instance in context")
        return wai

    @asynccontextmanager
    async def add_to_context(self):
        _wai_context.set(self)
        yield
        _wai_context.set(None)

    async def _register_task(self, task: Task[TaskInput, TaskOutput]):
        resource = task.to_serializable()
        stored, created = await self.storage.store_task_resource(resource)
        task.schema_id = stored.task_schema_id
        # Hack to set raw version for the API task
        # Only used when scoring in the CLI which should disappear soon
        if hasattr(task, "raw_version"):
            task.raw_version = stored.id  # type: ignore
        return (task.schema_id, created)

    # ------------------------------
    # Running

    async def get_runner(
        self,
        task: Task[TaskInput, TaskOutput],
        group: Optional[VersionReference] = None,
    ) -> AbstractRunner[Any]:
        group = group or VersionReference.with_properties()
        if group.version:
            self._logger.error(
                "Calling get runner with non properties is unexpected",
                extra={
                    "group": group.model_dump(exclude_none=True),
                    "task_id": task.id(),
                },
            )
            schema_id = task.schema_id
            if not schema_id:
                schema_id, _ = await self._register_task(task)
            existing_group = await self.storage.task_group_by_id(task.id(), schema_id, group.version)
            properties = existing_group.properties
        else:
            properties = group.properties or TaskGroupProperties()

        return WorkflowAIRunner(
            task.to_serializable(),
            cache_fetcher=self._cache_fetcher,
            properties=properties,
        )

    @_add_wai_to_ctx
    async def run(
        self,
        task: Task[TaskInput, TaskOutput],
        input: TaskInput,
        runner: Optional[AbstractRunner[Any]] = None,
        group: Optional[VersionReference] = None,
        task_run_id: Optional[str] = None,
        cache: CacheUsage = "auto",
        labels: Optional[set[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        trigger: RunTrigger | None = None,
        store_inline: bool = True,
    ) -> TaskOutput:
        runner = runner or await self.get_runner(task, group=group)
        builder = await runner.task_run_builder(
            input.model_dump(mode="json"),
            task_run_id=task_run_id,
            labels=labels,
            metadata=metadata,
        )
        run = await self._run_service.run_from_builder(
            builder,
            runner,
            cache=cache,
            trigger=trigger,
            store_inline=store_inline,
            file_storage=self._file_storage,
        )
        return task.validate_output(run.task_output, strip_extras=False)
