from typing import Any, Literal

from typing_extensions import override

from core.domain.llm_usage import LLMUsage
from core.domain.models import Model, Provider
from core.providers.google.google_provider_base import GoogleProviderBase
from core.providers.google.google_provider_domain import (
    GOOGLE_CHARS_PER_TOKEN,
    PER_TOKEN_MODELS,
    message_or_system_message,
)
from core.providers.google.vertex_base_config import VertexBaseConfig

# Models are global by default
_MIXED_REGION_MODELS = {
    Model.GEMINI_1_5_FLASH_002,
    Model.GEMINI_1_5_FLASH_001,
    Model.GEMINI_1_5_PRO_001,
    Model.GEMINI_1_5_PRO_002,
}

_GLOBAL_MODELS = {
    Model.GEMINI_2_5_FLASH_PREVIEW_0417,
    Model.GEMINI_2_5_FLASH_PREVIEW_0520,
    Model.GEMINI_2_5_PRO_PREVIEW_0506,
    Model.GEMINI_2_5_PRO_PREVIEW_0605,
    Model.GEMINI_2_5_FLASH_THINKING_PREVIEW_0417,
    Model.GEMINI_2_5_FLASH_THINKING_PREVIEW_0520,
    Model.GEMINI_2_0_FLASH_001,
    Model.GEMINI_2_0_FLASH_LITE_001,
    Model.GEMINI_2_5_PRO,
    Model.GEMINI_2_5_FLASH,
    Model.GEMINI_2_5_FLASH_LITE_PREVIEW_0617,
}


class GoogleProviderConfig(VertexBaseConfig):
    provider: Literal[Provider.GOOGLE] = Provider.GOOGLE


class GoogleProvider(GoogleProviderBase[GoogleProviderConfig]):
    def get_vertex_location(self, model: Model) -> str:
        if model in _GLOBAL_MODELS:
            return "global"

        if model not in _MIXED_REGION_MODELS:
            return self._config.vertex_location[0]

        return self._config.get_random_location(self._get_metadata, self._add_metadata)

    @override
    async def _request_headers(self, request: dict[str, Any], url: str, model: Model) -> dict[str, str]:
        return await self._config.get_request_headers()

    _MODEL_STR_OVERRIDES = {
        Model.LLAMA_3_2_90B: "llama-3.2-90b-vision-instruct-maas",
        Model.LLAMA_3_1_405B: "llama3-405b-instruct-maas",
    }

    @override
    def _model_url_str(self, model: Model) -> str:
        if model in self._MODEL_STR_OVERRIDES:
            return self._MODEL_STR_OVERRIDES[model]
        return super()._model_url_str(model)

    @override
    def _request_url(self, model: Model, stream: bool) -> str:
        location = self.get_vertex_location(model)

        PUBLISHER_OVERRIDES = {
            Model.LLAMA_3_1_405B: "meta",
        }

        if stream:
            suffix = "streamGenerateContent?alt=sse"
        else:
            suffix = "generateContent"

        model_str = self._model_url_str(model)
        publisher_str = PUBLISHER_OVERRIDES.get(model, "google")

        location_prefix = "" if location == "global" else f"{location}-"

        return f"https://{location_prefix}aiplatform.googleapis.com/v1/projects/{self._config.vertex_project}/locations/{location}/publishers/{publisher_str}/models/{model_str}:{suffix}"

    @override
    @classmethod
    def required_env_vars(cls) -> list[str]:
        return VertexBaseConfig.required_env_vars()

    @override
    @classmethod
    def name(cls) -> Provider:
        return Provider.GOOGLE

    @override
    @classmethod
    def _default_config(cls, index: int) -> GoogleProviderConfig:
        return GoogleProviderConfig.default(index)

    @property
    @override
    def max_number_of_file_urls(self):
        return 10

    @classmethod
    def sanitize_config(cls, config: GoogleProviderConfig) -> GoogleProviderConfig:
        return config.sanitize()

    def _compute_prompt_token_count_per_token(self, messages: list[dict[str, Any]], model: Model) -> float:
        token_count = 0

        for message in messages:
            domain_message = message_or_system_message(message)

            message_token_count = domain_message.text_token_count(model)
            token_count += message_token_count

        return token_count

    @override
    def _compute_prompt_token_count(
        self,
        messages: list[dict[str, Any]],
        model: Model,
    ) -> float:
        if model in PER_TOKEN_MODELS:
            return self._compute_prompt_token_count_per_token(messages, model)

        char_count = 0

        for message in messages:
            domain_message = message_or_system_message(message)
            message_char_count = domain_message.text_char_count()
            char_count += message_char_count

        return char_count / GOOGLE_CHARS_PER_TOKEN

    @override
    def _compute_prompt_image_count(
        self,
        messages: list[dict[str, Any]],
    ) -> int:
        image_count = 0

        for message in messages:
            domain_message = message_or_system_message(message)

            message_char_count = domain_message.image_count()
            image_count += message_char_count

        return image_count

    @override
    async def feed_prompt_token_count(self, llm_usage: LLMUsage, messages: list[dict[str, Any]], model: Model) -> None:
        if model in PER_TOKEN_MODELS:
            # For per token models, we just return the number of tokens
            await super().feed_prompt_token_count(llm_usage, messages, model)
            return
        # For other models, we have to compute the number of characters

        llm_usage.prompt_token_count = self._compute_prompt_token_count(messages, model)
        # the prompt token count should include the total number of tokens
        if llm_usage.prompt_audio_token_count is not None:
            llm_usage.prompt_token_count += llm_usage.prompt_audio_token_count

    @override
    def feed_completion_token_count(self, llm_usage: LLMUsage, response: str | None, model: Model) -> None:
        if model in PER_TOKEN_MODELS:
            # For per token models, we just return the number of tokens
            super().feed_completion_token_count(llm_usage, response, model)
            return

        llm_usage.completion_token_count = len(response.replace(" ", "")) / GOOGLE_CHARS_PER_TOKEN if response else 0

    @override
    def default_model(self) -> Model:
        return Model.GEMINI_2_0_FLASH_001
