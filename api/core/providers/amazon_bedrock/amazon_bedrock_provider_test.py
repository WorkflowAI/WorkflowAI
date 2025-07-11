import json
import logging
import os
import unittest
from collections.abc import Callable
from typing import Any, Type, cast
from unittest.mock import Mock, patch

import pytest
from httpx import Response
from pydantic import BaseModel
from pytest_httpx import HTTPXMock

from core.domain.errors import (
    InternalError,
    UnpriceableRunError,
)
from core.domain.llm_completion import LLMCompletion
from core.domain.llm_usage import LLMUsage
from core.domain.message import MessageDeprecated
from core.domain.models import Model, Provider
from core.domain.models.model_provider_data_mapping import AMAZON_BEDROCK_PROVIDER_DATA
from core.domain.models.utils import get_model_provider_data
from core.domain.structured_output import StructuredOutput
from core.domain.task_run_reply import RunReply
from core.domain.tool import Tool
from core.domain.tool_call import ToolCallRequestWithID
from core.providers.amazon_bedrock.amazon_bedrock_domain import (
    AmazonBedrockMessage,
    AmazonBedrockSystemMessage,
    CompletionRequest,
    CompletionResponse,
    ContentBlock,
    Usage,
)
from core.providers.amazon_bedrock.amazon_bedrock_provider import (
    AmazonBedrockConfig,
    AmazonBedrockProvider,
)
from core.providers.base.models import RawCompletion
from core.providers.base.provider_error import (
    MaxTokensExceededError,
    ModelDoesNotSupportMode,
    ProviderBadRequestError,
    ProviderInternalError,
)
from core.providers.base.provider_options import ProviderOptions
from core.providers.base.streaming_context import ToolCallRequestBuffer
from core.runners.builder_context import builder_context
from tests.utils import fixtures_json, request_json_body


@pytest.fixture(scope="function")
def amazon_provider():
    with patch.dict(
        os.environ,
        {"AWS_BEDROCK_API_KEY": "test_api_key"},
    ):
        provider = AmazonBedrockProvider()
    provider.logger = Mock(spec=logging.Logger)
    return provider


class TestAmazonBedrockProvider(unittest.TestCase):
    def test_name(self):
        """Test the name method returns the correct Provider enum."""
        self.assertEqual(AmazonBedrockProvider.name(), Provider.AMAZON_BEDROCK)

    def test_required_env_vars(self):
        """Test the required_env_vars method returOpns the correct environment variables."""
        expected_vars = ["AWS_BEDROCK_API_KEY"]
        self.assertEqual(AmazonBedrockProvider.required_env_vars(), expected_vars)

    def test_supports_model(self):
        """Test the supports_model method returns True for a supported model
        and False for an unsupported model"""
        with patch.dict(
            "os.environ",
            {
                "AWS_BEDROCK_API_KEY": "test_api_key",
                "AWS_BEDROCK_MODEL_REGION_MAP": '{"claude-3-opus-20240229": "us-west-2"}',
            },
        ):
            provider = AmazonBedrockProvider()
        self.assertTrue(provider.supports_model(Model.CLAUDE_3_OPUS_20240229))
        self.assertFalse(provider.supports_model(Model.GPT_4O_2024_05_13))

    @patch.dict(
        "os.environ",
        {
            "AWS_BEDROCK_API_KEY": "test_api_key",
            "AWS_BEDROCK_MODEL_REGION_MAP": '{"claude-3-opus-20240229": "us-west-2", "claude-3-sonnet-20240229": "us-west-1"}',
        },
    )
    def test_default_config(self):
        """Test the _default_config method returns the correct configuration."""
        provider = AmazonBedrockProvider()
        config = provider._default_config(0)  # pyright: ignore [reportPrivateUsage]

        self.assertIsInstance(config, AmazonBedrockConfig)
        self.assertEqual(config.api_key, "test_api_key")
        self.assertEqual(
            config.available_model_x_region_map,
            {
                Model.CLAUDE_3_OPUS_20240229: "us-west-2",
                Model.CLAUDE_3_SONNET_20240229: "us-west-1",
            },
        )

    @patch.dict(
        "os.environ",
        {
            "AWS_BEDROCK_API_KEY": "test_api_key",
            "AWS_BEDROCK_MODEL_REGION_MAP": "not_json",
        },
        clear=True,
    )
    def test_default_config_raises_AmazonBedrockModelError_on_broken_json(self):
        provider = AmazonBedrockProvider()
        config = provider._default_config(0)  # pyright: ignore [reportPrivateUsage]
        assert config.available_model_x_region_map == {}
        assert config.default_region


class TestHandleStatusCode:
    @pytest.mark.parametrize(
        ("message", "expected"),
        [
            ("Input is too long for requested model.", "Input is too long for requested model."),
            (
                "The model returned the following errors: Prompt contains 248198 tokens and 0 draft tokens, too large for model with 131072 maximum context length",
                "Prompt contains 248198 tokens and 0 draft tokens, too large for model with 131072 maximum context length",
            ),
        ],
    )
    def test_max_tokens(self, amazon_provider: AmazonBedrockProvider, message: str, expected: str):
        # Test MaxTokensExceededError
        res = Response(status_code=424, text=f'{{"message": "{message}"}}')

        with pytest.raises(MaxTokensExceededError) as error:
            amazon_provider._handle_error_status_code(res)  # pyright: ignore [reportPrivateUsage]
        assert str(error.value) == expected

    def test_unknown_error(self, amazon_provider: AmazonBedrockProvider):
        # Test other errors
        res = Response(status_code=424, text='{"message": "Some other error"}')
        # We don't raise here, it will be passed to a provider unknown error handler
        amazon_provider._handle_error_status_code(res)  # pyright: ignore [reportPrivateUsage]

    def test_provider_internal_error(self, amazon_provider: AmazonBedrockProvider):
        # Test ProviderInternalError
        res = Response(status_code=424, text='{"message": "Unexpected error"}')
        with pytest.raises(ProviderInternalError):
            amazon_provider._handle_error_status_code(res)  # pyright: ignore [reportPrivateUsage]

    def test_image_too_big(self, amazon_provider: AmazonBedrockProvider):
        # Test ProviderBadRequestError
        res = Response(
            status_code=400,
            text='{"message": "The model returned the following errors: Image exceeds max pixels allowed."}',
        )
        with pytest.raises(ProviderBadRequestError) as error:
            amazon_provider._handle_error_status_code(res)  # pyright: ignore [reportPrivateUsage]
        assert str(error.value) == "Image exceeds max pixels allowed."

    def test_image_format_mismatch(self, amazon_provider: AmazonBedrockProvider):
        # Test ProviderBadRequestError
        res = Response(
            status_code=400,
            text='{"message": "The model returned the following errors: The provided image does not match the specified image format."}',
        )
        with pytest.raises(ProviderBadRequestError) as error:
            amazon_provider._handle_error_status_code(res)  # pyright: ignore [reportPrivateUsage]
        assert error.value.capture
        assert str(error.value) == "The provided image does not match the specified image format."

    def test_too_many_images_and_documents(self, amazon_provider: AmazonBedrockProvider):
        # Test ProviderBadRequestError
        res = Response(
            status_code=400,
            text='{"message":"The model returned the following errors: too many images and documents: 23 + 0 > 20"}',
        )
        with pytest.raises(ProviderBadRequestError) as error:
            amazon_provider._handle_error_status_code(res)  # pyright: ignore [reportPrivateUsage]
        assert not error.value.capture

    @pytest.mark.parametrize(
        "message",
        [
            "This model doesn't support tool use.",
            "This model does not support tool use.",
            "This model doesn't support tool use in streaming mode.",
        ],
    )
    def test_does_not_support_tool_use(self, amazon_provider: AmazonBedrockProvider, message: str):
        res = Response(status_code=400, text=f'{{"message": "{message}"}}')
        with pytest.raises(ModelDoesNotSupportMode) as error:
            amazon_provider._handle_error_status_code(res)  # pyright: ignore [reportPrivateUsage]
        assert error.value.capture


@pytest.mark.parametrize(
    "messages, expected_token_count",
    [
        (
            [{"role": "user", "content": [{"type": "text", "text": "Hello, world!"}]}],
            11,  # 3 (boilerplate) + 4 (per message) + 4 (content)
        ),
        (
            [
                {"role": "system", "text": "You are a helpful assistant."},
                {"role": "user", "content": [{"text": "What's the weather like?"}]},
            ],
            23,  # 3 (boilerplate) + 8 (4 tokens per message) + 5 (content) + 7 (content)
        ),
    ],
)
def test_compute_prompt_token_count(
    amazon_provider: AmazonBedrockProvider,
    messages: list[dict[str, Any]],
    expected_token_count: int,
):
    model = Model.CLAUDE_3_OPUS_20240229

    token_count = amazon_provider._compute_prompt_token_count(messages, model)  # pyright: ignore [reportPrivateUsage]

    assert token_count == expected_token_count, f"Token count should be {expected_token_count}"


@pytest.mark.parametrize(
    "messages",
    [
        (
            [
                {"role": "system", "text": "You are a helpful assistant."},
                {
                    "role": "user",
                    "content": [
                        {"text": "Describe this image:"},
                        {
                            "image": {
                                "format": "jpeg",
                                "source": {"bytes": b"...."},
                            },
                        },
                    ],
                },
                {"role": "user", "content": [{"text": "What colors do you see?"}]},
            ]
        ),
    ],
)
def test_compute_prompt_token_count_should_raise(
    amazon_provider: AmazonBedrockProvider,
    messages: list[dict[str, Any]],
):
    model = Model.CLAUDE_3_OPUS_20240229

    with pytest.raises(UnpriceableRunError):
        amazon_provider._compute_prompt_token_count(messages, model)  # pyright: ignore [reportPrivateUsage]


def _get_model_price(model: Model) -> tuple[float, float]:
    data = get_model_provider_data(Provider.AMAZON_BEDROCK, model)
    return data.text_price.prompt_cost_per_token, data.text_price.completion_cost_per_token


def _llm_completion(messages: list[dict[str, Any]], usage: LLMUsage, response: str | None = None):
    return LLMCompletion(
        messages=messages,
        usage=usage,
        response=response,
        provider=Provider.AMAZON_BEDROCK,
    )


class TestProviderCostCalculation:
    # TODO: only use static values (instead of 'prompt_cost_per_token * 10' e.g), when the codebase will be more stable.

    @pytest.mark.parametrize("model", AMAZON_BEDROCK_PROVIDER_DATA.keys())
    async def test_token_count_is_fed(self, amazon_provider: AmazonBedrockProvider, model: Model):
        # Test the case when both the prompt and completion token counts are fed in the original usage

        llm_usage = await amazon_provider.compute_llm_completion_usage(
            model=model,
            completion=_llm_completion(
                messages=[],
                usage=LLMUsage(prompt_token_count=10, completion_token_count=20),
                response="Hello",
            ),
        )

        model_price = _get_model_price(model)
        prompt_cost_per_token = model_price[0]
        completion_cost_per_token = model_price[1]

        assert llm_usage.prompt_token_count == 10  # from initial usage
        assert llm_usage.prompt_cost_usd == prompt_cost_per_token * 10
        assert llm_usage.completion_token_count == 20  # from initial usage
        assert llm_usage.completion_cost_usd == completion_cost_per_token * 20

    @pytest.mark.parametrize("model", AMAZON_BEDROCK_PROVIDER_DATA.keys())
    async def test_token_count_is_fed_with_no_response(self, amazon_provider: AmazonBedrockProvider, model: Model):
        # Test the case when both the prompt and completion token counts are fed in the original usage

        llm_usage = await amazon_provider.compute_llm_completion_usage(
            model=model,
            completion=_llm_completion(
                messages=[],
                usage=LLMUsage(prompt_token_count=10, completion_token_count=20),
                response=None,
            ),
        )
        assert llm_usage.cost_usd != 0

    @pytest.mark.parametrize("model", AMAZON_BEDROCK_PROVIDER_DATA.keys())
    async def test_token_count_is_fed_with_no_response_and_no_completion_token_count(
        self,
        amazon_provider: AmazonBedrockProvider,
        model: Model,
    ):
        # Test the case when both the prompt and completion token counts are fed in the original usage

        llm_usage = await amazon_provider.compute_llm_completion_usage(
            model=model,
            completion=_llm_completion(
                messages=[],
                usage=LLMUsage(prompt_token_count=10),
                response=None,
            ),
        )
        assert llm_usage.cost_usd == 0

    @pytest.mark.parametrize("model", AMAZON_BEDROCK_PROVIDER_DATA.keys())
    async def test_token_count_is_not_fed(self, amazon_provider: AmazonBedrockProvider, model: Model):
        # Test the case when the token count is not fed in the original usage

        llm_usage = await amazon_provider.compute_llm_completion_usage(
            model=model,
            completion=_llm_completion(
                messages=[{"role": "user", "content": [{"text": "Hello !"}]}],
                response="Hello you !",
                usage=LLMUsage(),
            ),
        )

        model_price = _get_model_price(model)
        prompt_cost_per_token = model_price[0]
        completion_cost_per_token = model_price[1]

        assert (
            llm_usage.prompt_token_count == 9
        )  # computed from the messages, 2 tokens + 7 "message boilerplate" tokens
        assert llm_usage.prompt_cost_usd == prompt_cost_per_token * 9  # 2 tokens + 7 "message boilerplate" tokens
        assert llm_usage.completion_token_count == 3  # computed from the completion
        assert llm_usage.completion_cost_usd == completion_cost_per_token * 3

    async def test_token_count_is_not_fed_with_no_response(self, amazon_provider: AmazonBedrockProvider):
        # Test the case when the token count is not fed in the original usage

        llm_usage = await amazon_provider.compute_llm_completion_usage(
            model=Model.CLAUDE_3_7_SONNET_20250219,
            completion=_llm_completion(
                messages=[{"role": "user", "content": [{"text": "Hello !"}]}],
                response=None,
                usage=LLMUsage(),
            ),
        )
        assert llm_usage.cost_usd == 0

    async def test_token_count_is_not_fed_multiple_messages_and_long_completion(
        self,
        amazon_provider: AmazonBedrockProvider,
    ):
        # Test the case when the token count is not fed in the original usage
        model = Model.CLAUDE_3_7_SONNET_20250219

        llm_usage = await amazon_provider.compute_llm_completion_usage(
            model=model,
            completion=_llm_completion(
                messages=[
                    {"role": "user", "content": [{"text": "Hello !"}]},
                    {"role": "user", "content": [{"text": "How are you !"}]},
                ],
                response="Hello " * 999 + ".",
                usage=LLMUsage(),
            ),
        )

        model_price = _get_model_price(model)
        prompt_cost_per_token = model_price[0]
        completion_cost_per_token = model_price[1]

        assert (
            llm_usage.prompt_token_count == 17
        )  # computed from the messages, 2 tokens + 4 tokens + 7 "boilerplate" tokens + 4 "boilerplate tokens"
        assert llm_usage.prompt_cost_usd == prompt_cost_per_token * 17
        assert llm_usage.completion_token_count == 1000  # computed from the completion, 999 hellos + 1 period
        assert llm_usage.completion_cost_usd == completion_cost_per_token * 1000

    @pytest.mark.parametrize("model", AMAZON_BEDROCK_PROVIDER_DATA.keys())
    async def test_token_count_is_not_fed_multiple_messages_and_long_completion_with_no_response(
        self,
        amazon_provider: AmazonBedrockProvider,
        model: Model,
    ):
        # Test the case when the token count is not fed in the original usage

        llm_usage = await amazon_provider.compute_llm_completion_usage(
            model=model,
            completion=_llm_completion(
                messages=[
                    {"role": "user", "content": [{"text": "Hello !"}]},
                    {"role": "user", "content": [{"text": "How are you !"}]},
                ],
                response=None,
                usage=LLMUsage(),
            ),
        )
        assert llm_usage.cost_usd == 0

    @pytest.mark.parametrize("model", AMAZON_BEDROCK_PROVIDER_DATA.keys())
    async def test_only_prompt_count_is_fed(self, amazon_provider: AmazonBedrockProvider, model: Model):
        # Test the case when the prompt token count is fed in the original usage but the completion token count is not

        llm_usage = await amazon_provider.compute_llm_completion_usage(
            model=model,
            completion=_llm_completion(
                messages=[{"role": "user", "content": [{"text": "Hello !"}]}],
                response="Hello you !",
                usage=LLMUsage(prompt_token_count=10),
            ),
        )

        model_price = _get_model_price(model)
        prompt_cost_per_token = model_price[0]
        completion_cost_per_token = model_price[1]

        assert llm_usage.prompt_token_count == 10  # from initial usage
        assert llm_usage.prompt_cost_usd == prompt_cost_per_token * 10
        assert llm_usage.completion_token_count == 3  # computed from the completion
        assert llm_usage.completion_cost_usd == completion_cost_per_token * 3

    @pytest.mark.parametrize("model", AMAZON_BEDROCK_PROVIDER_DATA.keys())
    async def test_only_completion_count_is_fed(self, amazon_provider: AmazonBedrockProvider, model: Model):
        # Test the case when the completion token count is fed in the original usage but the prompt token count is not

        llm_usage = await amazon_provider.compute_llm_completion_usage(
            model=model,
            completion=_llm_completion(
                messages=[{"role": "user", "content": [{"text": "Hello !"}]}],
                response="Hello you !",
                usage=LLMUsage(completion_token_count=20),
            ),
        )

        model_price = _get_model_price(model)
        prompt_cost_per_token = model_price[0]
        completion_cost_per_token = model_price[1]

        assert (
            llm_usage.prompt_token_count == 9
        )  # computed from the messages, 2 tokens + 7 "message boilerplate" tokens
        assert llm_usage.prompt_cost_usd == prompt_cost_per_token * 9
        assert llm_usage.completion_token_count == 20  # from initial usage
        assert llm_usage.completion_cost_usd == completion_cost_per_token * 20

    # TODO[max-tokens]: Add tests for max tokens

    def test_build_request(self):
        """Test the _build_request method constructs the correct CompletionRequest."""
        provider = AmazonBedrockProvider()
        messages = [
            MessageDeprecated(role=MessageDeprecated.Role.SYSTEM, content="System message"),
            MessageDeprecated(role=MessageDeprecated.Role.USER, content="User message"),
            MessageDeprecated(role=MessageDeprecated.Role.ASSISTANT, content="Assistant message"),
            MessageDeprecated(role=MessageDeprecated.Role.USER, content="User message 2"),
        ]
        options = ProviderOptions(model=Model.CLAUDE_3_5_SONNET_20240620, temperature=0.7, max_tokens=100)
        stream = False

        request = provider._build_request(messages, options, stream)  # pyright: ignore [reportPrivateUsage]

        assert type(request) is CompletionRequest
        assert request.inferenceConfig.maxTokens == 100
        assert request.messages == [
            AmazonBedrockMessage(content=[ContentBlock(text="User message")], role="user"),
            AmazonBedrockMessage(content=[ContentBlock(text="Assistant message")], role="assistant"),
            AmazonBedrockMessage(content=[ContentBlock(text="User message 2")], role="user"),
        ]
        assert request.system == [AmazonBedrockSystemMessage(text="System message")]

    def test_build_request_without_max_tokens(self):
        """Test the _build_request method constructs the correct CompletionRequest."""
        provider = AmazonBedrockProvider()
        messages = [
            MessageDeprecated(role=MessageDeprecated.Role.SYSTEM, content="System message"),
            MessageDeprecated(role=MessageDeprecated.Role.USER, content="User message"),
            MessageDeprecated(role=MessageDeprecated.Role.ASSISTANT, content="Assistant message"),
            MessageDeprecated(role=MessageDeprecated.Role.USER, content="User message 2"),
        ]
        options = ProviderOptions(model=Model.CLAUDE_3_5_SONNET_20240620, temperature=0.7)
        stream = False

        request = provider._build_request(messages, options, stream)  # pyright: ignore [reportPrivateUsage]

        # model_data = get_model_data(model)

        assert type(request) is CompletionRequest
        # TODO[max-tokens]: Add when we have e2e tests
        assert request.inferenceConfig.maxTokens is None
        # if model_data.max_tokens_data.max_output_tokens:
        #     assert request.inferenceConfig.maxTokens == model_data.max_tokens_data.max_output_tokens
        # elif model_data.max_tokens_data.max_tokens:
        #     assert request.inferenceConfig.maxTokens == model_data.max_tokens_data.max_tokens
        assert request.messages == [
            AmazonBedrockMessage(content=[ContentBlock(text="User message")], role="user"),
            AmazonBedrockMessage(content=[ContentBlock(text="Assistant message")], role="assistant"),
            AmazonBedrockMessage(content=[ContentBlock(text="User message 2")], role="user"),
        ]
        assert request.system == [AmazonBedrockSystemMessage(text="System message")]


def _url(model: str = "us.anthropic.claude-3-5-sonnet-20240620-v1:0", region: str = "us-west-2") -> str:
    return f"https://bedrock-runtime.{region}.amazonaws.com/model/{model}/converse"


async def test_complete_500(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=_url(),
        status_code=500,
        text="Internal Server Error",
    )

    provider = AmazonBedrockProvider()

    with pytest.raises(ProviderInternalError) as e:
        await provider.complete(
            [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.CLAUDE_3_5_SONNET_20240620, max_tokens=10, temperature=0),
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
        )

    details = e.value.error_response().error.details
    assert details and details.get("provider_error") == {"raw": "Internal Server Error"}


class TestStandardizeMessages:
    def test_standardize_messages(self):
        messages = [
            {"role": "user", "content": [{"text": "Hello"}]},
            {"role": "user", "content": [{"text": "World"}]},
        ]

        standardized_messages = AmazonBedrockProvider.standardize_messages(messages)
        assert standardized_messages == [
            {"role": "user", "content": "Hello"},
            {"role": "user", "content": "World"},
        ]

    def test_standardize_messages_with_image(self):
        messages = [
            {
                "role": "user",
                "content": [{"text": "Hello"}, {"image": {"format": "jpeg", "source": {"bytes": "...."}}}],
            },
        ]

        standardized_messages = AmazonBedrockProvider.standardize_messages(messages)
        assert standardized_messages == [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Hello"},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,...."}},
                ],
            },
        ]

    def test_message_with_system_message(self):
        messages = [
            {"text": "Your goal is to generate a valid output"},
            {"content": [{"text": "Input data"}], "role": "user"},
        ]

        standardized_messages = AmazonBedrockProvider.standardize_messages(messages)
        assert standardized_messages == [
            {"role": "system", "content": "Your goal is to generate a valid output"},
            {"role": "user", "content": "Input data"},
        ]


class TestExtractContentStr:
    def test_absent_json_does_not_raise(self, amazon_provider: AmazonBedrockProvider):
        # An absent JSON is caught upstream so this function should not raise
        response = CompletionResponse(
            output=CompletionResponse.Output(
                message=CompletionResponse.Output.Message(content=[ContentBlock(text="Hello")]),
            ),
            stopReason="stopReason",
            usage=Usage(inputTokens=1, outputTokens=1, totalTokens=1),
        )

        res = amazon_provider._extract_content_str(response)  # pyright: ignore [reportPrivateUsage]
        assert res == "Hello"
        amazon_provider.logger.warning.assert_not_called()  # type: ignore


@pytest.fixture(scope="function")
def output_factory() -> Callable[[str, bool], StructuredOutput]:
    return lambda x, _: StructuredOutput(json.loads(x))


class TestCompleteWithRetry:
    async def test_complete_with_retry(
        self,
        amazon_provider: AmazonBedrockProvider,
        httpx_mock: HTTPXMock,
        output_factory: Callable[[str, bool], StructuredOutput],
    ):
        # First response has an invalid json
        httpx_mock.add_response(
            url=_url(),
            status_code=200,
            json={
                "output": {"message": {"content": [{"type": "text", "text": "Hello"}]}},
                "stopReason": "stopReason",
                "usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 1},
            },
        )
        # Second response has a valid json
        httpx_mock.add_response(
            url=_url(),
            status_code=200,
            json={
                "output": {"message": {"content": [{"type": "text", "text": '{"text": "Hello"}'}]}},
                "stopReason": "stopReason",
                "usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 1},
            },
        )

        messages = [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")]
        options = ProviderOptions(model=Model.CLAUDE_3_5_SONNET_20240620, max_tokens=10, temperature=0)

        o = await amazon_provider.complete(messages, options, output_factory=output_factory)
        assert o.output == {"text": "Hello"}

        reqs = httpx_mock.get_requests()
        assert len(reqs) == 2

        first_body = request_json_body(reqs[0])
        assert first_body == {
            "inferenceConfig": {
                "maxTokens": 10,
                "temperature": 0.0,
            },
            "messages": [
                {
                    "content": [
                        {
                            "text": "Hello",
                        },
                    ],
                    "role": "user",
                },
            ],
            "system": [],
        }

        second_body = request_json_body(reqs[1])
        assert second_body == {
            "inferenceConfig": {
                "maxTokens": 10,
                "temperature": 0.0,
            },
            "messages": [
                {
                    "content": [
                        {
                            "text": "Hello",
                        },
                    ],
                    "role": "user",
                },
                {
                    "content": [
                        {
                            "text": "Hello",
                        },
                    ],
                    "role": "assistant",
                },
                {
                    "content": [
                        {
                            "text": "Your previous response was invalid with error `Model failed to generate a valid json`.\n"
                            "Please retry",
                        },
                    ],
                    "role": "user",
                },
            ],
            "system": [],
        }


@pytest.mark.parametrize("error_class", [UnpriceableRunError, InternalError, ValueError])
async def test_cost_is_set_to_0_if_error_occurs_in_usage_computation(
    error_class: Type[Exception],
    amazon_provider: AmazonBedrockProvider,
    httpx_mock: HTTPXMock,
    output_factory: Callable[[str, bool], StructuredOutput],
):
    class Context(BaseModel):
        id: str = ""
        llm_completions: list[LLMCompletion]
        config_id: str | None
        reply: RunReply | None = None

        def add_metadata(self, key: str, value: Any) -> None:
            pass

        def get_metadata(self, key: str) -> Any | None:
            return None

        def record_file_download_seconds(self, seconds: float) -> None:
            pass

    builder_context.set(
        Context(llm_completions=[], config_id=None),
    )

    httpx_mock.add_response(
        url=_url(),
        status_code=200,
        json={
            "output": {"message": {"content": [{"type": "text", "text": '{"text": "Hello"}'}]}},
            "stopReason": "stopReason",
            "usage": {"inputTokens": 0, "outputTokens": 200, "totalTokens": 0},
        },
    )

    messages = [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")]
    options = ProviderOptions(model=Model.CLAUDE_3_5_SONNET_20240620, max_tokens=10, temperature=0)

    with patch.object(amazon_provider, "_compute_llm_completion_cost") as mock_compute_llm_completion_usage:
        mock_compute_llm_completion_usage.side_effect = error_class("test")
        _ = await amazon_provider.complete(messages, options, output_factory=output_factory)
        _builder_context = builder_context.get()
        assert _builder_context is not None
        assert len(_builder_context.llm_completions) == 1
        assert _builder_context.llm_completions[0].usage.prompt_cost_usd is None  # check that cost is set to None
        assert _builder_context.llm_completions[0].usage.completion_cost_usd is None  # check that cost is set to None


class TestExtractStreamDelta:
    def test_extract_stream_delta(self, amazon_provider: AmazonBedrockProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        delta = amazon_provider._extract_stream_delta(  # pyright: ignore reportPrivateUsage
            b'{"usage":{"inputTokens":35,"outputTokens":109,"totalTokens":144},"delta":{"text":"hello"}}',
            raw_completion,
            {},
        )
        assert delta.content == "hello"
        assert raw_completion.usage == LLMUsage(prompt_token_count=35, completion_token_count=109)


class TestPrepareCompletion:
    async def test_role_before_content(self, amazon_provider: AmazonBedrockProvider):
        """Test that the 'role' key appears before 'content' in the prepared request."""
        request = amazon_provider._build_request(  # pyright: ignore[reportPrivateUsage]
            messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.CLAUDE_3_5_SONNET_20240620, max_tokens=10, temperature=0),
            stream=False,
        )

        # Get the first message from the request
        message = request.model_dump()["messages"][0]

        # Get the actual order of keys in the message dictionary
        keys = list(message.keys())

        # Find the indices of 'role' and 'content' in the keys list
        role_index = keys.index("role")
        content_index = keys.index("content")

        assert role_index < content_index, (
            "The 'role' key must appear before the 'content' key in the message dictionary"
        )


class TestStreamingWithTools:
    def test_extract_stream_delta_with_tool_start(self, amazon_provider: AmazonBedrockProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer] = {}

        # Test tool start event
        delta = amazon_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            b'{"contentBlockIndex": 1, "start": {"toolUse": {"name": "test_tool", "toolUseId": "test_id"}}}',
            raw_completion,
            tool_call_request_buffer,
        )

        assert delta.content == ""
        assert len(tool_call_request_buffer) == 1
        assert tool_call_request_buffer[1].id == "test_id"
        assert tool_call_request_buffer[1].tool_name == "test_tool"
        assert tool_call_request_buffer[1].tool_input == ""

    def test_extract_stream_delta_with_tool_use_input(self, amazon_provider: AmazonBedrockProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        tool_call_request_buffer = {
            1: ToolCallRequestBuffer(id="test_id", tool_name="test_tool", tool_input=""),
        }

        # Test tool use input event
        delta = amazon_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            b'{"contentBlockIndex": 1, "delta": {"toolUse": {"input": "{\\"param\\": \\""}}}',
            raw_completion,
            tool_call_request_buffer,
        )

        assert delta.content == ""
        assert tool_call_request_buffer[1].tool_input == '{"param": "'

        # Test complete JSON input
        delta = amazon_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            b'{"contentBlockIndex": 1, "delta": {"toolUse": {"input": "value\\"}"}}}',
            raw_completion,
            tool_call_request_buffer,
        )

        tool_calls = delta.tool_calls
        assert tool_calls is not None
        assert len(tool_calls) == 1
        assert tool_calls[0].id == "test_id"
        assert tool_calls[0].tool_name == "test_tool"  # Assuming native_tool_name_to_internal returns same name
        assert tool_calls[0].tool_input_dict == {"param": "value"}

    def test_extract_stream_delta_with_missing_content_block_index(self, amazon_provider: AmazonBedrockProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer] = {}

        with pytest.raises(ValueError, match="Can't parse tool call input without a content block index"):
            amazon_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
                b'{"start": {"toolUse": {"name": "test_tool", "toolUseId": "test_id"}}}',
                raw_completion,
                tool_call_request_buffer,
            )

    def test_extract_stream_delta_with_missing_buffer(self, amazon_provider: AmazonBedrockProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())

        with pytest.raises(ValueError, match="Can't find tool call request buffer for content block index 1"):
            amazon_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
                b'{"contentBlockIndex": 1, "delta": {"toolUse": {"input": "test"}}}',
                raw_completion,
                {},
            )

    def test_extract_stream_delta_with_invalid_content_block_index(self, amazon_provider: AmazonBedrockProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        tool_call_request_buffer = {
            2: ToolCallRequestBuffer(id="test_id", tool_name="test_tool", tool_input=""),
        }

        with pytest.raises(ValueError, match="Can't find tool call request buffer for content block index 1"):
            amazon_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
                b'{"contentBlockIndex": 1, "delta": {"toolUse": {"input": "test"}}}',
                raw_completion,
                tool_call_request_buffer,
            )


class TestNativeTools:
    def test_extract_native_tool_calls(self, amazon_provider: AmazonBedrockProvider):
        response = CompletionResponse(
            output=CompletionResponse.Output(
                message=CompletionResponse.Output.Message(
                    content=[
                        ContentBlock(
                            toolUse=ContentBlock.ToolUse(
                                toolUseId="test_id",
                                name="test_tool",
                                input={"param": "value"},
                            ),
                        ),
                    ],
                ),
            ),
            stopReason="stopReason",
            usage=Usage(inputTokens=1, outputTokens=1, totalTokens=1),
        )

        tool_calls = amazon_provider._extract_native_tool_calls(response)  # pyright: ignore[reportPrivateUsage]
        assert len(tool_calls) == 1
        assert tool_calls[0].id == "test_id"
        assert tool_calls[0].tool_name == "test_tool"  # Assuming native_tool_name_to_internal returns same name
        assert tool_calls[0].tool_input_dict == {"param": "value"}

    def test_extract_native_tool_calls_with_no_tools(self, amazon_provider: AmazonBedrockProvider):
        response = CompletionResponse(
            output=CompletionResponse.Output(
                message=CompletionResponse.Output.Message(
                    content=[
                        ContentBlock(text="Hello"),
                    ],
                ),
            ),
            stopReason="stopReason",
            usage=Usage(inputTokens=1, outputTokens=1, totalTokens=1),
        )

        tool_calls = amazon_provider._extract_native_tool_calls(response)  # pyright: ignore[reportPrivateUsage]
        assert len(tool_calls) == 0

    def test_build_request_with_tools(self, amazon_provider: AmazonBedrockProvider):
        messages = [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Use tool")]
        options = ProviderOptions(
            model=Model.CLAUDE_3_5_SONNET_20240620,
            temperature=0.7,
            enabled_tools=[
                Tool(
                    name="test_tool",
                    description="Test tool description",
                    input_schema={"type": "object", "properties": {"param": {"type": "string"}}},
                    output_schema={"type": "object"},
                ),
            ],
        )

        request = amazon_provider._build_request(messages, options, stream=False)  # pyright: ignore[reportPrivateUsage]
        assert isinstance(request, CompletionRequest)
        assert request.toolConfig is not None
        assert len(request.toolConfig.tools) == 1
        assert (
            request.toolConfig.tools[0].toolSpec.name == "test_tool"
        )  # Assuming internal_tool_name_to_native_tool_call returns same name
        assert request.toolConfig.tools[0].toolSpec.description == "Test tool description"
        assert request.toolConfig.tools[0].toolSpec.inputSchema.json_schema == {
            "type": "object",
            "properties": {"param": {"type": "string"}},
        }

    def test_build_request_with_empty_tool_description(self, amazon_provider: AmazonBedrockProvider):
        messages = [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Use tool")]
        options = ProviderOptions(
            model=Model.CLAUDE_3_5_SONNET_20240620,
            temperature=0.7,
            enabled_tools=[
                Tool(
                    name="test_tool",
                    description="",  # Empty description
                    input_schema={"type": "object"},
                    output_schema={"type": "object"},
                ),
            ],
        )

        request = amazon_provider._build_request(messages, options, stream=False)  # pyright: ignore[reportPrivateUsage]
        assert isinstance(request, CompletionRequest)
        assert request.toolConfig is not None
        assert request.toolConfig.tools[0].toolSpec.description is None


class TestStreamingWithToolsFixture:
    async def test_stream_with_tools(
        self,
        amazon_provider: AmazonBedrockProvider,
    ):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer] = {}
        tool_calls: list[ToolCallRequestWithID] = []
        content: str = ""

        fixture_data = fixtures_json("bedrock/bedrock_stream_with_tools.json")

        for sse in fixture_data["SSEs"]:
            delta = amazon_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
                json.dumps(sse).encode(),
                raw_completion,
                tool_call_request_buffer,
            )
            content += delta.content
            if delta.tool_calls:
                tool_calls.extend(delta.tool_calls)

        # Verify the content and tool calls
        assert content == "\n\nNow, I'll retrieve the weather information using the city code:"

        # Verify tool calls were correctly extracted
        assert tool_calls == [
            ToolCallRequestWithID(
                id="tooluse_BbrvqbWgQmyeB79TM7dDRA",
                tool_name="get_temperature",
                tool_input_dict={"city_code": "125321"},
            ),
            ToolCallRequestWithID(
                id="tooluse_Lh3H3N-FSQ2B6gW1LYaKXQ",
                tool_name="get_rain_probability",
                tool_input_dict={"city_code": "125321"},
            ),
            ToolCallRequestWithID(
                id="tooluse_e6nmRdHAQCO4-eQeZzI8bw",
                tool_name="get_wind_speed",
                tool_input_dict={"city_code": "125321"},
            ),
            ToolCallRequestWithID(
                id="tooluse_ojzBRrx5T6G1g1TZCfzFlA",
                tool_name="get_weather_conditions",
                tool_input_dict={"city_code": "125321"},
            ),
        ]

        # Verify usage metrics were captured
        assert raw_completion.usage == LLMUsage(
            prompt_token_count=1133,
            completion_token_count=130,
        )


class TestIsStreamable:
    @pytest.mark.parametrize(
        "model, enabled_tools, expected_result",
        [
            # Case 1: Model that supports streaming without tools
            (Model.CLAUDE_3_SONNET_20240229, None, True),
            # Case 2: Model that supports streaming with tools
            (
                Model.CLAUDE_3_SONNET_20240229,
                [
                    Tool(
                        name="test_tool",
                        description="Test tool",
                        input_schema={"type": "object", "properties": {}},
                        output_schema={"type": "object", "properties": {}},
                    ),
                ],
                True,
            ),
            # Case 3: Model from _NON_STREAMING_WITH_TOOLS_MODELS with tools
            (
                Model.MISTRAL_LARGE_2_2407,
                [
                    Tool(
                        name="test_tool",
                        description="Test tool",
                        input_schema={"type": "object", "properties": {}},
                        output_schema={"type": "object", "properties": {}},
                    ),
                ],
                False,
            ),
            # Case 4: Model from _NON_STREAMING_WITH_TOOLS_MODELS without tools
            (Model.MISTRAL_LARGE_2_2407, None, True),
            # Case 5: Model from _NON_STREAMING_WITH_TOOLS_MODELS with empty tools list
            (Model.MISTRAL_LARGE_2_2407, [], True),
        ],
    )
    def test_is_streamable(
        self,
        amazon_provider: AmazonBedrockProvider,
        model: Model,
        enabled_tools: list[Tool] | None,
        expected_result: bool,
    ) -> None:
        result = amazon_provider.is_streamable(model, enabled_tools)
        assert result is expected_result


class TestExtractReasoningSteps:
    def test_extract_reasoning_steps_with_thinking_content(self, amazon_provider: AmazonBedrockProvider):
        """Test extraction of reasoning steps from thinking content blocks."""
        response = CompletionResponse(
            stopReason="end_turn",
            output=CompletionResponse.Output(
                message=CompletionResponse.Output.Message(
                    role="assistant",
                    content=[
                        ContentBlock(text="Here's my response."),
                        ContentBlock(
                            thinking=ContentBlock.ThinkingContent(
                                thinking="Let me think about this step by step...",
                                signature="sig_123",
                            ),
                        ),
                        ContentBlock(
                            thinking=ContentBlock.ThinkingContent(
                                thinking="Now I need to consider another approach...",
                            ),
                        ),
                    ],
                ),
            ),
            usage=Usage(inputTokens=100, outputTokens=50),
        )

        reasoning_steps = amazon_provider._extract_reasoning_steps(response)  # pyright: ignore[reportPrivateUsage]

        assert reasoning_steps is not None
        assert len(reasoning_steps) == 2
        assert reasoning_steps[0].explaination == "Let me think about this step by step..."
        assert reasoning_steps[1].explaination == "Now I need to consider another approach..."

    def test_extract_reasoning_steps_without_thinking_content(self, amazon_provider: AmazonBedrockProvider):
        """Test extraction when there are no thinking content blocks."""
        response = CompletionResponse(
            stopReason="end_turn",
            output=CompletionResponse.Output(
                message=CompletionResponse.Output.Message(
                    role="assistant",
                    content=[
                        ContentBlock(text="Here's my response."),
                        ContentBlock(
                            toolUse=ContentBlock.ToolUse(
                                toolUseId="tool_123",
                                name="test_tool",
                                input={"param": "value"},
                            ),
                        ),
                    ],
                ),
            ),
            usage=Usage(inputTokens=100, outputTokens=50),
        )

        reasoning_steps = amazon_provider._extract_reasoning_steps(response)  # pyright: ignore[reportPrivateUsage]

        assert reasoning_steps is None

    def test_extract_reasoning_steps_empty_content(self, amazon_provider: AmazonBedrockProvider):
        """Test extraction with empty content list."""
        response = CompletionResponse(
            stopReason="end_turn",
            output=CompletionResponse.Output(
                message=CompletionResponse.Output.Message(
                    role="assistant",
                    content=[],
                ),
            ),
            usage=Usage(inputTokens=100, outputTokens=50),
        )

        reasoning_steps = amazon_provider._extract_reasoning_steps(response)  # pyright: ignore[reportPrivateUsage]

        assert reasoning_steps is None


class TestBuildRequestWithThinking:
    def test_build_request_with_thinking_budget(self, amazon_provider: AmazonBedrockProvider):
        """Test that thinking budget is properly configured in requests."""
        from core.domain.models.model_data import ModelReasoningBudget
        from core.domain.models.utils import get_model_data
        from core.providers.base.provider_options import ProviderOptions

        model = Model.CLAUDE_3_5_SONNET_20240620
        model_data = get_model_data(model)

        # Mock the model data to have reasoning capabilities
        original_reasoning = model_data.reasoning
        model_data.reasoning = ModelReasoningBudget(disabled=None, low=500, medium=1000, high=2000, min=500, max=2000)

        try:
            # Create options with reasoning budget
            options = ProviderOptions(
                model=model,
                max_tokens=1000,
                reasoning_budget=500,
            )

            request = cast(
                CompletionRequest,
                amazon_provider._build_request(  # pyright: ignore[reportPrivateUsage]
                    messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                    options=options,
                    stream=False,
                ),
            )

            # Check that thinking is configured
            assert request.additionalModelRequestFields is not None
            assert request.additionalModelRequestFields.thinking is not None
            assert request.additionalModelRequestFields.thinking.type == "enabled"
            assert request.additionalModelRequestFields.thinking.budget_tokens == 500

            # Check that max_tokens includes the thinking budget
            assert request.inferenceConfig.maxTokens == 1000 + 500

        finally:
            # Restore original reasoning value
            model_data.reasoning = original_reasoning

    def test_build_request_without_thinking_budget(self, amazon_provider: AmazonBedrockProvider):
        """Test that no thinking configuration is added when reasoning budget is not set."""
        options = ProviderOptions(
            model=Model.CLAUDE_3_5_SONNET_20240620,
            max_tokens=1000,
        )

        request = cast(
            CompletionRequest,
            amazon_provider._build_request(  # pyright: ignore[reportPrivateUsage]
                messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=options,
                stream=False,
            ),
        )

        # Check that thinking is not configured
        assert request.additionalModelRequestFields is None

        # Check that max_tokens is not modified by thinking budget
        assert request.inferenceConfig.maxTokens == 1000


class TestThinkingStreamingDeltas:
    def test_extract_stream_delta_with_thinking(self, amazon_provider: AmazonBedrockProvider):
        """Test handling of thinking deltas in streaming."""
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer] = {}

        # Test thinking delta
        delta = amazon_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            b'{"contentBlockIndex": 0, "delta": {"reasoningContent": {"text": "I need to analyze this request..."}}}',
            raw_completion,
            tool_call_request_buffer,
        )

        assert delta.content == ""
        assert delta.reasoning_steps == "I need to analyze this request..."
        assert delta.tool_calls == []

    def test_extract_stream_delta_with_reasoning_content(self, amazon_provider: AmazonBedrockProvider):
        """Test handling of reasoningContent deltas in streaming."""
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer] = {}

        # Test reasoningContent delta
        delta = amazon_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            b'{"contentBlockIndex": 0, "delta": {"reasoningContent": {"text": "I need to analyze this request..."}}}',
            raw_completion,
            tool_call_request_buffer,
        )

        assert delta.content == ""
        assert delta.reasoning_steps == "I need to analyze this request..."
        assert delta.tool_calls == []

    def test_extract_stream_delta_with_text_and_thinking(self, amazon_provider: AmazonBedrockProvider):
        """Test handling of mixed text and thinking deltas."""
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer] = {}

        # Test text delta
        text_delta = amazon_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            b'{"contentBlockIndex": 0, "delta": {"text": "Here is my response: "}}',
            raw_completion,
            tool_call_request_buffer,
        )

        assert text_delta.content == "Here is my response: "
        assert text_delta.reasoning_steps is None
        assert text_delta.tool_calls == []

        # Test thinking delta
        thinking_delta = amazon_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            b'{"contentBlockIndex": 1, "delta": {"reasoningContent": {"text": "Let me verify this approach..."}}}',
            raw_completion,
            tool_call_request_buffer,
        )

        assert thinking_delta.content == ""
        assert thinking_delta.reasoning_steps == "Let me verify this approach..."
        assert thinking_delta.tool_calls == []

    def test_extract_stream_delta_without_thinking(self, amazon_provider: AmazonBedrockProvider):
        """Test normal streaming without thinking deltas."""
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer] = {}

        # Test regular text delta
        delta = amazon_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            b'{"delta": {"text": "Normal response text"}}',
            raw_completion,
            tool_call_request_buffer,
        )

        assert delta.content == "Normal response text"
        assert delta.reasoning_steps is None
        assert delta.tool_calls == []

    def test_stream_thinking_aggregation(self, amazon_provider: AmazonBedrockProvider):
        """Test aggregation of multiple thinking deltas."""
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer] = {}

        # Simulate multiple thinking delta events
        thinking_events = [
            b'{"contentBlockIndex": 0, "delta": {"reasoningContent": {"text": "First, I need to understand the problem..."}}}',
            b'{"contentBlockIndex": 0, "delta": {"reasoningContent": {"text": "Now I should consider the constraints..."}}}',
            b'{"contentBlockIndex": 0, "delta": {"reasoningContent": {"text": "Finally, let me formulate the solution..."}}}',
        ]

        reasoning_content = ""
        for event in thinking_events:
            delta = amazon_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
                event,
                raw_completion,
                tool_call_request_buffer,
            )

            if delta.reasoning_steps:
                reasoning_content += delta.reasoning_steps

        expected_content = (
            "First, I need to understand the problem..."
            "Now I should consider the constraints..."
            "Finally, let me formulate the solution..."
        )
        assert reasoning_content == expected_content


class TestUsageWithThinking:
    def test_extract_stream_delta_with_usage_and_thinking(self, amazon_provider: AmazonBedrockProvider):
        """Test that usage metrics are correctly extracted alongside thinking deltas."""
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer] = {}

        # Test delta with both usage and thinking
        delta = amazon_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            b'{"usage": {"inputTokens": 150, "outputTokens": 200, "totalTokens": 350}, "delta": {"reasoningContent": {"text": "Processing request..."}}}',
            raw_completion,
            tool_call_request_buffer,
        )

        assert delta.content == ""
        assert delta.reasoning_steps == "Processing request..."
        assert raw_completion.usage == LLMUsage(prompt_token_count=150, completion_token_count=200)
