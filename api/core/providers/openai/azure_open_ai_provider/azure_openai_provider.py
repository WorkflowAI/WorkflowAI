import json
from typing import Any

from typing_extensions import override

from core.domain.errors import InvalidProviderConfig, ProviderDoesNotSupportModelError
from core.domain.models import Model, Provider
from core.domain.tool import Tool
from core.providers.base.utils import get_provider_config_env
from core.providers.openai.azure_open_ai_provider.azure_openai_config import AzureOpenAIConfig
from core.providers.openai.openai_domain import MODEL_NAME_MAP
from core.providers.openai.openai_provider_base import OpenAIProviderBase

_AZURE_API_REGION_METADATA_KEY = "workflowai.azure_openai_api_region"

_ADDITONAL_NON_STREAMING_MODELS = {
    Model.O1_MINI_2024_09_12,
    Model.O1_PREVIEW_2024_09_12,
    Model.O1_MINI_LATEST,
}


class AzureOpenAIProvider(OpenAIProviderBase[AzureOpenAIConfig]):
    def get_best_region_for_model(self, model_value: str):
        for region, region_config in self._config.deployments.items():
            if model_value in region_config.models:
                return region, region_config

        raise ProviderDoesNotSupportModelError(model=model_value, provider=self.name())

    @override
    async def _request_headers(self, request: dict[str, Any], url: str, model: Model) -> dict[str, str]:
        region = self._get_metadata(_AZURE_API_REGION_METADATA_KEY)
        if not region:
            self.logger.warning("No region found for model %s", model)
            region, _ = self.get_best_region_for_model(model)

        region_config = self._config.deployments[region]
        return {
            "Content-Type": "application/json",
            "api-key": str(region_config.api_key),
        }

    @override
    def _request_url(self, model: Model, stream: bool) -> str:
        model_value = MODEL_NAME_MAP.get(model, model.value)
        region, region_config = self.get_best_region_for_model(model_value)
        if not region_config:
            raise ProviderDoesNotSupportModelError(model=model, provider=self.name())
        self._add_metadata(_AZURE_API_REGION_METADATA_KEY, region)
        return f"{region_config.url}{model_value}/chat/completions?api-version={self._config.api_version}"

    @override
    @classmethod
    def required_env_vars(cls) -> list[str]:
        return ["AZURE_OPENAI_CONFIG"]

    @override
    @classmethod
    def name(cls) -> Provider:
        return Provider.AZURE_OPEN_AI

    @override
    @classmethod
    def _default_config(cls, index: int) -> AzureOpenAIConfig:
        config_str = get_provider_config_env("AZURE_OPENAI_CONFIG", index)
        try:
            config_data = json.loads(config_str)
        except Exception as e:
            raise InvalidProviderConfig("Azure config is not a valid json") from e

        return AzureOpenAIConfig(
            deployments=config_data.get("deployments", {}),
        )

    @override
    def default_model(self) -> Model:
        return Model.GPT_4O_2024_11_20

    @override
    def is_streamable(self, model: Model, enabled_tools: list[Tool] | None = None) -> bool:
        return model not in _ADDITONAL_NON_STREAMING_MODELS and super().is_streamable(model)
