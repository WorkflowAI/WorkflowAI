from unittest.mock import patch

import pytest

from core.domain.message import MessageDeprecated
from core.domain.models import Model
from core.domain.structured_output import StructuredOutput
from core.providers.base.provider_options import ProviderOptions
from core.providers.google.google_provider import (
    _MIXED_REGION_MODELS,  # pyright: ignore [reportPrivateUsage]
    GoogleProvider,
)

_VERTEX_REGIONS = ["us-central1", "us-east1", "us-east4", "us-east5", "us-south1", "us-west1", "us-west4"]


class TestModelsAvailabeInRegions:
    @pytest.mark.parametrize("model", _MIXED_REGION_MODELS)
    @pytest.mark.parametrize("region", _VERTEX_REGIONS)
    async def test_models_available_in_regions(self, model: Model, region: str) -> None:
        # Check that our config allows hitting all vertex regions
        # Note: Monitor if ProviderErrors are raised consistently.
        with patch("core.providers.google.google_provider.GoogleProvider.get_vertex_location", return_value=region):
            provider = GoogleProvider()
            url = provider._request_url(model, False)  # pyright: ignore [reportPrivateUsage]
            assert region in str(url), "sanity"
            instructions = """Respond in this format only, Ignore spaces and newlines from the response. Format: {"capital": "Paris"}."""
            question = """What is the capital of Germany?"""
            res = await provider.complete(
                messages=[
                    MessageDeprecated(role=MessageDeprecated.Role.SYSTEM, content=instructions),
                    MessageDeprecated(role=MessageDeprecated.Role.USER, content=question),
                ],
                options=ProviderOptions(model=model, max_tokens=10, temperature=0),
                output_factory=lambda x, _: StructuredOutput({"capital": x}),
            )
            assert res is not None
