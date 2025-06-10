import datetime
from typing import Any, Iterator

import pytest

from core.domain.models.utils import is_model_available_at_provider
from core.providers.base.abstract_provider import AbstractProvider
from core.providers.factory.local_provider_factory import LocalProviderFactory
from core.providers.openai.azure_open_ai_provider.azure_openai_provider import AzureOpenAIProvider


def get_provider() -> Iterator[type[AbstractProvider[Any, Any]]]:
    for provider in LocalProviderFactory.PROVIDER_TYPES.values():
        yield provider


@pytest.mark.parametrize("provider", get_provider())
def test_provider_default_model_is_up_to_date(provider: type[AbstractProvider[Any, Any]]) -> None:
    """
    Test that all provider have a default model defined in 'PROVIDER_DEFAULT_MODEL'
    """

    if provider is AzureOpenAIProvider:
        pytest.skip("AzureOpenAIProvider is not implemented yet")

    try:
        default_model = provider().default_model()
    except StopIteration as e:
        raise e

    # Check that the provider default model will still available at the provider in 15 days
    provider_default_model_available_in_3_days = is_model_available_at_provider(
        provider=provider.name(),
        model=default_model,
        today=datetime.date.today() + datetime.timedelta(days=3),
    )

    assert provider_default_model_available_in_3_days, (
        f"Default model {default_model} for provider {provider} will not be available in 3 days"
    )
