import json
import re
from typing import Any, Literal

from httpx import Response
from pydantic import BaseModel, ConfigDict, ValidationError
from typing_extensions import override

from core.domain.fields.file import File
from core.domain.llm_usage import LLMUsage
from core.domain.message import MessageDeprecated
from core.domain.models import Model, Provider
from core.domain.models.model_data import ModelData
from core.domain.tool_call import ToolCallRequestWithID
from core.providers.base.abstract_provider import RawCompletion
from core.providers.base.httpx_provider import HTTPXProvider
from core.providers.base.models import StandardMessage
from core.providers.base.provider_error import (
    ContentModerationError,
    FailedGenerationError,
    MaxTokensExceededError,
    ProviderBadRequestError,
    ProviderInvalidFileError,
    UnknownProviderError,
)
from core.providers.base.provider_options import ProviderOptions
from core.providers.base.streaming_context import ParsedResponse, ToolCallRequestBuffer
from core.providers.base.utils import get_provider_config_env
from core.providers.google.google_provider_domain import native_tool_name_to_internal
from core.providers.groq.groq_domain import (
    CompletionRequest,
    CompletionResponse,
    GroqError,
    GroqMessage,
    GroqToolDescription,
    StreamedResponse,
    TextResponseFormat,
)
from core.providers.openai.openai_domain import parse_tool_call_or_raise


class GroqConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    provider: Literal[Provider.GROQ] = Provider.GROQ
    api_key: str
    url: str = "https://api.groq.com/openai/v1/chat/completions"

    def __str__(self):
        return f"GroqConfig(api_key={self.api_key[:4]}****)"


NAME_OVERRIDE_MAP = {
    Model.LLAMA_3_3_70B: "llama-3.3-70b-versatile",
    Model.LLAMA_3_1_8B: "llama-3.1-8b-instant",
    # The fast version of llama 4 is simply a way to target groq
    # instead of fireworks for llama 4 models
    Model.LLAMA_4_MAVERICK_FAST: "meta-llama/llama-4-maverick-17b-128e-instruct",
    Model.LLAMA_4_SCOUT_FAST: "meta-llama/llama-4-scout-17b-16e-instruct",
    Model.QWEN3_32B: "qwen/qwen3-32b",
    Model.GPT_OSS_20B: "openai/gpt-oss-20b",
    Model.GPT_OSS_120B: "openai/gpt-oss-120b",
}


class GroqProvider(HTTPXProvider[GroqConfig, CompletionResponse]):
    _content_moderation_regexp = re.compile(r"(can't|not)[^\.]*(help|assist|going)[^\.]*with that", re.IGNORECASE)

    @classmethod
    def is_content_moderation_completion(cls, raw_completion: str) -> bool:
        return cls._content_moderation_regexp.search(raw_completion) is not None

    @classmethod
    @override
    def _invalid_json_error(
        cls,
        response: Response | None,
        exception: Exception | None,
        raw_completion: str,
        error_msg: str,
        retry: bool = False,
    ) -> Exception:
        if cls.is_content_moderation_completion(raw_completion):
            return ContentModerationError(retry=retry, provider_error=raw_completion, capture=False)
        return super()._invalid_json_error(response, exception, raw_completion, error_msg, retry)

    @override
    @classmethod
    def name(cls) -> Provider:
        return Provider.GROQ

    @override
    @classmethod
    def standardize_messages(cls, messages: list[dict[str, Any]]) -> list[StandardMessage]:
        return [GroqMessage.model_validate(m).to_standard() for m in messages]

    def model_str(self, model: Model) -> str:
        return NAME_OVERRIDE_MAP.get(model, model.value)

    @override
    @classmethod
    def requires_downloading_file(cls, file: File, model: Model) -> bool:
        # For now groq models do not support files anyway
        return False

    @override
    @classmethod
    def required_env_vars(cls) -> list[str]:
        return ["GROQ_API_KEY"]

    @override
    def _build_request(self, messages: list[MessageDeprecated], options: ProviderOptions, stream: bool) -> BaseModel:
        groq_messages: list[GroqMessage] = []
        for m in messages:
            groq_messages.extend(GroqMessage.from_domain(m))

        return CompletionRequest(
            messages=groq_messages,
            model=self.model_str(Model(options.model)),
            temperature=options.temperature,
            max_tokens=options.max_tokens,
            stream=stream,
            # Looks like JSONResponseFormat does not work great on Groq
            response_format=TextResponseFormat(),
            tools=[GroqToolDescription.from_domain(t) for t in options.enabled_tools]
            if options.enabled_tools
            else None,
            top_p=options.top_p,
            presence_penalty=options.presence_penalty,
            frequency_penalty=options.frequency_penalty,
            parallel_tool_calls=options.parallel_tool_calls,
        )

    @override
    async def _request_headers(self, request: dict[str, Any], url: str, model: Model) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._config.api_key}",
        }

    @override
    def _request_url(self, model: Model, stream: bool) -> str:
        return self._config.url

    @override
    def _response_model_cls(self) -> type[CompletionResponse]:
        return CompletionResponse

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
        return response.usage.to_domain()

    @override
    def _unknown_error_message(self, response: Response):
        try:
            payload = GroqError.model_validate_json(response.text)
            return payload.error.message or super()._unknown_error_message(response)
        except Exception:
            self.logger.exception("failed to parse Groq error response", extra={"response": response.text})
            return super()._unknown_error_message(response)

    @override
    @classmethod
    def _default_config(cls, index: int) -> GroqConfig:
        return GroqConfig(
            api_key=get_provider_config_env("GROQ_API_KEY", index),
        )

    @override
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
                        except json.JSONDecodeError:
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
    ) -> int:
        GROQ_BOILERPLATE_TOKENS = 3
        GROQ_MESSAGE_BOILERPLATE_TOKENS = 4

        token_count = GROQ_BOILERPLATE_TOKENS

        for message in messages:
            domain_message = GroqMessage.model_validate(message)

            token_count += domain_message.token_count(model)
            token_count += GROQ_MESSAGE_BOILERPLATE_TOKENS

        return token_count

    def _invalid_request_error(self, payload: GroqError, response: Response):
        base_cls = UnknownProviderError
        capture: bool | None = None

        if payload.error.message:
            lower_msg = payload.error.message.lower()
            match lower_msg:
                case m if "localhost: no such host" in m:
                    base_cls = ProviderBadRequestError
                case m if "failed to retrieve media" in m:
                    base_cls = ProviderInvalidFileError
                    capture = False
                case _:
                    pass

        return base_cls(
            msg=payload.error.message or "Unknown error",
            response=response,
            capture=capture,
        )

    @override
    def _unknown_error(self, response: Response):
        if response.status_code == 413:
            # Not re-using the error message from Groq as it is not explicit (it's just "Request Entity Too Large")
            return MaxTokensExceededError("Max tokens exceeded")

        try:
            payload = GroqError.model_validate_json(response.text)
            error_message = payload.error.message

            if error_message == "Please reduce the length of the messages or completion.":
                return MaxTokensExceededError("Max tokens exceeded")
            if payload.error.code == "json_validate_failed":
                return FailedGenerationError(
                    msg="Model did not generate a valid JSON response",
                    capture=True,
                )
            if payload.error.type == "invalid_request_error":
                return self._invalid_request_error(payload, response)

        except (ValueError, ValidationError):
            pass
            # Failed to parse the error message, continue

        return super()._unknown_error(response)

    def _compute_prompt_image_count(
        self,
        messages: list[dict[str, Any]],
    ) -> int:
        # No Groq models support images in the prompt
        return 0

    @override
    async def _compute_prompt_audio_token_count(
        self,
        messages: list[dict[str, Any]],
    ):
        return 0, None

    @override
    def sanitize_model_data(self, model_data: ModelData):
        # Groq does not support structured output yet
        model_data.supports_structured_output = False
        model_data.supports_input_audio = False
        model_data.supports_input_pdf = False

    @classmethod
    def _extract_native_tool_calls(cls, response: CompletionResponse) -> list[ToolCallRequestWithID]:
        choice = response.choices[0]

        tool_calls: list[ToolCallRequestWithID] = [
            ToolCallRequestWithID(
                id=tool_call.id or "",
                tool_name=native_tool_name_to_internal(tool_call.function.name or ""),
                # OpenAI returns the tool call arguments as a string, so we need to parse it
                tool_input_dict=parse_tool_call_or_raise(tool_call.function.arguments) or {},
            )
            for tool_call in choice.message.tool_calls or []
        ]
        return tool_calls

    @override
    def default_model(self) -> Model:
        return Model.LLAMA_4_SCOUT_FAST
