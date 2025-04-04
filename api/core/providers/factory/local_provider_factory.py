import logging
from collections.abc import Iterable
from typing import Any

from typing_extensions import override

from core.domain.errors import (
    MissingEnvVariablesError,
)
from core.domain.models import Provider
from core.domain.tenant_data import ProviderConfig
from core.providers.amazon_bedrock.amazon_bedrock_provider import AmazonBedrockProvider
from core.providers.anthropic.anthropic_provider import AnthropicProvider
from core.providers.base.abstract_provider import AbstractProvider, ProviderConfigVar
from core.providers.factory.abstract_provider_factory import AbstractProviderFactory
from core.providers.fireworks.fireworks_provider import FireworksAIProvider
from core.providers.google.gemini.gemini_api_provider import GoogleGeminiAPIProvider
from core.providers.google.google_provider import GoogleProvider
from core.providers.groq.groq_provider import GroqProvider
from core.providers.mistral.mistral_provider import MistralAIProvider
from core.providers.openai.azure_open_ai_provider.azure_openai_provider import AzureOpenAIProvider
from core.providers.openai.openai_provider import OpenAIProvider

_provider_cls: list[type[AbstractProvider[Any, Any]]] = [
    OpenAIProvider,
    AzureOpenAIProvider,
    GroqProvider,
    GoogleProvider,
    AmazonBedrockProvider,
    MistralAIProvider,
    AnthropicProvider,
    GoogleGeminiAPIProvider,
    FireworksAIProvider,
]

_logger = logging.getLogger("LocalProviderFactory")


class LocalProviderFactory(AbstractProviderFactory):
    """A provider factory that uses locally defined providers.
    To add a supported provider, add it to the PROVIDER_TYPES list."""

    PROVIDER_TYPES: dict[Provider, type[AbstractProvider[Any, Any]]] = {
        provider.name(): provider for provider in _provider_cls
    }

    def __init__(self) -> None:
        self._providers = self.build_available_providers()

    @override
    def get_provider(self, provider: Provider, index: int = 0) -> AbstractProvider[Any, Any]:
        return self._providers[provider][index]

    @override
    def get_providers(self, provider: Provider) -> Iterable[AbstractProvider[Any, Any]]:
        # We return the providers in the order they were inserted
        # If prepare_all_providers was called first, it should be the same order
        return self._providers[provider]

    @classmethod
    def _build_providers_for_type(cls, provider: Provider, index: int):
        providers: list[AbstractProvider[Any, Any]] = []
        try:
            provider_type = cls.PROVIDER_TYPES[provider]
        except KeyError:
            raise ValueError(f"Provider {provider} index {index} not supported")

        for i in range(10):
            try:
                providers.append(provider_type(index=i))
                _logger.info(
                    "Successfully prepared provider",
                    extra={"provider_name": provider, "index": i},
                )
            except MissingEnvVariablesError:
                if i == 0:
                    _logger.warning(
                        "Skipping provider",
                        extra={"provider_name": provider},
                        exc_info=True,
                    )
                # We end at the first missing env variable
                break
            except Exception:
                _logger.exception("Failed to prepare provider", extra={"provider_name": provider, "index": i})
        return providers

    @classmethod
    def build_available_providers(cls) -> dict[Provider, list[AbstractProvider[Any, Any]]]:
        return {
            provider: cls._build_providers_for_type(provider, 0)
            for provider in LocalProviderFactory.PROVIDER_TYPES.keys()
        }

    @override
    def provider_type(self, config: ProviderConfigVar) -> type[AbstractProvider[ProviderConfigVar, Any]]:
        """Return the provider type for the given provider."""
        return self.PROVIDER_TYPES[config.provider]

    @override
    def build_provider(
        self,
        config: ProviderConfig,
        config_id: str,
        preserve_credits: bool | None,
    ) -> AbstractProvider[Any, Any]:
        """Build a provider from a configuration dictionary."""
        return self.provider_type(config)(config=config, config_id=config_id, preserve_credits=preserve_credits)

    def available_providers(self) -> Iterable[Provider]:
        return self._providers.keys()
