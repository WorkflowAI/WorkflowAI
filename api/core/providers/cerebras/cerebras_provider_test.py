import pytest

from core.domain.models import Model, Provider
from core.providers.cerebras.cerebras_config import CerebrasConfig
from core.providers.cerebras.cerebras_provider import CerebrasProvider


class TestCerebrasProvider:
    @pytest.fixture
    def cerebras_provider(self):
        config = CerebrasConfig(api_key="test_key")
        return CerebrasProvider(config)

    def test_name(self, cerebras_provider: CerebrasProvider):
        assert cerebras_provider.name() == Provider.CEREBRAS

    def test_required_env_vars(self):
        assert CerebrasProvider.required_env_vars() == ["CEREBRAS_API_KEY"]

    def test_default_model(self, cerebras_provider: CerebrasProvider):
        assert cerebras_provider.default_model() == Model.LLAMA_4_SCOUT_FAST

    def test_request_url(self, cerebras_provider: CerebrasProvider):
        url = cerebras_provider._request_url(Model.LLAMA_4_SCOUT_FAST, stream=False)
        assert url == "https://api.cerebras.ai/v1/chat/completions"

    @pytest.mark.asyncio
    async def test_request_headers(self, cerebras_provider: CerebrasProvider):
        headers = await cerebras_provider._request_headers({}, "", Model.LLAMA_4_SCOUT_FAST)
        assert headers == {"Authorization": "Bearer test_key"}

    def test_config_str(self):
        config = CerebrasConfig(api_key="test_key_12345")
        assert str(config) == "CerebrasConfig(url=https://api.cerebras.ai/v1/chat/completions, api_key=test****)"
