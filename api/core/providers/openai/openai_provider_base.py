import copy
import json
from abc import abstractmethod
from json import JSONDecodeError
from typing import Any, Generic, Protocol, TypeVar, override

from httpx import Response
from pydantic import BaseModel, ValidationError

from core.domain.errors import (
    ContentModerationError,
    FailedGenerationError,
    MaxTokensExceededError,
    ModelDoesNotSupportMode,
    ProviderBadRequestError,
    StructuredGenerationError,
    UnknownProviderError,
)
from core.domain.llm_usage import LLMUsage
from core.domain.message import Message
from core.domain.models import Model
from core.domain.structured_output import StructuredOutput
from core.domain.tool_call import ToolCallRequestWithID
from core.providers.base.abstract_provider import ProviderConfigInterface, RawCompletion
from core.providers.base.httpx_provider import HTTPXProvider, ParsedResponse
from core.providers.base.models import StandardMessage
from core.providers.base.provider_options import ProviderOptions
from core.providers.base.streaming_context import ToolCallRequestBuffer
from core.providers.google.google_provider_domain import (
    internal_tool_name_to_native_tool_call,
    native_tool_name_to_internal,
)
from core.providers.openai._openai_utils import get_openai_json_schema_name, prepare_openai_json_schema
from core.runners.workflowai.utils import FileWithKeyPath
from core.utils.redis_cache import redis_cached

from .openai_domain import (
    MODEL_NAME_MAP,
    CompletionRequest,
    CompletionResponse,
    JSONResponseFormat,
    JSONSchemaResponseFormat,
    OpenAIError,
    OpenAIMessage,
    OpenAISchema,
    OpenAIToolMessage,
    StreamedResponse,
    StreamOptions,
    TextResponseFormat,
    Tool,
    ToolFunction,
    parse_tool_call_or_raise,
)


class OpenAIProviderBaseConfig(ProviderConfigInterface, Protocol):
    pass


_O1_PREVIEW_MODELS = {
    Model.O1_PREVIEW_2024_09_12,
    Model.O1_MINI_2024_09_12,
}

_AUDIO_PREVIEW_MODELS = {
    Model.GPT_40_AUDIO_PREVIEW_2024_10_01,
    Model.GPT_4O_AUDIO_PREVIEW_2024_12_17,
}

_UNSUPPORTED_TEMPERATURES = {
    Model.O1_2024_12_17_LOW_REASONING_EFFORT,
    Model.O1_2024_12_17_MEDIUM_REASONING_EFFORT,
    Model.O1_2024_12_17_HIGH_REASONING_EFFORT,
    Model.O3_MINI_2025_01_31_HIGH_REASONING_EFFORT,
    Model.O3_MINI_2025_01_31_MEDIUM_REASONING_EFFORT,
    Model.O3_MINI_2025_01_31_LOW_REASONING_EFFORT,
    *_O1_PREVIEW_MODELS,
    *_AUDIO_PREVIEW_MODELS,
}

_REASONING_EFFORT_FOR_MODEL = {
    Model.O1_2024_12_17_LOW_REASONING_EFFORT: "low",
    Model.O1_2024_12_17_MEDIUM_REASONING_EFFORT: "medium",
    Model.O1_2024_12_17_HIGH_REASONING_EFFORT: "high",
    Model.O3_MINI_2025_01_31_HIGH_REASONING_EFFORT: "high",
    Model.O3_MINI_2025_01_31_MEDIUM_REASONING_EFFORT: "medium",
    Model.O3_MINI_2025_01_31_LOW_REASONING_EFFORT: "low",
}

_OpenAIConfigVar = TypeVar("_OpenAIConfigVar", bound=OpenAIProviderBaseConfig)


class OpenAIProviderBase(HTTPXProvider[_OpenAIConfigVar, CompletionResponse], Generic[_OpenAIConfigVar]):
    def _build_request(self, messages: list[Message], options: ProviderOptions, stream: bool) -> BaseModel:
        model_name = MODEL_NAME_MAP.get(options.model, options.model)
        is_preview_model = options.model in _O1_PREVIEW_MODELS or options.model in _AUDIO_PREVIEW_MODELS

        message: list[OpenAIMessage | OpenAIToolMessage] = []
        for m in messages:
            if m.tool_call_results:
                message.extend(OpenAIToolMessage.from_domain(m))
            else:
                message.append(OpenAIMessage.from_domain(m, is_system_allowed=not is_preview_model))

        # Preview models only support temperature 1.0
        temperature = 1.0 if options.model in _UNSUPPORTED_TEMPERATURES else options.temperature
        completion_request = CompletionRequest(
            messages=message,
            model=model_name,
            temperature=temperature,
            # TODO[max-tokens]: re-add max_tokens
            max_tokens=options.max_tokens,
            stream=stream,
            stream_options=StreamOptions(include_usage=True) if stream else None,
            # store=True,
            response_format=self._response_format(options, is_preview_model),
            reasoning_effort=_REASONING_EFFORT_FOR_MODEL.get(options.model, None),
        )

        if options.enabled_tools is not None and options.enabled_tools != []:
            completion_request.tools = [
                Tool(
                    type="function",
                    function=ToolFunction(
                        name=internal_tool_name_to_native_tool_call(tool.name),
                        description=tool.description,
                        parameters=tool.input_schema,
                    ),
                )
                for tool in options.enabled_tools
            ]

        return completion_request

    def _response_format(
        self,
        options: ProviderOptions,
        is_preview_model: bool,
    ) -> TextResponseFormat | JSONResponseFormat | JSONSchemaResponseFormat:
        if is_preview_model:
            return TextResponseFormat()

        schema = copy.deepcopy(options.output_schema)
        if not schema or not options.structured_generation:
            return JSONResponseFormat()

        task_name = options.task_name or ""

        return JSONSchemaResponseFormat(
            json_schema=OpenAISchema(
                name=get_openai_json_schema_name(task_name, schema),
                json_schema=prepare_openai_json_schema(schema),
            ),
        )

    @abstractmethod
    def _request_url(self, model: Model, stream: bool) -> str:
        pass

    @abstractmethod
    async def _request_headers(self, request: dict[str, Any], url: str, model: Model) -> dict[str, str]:
        pass

    @classmethod
    def open_ai_message_or_tool_message(cls, messag_dict: dict[str, Any]) -> OpenAIMessage | OpenAIToolMessage:
        try:
            return OpenAIToolMessage.model_validate(messag_dict)
        except ValidationError:
            return OpenAIMessage.model_validate(messag_dict)

    @classmethod
    def standardize_messages(cls, messages: list[dict[str, Any]]) -> list[StandardMessage]:
        result: list[StandardMessage] = []
        current_tool_messages: list[OpenAIToolMessage] = []

        for message in (cls.open_ai_message_or_tool_message(m) for m in messages):
            if isinstance(message, OpenAIToolMessage):
                current_tool_messages.append(message)
            else:
                # Process any accumulated tool messages before adding the non-tool message
                if current_tool_messages:
                    if tool_message := OpenAIToolMessage.to_standard(current_tool_messages):
                        result.append(tool_message)
                    current_tool_messages = []

                # Add the non-tool message
                result.append(message.to_standard())

        # Handle any remaining tool messages at the end
        if current_tool_messages:
            if tool_message := OpenAIToolMessage.to_standard(current_tool_messages):
                result.append(tool_message)

        return result

    def _response_model_cls(self) -> type[CompletionResponse]:
        return CompletionResponse

    def _extract_content_str(self, response: CompletionResponse) -> str:
        for choice in response.choices:
            if choice.finish_reason == "length":
                raise MaxTokensExceededError(
                    msg="Model returned a response with a length finish reason, meaning the maximum number of tokens was exceeded.",
                    raw_completion=response,
                )
        message = response.choices[0].message
        content = message.content
        if content is None:
            if message.refusal:
                # TODO: track metric for refusals
                raise ContentModerationError(
                    msg=f"Model refused to generate a response: {message.refusal}",
                )
            if not message.tool_calls:
                raise FailedGenerationError(
                    msg="Model did not generate a response content",
                    capture=True,
                )
            return ""
        if isinstance(content, str):
            return content
        if len(content) > 1:
            self.logger.warning("Multiple content items found in response", extra={"response": response.model_dump()})
        # TODO: we should check if it is possible to have multiple text content items
        for item in content:
            if item.type == "text":
                return item.text
        self.logger.warning("No content found in response", extra={"response": response.model_dump()})
        return ""

    def _invalid_json_error(self, response: Response, exception: Exception, content_str: str):
        # Sometimes OpenAI returns a non-JSON response that contains an excuse
        if "sorry" in content_str.lower():
            return FailedGenerationError(
                msg=f"Model refused to generate a response: {content_str}",
                response=response,
            )
        return super()._invalid_json_error(response, exception=exception, content_str=content_str)

    def _extract_usage(self, response: CompletionResponse) -> LLMUsage | None:
        return response.usage.to_domain() if response.usage else None

    def _unsupported_parameter_error(self, payload: OpenAIError, response: Response):
        if payload.error.param == "tools":
            # Capturing here, it should be caught by the model data setting
            return ModelDoesNotSupportMode(msg=payload.error.message, response=response, capture=True)
        return None

    def _invalid_request_error(self, payload: OpenAIError, response: Response):
        if payload.error.param == "response_format":
            if "Invalid schema" in payload.error.message:
                return StructuredGenerationError(
                    msg=payload.error.message,
                    response=response,
                )
        # Azure started returning an error with very little information about
        # a model not supporting structured generation
        if "response_format" in payload.error.message and "json_schema" in payload.error.message:
            return StructuredGenerationError(
                msg=payload.error.message,
                response=response,
            )
        if "tools is not supported in this model" in payload.error.message:
            return ModelDoesNotSupportMode(
                msg=payload.error.message,
                response=response,
                capture=True,
            )

        return None

    def _invalid_value_error(self, payload: OpenAIError, response: Response):
        if payload.error.param == "model":
            return ModelDoesNotSupportMode(
                msg=payload.error.message,
                response=response,
                # Capturing for now
                capture=True,
            )
        return None

    def _unknown_error(self, response: Response):  # noqa: C901
        try:
            payload = OpenAIError.model_validate_json(response.text)

            match payload.error.code:
                case "string_above_max_length":
                    # In this case we do not want to store the task run because it is a request error that
                    # does not incur cost
                    # We still bin with max tokens exceeded since it is related
                    return MaxTokensExceededError(msg=payload.error.message, response=response, store_task_run=False)
                case "invalid_prompt":
                    if "violating our usage policy" in payload.error.message:
                        return ContentModerationError(msg=payload.error.message, response=response)
                case "content_filter":
                    return ContentModerationError(msg=payload.error.message, response=response)
                case "unsupported_parameter":
                    if error := self._unsupported_parameter_error(payload, response):
                        return error
                case "invalid_value":
                    if error := self._invalid_value_error(payload, response):
                        return error
                case "invalid_image_format":
                    return ProviderBadRequestError(msg=payload.error.message, response=response)
                case "invalid_image_url":
                    return ProviderBadRequestError(msg=payload.error.message, response=response)
                case "BadRequest":
                    # Capturing for now
                    return ProviderBadRequestError(msg=payload.error.message, response=response, capture=True)
                case _:
                    pass
            if payload.error.type == "invalid_request_error":
                if error := self._invalid_request_error(payload, response):
                    return error
            return UnknownProviderError(msg=payload.error.message, response=response)
        except Exception:
            self.logger.exception("failed to parse OpenAI error response", extra={"response": response.text})
            return UnknownProviderError(msg=f"Unknown error status {response.status_code}", response=response)

    def _unknown_error_message(self, response: Response):
        try:
            payload = OpenAIError.model_validate_json(response.text)
            return payload.error.message
        except Exception:
            self.logger.exception("failed to parse OpenAI error response", extra={"response": response.text})
            return super()._unknown_error_message(response)

    @classmethod
    def requires_downloading_file(cls, file: FileWithKeyPath, model: Model) -> bool:
        # OpenAI requires downloading files for non-image files
        return not file.is_image

    @property
    def is_structured_generation_supported(self) -> bool:
        return True

    @redis_cached()
    async def is_schema_supported_for_structured_generation(
        self,
        task_name: str,
        model: Model,
        schema: dict[str, Any],
    ) -> bool:
        # Check if the task schema is actually supported by the OpenAI's implementation of structured generation
        try:
            options = ProviderOptions(
                task_name=task_name,
                model=model,
                output_schema=schema,
                structured_generation=True,  # We are forcing structured generation to be used
            )

            request, llm_completion = await self._prepare_completion(
                messages=[Message(content="Generate a test output", role=Message.Role.USER)],
                options=options,
                stream=False,
            )
            raw_completion = RawCompletion(response="", usage=llm_completion.usage)
            await self._single_complete(request, lambda x, _: StructuredOutput(json.loads(x)), raw_completion, options)
        except Exception:
            # Caught exception is wide because we do not want to impact group creation in any way, and the error is logged.
            self.logger.exception(
                "Schema is not supported for structured generation",
                extra={"schema": schema},
            )
            return False
        return True

    def _extract_stream_delta(  # noqa: C901
        self,
        sse_event: bytes,
        raw_completion: RawCompletion,
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer],
    ):
        if sse_event == b"[DONE]":
            return ParsedResponse("")
        raw = StreamedResponse.model_validate_json(sse_event)
        for choice in raw.choices:
            if choice.finish_reason == "length":
                raise MaxTokensExceededError(
                    msg="Model returned a response with a length finish reason, meaning the maximum number of tokens was exceeded.",
                    raw_completion=raw,
                )
        if raw.usage:
            raw_completion.usage = raw.usage.to_domain()

        if raw.choices:
            tools_calls: list[ToolCallRequestWithID] = []
            if raw.choices[0].delta.tool_calls:
                for tool_call in raw.choices[0].delta.tool_calls:
                    # Check if a tool call at that index is already in the buffer
                    if tool_call.index not in tool_call_request_buffer:
                        tool_call_request_buffer[tool_call.index] = ToolCallRequestBuffer()

                    buffered_tool_call = tool_call_request_buffer[tool_call.index]

                    if tool_call.id and not buffered_tool_call.id:
                        buffered_tool_call.id = tool_call.id

                    if tool_call.function.name and not buffered_tool_call.tool_name:
                        buffered_tool_call.tool_name = tool_call.function.name

                    if tool_call.function.arguments:
                        buffered_tool_call.tool_input += tool_call.function.arguments

                    if buffered_tool_call.id and buffered_tool_call.tool_name and buffered_tool_call.tool_input:
                        try:
                            tool_input_dict = json.loads(buffered_tool_call.tool_input)
                        except JSONDecodeError:
                            # That means the tool call is not full streamed yet
                            continue

                        tools_calls.append(
                            ToolCallRequestWithID(
                                id=buffered_tool_call.id,
                                tool_name=native_tool_name_to_internal(buffered_tool_call.tool_name),
                                tool_input_dict=tool_input_dict,
                            ),
                        )

            return ParsedResponse(
                raw.choices[0].delta.content or "",
                tool_calls=tools_calls,
            )

        return ParsedResponse("")

    def _compute_prompt_token_count(
        self,
        messages: list[dict[str, Any]],
        model: Model,
    ) -> float:
        """Return the number of tokens used by a list of messages.

        Simplified version of https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
        """
        OPENAI_BOILERPLATE_TOKENS = 3
        OPENAI_MESSAGE_BOILERPLATE_TOKENS = 4

        num_tokens = OPENAI_BOILERPLATE_TOKENS

        for message in messages:
            domain_message = self.open_ai_message_or_tool_message(message)
            num_tokens += domain_message.token_count(model)
            num_tokens += OPENAI_MESSAGE_BOILERPLATE_TOKENS

        return num_tokens

    def _handle_error_status_code(self, response: Response):
        try:
            response_json = response.json()
        except JSONDecodeError:
            super()._handle_error_status_code(response)
            return

        if (
            response_json.get("error")
            and response_json["error"].get("code")
            and response_json["error"]["code"] == "context_length_exceeded"
        ):
            raise MaxTokensExceededError(response_json["error"].get("message", "Max tokens exceeded"))

        if (
            response_json.get("error")
            and response_json["error"].get("message")
            and "content management policy" in response_json["error"]["message"]
        ):
            raise ContentModerationError(response_json["error"].get("message", "Content moderation error"))

        super()._handle_error_status_code(response)

    def _compute_prompt_image_count(
        self,
        messages: list[dict[str, Any]],
    ) -> int:
        # OpenAI includes image usage in the prompt token count, so we do not need to add those separately
        return 0

    async def _compute_prompt_audio_token_count(
        self,
        messages: list[dict[str, Any]],
    ):
        return 0, None

    @classmethod
    def _extract_native_tool_calls(cls, response: CompletionResponse) -> list[ToolCallRequestWithID]:
        choice = response.choices[0]

        tool_calls: list[ToolCallRequestWithID] = [
            ToolCallRequestWithID(
                id=tool_call.id,
                tool_name=native_tool_name_to_internal(tool_call.function.name),
                # OpenAI returns the tool call arguments as a string, so we need to parse it
                tool_input_dict=parse_tool_call_or_raise(tool_call.function.arguments) or {},
            )
            for tool_call in choice.message.tool_calls or []
        ]
        return tool_calls

    @override
    async def _extract_and_log_rate_limits(self, response: Response, model: Model):
        await self._log_rate_limit_remaining(
            "requests",
            remaining=response.headers.get("x-ratelimit-remaining-requests"),
            total=response.headers.get("x-ratelimit-limit-requests"),
            model=model,
        )
        await self._log_rate_limit_remaining(
            "tokens",
            remaining=response.headers.get("x-ratelimit-remaining-tokens"),
            total=response.headers.get("x-ratelimit-limit-tokens"),
            model=model,
        )
