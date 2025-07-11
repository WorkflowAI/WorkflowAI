import json
from json import JSONDecodeError
from typing import Any, override

from httpx import Response
from pydantic import BaseModel, ValidationError

from core.domain.fields.file import File
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
    ProviderError,
    StructuredGenerationError,
    UnknownProviderError,
)
from core.providers.base.provider_options import ProviderOptions
from core.providers.base.streaming_context import ParsedResponse, ToolCallRequestBuffer
from core.providers.base.utils import get_provider_config_env, get_unique_schema_name, should_use_structured_output
from core.providers.cerebras.cerebras_config import CerebrasConfig
from core.providers.cerebras.cerebras_domain import (
    CerebrasError,
    CerebrasMessage,
    CerebrasSchema,
    CerebrasToolMessage,
    CompletionRequest,
    CompletionResponse,
    JSONSchemaResponseFormat,
    StreamedResponse,
    ToolFunction,
    parse_tool_call_or_raise,
)
from core.providers.cerebras.cerebras_domain import (
    Tool as CerebrasTool,
)
from core.providers.cerebras.cerebras_utils import prepare_cerebras_json_schema
from core.providers.google.google_provider_domain import (
    native_tool_name_to_internal,
)


class CerebrasProvider(HTTPXProvider[CerebrasConfig, CompletionResponse]):
    # Mapping from internal model IDs to Cerebras-specific model IDs
    MODEL_ID_MAPPING = {
        Model.LLAMA_4_SCOUT_FAST: "llama-4-scout-17b-16e-instruct",
        Model.LLAMA_3_1_8B: "llama3.1-8b",
        Model.LLAMA_3_3_70B: "llama-3.3-70b",
    }

    def _response_format(self, options: ProviderOptions, model_data: ModelData):
        if options.output_schema is None:
            return None

        if not should_use_structured_output(options, model_data) or not options.output_schema:
            # TODO: at the time of writing, Cerebras does not support
            # any response format, so we return None when structured generation is disabled
            # to be able to use the structured output
            return None

        return JSONSchemaResponseFormat(
            json_schema=CerebrasSchema(
                name=get_unique_schema_name(options.task_name, options.output_schema),
                json_schema=prepare_cerebras_json_schema(options.output_schema),
            ),
        )

    @override
    def _build_request(self, messages: list[MessageDeprecated], options: ProviderOptions, stream: bool) -> BaseModel:
        # Map internal model ID to Cerebras-specific model ID
        cerebras_model_id = self.MODEL_ID_MAPPING.get(options.model, options.model)

        message: list[CerebrasMessage | CerebrasToolMessage] = []
        for m in messages:
            if m.tool_call_results:
                message.extend(CerebrasToolMessage.from_domain(m))
            else:
                message.append(CerebrasMessage.from_domain(m, cerebras_model_id))

        model_data = get_model_data(options.model)

        completion_request = CompletionRequest(
            messages=message,
            model=cerebras_model_id,
            temperature=options.temperature,
            max_completion_tokens=options.max_tokens,
            stream=stream,
            response_format=self._response_format(options, model_data),
            tool_choice=CompletionRequest.tool_choice_from_domain(options.tool_choice),
            top_p=options.top_p,
        )

        if options.enabled_tools is not None and options.enabled_tools != []:
            completion_request.tools = [
                CerebrasTool(
                    type="function",
                    function=ToolFunction(
                        name=tool.name,
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
    def cerebras_message_or_tool_message(cls, message_dict: dict[str, Any]) -> CerebrasMessage | CerebrasToolMessage:
        try:
            return CerebrasToolMessage.model_validate(message_dict)
        except ValidationError:
            return CerebrasMessage.model_validate(message_dict)

    @classmethod
    def standardize_messages(cls, messages: list[dict[str, Any]]) -> list[StandardMessage]:
        result: list[StandardMessage] = []
        current_tool_messages: list[CerebrasToolMessage] = []

        for message in (cls.cerebras_message_or_tool_message(m) for m in messages):
            if isinstance(message, CerebrasToolMessage):
                current_tool_messages.append(message)
            else:
                # Process any accumulated tool messages before adding the non-tool message
                if current_tool_messages:
                    if tool_message := CerebrasToolMessage.to_standard(current_tool_messages):
                        result.append(tool_message)
                    current_tool_messages = []

                # Add the non-tool message
                result.append(message.to_standard())

        # Handle any remaining tool messages at the end
        if current_tool_messages:
            if tool_message := CerebrasToolMessage.to_standard(current_tool_messages):
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
    @classmethod
    def requires_downloading_file(cls, file: File, model: Model) -> bool:
        return False

    @override
    @classmethod
    def required_env_vars(cls) -> list[str]:
        return ["CEREBRAS_API_KEY"]

    @override
    @classmethod
    def name(cls) -> Provider:
        return Provider.CEREBRAS

    @override
    @classmethod
    def _default_config(cls, index: int) -> CerebrasConfig:
        return CerebrasConfig(api_key=get_provider_config_env("CEREBRAS_API_KEY", index))

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
        )

    def _compute_prompt_token_count(
        self,
        messages: list[dict[str, Any]],
        model: Model,
    ) -> float:
        """Return the number of tokens used by a list of messages.

        Uses a similar approach to OpenAI's token counting with boilerplate tokens.
        """
        CEREBRAS_BOILERPLATE_TOKENS = 3
        CEREBRAS_MESSAGE_BOILERPLATE_TOKENS = 4

        num_tokens = CEREBRAS_BOILERPLATE_TOKENS

        for message in messages:
            domain_message = self.cerebras_message_or_tool_message(message)
            num_tokens += domain_message.token_count(model)
            num_tokens += CEREBRAS_MESSAGE_BOILERPLATE_TOKENS

        return num_tokens

    def _compute_prompt_image_count(
        self,
        messages: list[dict[str, Any]],
    ) -> int:
        # Cerebras does not support images
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
                # Cerebras returns the tool call arguments as a string, so we need to parse it
                tool_input_dict=parse_tool_call_or_raise(tool_call.function.arguments) or {},
            )
            for tool_call in choice.message.tool_calls or []
        ]
        return tool_calls

    def _invalid_argument_error(self, payload: CerebrasError, response: Response) -> ProviderError:
        message = payload.message
        lower_msg = message.lower()
        match lower_msg:
            case m if "please reduce the length of the messages" in m:
                error_cls = MaxTokensExceededError
            case m if "JSON schema fields" in m:
                error_cls = StructuredGenerationError
            case _:
                error_cls = UnknownProviderError
        return error_cls(msg=message, response=response)

    @override
    def _unknown_error(self, response: Response) -> ProviderError:
        try:
            payload = CerebrasError.model_validate_json(response.text)

            # Handle specific error types
            if payload.type == "invalid_request_error":
                return self._invalid_argument_error(payload, response)

            return UnknownProviderError(
                msg=payload.message or f"Unknown error status {response.status_code}",
                response=response,
            )
        except Exception as e:
            self.logger.exception(
                "failed to parse Cerebras error response",
                extra={
                    "response": response.text,
                    "parse_error": str(e),
                },
            )
        return UnknownProviderError(msg=f"Unknown error status {response.status_code}", response=response)

    @override
    def default_model(self) -> Model:
        return Model.LLAMA_4_SCOUT_FAST
