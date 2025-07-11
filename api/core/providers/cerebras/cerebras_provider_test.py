from typing import Any
from unittest.mock import Mock, patch

import pytest
from httpx import Response

from core.domain.models import Model, Provider
from core.providers.base.provider_error import MaxTokensExceededError, UnknownProviderError
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
        url = cerebras_provider._request_url(Model.LLAMA_4_SCOUT_FAST, stream=False)  # type: ignore[reportPrivateUsage]
        assert url == "https://api.cerebras.ai/v1/chat/completions"

    @pytest.mark.asyncio
    async def test_request_headers(self, cerebras_provider: CerebrasProvider):
        headers = await cerebras_provider._request_headers({}, "", Model.LLAMA_4_SCOUT_FAST)  # type: ignore[reportPrivateUsage]
        assert headers == {"Authorization": "Bearer test_key"}

    def test_config_str(self):
        config = CerebrasConfig(api_key="test_key_12345")
        assert str(config) == "CerebrasConfig(url=https://api.cerebras.ai/v1/chat/completions, api_key=test****)"

    @pytest.mark.parametrize(
        "messages,expected_token_count",
        [
            # Test with a single user message
            (
                [{"role": "user", "content": "Hello"}],
                8,  # 3 (boilerplate) + 4 (message boilerplate) + 1 (content token)
            ),
            # Test with multiple messages
            (
                [
                    {"role": "system", "content": "You are helpful"},
                    {"role": "user", "content": "Hello"},
                ],
                15,  # 3 (boilerplate) + 2 * (4 (message boilerplate)) + 2 (content tokens)
            ),
            # Test with empty message list
            (
                [],
                3,  # 3 (boilerplate only)
            ),
        ],
    )
    def test_compute_prompt_token_count(
        self,
        cerebras_provider: CerebrasProvider,
        messages: list[dict[str, Any]],
        expected_token_count: int,
    ):
        """Test token count calculation for different message configurations."""
        with patch("core.utils.token_utils.tokens_from_string", return_value=1):
            result = cerebras_provider._compute_prompt_token_count(messages, Model.LLAMA_4_SCOUT_FAST)  # type: ignore[reportPrivateUsage]
            assert result == expected_token_count

    def test_max_tokens_error_handling(self, cerebras_provider: CerebrasProvider):
        """Test that 'Please reduce the length of the messages' error is handled as MaxTokensExceededError."""
        # Mock HTTP response with Cerebras error
        mock_response = Mock(spec=Response)
        mock_response.status_code = 400
        mock_response.text = '{"message": "Please reduce the length of the messages", "type": "invalid_request_error", "param": null, "code": null}'
        mock_response.headers = {}
        mock_response.request = Mock()
        mock_response.request.url = "https://api.cerebras.ai/v1/chat/completions"
        mock_response.request.method = "POST"

        # Test that the error is properly handled
        error = cerebras_provider._unknown_error(mock_response)  # type: ignore[reportPrivateUsage]
        assert isinstance(error, MaxTokensExceededError)
        assert "Please reduce the length of the messages" in str(error)

    def test_unknown_error_handling(self, cerebras_provider: CerebrasProvider):
        """Test that other errors are handled as UnknownProviderError."""
        # Mock HTTP response with unknown error
        mock_response = Mock(spec=Response)
        mock_response.status_code = 400
        mock_response.text = (
            '{"message": "Some other error", "type": "invalid_request_error", "param": null, "code": null}'
        )
        mock_response.headers = {}
        mock_response.request = Mock()
        mock_response.request.url = "https://api.cerebras.ai/v1/chat/completions"
        mock_response.request.method = "POST"

        # Test that the error is properly handled
        error = cerebras_provider._unknown_error(mock_response)  # type: ignore[reportPrivateUsage]
        assert isinstance(error, UnknownProviderError)
        assert "Some other error" in str(error)
