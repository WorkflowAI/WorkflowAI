import logging
from collections.abc import Iterable
from typing import Any

from typing_extensions import override

from core.domain.errors import (
    MissingEnvVariablesError,
)
from core.domain.models import Provider
from core.domain.organization_settings import ProviderConfig
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


class LocalProviderFactory(AbstractProviderFactory):
    """A provider factory that uses locally defined providers.
    To add a supported provider, add it to the PROVIDER_TYPES list."""

    PROVIDER_TYPES: dict[Provider, type[AbstractProvider[Any, Any]]] = {
        provider.name(): provider for provider in _provider_cls
    }

    def __init__(self) -> None:
        self._providers: dict[Provider, dict[int, AbstractProvider[Any, Any]]] = {}
        self._logger = logging.getLogger(self.__class__.__name__)

    @override
    def get_provider(self, provider: Provider, index: int = 0) -> AbstractProvider[Any, Any]:
        if provider not in self._providers or index not in self._providers[provider]:
            try:
                provider_type = self.PROVIDER_TYPES[provider]
            except KeyError:
                raise ValueError(f"Provider {provider} index {index} not supported")

            self._providers.setdefault(provider, {})[index] = provider_type(index=index)

        return self._providers[provider][index]

    @override
    def get_providers(self, provider: Provider) -> Iterable[AbstractProvider[Any, Any]]:
        # We return the providers in the order they were inserted
        # If prepare_all_providers was called first, it should be the same order
        return self._providers[provider].values()

    def _prepare_provider_for_type(self, provider: Provider):
        for i in range(10):
            try:
                self.get_provider(provider, i)
                self._logger.info(
                    "Successfully prepared provider",
                    extra={"provider_name": provider, "index": i},
                )
            except MissingEnvVariablesError:
                if i == 0:
                    self._logger.warning(
                        "Skipping provider",
                        extra={"provider_name": provider},
                        exc_info=True,
                    )
                # We end at the first missing env variable
                return
            except Exception:
                self._logger.exception("Failed to prepare provider", extra={"provider_name": provider, "index": i})

    def prepare_all_providers(self):
        for provider_name in LocalProviderFactory.PROVIDER_TYPES.keys():
            self._prepare_provider_for_type(provider_name)

        provider_names = ", ".join(list(self._providers.keys()))
        self._logger.info(f"Prepared providers {provider_names}")  # noqa: G004

    @override
    def provider_type(self, config: ProviderConfigVar) -> type[AbstractProvider[ProviderConfigVar, Any]]:
        """Return the provider type for the given provider."""
        return self.PROVIDER_TYPES[config.provider]

    @override
    def build_provider(self, config: ProviderConfig, config_id: str) -> AbstractProvider[Any, Any]:
        """Build a provider from a configuration dictionary."""
        return self.provider_type(config)(config=config, config_id=config_id)


_shared_provider_factory = LocalProviderFactory()


def shared_provider_factory() -> LocalProviderFactory:
    return _shared_provider_factory
