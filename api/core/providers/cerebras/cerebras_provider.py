from typing import Any, Literal

from pydantic import BaseModel
from typing_extensions import override

from core.domain.models import Model, Provider
from core.providers.base.utils import get_provider_config_env
from core.providers.openai.openai_provider_base import OpenAIProviderBase


class CerebrasConfig(BaseModel):
    provider: Literal[Provider.CEREBRAS] = Provider.CEREBRAS

    url: str = "https://api.cerebras.ai/v1/chat/completions"
    api_key: str

    def __str__(self):
        return f"CerebrasConfig(url={self.url}, api_key={self.api_key[:4]}****)"


class CerebrasProvider(OpenAIProviderBase[CerebrasConfig]):
    @override
    async def _request_headers(self, request: dict[str, Any], url: str, model: Model) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._config.api_key}",
        }

    @override
    def _request_url(self, model: Model, stream: bool) -> str:
        return self._config.url

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
        return CerebrasConfig(
            api_key=get_provider_config_env("CEREBRAS_API_KEY", index),
            url=get_provider_config_env("CEREBRAS_URL", index, "https://api.cerebras.ai/v1/chat/completions"),
        )

    @override
    def default_model(self) -> Model:
        return Model.LLAMA_3_1_8B
