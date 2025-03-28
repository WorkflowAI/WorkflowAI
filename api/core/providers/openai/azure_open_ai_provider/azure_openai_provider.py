import json
from typing import Any, Literal

from pydantic import BaseModel
from typing_extensions import override

from core.domain.errors import InvalidProviderConfig, ProviderDoesNotSupportModelError
from core.domain.models import Model, Provider
from core.domain.tool import Tool
from core.providers.base.utils import get_provider_config_env
from core.providers.openai.openai_domain import MODEL_NAME_MAP
from core.providers.openai.openai_provider_base import OpenAIProviderBase

_AZURE_API_REGION_METADATA_KEY = "workflowai.azure_openai_api_region"

_ADDITONAL_NON_STREAMING_MODELS = {
    Model.O1_MINI_2024_09_12,
    Model.O1_PREVIEW_2024_09_12,
    Model.O1_MINI_LATEST,
}


class AzureOpenAIConfig(BaseModel):
    provider: Literal[Provider.AZURE_OPEN_AI] = Provider.AZURE_OPEN_AI
    deployments: dict[str, dict[str, str | list[str]]]
    api_version: str = "2024-12-01-preview"
    default_region: str = "eastus"

    def get_region_config(self, region: str) -> dict[str, str | list[str]] | None:
        return self.deployments.get(region) or self.deployments.get(self.default_region)

    def __str__(self) -> str:
        return f"AzureOpenAIConfig(deployments={list(self.deployments.keys())}, api_version={self.api_version})"


class AzureOpenAIProvider(OpenAIProviderBase[AzureOpenAIConfig]):
    def is_model_available_in_region(self, model_value: str, region: str) -> bool:
        region_config = self.config.get_region_config(region)
        if not region_config:
            return False
        return model_value in region_config["models"]  # type: ignore

    def get_best_region_for_model(self, model_value: str) -> str:
        if self.is_model_available_in_region(model_value, "eastus"):
            return self.config.default_region
        for region in self.config.deployments:
            if self.is_model_available_in_region(model_value, region):
                return region
        raise ValueError(f"No region found for model {model_value}")

    @override
    async def _request_headers(self, request: dict[str, Any], url: str, model: Model) -> dict[str, str]:
        region = self._get_metadata(_AZURE_API_REGION_METADATA_KEY) or self.config.default_region
        region_config = self.config.get_region_config(region)
        if not region_config:
            raise ValueError(f"No configuration found for region {region}")
        return {
            "Content-Type": "application/json",
            "api-key": str(region_config["api_key"]),
        }

    @override
    def _request_url(self, model: Model, stream: bool) -> str:
        model_value = MODEL_NAME_MAP.get(model, model.value)
        region = self.get_best_region_for_model(model_value) or self.config.default_region
        region_config = self.config.get_region_config(region)
        if not region_config:
            raise ProviderDoesNotSupportModelError(model=model, provider=self.name())
        self._add_metadata(_AZURE_API_REGION_METADATA_KEY, region)
        return f"{region_config['url']}{model_value}/chat/completions?api-version={self.config.api_version}"

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
