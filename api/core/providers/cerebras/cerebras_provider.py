from typing import Any, Literal

from pydantic import BaseModel
from typing_extensions import override

from core.domain.llm_usage import LLMUsage
from core.domain.message import MessageDeprecated
from core.domain.models import Model, Provider
from core.providers.base.abstract_provider import RawCompletion
from core.providers.base.httpx_provider import HTTPXProvider
from core.providers.base.models import StandardMessage
from core.providers.base.provider_error import (
    FailedGenerationError,
    MaxTokensExceededError,
)
from core.providers.base.provider_options import ProviderOptions
from core.providers.base.streaming_context import ParsedResponse, ToolCallRequestBuffer
from core.providers.base.utils import get_provider_config_env
from core.utils.token_utils import tokens_from_string

from .cerebras_domain import (
    CerebrasMessage,
    CompletionRequest,
    CompletionResponse,
    StreamedResponse,
)


class CerebrasConfig(BaseModel):
    provider: Literal[Provider.CEREBRAS] = Provider.CEREBRAS
    api_key: str
    url: str = "https://api.cerebras.ai/v1/chat/completions"
    models_url: str = "https://api.cerebras.ai/v1/models"

    def __str__(self):
        return f"CerebrasConfig(api_key={self.api_key[:4]}****)"


class CerebrasProvider(HTTPXProvider[CerebrasConfig, CompletionResponse]):
    @override
    @classmethod
    def name(cls) -> Provider:
        return Provider.CEREBRAS

    @override
    @classmethod
    def required_env_vars(cls) -> list[str]:
        return ["CEREBRAS_API_KEY"]

    @override
    @classmethod
    def standardize_messages(cls, messages: list[dict[str, Any]]) -> list[StandardMessage]:
        return [CerebrasMessage.model_validate(m).to_standard() for m in messages]

    def model_str(self, model: Model) -> str:
        return model.value

    @override
    def _build_request(self, messages: list[MessageDeprecated], options: ProviderOptions, stream: bool) -> BaseModel:
        return CompletionRequest(
            messages=[CerebrasMessage.from_domain(m) for m in messages],
            model=self.model_str(Model(options.model)),
            temperature=options.temperature,
            max_tokens=options.max_tokens,
            stream=stream,
            top_p=options.top_p,
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
        if not message.content:
            raise FailedGenerationError(
                msg="Model did not generate a response content",
                capture=True,
            )
        return message.content

    @override
    def _extract_usage(self, response: CompletionResponse) -> LLMUsage | None:
        return response.usage.to_domain() if response.usage else None

    def _compute_prompt_token_count(
        self,
        messages: list[dict[str, Any]],
        model: Model,
    ) -> int:
        CEREBRAS_BOILERPLATE_TOKENS = 3
        CEREBRAS_MESSAGE_BOILERPLATE_TOKENS = 4

        token_count = CEREBRAS_BOILERPLATE_TOKENS

        for message in messages:
            domain_message = CerebrasMessage.model_validate(message)
            if domain_message.content:
                token_count += tokens_from_string(domain_message.content, model.value)
            token_count += CEREBRAS_MESSAGE_BOILERPLATE_TOKENS

        return token_count

    def _compute_prompt_image_count(
        self,
        messages: list[dict[str, Any]],
    ) -> int:
        return 0

    async def _compute_prompt_audio_token_count(
        self,
        messages: list[dict[str, Any]],
    ) -> tuple[float, float | None]:
        return 0, None

    @override
    @classmethod
    def _default_config(cls, index: int) -> CerebrasConfig:
        return CerebrasConfig(
            api_key=get_provider_config_env("CEREBRAS_API_KEY", index),
            url=get_provider_config_env("CEREBRAS_API_URL", index, "https://api.cerebras.ai/v1/chat/completions"),
            models_url=get_provider_config_env("CEREBRAS_MODELS_URL", index, "https://api.cerebras.ai/v1/models"),
        )

    @override
    def _extract_stream_delta(
        self,
        sse_event: bytes,
        raw_completion: RawCompletion,
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer],
    ) -> ParsedResponse:
        if sse_event == b"[DONE]":
            return ParsedResponse("")
        raw = StreamedResponse.model_validate_json(sse_event)
        if raw.choices:
            if raw.choices[0].finish_reason == "length":
                raise MaxTokensExceededError(
                    msg="Model returned a response with a length finish reason, meaning the maximum number of tokens was exceeded.",
                    raw_completion=raw,
                )
        if raw.usage:
            raw_completion.usage = raw.usage.to_domain()
        if raw.choices and raw.choices[0].delta:
            return ParsedResponse(raw.choices[0].delta.content or "")
        return ParsedResponse("")

    def default_model(self) -> Model:
        return Model.LLAMA_3_1_8B

    async def list_models(self) -> list[str]:
        """Return the list of models supported by the Cerebras API."""
        async with self._open_client(self._config.models_url) as client:
            response = await client.get(self._config.models_url)
            response.raise_for_status()
            data = response.json()
            # API returns {"data": [{"id": ...}]} or a plain list
            if isinstance(data, dict):
                models = [m.get("id") for m in data.get("data", [])]
            else:
                models = [m.get("id") for m in data]
            return [m for m in models if m]
