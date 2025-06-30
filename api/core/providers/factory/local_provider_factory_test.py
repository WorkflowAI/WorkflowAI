# pyright: reportPrivateUsage=false

import pytest

from core.domain.models.model_provider_data_mapping import MODEL_PROVIDER_DATAS
from core.providers.factory.local_provider_factory import LocalProviderFactory


@pytest.fixture
def provider_factory():
    return LocalProviderFactory()


def test_default_models_are_supported(provider_factory: LocalProviderFactory):
    assert provider_factory._providers, "sanity"
    for providers in provider_factory._providers.values():
        provider = providers[0]
        default_model = provider.default_model()

        # Check that model is supported by provider
        assert default_model in MODEL_PROVIDER_DATAS[provider.name()], (
            f"model {default_model} is not supported by provider {provider.name()}"
        )
