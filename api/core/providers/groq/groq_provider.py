from typing import Any, Literal

from httpx import Response
from pydantic import BaseModel, ValidationError
from typing_extensions import override

from core.domain.errors import MaxTokensExceededError, UnknownProviderError
from core.domain.llm_usage import LLMUsage
from core.domain.message import Message
from core.domain.models import Model, Provider
from core.domain.models.model_data import ModelData
from core.domain.tool import Tool
from core.providers.base.abstract_provider import RawCompletion
from core.providers.base.httpx_provider import HTTPXProvider, ParsedResponse
from core.providers.base.models import StandardMessage
from core.providers.base.provider_options import ProviderOptions
from core.providers.base.streaming_context import ToolCallRequestBuffer
from core.providers.base.utils import get_provider_config_env
from core.providers.groq.groq_domain import (
    CompletionRequest,
    CompletionResponse,
    GroqError,
    GroqMessage,
    JSONResponseFormat,
    StreamedResponse,
)
from core.runners.workflowai.utils import FileWithKeyPath


class GroqConfig(BaseModel):
    provider: Literal[Provider.GROQ] = Provider.GROQ
    api_key: str

    def __str__(self):
        return f"GroqConfig(api_key={self.api_key[:4]}****)"


class GroqProvider(HTTPXProvider[GroqConfig, CompletionResponse]):
    @override
    @classmethod
    def name(cls) -> Provider:
        return Provider.GROQ

    @override
    @classmethod
    def standardize_messages(cls, messages: list[dict[str, Any]]) -> list[StandardMessage]:
        return [GroqMessage.model_validate(m).to_standard() for m in messages]

    def model_str(self, model: Model) -> str:
        NAME_OVERRIDE_MAP = {
            Model.LLAMA_3_3_70B: "llama-3.3-70b-versatile",
            Model.LLAMA_3_1_70B: "llama-3.1-70b-versatile",
            Model.LLAMA_3_1_8B: "llama-3.1-8b-instant",
        }

        return NAME_OVERRIDE_MAP.get(model, model.value)

    @override
    @classmethod
    def requires_downloading_file(cls, file: FileWithKeyPath, model: Model) -> bool:
        # For now groq models do not support files anyway
        return False

    @override
    @classmethod
    def required_env_vars(cls) -> list[str]:
        return ["GROQ_API_KEY"]

    @override
    def default_model(self) -> Model:
        return Model.LLAMA_3_1_70B

    @override
    def _build_request(self, messages: list[Message], options: ProviderOptions, stream: bool) -> BaseModel:
        # NOTE: Enforce JSON Response Format for Groq, and as side effect disable streaming
        response_format = JSONResponseFormat()
        stream = False

        return CompletionRequest(
            messages=[GroqMessage.from_domain(m) for m in messages],
            model=self.model_str(Model(options.model)),
            temperature=options.temperature,
            # TODO[max-tokens]: Set the max token from the context data
            max_tokens=options.max_tokens,
            stream=stream,
            response_format=response_format,
        )

    @override
    async def _request_headers(self, request: dict[str, Any], url: str, model: Model) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
        }

    @override
    def _request_url(self, model: Model, stream: bool) -> str:
        return "https://api.groq.com/openai/v1/chat/completions"

    @override
    def _response_model_cls(self) -> type[CompletionResponse]:
        return CompletionResponse

    @override
    def _extract_content_str(self, response: CompletionResponse) -> str:
        try:
            for choice in response.choices:
                if choice.finish_reason == "length":
                    raise MaxTokensExceededError(
                        msg="Model returned a response with a length finish reason, meaning the maximum number of tokens was exceeded.",
                        raw_completion=response,
                    )
            return response.choices[0].message.content
        except IndexError:
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
    def _extract_stream_delta(
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
        elif raw.x_groq:
            if raw.x_groq.usage:
                raw_completion.usage = raw.x_groq.usage.to_domain()
            if raw.x_groq.error:
                if raw.x_groq.error == "over_capacity":
                    raise MaxTokensExceededError("Max tokens exceeded")
                raise UnknownProviderError(raw.x_groq.error)
        if raw.choices:
            return ParsedResponse(raw.choices[0].delta.content)

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

    def _handle_error_status_code(self, response: Response):
        if response.status_code == 413:
            # Not re-using the error message from Groq as it is not explicit (it's just "Request Entity Too Large")
            raise MaxTokensExceededError("Max tokens exceeded")

        try:
            payload = GroqError.model_validate_json(response.text)
            error_message = payload.error.message

            if error_message == "Please reduce the length of the messages or completion.":
                raise MaxTokensExceededError("Max tokens exceeded")

        except (ValueError, ValidationError):
            pass
            # Failed to parse the error message, continue

        super()._handle_error_status_code(response)

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
    def is_streamable(self, model: Model, enabled_tools: list[Tool] | None = None) -> bool:
        # Disable streaming to enforce JSON Response Format
        return False

    @override
    def sanitize_model_data(self, model_data: ModelData):
        # Groq does not support structured output yet
        model_data.supports_structured_output = False
        # Native tool calling is not implemented on Groq yet.
        model_data.supports_tool_calling = False
