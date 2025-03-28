import asyncio
import logging
import os
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Callable, Generic, Optional, Protocol, Sequence, TypeVar

from pydantic import ValidationError

from core.domain.errors import (
    InternalError,
    InvalidGenerationError,
    JSONSchemaValidationError,
    ProviderDoesNotSupportModelError,
    ProviderError,
    UnpriceableRunError,
)
from core.domain.llm_completion import LLMCompletion
from core.domain.llm_usage import LLMUsage
from core.domain.message import Message
from core.domain.metrics import Metric, send_counter, send_gauge
from core.domain.models import Model, Provider
from core.domain.models.model_data import ModelData
from core.domain.models.model_provider_data import (
    AudioPricePerSecond,
    AudioPricePerToken,
    ImageFixedPrice,
    ModelProviderData,
    TextPricePerToken,
)
from core.domain.models.utils import get_model_data, get_model_provider_data, get_provider_data_by_model
from core.domain.structured_output import StructuredOutput
from core.domain.tool import Tool
from core.domain.tool_call import ToolCallRequestWithID
from core.providers.base.models import RawCompletion, StandardMessage
from core.providers.base.provider_options import ProviderOptions
from core.runners.builder_context import builder_context
from core.runners.workflowai.templates import TemplateName
from core.runners.workflowai.utils import FileWithKeyPath
from core.tools import ToolKind
from core.utils.fields import datetime_factory
from core.utils.token_utils import tokens_from_string


class ProviderConfigInterface(Protocol):
    @property
    def provider(self) -> Provider: ...


ProviderConfigVar = TypeVar("ProviderConfigVar", bound=ProviderConfigInterface)
ProviderRequestVar = TypeVar("ProviderRequestVar")
ProviderOutput = TypeVar("ProviderOutput")


class AbstractProvider(ABC, Generic[ProviderConfigVar, ProviderRequestVar]):
    def __init__(self, config: Optional[ProviderConfigVar] = None, config_id: Optional[str] = None, index: int = 0):
        self.config: ProviderConfigVar = config or self._default_config(index=index)
        self.config_id = config_id
        # The index of the provider, useful when there are multiple
        # Providers configured for a single provider type
        self._index = index
        self.logger = logging.getLogger(type(self).__name__)

    @property
    def _is_custom_config(self) -> bool:
        return self.config_id is not None

    # TODO: remove
    @abstractmethod
    def default_model(self) -> Model:
        pass

    @classmethod
    @abstractmethod
    def name(cls) -> Provider:
        pass

    @classmethod
    def display_name(cls) -> str:
        return cls.__name__.removesuffix("Provider")

    def supports_model(self, model: Model) -> bool:
        try:
            get_model_provider_data(self.name(), model)
            return True
        except ProviderDoesNotSupportModelError:
            return False

    # DO NOT USE: it does not include any latest models
    @classmethod
    def all_supported_models(cls) -> Iterator[Model]:
        for model in get_provider_data_by_model(cls.name()).keys():
            yield model

    @classmethod
    @abstractmethod
    def required_env_vars(cls) -> list[str]:
        pass

    # TODO: only used by the CLI. remove
    @classmethod
    def is_configured(cls) -> bool:
        """Check if the provider is configured by checking if all required environment variables are set"""
        for var in cls.required_env_vars():
            if var not in os.environ:
                return False
        return True

    @classmethod
    @abstractmethod
    def _default_config(cls, index: int) -> ProviderConfigVar:
        pass

    @abstractmethod
    async def check_valid(self) -> bool:
        pass

    @classmethod
    @abstractmethod
    def standardize_messages(cls, messages: list[dict[str, Any]]) -> list[StandardMessage]:
        pass

    def is_streamable(self, model: Model, enabled_tools: list[Tool] | None = None) -> bool:
        return True

    @property
    def is_structured_generation_supported(self) -> bool:
        return False

    async def is_schema_supported_for_structured_generation(
        self,
        task_name: str,
        model: Model,
        schema: dict[str, Any],
    ) -> bool:
        # Check if the task schema is actually supported by the provider's implementation of structured generation
        return False

    @classmethod
    def sanitize_agent_instructions(cls, instructions: str) -> str:
        # Remove the "@" prefix from tool names, since Google API does not support it for native tool calls
        for tool_name in ToolKind.__members__.values():
            if tool_name.startswith("@"):
                instructions = instructions.replace(tool_name, tool_name[1:])

        return instructions

    @abstractmethod
    def _compute_prompt_token_count(
        self,
        messages: list[dict[str, Any]],
        model: Model,
    ) -> float:
        pass

    @classmethod
    def _compute_completion_token_count(
        cls,
        response: str,
        model: Model,
    ) -> int:
        return tokens_from_string(response, model.value)

    @classmethod
    def requires_downloading_file(cls, file: FileWithKeyPath, model: Model) -> bool:
        # Whether the provider requires downloading the file
        # before making a completion request
        return False

    # TODO: deprecate this method
    @abstractmethod
    def _compute_prompt_image_count(
        self,
        messages: list[dict[str, Any]],
    ) -> int:
        pass

    @abstractmethod
    async def _compute_prompt_audio_token_count(
        self,
        messages: list[dict[str, Any]],
    ) -> tuple[float, float | None]:
        """Returns the token count and an optionalduration"""
        pass

    async def _send_no_prompt_token_count_metric(self, llm_usage: LLMUsage, model: Model) -> None:
        await Metric(
            name="no_prompt_token_count",
            counter=1,
            tags={"provider": self.name(), "model": model.value},
        ).send()

    async def feed_prompt_token_count(self, llm_usage: LLMUsage, messages: list[dict[str, Any]], model: Model) -> None:
        if llm_usage.prompt_token_count is None:
            # Send metric so we can see how many runs are missing the prompt token count
            await self._send_no_prompt_token_count_metric(llm_usage, model)
            # Compute the prompt token count
            llm_usage.prompt_token_count = self._compute_prompt_token_count(messages, model)

    def feed_completion_token_count(self, llm_usage: LLMUsage, response: str | None, model: Model) -> None:
        if llm_usage.completion_token_count is None:
            llm_usage.completion_token_count = self._compute_completion_token_count(response, model) if response else 0

    def feed_prompt_image_count(self, llm_usage: LLMUsage, messages: list[dict[str, Any]]) -> None:
        if llm_usage.prompt_image_count is None:
            # Prompt image count should be fed upstream
            self.logger.warning("Prompt image count is None while calculating image price")
            llm_usage.prompt_image_count = self._compute_prompt_image_count(messages)

    async def feed_prompt_audio_token_count(
        self,
        llm_usage: LLMUsage,
        messages: list[dict[str, Any]],
    ):
        """Returns the token count and duration"""
        if llm_usage.prompt_audio_token_count is None:
            token, duration = await self._compute_prompt_audio_token_count(messages)
            llm_usage.prompt_audio_token_count = token
            llm_usage.prompt_audio_duration_seconds = duration

    def _get_context_token_count(self, llm_usage: LLMUsage, model: Model) -> float:
        """Return the total number of tokens in the prompt"""
        if llm_usage.prompt_token_count is None:
            raise UnpriceableRunError("Prompt token count is None while calculating context token count")
        return llm_usage.prompt_token_count

    def _set_llm_usage_model_context_window_size(self, llm_usage: LLMUsage, model: Model):
        if llm_usage.model_context_window_size:
            # No need to change if it's already set
            return

        model_data = get_model_data(model)
        llm_usage.model_context_window_size = model_data.max_tokens_data.max_tokens

    def get_model_provider_data(self, model: Model):
        return get_model_provider_data(self.name(), model)

    async def _compute_llm_completion_cost(
        self,
        model: Model,
        llm_usage: LLMUsage,
        completion: LLMCompletion,
    ):
        if not completion.incur_cost():
            llm_usage.prompt_cost_usd = 0
            llm_usage.completion_cost_usd = 0
            return

        # These functions are on the run critical path so they should be very fast
        # And not error prone
        model_provider_data = self.get_model_provider_data(model)
        context_token_count = self._get_context_token_count(llm_usage, model)

        llm_usage.prompt_cost_usd, llm_usage.completion_cost_usd = self._calculate_text_price(
            model_provider_data,
            llm_usage,
            context_token_count,
        )

        prompt_image_cost_usd = self._calculate_image_price(
            model_provider_data,
            llm_usage,
            context_token_count,
        )

        prompt_audio_cost_usd = self._calculate_audio_price(
            model_provider_data,
            llm_usage,
            context_token_count,
        )

        llm_usage.prompt_cost_usd += prompt_image_cost_usd + prompt_audio_cost_usd

    async def compute_llm_completion_usage(
        self,
        model: Model,
        completion: LLMCompletion,
    ) -> LLMUsage:
        # TODO: there are some sub-optimizations here:
        # - completion.messages should be using the provider's message format instead of being a plain list of dicts
        # It is very likely that most providers will convert to their own message format when computing each usage...
        # - prompt_token_count has a different meaning based on the provider. For google for example, it only
        # contains the number of text tokens. However for OpenAI it contains the total number of tokens as returned
        # by the API.
        # - some methods like "feed_prompt_image_count" should really not be provider specific

        llm_usage = completion.usage or LLMUsage()

        await self.feed_prompt_audio_token_count(llm_usage, completion.messages)
        self.feed_prompt_image_count(llm_usage, completion.messages)
        await self.feed_prompt_token_count(llm_usage, completion.messages, model)
        self.feed_completion_token_count(llm_usage, completion.response, model)

        self._set_llm_usage_model_context_window_size(llm_usage, model)
        await self._compute_llm_completion_cost(model, llm_usage, completion)

        return llm_usage

    def _get_prompt_text_token_count(self, llm_usage: LLMUsage):
        return llm_usage.prompt_token_count

    def _calculate_text_price(
        self,
        model_provider_data: ModelProviderData,
        llm_usage: LLMUsage,
        context_token_count: float,
    ) -> tuple[float, float]:
        if type(model_provider_data.text_price) is TextPricePerToken:
            prompt_cost_per_token = model_provider_data.text_price.prompt_cost_per_token
            completion_cost_per_token = model_provider_data.text_price.completion_cost_per_token
            prompt_text_token_count = self._get_prompt_text_token_count(llm_usage)

            if model_provider_data.text_price.thresholded_prices:
                # We know for sure that there is only one thresholded price
                thresholded_price = model_provider_data.text_price.thresholded_prices[0]

                if context_token_count > thresholded_price.threshold:
                    prompt_cost_per_token = thresholded_price.prompt_cost_per_token_over_threshold
                    completion_cost_per_token = thresholded_price.completion_cost_per_token_over_threshold

            # Apply discout for cached tokens
            if llm_usage.prompt_token_count_cached:
                cached_tokens_discount = model_provider_data.text_price.prompt_cached_tokens_discount

                if cached_tokens_discount == 0.0:
                    self.logger.warning(
                        "Cached tokens discount is 0.0 for model while there are cached tokens. Please review pricing config!",
                    )
                prompt_cost_usd = (
                    (prompt_text_token_count - llm_usage.prompt_token_count_cached) * prompt_cost_per_token
                    + (llm_usage.prompt_token_count_cached * (1 - cached_tokens_discount) * prompt_cost_per_token)
                    if prompt_text_token_count
                    else 0
                )
            else:
                prompt_cost_usd = prompt_text_token_count * prompt_cost_per_token if prompt_text_token_count else 0

            completion_cost_usd = (
                llm_usage.completion_token_count * completion_cost_per_token if llm_usage.completion_token_count else 0
            )
            return prompt_cost_usd, completion_cost_usd

        raise Exception(f"Unknown text price type {type(model_provider_data.text_price)}")

    def _calculate_image_price(
        self,
        model_provider_data: ModelProviderData,
        llm_usage: LLMUsage,
        context_token_count: float,
    ) -> float:
        if not model_provider_data.image_price:
            return 0

        prompt_image_cost_usd = 0

        if llm_usage.prompt_image_count is None:
            self.logger.warning("Prompt image count is None while calculating image price")
            return prompt_image_cost_usd

        if llm_usage.prompt_image_count > 0:
            if not model_provider_data.image_price:
                self.logger.debug("Model has no per image price, skipping image cost")
                return 0

            image_price = model_provider_data.image_price.cost_per_image

            if type(model_provider_data.image_price) is ImageFixedPrice:
                if model_provider_data.image_price.thresholded_prices:
                    # We know for sure that there is only one thresholded price
                    thresholded_price = model_provider_data.image_price.thresholded_prices[0]

                    if context_token_count > thresholded_price.threshold:
                        image_price = thresholded_price.cost_per_image_over_threshold

                prompt_image_cost_usd = llm_usage.prompt_image_count * image_price
            else:
                raise Exception(f"Unknown image price type {type(image_price)}")

        return prompt_image_cost_usd

    def _calculate_audio_price(
        self,
        model_provider_data: ModelProviderData,
        llm_usage: LLMUsage,
        context_token_count: float,
    ) -> float:
        if not model_provider_data.audio_price:
            return 0

        if llm_usage.prompt_audio_token_count is None:
            self.logger.warning("Prompt audio token count is None while calculating audio price")
            return 0

        if not llm_usage.prompt_audio_token_count:
            return 0

        if type(model_provider_data.audio_price) is AudioPricePerToken:
            return llm_usage.prompt_audio_token_count * model_provider_data.audio_price.audio_input_cost_per_token

        if type(model_provider_data.audio_price) is AudioPricePerSecond:
            if not llm_usage.prompt_audio_duration_seconds:
                raise UnpriceableRunError("Prompt audio duration seconds is None while calculating audio price")

            audio_price = model_provider_data.audio_price.cost_per_second
            if model_provider_data.audio_price.thresholded_prices:
                thresholded_price = model_provider_data.audio_price.thresholded_prices[0]

                if context_token_count > thresholded_price.threshold:
                    audio_price = thresholded_price.cost_per_second_over_threshold
            return llm_usage.prompt_audio_duration_seconds * audio_price

        raise UnpriceableRunError(f"Unknown audio price type {type(model_provider_data.audio_price)}")

    @classmethod
    def _assign_raw_completion(
        cls,
        raw_completion: RawCompletion,
        llm_completion: LLMCompletion,
        tool_calls: list[ToolCallRequestWithID] | None = None,
    ):
        llm_completion.duration_seconds = round((datetime_factory() - raw_completion.start_time).total_seconds(), 2)
        llm_completion.tool_calls = tool_calls
        llm_completion.response = raw_completion.response
        if raw_completion.usage.completion_token_count is not None:
            llm_completion.usage.completion_token_count = raw_completion.usage.completion_token_count
        if raw_completion.usage.completion_cost_usd is not None:
            llm_completion.usage.completion_cost_usd = raw_completion.usage.completion_cost_usd
        if raw_completion.usage.prompt_token_count is not None:
            llm_completion.usage.prompt_token_count = raw_completion.usage.prompt_token_count
        if raw_completion.usage.prompt_cost_usd is not None:
            llm_completion.usage.prompt_cost_usd = raw_completion.usage.prompt_cost_usd
        if raw_completion.usage.prompt_token_count_cached is not None:
            llm_completion.usage.prompt_token_count_cached = raw_completion.usage.prompt_token_count_cached
        if raw_completion.usage.model_context_window_size is not None:
            llm_completion.usage.model_context_window_size = raw_completion.usage.model_context_window_size
        if raw_completion.usage.reasoning_token_count is not None:
            llm_completion.usage.reasoning_token_count = raw_completion.usage.reasoning_token_count

    @abstractmethod
    async def _prepare_completion(
        self,
        messages: list[Message],
        options: ProviderOptions,
        stream: bool,
    ) -> tuple[ProviderRequestVar, LLMCompletion]:
        """Prepare the completion request. Override in subclasses to add provider-specific logic"""
        pass

    def _builder_context(self):
        return builder_context.get()

    def _add_metadata(self, key: str, value: Any) -> None:
        ctx = self._builder_context()
        if ctx is None:
            return
        ctx.add_metadata(key, value)

    def _get_metadata(self, key: str) -> Any | None:
        ctx = self._builder_context()
        if ctx is None:
            return None
        return ctx.get_metadata(key)

    def _run_id(self) -> str | None:
        ctx = self._builder_context()
        if ctx is None:
            return None
        return ctx.id

    async def _prepare_completion_and_add_to_ctx(
        self,
        messages: list[Message],
        options: ProviderOptions,
        stream: bool,
    ) -> tuple[ProviderRequestVar, LLMCompletion]:
        """Calls _prepare_completion and adds the completion to the builder context.
        The completion object can then be updated in place"""

        kwargs, raw = await self._prepare_completion(messages, options, stream)
        builder = self._builder_context()
        if builder is not None:
            builder.llm_completions.append(raw)

            if self.config_id:
                builder.config_id = self.config_id
        return kwargs, raw

    def validate_output(
        self,
        content_str: str,
        output_factory: Callable[[str, bool], StructuredOutput],
        allow_json_repair: bool = True,
    ) -> StructuredOutput:
        """
        Validates that the 'response' from the model enforces the schema of the output class ('output_cls').

        When 'allow_json_repair' is set to True, if a JSON is not directly parsable from the 'response',
        typically because the model has added some additional content like, "here is the JSON response: ...",
        or ```json ... ``` around the JSON; the method will attempt to extract the JSON from the response string and validate it.
        """

        try:
            return output_factory(content_str, False)
        except (ValidationError, JSONSchemaValidationError) as e:
            partial = output_factory(content_str, True)
            raise InvalidGenerationError(msg=str(e), partial_output=partial.output)

    def _add_exception_to_messages(self, messages: list[Message], response: str | None, e: Exception) -> list[Message]:
        """Add an exception message to the messages list so it can be retried"""

        return [
            *messages,
            Message(
                role=Message.Role.ASSISTANT,
                content=response or "EMPTY MESSAGE",
            ),
            Message(
                role=Message.Role.USER,
                content=f"Your previous response was invalid with error `{e}`.\nPlease retry",
            ),
        ]

    async def _set_llm_completion_usage(
        self,
        model: Model,
        llm_completion: LLMCompletion,
        timeout: float | None,  # noqa: ASYNC109
    ) -> None:
        # All exceptions must be handled in this method
        try:
            async with asyncio.timeout(timeout):
                llm_completion.usage = await self.compute_llm_completion_usage(model, llm_completion)
        except UnpriceableRunError:
            # If anything wrong happen with the usage computation, we set cost to None
            llm_completion.usage.prompt_cost_usd = None
            llm_completion.usage.completion_cost_usd = None
            self.logger.exception(
                "Unpricable run",
                extra={"run_id": self._run_id()},
            )
        except asyncio.TimeoutError:
            llm_completion.usage.prompt_cost_usd = None
            llm_completion.usage.completion_cost_usd = None
            self.logger.error(
                "Timeout while computing usage for completion",
                extra={"run_id": self._run_id()},
            )
        except Exception:
            # If anything wrong happen with the usage computation, we set cost to None
            llm_completion.usage.prompt_cost_usd = None
            llm_completion.usage.completion_cost_usd = None
            self.logger.exception(
                "Unknown error while computing usage for completion",
                extra={"run_id": self._run_id()},
            )

    async def finalize_completions(
        self,
        model: Model,
        llm_completions: Sequence[LLMCompletion],
        timeout: float | None = None,  # noqa: ASYNC109
    ) -> None:
        async with asyncio.TaskGroup() as tg:
            for completion in llm_completions:
                tg.create_task(self._set_llm_completion_usage(model, completion, timeout))

    # On the critical path, we timeout after 1 second
    _FINALIZE_COMPLETIONS_TIMEOUT = 1

    # Method is called on critical path so it should handle all exceptions and timeout after a reasonable amount of time
    async def _finalize_completions_in_context(self, model: Model):
        builder = self._builder_context()
        if builder is None:
            self.logger.error("No builder context while finalizing completions")
            return
        await self.finalize_completions(model, builder.llm_completions, AbstractProvider._FINALIZE_COMPLETIONS_TIMEOUT)

    # -------------------------------------------------
    # Completions without stream

    async def complete(
        self,
        messages: list[Message],
        options: ProviderOptions,
        output_factory: Callable[[str, bool], StructuredOutput],
    ) -> StructuredOutput:
        """Create a task output from a list of messages

        Args:
            messages (list[Message]): a list of messages
            options (ProviderOptions): the provider options
            output_factory (Callable[[str], TaskOutput]): a factory function to create the output from a json string

        Returns:
            TaskOutput: a task output
        """

        try:
            return await self._retryable_complete(messages, options, output_factory)
        finally:
            await self._finalize_completions_in_context(options.model)

    def _prepare_provider_error(self, e: ProviderError, options: ProviderOptions):
        if e.provider_options is None:
            e.provider_options = options
        e.provider = self.name()
        e.task_run_id = self._run_id()
        return e

    @asynccontextmanager
    async def _wrap_for_metric(self, model: Model, tenant: str | None):
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
            await send_counter(
                "provider_inference",
                model=model.value,
                provider=self.name(),
                tenant=tenant or "unknown",
                status=status,
            )

    async def _retryable_complete(
        self,
        messages: list[Message],
        options: ProviderOptions,
        output_factory: Callable[[str, bool], StructuredOutput],
        max_attempts: int | None = None,
    ) -> StructuredOutput:
        request, raw = await self._prepare_completion_and_add_to_ctx(messages, options, False)
        # raw_completion cannot be in the StructuredOutput because it should still be used on raise
        raw_completion = RawCompletion(response="", usage=raw.usage)
        try:
            async with self._wrap_for_metric(options.model, options.tenant):
                output = await self._single_complete(
                    request=request,
                    output_factory=output_factory,
                    raw_completion=raw_completion,
                    options=options,
                )
            self._assign_raw_completion(raw_completion, raw, tool_calls=output.tool_calls)
            return output
        except ProviderError as e:
            self._prepare_provider_error(e, options)
            self._assign_raw_completion(raw_completion, raw)
            retries = max_attempts - 1 if max_attempts is not None else e.max_attempt_count - 1
            if not e.retry or retries <= 0:
                raise e

            return await self._retryable_complete(
                self._add_exception_to_messages(messages, raw_completion.response, e),
                options,
                output_factory,
                retries,
            )
        # Any other error is a crash

    @abstractmethod
    async def _single_complete(
        self,
        request: ProviderRequestVar,
        output_factory: Callable[[str, bool], StructuredOutput],
        raw_completion: RawCompletion,
        options: ProviderOptions,
    ) -> StructuredOutput:
        """Override in subclasses. This method is responsible for calling the provider completion method and fill
        the raw_completion object"""
        pass

    # -------------------------------------------------
    # Completions with stream

    @abstractmethod
    def _single_stream(
        self,
        request: ProviderRequestVar,
        output_factory: Callable[[str, bool], StructuredOutput],
        partial_output_factory: Callable[[Any], StructuredOutput],
        raw_completion: RawCompletion,
        options: ProviderOptions,
    ) -> AsyncGenerator[StructuredOutput, None]:
        pass

    async def _retryable_stream(
        self,
        messages: list[Message],
        options: ProviderOptions,
        output_factory: Callable[[str, bool], StructuredOutput],
        partial_output_factory: Callable[[Any], StructuredOutput],
        max_attempts: int | None = None,
    ):
        stream_exc: Exception | None = None

        while max_attempts is None or max_attempts >= 1:
            kwargs, raw = await self._prepare_completion_and_add_to_ctx(messages, options, True)
            raw_completion = RawCompletion(response="", usage=raw.usage)
            try:
                output: StructuredOutput | None = None
                async with self._wrap_for_metric(options.model, options.tenant):
                    async for output in self._single_stream(
                        kwargs,
                        output_factory=output_factory,
                        partial_output_factory=partial_output_factory,
                        raw_completion=raw_completion,
                        options=options,
                    ):
                        yield output
                self._assign_raw_completion(raw_completion, raw, tool_calls=output.tool_calls if output else None)
                return
            except ProviderError as e:
                self._prepare_provider_error(e, options)
                stream_exc = e
                self._assign_raw_completion(raw_completion, raw)
                if not e.retry:
                    break
                max_attempts = max_attempts - 1 if max_attempts is not None else e.max_attempt_count - 1
                messages = self._add_exception_to_messages(messages, raw_completion.response, e)

        if not stream_exc:
            # This should never happen
            raise InternalError("Stream failed without an exception")
        raise stream_exc

    async def stream(
        self,
        messages: list[Message],
        options: ProviderOptions,
        output_factory: Callable[[str, bool], StructuredOutput],
        partial_output_factory: Callable[[Any], StructuredOutput],
    ) -> AsyncIterator[StructuredOutput]:
        def wrapped_partial_output_factory(obj: Any) -> StructuredOutput:
            try:
                return partial_output_factory(obj)
            except (ValidationError, JSONSchemaValidationError) as e:
                raise InvalidGenerationError(msg=str(e), provider_status_code=200)

        o: StructuredOutput | None = None
        try:
            async for o in self._retryable_stream(
                messages,
                options,
                output_factory=output_factory,
                partial_output_factory=wrapped_partial_output_factory,
            ):
                yield o
        except ProviderError as e:
            if o is not None:
                e.partial_output = o.output
            raise e
        finally:
            await self._finalize_completions_in_context(options.model)

    @classmethod
    def sanitize_config(cls, config: ProviderConfigVar) -> ProviderConfigVar:
        return config

    def sanitize_template(self, template: TemplateName):
        """An opportunity for the provider to override the template name"""
        return template

    def sanitize_model_data(self, model_data: ModelData):
        """An opportunity for the provider to override the model data. Object should be updated in place"""
        pass

    async def _log_rate_limit(self, limit_name: str, percentage: float, model: Model):
        """Percentage is a float between 0 and 1"""
        await send_gauge(
            "provider_rate_limit",
            percentage,
            provider=self.name(),
            limit_name=limit_name,
            model=model.value,
        )

    async def _log_rate_limit_remaining(
        self,
        limit_name: str,
        remaining: int | float | str | None,
        total: int | float | str | None,
        model: Model,
    ):
        if remaining is None or total is None:
            self.logger.warning(
                "Rate limit remaining or total is None while logging rate limit",
                extra={"remaining": remaining, "total": total, "model": model.value},
            )
            return
        try:
            remaining = float(remaining)
            total = float(total)
        except (ValueError, TypeError):
            self.logger.exception(
                "Could not parse rate limit remaining and total",
                extra={"remaining": remaining, "total": total, "model": model.value},
            )
            return

        await self._log_rate_limit(limit_name, 1 - (remaining / total), model)
