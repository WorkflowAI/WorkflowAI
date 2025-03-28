import json
import unittest
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import BaseModel
from pytest_httpx import HTTPXMock, IteratorStream

from core.domain.errors import MaxTokensExceededError, ProviderInternalError
from core.domain.llm_completion import LLMCompletion
from core.domain.llm_usage import LLMUsage
from core.domain.message import Message
from core.domain.models import Model, Provider
from core.domain.models.model_provider_datas_mapping import GOOGLE_GEMINI_API_PROVIDER_DATA
from core.domain.structured_output import StructuredOutput
from core.providers.base.models import RawCompletion
from core.providers.base.provider_options import ProviderOptions
from core.providers.google.gemini.gemini_api_provider import GoogleGeminiAPIProvider, GoogleGeminiAPIProviderConfig
from core.providers.google.google_provider_domain import (
    Blob,
    CompletionRequest,
    GoogleMessage,
    GoogleSystemMessage,
    Part,
)
from core.runners.workflowai.utils import FileWithKeyPath
from tests.utils import fixtures_json, mock_aiter


@pytest.fixture(scope="module", autouse=True)
def patch_google_env_vars():
    with patch.dict(
        "os.environ",
        {"GEMINI_API_KEY": "worfklowai"},
    ):
        yield


@pytest.fixture
def gemini_provider():
    return GoogleGeminiAPIProvider()


@pytest.fixture()
def builder_context(gemini_provider: GoogleGeminiAPIProvider):
    class Context(BaseModel):
        id: str = ""
        llm_completions: list[LLMCompletion]
        config_id: str | None
        metadata: dict[str, Any] = {}

        def add_metadata(self, key: str, value: Any) -> None:
            self.metadata[key] = value

        def get_metadata(self, key: str) -> Any | None:
            return self.metadata.get(key)

    with patch.object(gemini_provider, "_builder_context") as mock_builder_context:
        ctx = Context(llm_completions=[], config_id=None)
        mock_builder_context.return_value = ctx
        yield ctx


class TestGeminiAPIProvider(unittest.TestCase):
    def test_request_url(self):
        provider = GoogleGeminiAPIProvider()
        assert "v1beta" in provider._request_url(Model.GEMINI_1_5_PRO_001, False)  # pyright: ignore [reportPrivateUsage]
        assert "v1alpha" not in provider._request_url(Model.GEMINI_1_5_FLASH_8B, False)  # pyright: ignore [reportPrivateUsage]
        assert "v1beta" in provider._request_url(Model.GEMINI_1_5_PRO_001, True)  # pyright: ignore [reportPrivateUsage]
        assert "v1alpha" in provider._request_url(Model.GEMINI_2_0_FLASH_THINKING_EXP_1219, False)  # pyright: ignore [reportPrivateUsage]
        assert "v1alpha" in provider._request_url(Model.GEMINI_2_0_FLASH_THINKING_EXP_1219, True)  # pyright: ignore [reportPrivateUsage]

    def test_name(self):
        """Test the name method returns the correct Provider enum."""
        self.assertEqual(GoogleGeminiAPIProvider.name(), Provider.GOOGLE_GEMINI)

    def test_required_env_vars(self):
        """Test the required_env_vars method returOpns the correct environment variables."""
        expected_vars = ["GEMINI_API_KEY"]
        self.assertEqual(GoogleGeminiAPIProvider.required_env_vars(), expected_vars)

    def test_supports_model(self):
        """Test the supports_model method returns True for a supported model
        and False for an unsupported model"""
        provider = GoogleGeminiAPIProvider()
        self.assertTrue(provider.supports_model(Model.GEMINI_1_5_FLASH_8B))
        self.assertTrue(provider.supports_model(Model.GEMINI_1_5_PRO_001))
        self.assertFalse(provider.supports_model(Model.GPT_3_5_TURBO_0125))

    async def test_default_config(self):
        """Test the _default_config method returns the correct configuration."""
        provider = GoogleGeminiAPIProvider()
        config = provider._default_config(0)  # pyright: ignore [reportPrivateUsage]

        self.assertIsInstance(config, GoogleGeminiAPIProviderConfig)
        self.assertEqual(config.api_key, "worfklowai")
        self.assertEqual(config.url, "https://generativelanguage.googleapis.com")


class PerTokenPricing(BaseModel):
    prompt_cost_per_token: float
    completion_cost_per_token: float


MODEL_PRICE_PER_TOKEN = {
    Model.GEMINI_1_5_PRO_001: PerTokenPricing(
        prompt_cost_per_token=1.25 / 1_000_000,
        completion_cost_per_token=5 / 1_000_000,
    ),
    Model.GEMINI_1_5_FLASH_001: PerTokenPricing(
        prompt_cost_per_token=0.075 / 1_000_000,
        completion_cost_per_token=0.30 / 1_000_000,
    ),
    Model.GEMINI_1_5_FLASH_002: PerTokenPricing(
        prompt_cost_per_token=0.075 / 1_000_000,
        completion_cost_per_token=0.30 / 1_000_000,
    ),
    Model.GEMINI_1_5_PRO_002: PerTokenPricing(
        prompt_cost_per_token=1.25 / 1_000_000,
        completion_cost_per_token=5 / 1_000_000,
    ),
    Model.GEMINI_1_5_FLASH_8B: PerTokenPricing(
        prompt_cost_per_token=0.0375 / 1_000_000,
        completion_cost_per_token=0.15 / 1_000_000,
    ),
    Model.GEMINI_EXP_1206: PerTokenPricing(prompt_cost_per_token=0.0, completion_cost_per_token=0.0),
}


def _llm_completion(**kwargs: Any) -> LLMCompletion:
    return LLMCompletion(
        provider=Provider.GOOGLE_GEMINI,
        **kwargs,
    )


class TestGoogleProviderPerTokenCostCalculation:
    # TODO: only use static values (instead of 'prompt_cost_per_token * 10' e.g), when the codebase will be more stable.

    @pytest.mark.parametrize("model", MODEL_PRICE_PER_TOKEN.keys())
    async def test_basic_case_from_initial_llm_usage(self, model: Model):
        system_message = GoogleSystemMessage(
            parts=[
                GoogleSystemMessage.Part(text="Hello !"),
                GoogleSystemMessage.Part(text="World !"),
            ],
        )

        user_messages = [
            GoogleMessage(
                role="user",
                parts=[
                    Part(text="Hello !"),
                    Part(text="World !"),
                ],
            ),
            GoogleMessage(
                role="user",
                parts=[
                    Part(text="Hello !"),
                    Part(text="World !"),
                ],
            ),
        ]

        model_per_token_pricing = MODEL_PRICE_PER_TOKEN[model]

        llm_usage = await GoogleGeminiAPIProvider().compute_llm_completion_usage(
            model=model,
            completion=_llm_completion(
                messages=[system_message.model_dump(), *[message.model_dump() for message in user_messages]],
                response="Hello you !",
                usage=LLMUsage(prompt_token_count=14, completion_token_count=20),
            ),
        )

        assert llm_usage.prompt_token_count == 14  # From the initial LLM usage
        assert llm_usage.prompt_cost_usd == 14 * model_per_token_pricing.prompt_cost_per_token

        assert llm_usage.completion_token_count == 20
        assert llm_usage.completion_cost_usd == 20 * model_per_token_pricing.completion_cost_per_token

    @pytest.mark.parametrize("model", MODEL_PRICE_PER_TOKEN.keys())
    async def test_basic_case_no_initial_llm_usage(self, model: Model):
        system_message = GoogleSystemMessage(
            parts=[GoogleSystemMessage.Part(text="Hello !"), GoogleSystemMessage.Part(text="World !")],
        )

        user_messages = [
            GoogleMessage(
                role="user",
                parts=[
                    Part(text="Hello !"),
                    Part(text="World !"),
                ],
            ),
            GoogleMessage(
                role="user",
                parts=[
                    Part(text="Hello !"),
                    Part(text="World !"),
                ],
            ),
        ]

        model_per_token_pricing = MODEL_PRICE_PER_TOKEN[model]

        llm_usage = await GoogleGeminiAPIProvider().compute_llm_completion_usage(
            model=model,
            completion=_llm_completion(
                messages=[system_message.model_dump(), *[message.model_dump() for message in user_messages]],
                response="Hello you !",
                usage=LLMUsage(),
            ),
        )

        assert llm_usage.prompt_token_count == 12
        assert llm_usage.prompt_cost_usd == 12 * model_per_token_pricing.prompt_cost_per_token

        assert llm_usage.completion_token_count == 3
        assert llm_usage.completion_cost_usd == 3 * model_per_token_pricing.completion_cost_per_token


class TestWrapSSE:
    async def test_vertex_ai(self):
        iter = mock_aiter(
            b"data: 1",
            b"2\n\ndata: 3\r\n\r\n",
        )

        wrapped = GoogleGeminiAPIProvider().wrap_sse(iter)
        chunks = [chunk async for chunk in wrapped]
        assert chunks == [b"12", b"3"]

    async def test_multiple_events_in_single_chunk(self):
        iter = mock_aiter(
            b"data: 1\n\ndata: 2\n\ndata: 3\r\n\r\n",
        )
        chunks = [chunk async for chunk in GoogleGeminiAPIProvider().wrap_sse(iter)]
        assert chunks == [b"1", b"2", b"3"]

    async def test_split_at_newline(self):
        # Test that we correctly handle when a split happens between the new line chars
        iter = mock_aiter(
            b"data: 1\n",
            b"\ndata: 2\r\n\r\n",
        )
        chunks = [chunk async for chunk in GoogleGeminiAPIProvider().wrap_sse(iter)]
        assert chunks == [b"1", b"2"]


def test_compute_prompt_token_count_per_char() -> None:
    system_message = GoogleSystemMessage(
        parts=[
            GoogleSystemMessage.Part(text="Hello !"),
            GoogleSystemMessage.Part(text="World !"),
        ],
    )

    user_messages = [
        GoogleMessage(
            role="user",
            parts=[
                Part(text="Hello !"),
                Part(text="World !", inlineData=Blob(mimeType="image/png", data="data")),
                Part(inlineData=Blob(mimeType="image/png", data="data")),
            ],
        ),
        GoogleMessage(
            role="user",
            parts=[
                Part(text="Hello !"),
                Part(text="World !"),
            ],
        ),
    ]

    raw_message = [system_message.model_dump(), *[message.model_dump() for message in user_messages]]

    token_count = GoogleGeminiAPIProvider()._compute_prompt_token_count(raw_message, Model.GEMINI_1_5_PRO_001)  # type: ignore

    assert token_count == 12


async def test_complete_500(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro-001:generateContent?key=worfklowai",
        status_code=500,
        text="Internal Server Error",
    )

    provider = GoogleGeminiAPIProvider(
        config=GoogleGeminiAPIProviderConfig(
            api_key="worfklowai",
            url="https://generativelanguage.googleapis.com",
        ),
    )

    with pytest.raises(ProviderInternalError) as e:
        await provider.complete(
            [Message(role=Message.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.GEMINI_1_5_PRO_001, max_tokens=10, temperature=0),
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
        )

    details = e.value.error_response().error.details
    assert details and details.get("provider_error") == {"raw": "Internal Server Error"}


async def test_complete_max_tokens(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro-001:generateContent?key=worfklowai",
        status_code=200,
        json=fixtures_json("gemini", "finish_reason_max_tokens_completion.json"),
    )

    provider = GoogleGeminiAPIProvider(
        config=GoogleGeminiAPIProviderConfig(
            api_key="worfklowai",
            url="https://generativelanguage.googleapis.com",
        ),
    )

    with pytest.raises(MaxTokensExceededError) as e:
        await provider.complete(
            [Message(role=Message.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.GEMINI_1_5_PRO_001, max_tokens=10, temperature=0),
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
        )

    assert e.value.code == "max_tokens_exceeded"
    assert (
        e.value.args[0]
        == "Model returned a MAX_TOKENS finish reason. The max number of tokens as specified in the request was reached."
    )


def test_extract_stream_delta_max_tokens():
    provider = GoogleGeminiAPIProvider()

    sse_event_max_tokens = json.dumps(
        {
            "candidates": [
                {"content": {"parts": [{"text": "Hello, world!"}], "role": "model"}},
                {"finishReason": "MAX_TOKENS"},
            ],
        },
    ).encode()
    with pytest.raises(MaxTokensExceededError) as e:
        provider._extract_stream_delta(sse_event_max_tokens, RawCompletion(response="", usage=LLMUsage()), {})  # pyright: ignore [reportPrivateUsage]

    assert (
        str(e.value)
        == "Model returned a MAX_TOKENS finish reason. The maximum number of tokens as specified in the request was reached."
    )


class TestPrepareCompletion:
    async def test_role_before_content(self, patch_google_env_vars: None) -> None:
        """Test that the 'role' key appears before 'content' in the prepared request."""
        provider = GoogleGeminiAPIProvider()
        request = provider._build_request(  # pyright: ignore[reportPrivateUsage]
            messages=[Message(role=Message.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.GEMINI_1_5_PRO_001, max_tokens=10, temperature=0),
            stream=False,
        )

        # Get the first message from the request
        message = request.model_dump()["contents"][0]

        # Get the actual order of keys in the message dictionary
        keys = list(message.keys())

        # Find the indices of 'role' and 'content' in the keys list
        role_index = keys.index("role")
        content_index = keys.index("parts")  # Gemini uses 'parts' instead of 'content'

        assert role_index < content_index, "The 'role' key must appear before the 'parts' key in the message dictionary"


class TestRequiresDownloadingFile:
    @pytest.mark.parametrize(
        "file",
        (
            FileWithKeyPath(url="url", content_type="audio/wav", key_path=[]),
            FileWithKeyPath(url="url", content_type=None, format="audio", key_path=[]),
            FileWithKeyPath(url="url", format="image", key_path=[]),  # no content type
        ),
    )
    def test_requires_downloading_file(self, file: FileWithKeyPath):
        assert GoogleGeminiAPIProvider.requires_downloading_file(file, Model.GEMINI_1_5_PRO_001)

    def test_requires_downloading_file_experimental_models(self):
        assert GoogleGeminiAPIProvider.requires_downloading_file(
            FileWithKeyPath(url="url", content_type="image/png", key_path=[]),
            Model.GEMINI_2_0_FLASH_THINKING_EXP_1219,
        )

        assert GoogleGeminiAPIProvider.requires_downloading_file(
            FileWithKeyPath(url="url", content_type="image/png", key_path=[]),
            Model.GEMINI_2_0_FLASH_THINKING_EXP_0121,
        )

        assert GoogleGeminiAPIProvider.requires_downloading_file(
            FileWithKeyPath(url="url", content_type="image/png", key_path=[]),
            Model.GEMINI_2_0_FLASH_001,
        )

        assert GoogleGeminiAPIProvider.requires_downloading_file(
            FileWithKeyPath(url="url", content_type="image/png", key_path=[]),
            Model.GEMINI_EXP_1206,
        )

    @pytest.mark.parametrize(
        "file",
        (FileWithKeyPath(url="url", content_type="image/png", key_path=[]),),
    )
    @pytest.mark.parametrize("model", GOOGLE_GEMINI_API_PROVIDER_DATA.keys())
    def test_require_downloading_file_all_models(self, file: FileWithKeyPath, model: Model):
        assert GoogleGeminiAPIProvider.requires_downloading_file(file, model)


class TestBuildRequest:
    def test_build_request_with_max_output_tokens(self, gemini_provider: GoogleGeminiAPIProvider):
        request = gemini_provider._build_request(  # pyright: ignore [reportPrivateUsage]
            messages=[Message(role=Message.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.GEMINI_1_5_PRO_001, max_tokens=10, temperature=0),
            stream=False,
        )
        assert isinstance(request, CompletionRequest)
        assert request.generationConfig.maxOutputTokens == 10

    def test_build_request_without_max_output_tokens(self, gemini_provider: GoogleGeminiAPIProvider):
        request = gemini_provider._build_request(  # pyright: ignore [reportPrivateUsage]
            messages=[Message(role=Message.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.GEMINI_1_5_PRO_001, temperature=0),
            stream=False,
        )

        assert isinstance(request, CompletionRequest)
        assert request.generationConfig.maxOutputTokens is None


class TestStream:
    async def test_stream_with_no_candidates(
        self,
        gemini_provider: GoogleGeminiAPIProvider,
        httpx_mock: HTTPXMock,
        builder_context: Any,
    ):
        """Check that we can handle when the last message has no candidates"""

        # Just mocking 2 chunks of data
        # 1 with candidates and the seconbd one with the usage
        httpx_mock.add_response(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro-001:streamGenerateContent?alt=sse&key=worfklowai",
            status_code=200,
            stream=IteratorStream(
                [
                    b"""data: {"candidates":[{"content":{"parts":[{"text":"{\\"hello\\": \\"world\\"}"}],"role":"model"}}]}\r\n\r\n""",
                    b"""data: {"usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 3}}\r\n\r\n""",
                ],
            ),
        )

        cs = [
            c
            async for c in gemini_provider.stream(
                messages=[Message(role=Message.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.GEMINI_1_5_PRO_001, max_tokens=10, temperature=0),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
                partial_output_factory=lambda x: StructuredOutput(x),
            )
        ]
        assert len(cs) == 2
        assert cs[-1].output == {"hello": "world"}

        # Here we just use the usageMetadata from the last chunk since the pricing is per token
        assert builder_context.llm_completions[0].usage.prompt_token_count == 10
