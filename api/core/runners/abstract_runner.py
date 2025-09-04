import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Generic, Literal, Optional, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from core.domain.agent_run import AgentRun
from core.domain.errors import InvalidRunnerOptionsError, MissingCacheError
from core.domain.message import Messages
from core.domain.metrics import measure_time, send_counter
from core.domain.run_output import RunOutput
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_run_builder import TaskRunBuilder
from core.domain.task_run_reply import RunReply
from core.domain.task_variant import SerializableTaskVariant
from core.domain.types import AgentInput, CacheUsage
from core.providers.base.provider_error import ProviderError
from core.runners.builder_context import builder_context
from core.storage import TaskTuple
from core.utils.tags import compute_tags
from core.utils.uuid import uuid7

RunnerOptionsVar = TypeVar("RunnerOptionsVar", bound=BaseModel)

CacheType = Literal["always", "only", "never", "auto", "when_available"]

_logger = logging.getLogger(__name__)


class CacheFetcher(Protocol):
    async def __call__(
        self,
        task_id: TaskTuple,
        task_schema_id: int,
        task_input_hash: str,
        group_id: str,
        timeout_ms: int | None,
    ) -> AgentRun | None: ...


class AbstractRunner(
    ABC,
    Generic[RunnerOptionsVar],
):
    """
    The base class for all runners.
    A runner is responsible for converting a task input into a task output and storing the
    resulting task run.
    """

    def __init__(
        self,
        task: SerializableTaskVariant,
        properties: Optional[TaskGroupProperties] = None,
        options: Optional[RunnerOptionsVar] = None,
        cache_fetcher: Optional[CacheFetcher] = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.task = task
        # Since properties are very open, options act as an intermediary object
        # that allows "filling the blanks" and validating fields.
        # Note that passed properties are not necessarily the ones used in the task run
        # They are validated, and then the final properties are built from them
        # For example:
        # - you could have `properties={}` in the __init__ which allows running with default values
        # - the options are created with default values -> for ex: model=...
        # - final properties are model=..., runner_name=...
        if options is not None:
            self._options: RunnerOptionsVar = options
        else:
            try:
                self._options = self._build_options(task, properties or TaskGroupProperties())
            except ValidationError as e:
                raise InvalidRunnerOptionsError(e)

        # Properties are built when prepare() is called
        self.properties = self._build_properties(self._options, original=properties)
        self.cache_fetcher = cache_fetcher
        self.metadata = metadata
        # Set from the outside for analytics
        self.metric_tags: dict[str, int | str | float | bool | None] = {}

    async def validate_run_options(self):
        """An opportunity to validate the run options before they are used. This method
        shoudl throw an InvalidRunOption if needed"""
        pass

    @classmethod
    def name(cls) -> str:
        """
        The name of the runner, that will be added to the task run metadata.
        """
        return cls.__name__.removesuffix("Runner")

    # TODO: add support method to check if runner supports a task ?

    @abstractmethod
    def version(self) -> str:
        """
        The version of the runner for the specific task it was instantiated with,
        that will be added to the task group propertoes.
        The function is provided as an instance method to allow dynamic versioning
        based on the task bluepring the runner is instantiated with.
        """
        pass

    @abstractmethod
    async def _build_task_output(self, input: AgentInput | Messages) -> RunOutput:
        """
        The function that does the actual input -> output conversion, should
        be overriden in each subclass but not called directly.
        """
        pass

    async def _stream_task_output(self, input: AgentInput | Messages) -> AsyncIterator[RunOutput]:
        """
        The function that does the actual input -> output conversion, should
        be overriden in each subclass but not called directly.

        By default this function streams the entire output once
        """
        yield await self._build_task_output(input)

    @classmethod
    @abstractmethod
    def supports(cls, task: SerializableTaskVariant) -> bool:
        """
        Returns True if the runner supports a specific task
        """
        pass

    async def _from_cache_inner(
        self,
        input: AgentInput | Messages,
        timeout: float = 0.1,  # noqa: ASYNC109
    ) -> Optional[AgentRun]:
        """
        Retrieve the output from the cache if it exists
        """

        if not self.cache_fetcher:
            _logger.warning("No storage provided, cannot retrieve from cache")
            return None

        cached = await self.cache_fetcher(
            task_id=self.task.id_tuple,
            task_schema_id=self.task.task_schema_id,
            task_input_hash=self.task.compute_input_hash(
                input.to_input_dict() if isinstance(input, Messages) else input,
            ),
            group_id=self.properties.model_hash(),
            timeout_ms=int(timeout * 1000),
        )
        if cached:
            cached.from_cache = True
            return cached
        return None

    async def from_cache(
        self,
        input: AgentInput | Messages,
        timeout: float = 0.1,  # noqa: ASYNC109
    ) -> AgentRun | None:
        """
        Retrieve the output from the cache if it exists, with a timeout of 100ms.
        """

        try:
            return await self._from_cache_inner(input, timeout=timeout)
        except Exception:
            _logger.exception(
                "Exception while fetching from cache",
                extra={
                    "task_id": self.task.id,
                    "group_hash": self.properties.model_hash(),
                },
            )
            return None

    def _merge_metadata(self, metadata: dict[str, Any] | None) -> dict[str, Any]:
        if metadata is None:
            return self.metadata or {}
        if self.metadata is None:
            return metadata
        return {**self.metadata, **metadata}

    async def task_run_builder(
        self,
        input: AgentInput | Messages,
        start_time: float,
        task_run_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        private_fields: Optional[set[str]] = None,
        reply: RunReply | None = None,
        conversation_id: str | None = None,
    ) -> TaskRunBuilder:
        """Construct a task run builder for the given input and properties"""

        return TaskRunBuilder(
            id=task_run_id or str(uuid7()),
            task=self.task,
            task_input=input,
            properties=self.properties,
            tags=self.group_tags(),
            metadata=self._merge_metadata(metadata),
            private_fields=private_fields,
            reply=reply,
            start_time=start_time,
            conversation_id=conversation_id,
        )

    def _should_use_cache(self, cache: CacheUsage) -> bool:
        match cache:
            case "never":
                return False
            case "always" | "only" | "when_available":
                return True
            case "auto":
                return self.properties.temperature == 0 and not self.properties.enabled_tools

    async def _cache_or_none(
        self,
        input: AgentInput | Messages,
        cache: CacheUsage,
    ) -> AgentRun | None:
        if not self._should_use_cache(cache):
            return None
        from_cache = await self.from_cache(input, timeout=2 if cache == "only" else 0.1)
        if from_cache is not None:
            return from_cache
        if cache == "only":
            raise MissingCacheError()
        return None

    def _get_builder_context(self):
        return builder_context.get()

    async def _prepare_builder(
        self,
        builder: TaskRunBuilder,
        cache: CacheUsage = "auto",
    ):
        builder_context.set(builder)

        if builder.reply is not None:
            return None

        cached = await self._cache_or_none(builder.task_input, cache)
        if cached is not None:
            # Hack to make sure the returned built task run is the same as the cached one
            builder._task_run = cached  # pyright: ignore [reportPrivateUsage]
            # Updating the builder id to match the cached one
            builder.id = cached.id
            return cached
        return None

    @asynccontextmanager
    async def _wrap_for_metric(self):
        status = "success"
        try:
            yield
        except ProviderError as e:
            status = e.code
            raise e
        except Exception as e:
            status = "workflowai_internal_error"
            raise e
        finally:
            send_counter(
                "workflowai_inference",
                model=self.properties.model or "unknown",
                provider=self.properties.provider or "workflowai",
                tenant=self.task.tenant or "unknown",
                status=status,
            )

    async def run(
        self,
        builder: TaskRunBuilder,
        cache: CacheUsage = "auto",
    ) -> AgentRun:
        """
        The main runner function that is called when an input is provided
        """

        with measure_time("run_overhead_builder", **self.metric_tags):
            cached = await self._prepare_builder(builder, cache)
        if cached is not None:
            return cached

        async with self._wrap_for_metric():
            chunk = await self._build_task_output(builder.task_input)
            return builder.build(chunk)

    async def stream(
        self,
        builder: TaskRunBuilder,
        cache: CacheUsage = "auto",
    ) -> AsyncIterator[RunOutput]:
        cached = await self._prepare_builder(builder, cache)
        if cached is not None:
            yield RunOutput.from_run(cached)
            return

        async with self._wrap_for_metric():
            async for o in self._stream_task_output(builder.task_input):
                # Making sure the chunk is built
                if o.final:
                    if builder.task_run:
                        _logger.warning(
                            "Task run already built. Likely had multiple final chunks",
                            extra={"task_id": builder.task.id},
                        )
                    # Forcing here, just in case we are in a case where we had multiple final chunks
                    builder.build(o, force=True)
                yield o

    @classmethod
    @abstractmethod
    def options_class(cls) -> type[RunnerOptionsVar]:
        """
        A class for runner specific options.
        The option class will be instantiated based on user or API input, passed
        to the _build_task_output function and stored in the task run metadata.
        """
        pass

    @classmethod
    def _build_options(
        cls,
        task: SerializableTaskVariant,
        properties: TaskGroupProperties,
    ) -> RunnerOptionsVar:
        """
        Builds the runner options from a dictionary
        """
        return cls.options_class().model_validate(properties.model_dump(exclude_none=True))

    def _build_properties(self, options: RunnerOptionsVar, original: TaskGroupProperties | None) -> TaskGroupProperties:
        """
        Builds the task run group properties from the selected options
        """
        # Adding some info to the group so it can be re-used later
        base = options.model_dump(exclude={"name"})
        base["runner_name"] = self.name()
        base["runner_version"] = self.version()
        return TaskGroupProperties.model_validate(base)

    @classmethod
    def _exclude_in_build_run_tags(cls) -> set[str]:
        return {"runner_name", "runner_version", "task_schema_id"}

    def group_tags(self) -> list[str]:
        """The tags for the associated group"""
        dumped = self.properties.model_dump(exclude_none=True, exclude=self._exclude_in_build_run_tags())
        return compute_tags(dumped)

    def _set_metadata(self, key: str, value: str):
        if ctx := self._get_builder_context():
            ctx.add_metadata(key, value)

    def _append_metadata(self, key: str, value: str):
        if ctx := self._get_builder_context():
            if metadata := ctx.get_metadata(key):
                if isinstance(metadata, list):
                    metadata.append(value)  # pyright: ignore [reportUnknownMemberType]
                else:
                    ctx.add_metadata(key, [metadata, value])
            else:
                ctx.add_metadata(key, [value])
