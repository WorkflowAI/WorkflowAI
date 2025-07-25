import json
from json import JSONDecodeError
from typing import Any, override

from httpx import Response
from pydantic import BaseModel, ValidationError

from core.domain.fields.file import File
from core.domain.fields.internal_reasoning_steps import InternalReasoningStep
from core.domain.llm_usage import LLMUsage
from core.domain.message import MessageDeprecated
from core.domain.models import Model, Provider
from core.domain.models.model_data import ModelData
from core.domain.models.utils import get_model_data
from core.domain.tool_call import ToolCallRequestWithID
from core.providers.base.httpx_provider import HTTPXProvider
from core.providers.base.models import RawCompletion, StandardMessage
from core.providers.base.provider_error import (
    ContentModerationError,
    FailedGenerationError,
    MaxTokensExceededError,
    ModelDoesNotSupportMode,
    ProviderError,
    ProviderInternalError,
    ProviderInvalidFileError,
    StructuredGenerationError,
    UnknownProviderError,
)
from core.providers.base.provider_options import ProviderOptions
from core.providers.base.streaming_context import ParsedResponse, ToolCallRequestBuffer
from core.providers.base.utils import get_provider_config_env, get_unique_schema_name, should_use_structured_output
from core.providers.google.google_provider_domain import (
    internal_tool_name_to_native_tool_call,
    native_tool_name_to_internal,
)
from core.providers.openai._openai_utils import prepare_openai_json_schema
from core.providers.openai.openai_domain import parse_tool_call_or_raise
from core.providers.xai.xai_config import XAIConfig
from core.providers.xai.xai_domain import (
    CompletionRequest,
    CompletionResponse,
    JSONSchemaResponseFormat,
    StreamedResponse,
    StreamOptions,
    Tool,
    ToolFunction,
    XAIError,
    XAIMessage,
    XAISchema,
    XAIToolMessage,
)


class XAIProvider(HTTPXProvider[XAIConfig, CompletionResponse]):
    def _response_format(self, options: ProviderOptions, model_data: ModelData):
        if options.output_schema is None:
            return None

        if not should_use_structured_output(options, model_data) or not options.output_schema:
            # TODO: at the time of writing, xAI does not support
            # any response format, so we return None when structured generation is disabled
            # to be able to use the structured output
            return None
            # return JSONResponseFormat()

        return JSONSchemaResponseFormat(
            json_schema=XAISchema(
                name=get_unique_schema_name(options.task_name, options.output_schema),
                json_schema=prepare_openai_json_schema(options.output_schema),
            ),
        )

    @override
    def _build_request(self, messages: list[MessageDeprecated], options: ProviderOptions, stream: bool) -> BaseModel:
        message: list[XAIMessage | XAIToolMessage] = []
        for m in messages:
            if m.tool_call_results:
                message.extend(XAIToolMessage.from_domain(m))
            else:
                message.append(XAIMessage.from_domain(m))

        model_data = get_model_data(options.model)

        completion_request = CompletionRequest(
            messages=message,
            model=options.model,
            temperature=options.temperature,
            max_tokens=options.max_tokens,
            stream=stream,
            stream_options=StreamOptions(include_usage=True) if stream else None,
            response_format=self._response_format(options, model_data),
            reasoning_effort=options.final_reasoning_effort(model_data.reasoning),
            tool_choice=CompletionRequest.tool_choice_from_domain(options.tool_choice),
            top_p=options.top_p,
            presence_penalty=options.presence_penalty,
            frequency_penalty=options.frequency_penalty,
        )

        if options.enabled_tools is not None and options.enabled_tools != []:
            completion_request.tools = [
                Tool(
                    type="function",
                    function=ToolFunction(
                        name=internal_tool_name_to_native_tool_call(tool.name),
                        description=tool.description,
                        parameters=tool.input_schema,
                        strict=tool.strict is True,
                    ),
                )
                for tool in options.enabled_tools
            ]

        return completion_request

    @override
    def _response_model_cls(self) -> type[CompletionResponse]:
        return CompletionResponse

    @classmethod
    def xai_message_or_tool_message(cls, messag_dict: dict[str, Any]) -> XAIMessage | XAIToolMessage:
        try:
            return XAIToolMessage.model_validate(messag_dict)
        except ValidationError:
            return XAIMessage.model_validate(messag_dict)

    @classmethod
    def standardize_messages(cls, messages: list[dict[str, Any]]) -> list[StandardMessage]:
        result: list[StandardMessage] = []
        current_tool_messages: list[XAIToolMessage] = []

        for message in (cls.xai_message_or_tool_message(m) for m in messages):
            if isinstance(message, XAIToolMessage):
                current_tool_messages.append(message)
            else:
                # Process any accumulated tool messages before adding the non-tool message
                if current_tool_messages:
                    if tool_message := XAIToolMessage.to_standard(current_tool_messages):
                        result.append(tool_message)
                    current_tool_messages = []

                # Add the non-tool message
                result.append(message.to_standard())

        # Handle any remaining tool messages at the end
        if current_tool_messages:
            if tool_message := XAIToolMessage.to_standard(current_tool_messages):
                result.append(tool_message)

        return result

    @override
    async def _request_headers(self, request: dict[str, Any], url: str, model: Model) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._config.api_key}",
        }

    @override
    def _request_url(self, model: Model, stream: bool) -> str:
        return self._config.url

    @override
    def _extract_reasoning_steps(self, response: CompletionResponse) -> list[InternalReasoningStep] | None:
        try:
            content = response.choices[0].message.reasoning_content
        except IndexError:
            return None
        return [InternalReasoningStep(explaination=content)]

    @override
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

    @override
    def _extract_usage(self, response: CompletionResponse) -> LLMUsage | None:
        return response.usage.to_domain() if response.usage else None

    @override
    def _unknown_error_message(self, response: Response):
        self.logger.warning("Unknown error message should not be used for XAI", extra={"response": response.text})
        return super()._unknown_error_message(response)

    @override
    @classmethod
    def requires_downloading_file(cls, file: File, model: Model) -> bool:
        return False

    @override
    @classmethod
    def required_env_vars(cls) -> list[str]:
        return ["XAI_API_KEY"]

    @override
    @classmethod
    def name(cls) -> Provider:
        return Provider.X_AI

    @override
    @classmethod
    def _default_config(cls, index: int) -> XAIConfig:
        return XAIConfig(api_key=get_provider_config_env("XAI_API_KEY", index))

    @property
    def is_structured_generation_supported(self) -> bool:
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

        if not raw.choices:
            return ParsedResponse("")

        first_choice_delta = raw.choices[0].delta
        tools_calls: list[ToolCallRequestWithID] = []
        if first_choice_delta.tool_calls:
            for tool_call in first_choice_delta.tool_calls:
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
            first_choice_delta.content or "",
            tool_calls=tools_calls,
            reasoning_steps=first_choice_delta.reasoning_content,
        )

    def _compute_prompt_token_count(
        self,
        messages: list[dict[str, Any]],
        model: Model,
    ) -> float:
        raise NotImplementedError("Token counting is not implemented for XAI")

    def _compute_prompt_image_count(
        self,
        messages: list[dict[str, Any]],
    ) -> int:
        # XAI includes image usage in the prompt token count, so we do not need to add those separately
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
                # XAI returns the tool call arguments as a string, so we need to parse it
                tool_input_dict=parse_tool_call_or_raise(tool_call.function.arguments) or {},
            )
            for tool_call in choice.message.tool_calls or []
        ]
        return tool_calls

    def _invalid_argument_error(self, payload: XAIError, response: Response) -> ProviderError:
        message = payload.error
        lower_msg = message.lower()
        match lower_msg:
            case m if "maximum prompt length" in m:
                error_cls = MaxTokensExceededError
            case m if "response does not contain a valid jpg or png image" in m:
                error_cls = ProviderInvalidFileError
            case m if "prefill bootstrap failed for request" in m:
                error_cls = ProviderInternalError
            case m if "model does not support formatted output" in m:
                error_cls = StructuredGenerationError
            case _:
                error_cls = UnknownProviderError
        return error_cls(msg=message, response=response)

    @override
    def _unknown_error(self, response: Response) -> ProviderError:
        try:
            payload = XAIError.model_validate_json(response.text)

            match payload.code:
                case "Client specified an invalid argument":
                    return self._invalid_argument_error(payload, response)
                case _:
                    pass

            lowed_msg = payload.error.lower()

            if "unsupported content-type encountered when downloading image" in lowed_msg:
                return ModelDoesNotSupportMode(
                    msg=payload.error or f"Unknown error status {response.status_code}",
                    response=response,
                )

            return UnknownProviderError(
                msg=payload.error or f"Unknown error status {response.status_code}",
                response=response,
            )
        except Exception:
            self.logger.exception("failed to parse XAI error response", extra={"response": response.text})
        return UnknownProviderError(msg=f"Unknown error status {response.status_code}", response=response)

    @override
    def default_model(self) -> Model:
        return Model.GROK_3_MINI_BETA
