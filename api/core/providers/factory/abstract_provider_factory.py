from abc import ABC, abstractmethod
from typing import Any, Iterable

from core.domain.models import Provider
from core.providers.base.abstract_provider import AbstractProvider, ProviderConfigVar
from core.providers.base.config import ProviderConfig


class AbstractProviderFactory(ABC):
    @abstractmethod
    def build_provider(self, config: ProviderConfig, config_id: str) -> AbstractProvider[Any, Any]:
        pass

    @abstractmethod
    def get_provider(self, provider: Provider) -> AbstractProvider[Any, Any]:
        pass

    @abstractmethod
    def get_providers(self, provider: Provider) -> Iterable[AbstractProvider[Any, Any]]:
        pass

    @abstractmethod
    def provider_type(self, config: ProviderConfigVar) -> type[AbstractProvider[ProviderConfigVar, Any]]:
        pass
