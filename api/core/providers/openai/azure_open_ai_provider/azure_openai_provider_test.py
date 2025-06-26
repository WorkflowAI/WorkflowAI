import json
import unittest
from collections.abc import Callable
from typing import Any, cast
from unittest.mock import patch

import pytest
from httpx import Response
from pytest_httpx import HTTPXMock, IteratorStream

from core.domain.fields.file import File
from core.domain.llm_usage import LLMUsage
from core.domain.message import MessageDeprecated
from core.domain.models import Model, Provider
from core.domain.structured_output import StructuredOutput
from core.providers.base.models import RawCompletion, StandardMessage
from core.providers.base.provider_error import (
    ContentModerationError,
    MaxTokensExceededError,
    ModelDoesNotSupportMode,
    ProviderBadRequestError,
    ProviderError,
    ProviderInternalError,
    StructuredGenerationError,
)
from core.providers.base.provider_options import ProviderOptions
from core.providers.openai.azure_open_ai_provider.azure_openai_provider import (
    _AZURE_API_REGION_METADATA_KEY,  # pyright: ignore [reportPrivateUsage]
    AzureOpenAIConfig,
    AzureOpenAIProvider,
)
from core.providers.openai.openai_domain import CompletionRequest
from core.runners.workflowai.utils import FileWithKeyPath
from tests.utils import fixture_bytes, fixtures_json


@pytest.fixture(scope="function")
def azure_openai_provider():
    return AzureOpenAIProvider()


def _output_factory(x: str, *args: Any, **kwargs: Any):
    return StructuredOutput(json.loads(x))


class TestValues(unittest.TestCase):
    def test_name(self):
        """Test the name method returns the correct Provider enum."""
        self.assertEqual(AzureOpenAIProvider.name(), Provider.AZURE_OPEN_AI)

    def test_required_env_vars(self):
        """Test the required_env_vars method returns the correct environment variables."""
        expected_vars = ["AZURE_OPENAI_CONFIG"]
        self.assertEqual(AzureOpenAIProvider.required_env_vars(), expected_vars)

    def test_supports_model(self):
        """Test the supports_model method returns True for a supported model
        and False for an unsupported model"""
        provider = AzureOpenAIProvider()
        self.assertTrue(provider.supports_model(Model.GPT_4O_2024_08_06))
        self.assertFalse(provider.supports_model(Model.CLAUDE_3_OPUS_20240229))


class TestRequestHeaders:
    async def test_request_headers_with_metadata(self, azure_openai_provider: AzureOpenAIProvider):
        # Setup provider with test config
        azure_openai_provider._config = AzureOpenAIConfig.model_validate(  # pyright: ignore [reportPrivateUsage]
            {
                "deployments": {
                    "eastus": {
                        "api_key": "test-key-eastus",
                        "url": "https://test-eastus.openai.azure.com",
                        "models": ["gpt-4o-2024-11-20"],
                    },
                    "westus": {
                        "api_key": "test-key-westus",
                        "url": "https://test-westus.openai.azure.com",
                        "models": ["gpt-4-turbo-2024-04-09"],
                    },
                },
            },
        )

        # Simulate _request_url setting the metadata

        headers = await azure_openai_provider._request_headers(  # pyright: ignore [reportPrivateUsage]
            request={},
            url="https://test-eastus.openai.azure.com",
            model=Model.GPT_4O_2024_11_20,
        )

        assert headers == {
            "Content-Type": "application/json",
            "api-key": "test-key-eastus",
        }


class TestBuildRequest:
    def test_build_request(self, azure_openai_provider: AzureOpenAIProvider):
        request = cast(
            CompletionRequest,
            azure_openai_provider._build_request(  # pyright: ignore [reportPrivateUsage]
                messages=[
                    MessageDeprecated(role=MessageDeprecated.Role.SYSTEM, content="Hello 1"),
                    MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello"),
                ],
                options=ProviderOptions(model=Model.GPT_4_TURBO_2024_04_09, max_tokens=10, temperature=0),
                stream=False,
            ),
        )
        # We can exclude None values because the HTTPxProvider does the same
        assert request.model_dump(include={"messages"}, exclude_none=True)["messages"] == [
            {
                "role": "system",
                "content": "Hello 1",
            },
            {
                "role": "user",
                "content": "Hello",
            },
        ]
        assert request.temperature == 0

    def test_build_request_no_system(self, azure_openai_provider: AzureOpenAIProvider):
        request = cast(
            CompletionRequest,
            azure_openai_provider._build_request(  # pyright: ignore [reportPrivateUsage]
                messages=[
                    MessageDeprecated(role=MessageDeprecated.Role.SYSTEM, content="Hello 1"),
                    MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello"),
                ],
                options=ProviderOptions(model=Model.O1_PREVIEW_2024_09_12, max_tokens=10, temperature=0),
                stream=False,
            ),
        )
        # We can exclude None values because the HTTPxProvider does the same
        assert request.model_dump(include={"messages"}, exclude_none=True)["messages"] == [
            {
                "role": "user",
                "content": "Hello 1",
            },
            {
                "role": "user",
                "content": "Hello",
            },
        ]
        assert request.temperature == 1.0

    def test_build_request_with_reasoing_effort_high(self, azure_openai_provider: AzureOpenAIProvider):
        request = cast(
            CompletionRequest,
            azure_openai_provider._build_request(  # pyright: ignore [reportPrivateUsage]
                messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.O1_2024_12_17_HIGH_REASONING_EFFORT, max_tokens=10, temperature=0),
                stream=False,
            ),
        )
        # We can exclude None values because the HTTPxProvider does the same
        assert request.model_dump(include={"messages", "reasoning_effort"}, exclude_none=True) == {
            "messages": [
                {
                    "role": "user",
                    "content": "Hello",
                },
            ],
            "reasoning_effort": "high",
        }

    def test_build_request_with_reasoing_effort_medium(self, azure_openai_provider: AzureOpenAIProvider):
        request = cast(
            CompletionRequest,
            azure_openai_provider._build_request(  # pyright: ignore [reportPrivateUsage]
                messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(
                    model=Model.O3_2025_04_16,
                    max_tokens=10,
                    temperature=0,
                ),
                stream=False,
            ),
        )
        # We can exclude None values because the HTTPxProvider does the same
        assert request.model_dump(include={"messages", "reasoning_effort"}, exclude_none=True) == {
            "messages": [
                {
                    "role": "user",
                    "content": "Hello",
                },
            ],
            "reasoning_effort": "medium",
        }

    def test_build_request_with_reasoing_effort_low(self, azure_openai_provider: AzureOpenAIProvider):
        request = cast(
            CompletionRequest,
            azure_openai_provider._build_request(  # pyright: ignore [reportPrivateUsage]
                messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.O1_2024_12_17_LOW_REASONING_EFFORT, max_tokens=10, temperature=0),
                stream=False,
            ),
        )
        # We can exclude None values because the HTTPxProvider does the same
        assert request.model_dump(include={"messages", "reasoning_effort"}, exclude_none=True) == {
            "messages": [
                {
                    "role": "user",
                    "content": "Hello",
                },
            ],
            "reasoning_effort": "low",
        }


def mock_azure_openai_stream(httpx_mock: HTTPXMock, model: str):
    httpx_mock.add_response(
        url=f"https://workflowai-azure-oai-staging-eastus.openai.azure.com/openai/deployments/{model}/chat/completions?api-version=2024-12-01-preview",
        stream=IteratorStream(
            [
                fixture_bytes("azure", "oai_stream_response.txt"),
            ],
        ),
    )


@pytest.fixture(autouse=True)
def patched_get_metadata():
    def get_metadata_side_effect(key: str) -> str | None:
        if key == _AZURE_API_REGION_METADATA_KEY:
            return "eastus"
        return None

    with patch(
        "core.providers.openai.azure_open_ai_provider.azure_openai_provider.AzureOpenAIProvider._get_metadata",
    ) as mock_get_metadata:
        mock_get_metadata.side_effect = get_metadata_side_effect
        yield


class TestSingleStream:
    async def test_stream_data(self, httpx_mock: HTTPXMock, azure_openai_provider: AzureOpenAIProvider):
        mock_azure_openai_stream(httpx_mock, "gpt-4o-2024-11-20")

        raw = RawCompletion(usage=LLMUsage(), response="")

        raw_chunks = azure_openai_provider._single_stream(  # pyright: ignore [reportPrivateUsage]
            request={"messages": [{"role": "user", "content": "Hello"}]},
            output_factory=_output_factory,
            partial_output_factory=StructuredOutput,
            raw_completion=raw,
            options=ProviderOptions(model=Model.GPT_4O_2024_11_20, max_tokens=10, temperature=0, output_schema={}),
        )

        parsed_chunks = [(chunk.output, chunk.tool_calls) async for chunk in raw_chunks]

        assert len(parsed_chunks) == 13

        expected_chunk: dict[str, Any] = {
            "summary": "Artificial intelligence (AI) has significantly impacted various industries.",
            "word_count": 91,
        }
        assert parsed_chunks[0][0] == expected_chunk
        assert parsed_chunks[1][0] == expected_chunk
        assert parsed_chunks[2][0] == expected_chunk
        assert len(httpx_mock.get_requests()) == 1

    async def test_max_message_length(self, httpx_mock: HTTPXMock, azure_openai_provider: AzureOpenAIProvider):
        httpx_mock.add_response(
            url="https://workflowai-azure-oai-staging-eastus.openai.azure.com/openai/deployments/gpt-4o-2024-11-20/chat/completions?api-version=2024-12-01-preview",
            status_code=400,
            json={"error": {"code": "string_above_max_length", "message": "The string is too long"}},
        )
        raw = RawCompletion(usage=LLMUsage(), response="")

        with pytest.raises(MaxTokensExceededError) as e:
            raw_chunks = azure_openai_provider._single_stream(  # pyright: ignore [reportPrivateUsage]
                request={"messages": [{"role": "user", "content": "Hello"}]},
                output_factory=_output_factory,
                partial_output_factory=StructuredOutput,
                raw_completion=raw,
                options=ProviderOptions(model=Model.GPT_4O_2024_11_20, max_tokens=10, temperature=0),
            )
            [chunk.output async for chunk in raw_chunks]
        assert e.value.store_task_run


class TestStream:
    # Tests overlap with single stream above but check the entire structure
    async def test_stream(self, httpx_mock: HTTPXMock, azure_openai_provider: AzureOpenAIProvider):
        mock_azure_openai_stream(httpx_mock, "gpt-4o-2024-11-20")

        streamer = azure_openai_provider.stream(
            [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.GPT_4O_2024_11_20, max_tokens=10, temperature=0, output_schema={}),
            output_factory=_output_factory,
            partial_output_factory=StructuredOutput,
        )
        chunks = [chunk async for chunk in streamer]
        assert len(chunks) == 13

        # Not sure why the pyright in the CI reports an error here
        request = httpx_mock.get_requests()[0]
        assert request.method == "POST"  # pyright: ignore reportUnknownMemberType
        body = json.loads(request.read().decode())
        assert body == {
            "max_completion_tokens": 10,
            "model": "gpt-4o-2024-11-20",
            "messages": [
                {
                    "content": "Hello",
                    "role": "user",
                },
            ],
            "response_format": {
                "type": "json_object",
            },
            "stream": True,
            "stream_options": {
                "include_usage": True,
            },
            "temperature": 0.0,
            # "store": True,
        }


class TestComplete:
    async def test_complete_content_moderation(self, httpx_mock: HTTPXMock, azure_openai_provider: AzureOpenAIProvider):
        httpx_mock.add_response(
            json=fixtures_json("azure", "content_moderation.json"),
            status_code=400,
        )

        with pytest.raises(ContentModerationError):
            await azure_openai_provider.complete(
                [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.GPT_4O_2024_11_20, max_tokens=10, temperature=0),
                output_factory=_output_factory,
            )

    # Tests overlap with single stream above but check the entire structure
    async def test_complete_images(self, httpx_mock: HTTPXMock, azure_openai_provider: AzureOpenAIProvider):
        httpx_mock.add_response(
            json=fixtures_json("azure", "response.json"),
        )

        chunk = await azure_openai_provider.complete(
            [
                MessageDeprecated(
                    role=MessageDeprecated.Role.USER,
                    content="Hello",
                    files=[
                        File(data="data", content_type="image/png"),
                    ],
                ),
            ],
            options=ProviderOptions(model=Model.GPT_4O_2024_11_20, max_tokens=10, temperature=0, output_schema={}),
            output_factory=_output_factory,
        )
        assert chunk.output
        assert chunk.tool_calls is None
        # Not sure why the pyright in the CI reports an error here
        request = httpx_mock.get_requests()[0]
        assert request.method == "POST"  # pyright: ignore reportUnknownMemberType
        body = json.loads(request.read().decode())
        assert body == {
            "max_completion_tokens": 10,
            "model": "gpt-4o-2024-11-20",
            "messages": [
                {
                    "content": [
                        {
                            "text": "Hello",
                            "type": "text",
                        },
                        {
                            "image_url": {
                                "url": "data:image/png;base64,data",
                            },
                            "type": "image_url",
                        },
                    ],
                    "role": "user",
                },
            ],
            "response_format": {
                "type": "json_object",
            },
            "stream": False,
            "temperature": 0.0,
        }

    async def test_complete_500(self, httpx_mock: HTTPXMock, azure_openai_provider: AzureOpenAIProvider):
        httpx_mock.add_response(
            url="https://workflowai-azure-oai-staging-eastus.openai.azure.com/openai/deployments/gpt-4o-2024-11-20/chat/completions?api-version=2024-12-01-preview",
            status_code=500,
            text="Internal Server Error",
        )

        with pytest.raises(ProviderInternalError) as e:
            await azure_openai_provider.complete(
                [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.GPT_4O_2024_11_20, max_tokens=10, temperature=0),
                output_factory=_output_factory,
            )

        details = e.value.error_response().error.details
        assert details and details.get("provider_error") == {"raw": "Internal Server Error"}

    async def test_complete_structured(self, httpx_mock: HTTPXMock, azure_openai_provider: AzureOpenAIProvider):
        httpx_mock.add_response(
            url="https://workflowai-azure-oai-staging-eastus.openai.azure.com/openai/deployments/gpt-4o-2024-11-20/chat/completions?api-version=2024-12-01-preview",
            json=fixtures_json("azure", "response.json"),
        )

        chunk = await azure_openai_provider.complete(
            [
                MessageDeprecated(
                    role=MessageDeprecated.Role.USER,
                    content="Hello",
                    files=[
                        File(data="data", content_type="image/png"),
                    ],
                ),
            ],
            options=ProviderOptions(
                model=Model.GPT_4O_2024_11_20,
                max_tokens=10,
                temperature=0,
                task_name="hello",
                structured_generation=True,
                output_schema={"type": "object"},
            ),
            output_factory=_output_factory,
        )
        assert chunk.output
        assert chunk.tool_calls is None

        # Not sure why the pyright in the CI reports an error here
        request = httpx_mock.get_requests()[0]
        assert request.method == "POST"  # pyright: ignore reportUnknownMemberType
        body = json.loads(request.read().decode())
        assert body == {
            "max_completion_tokens": 10,
            "model": "gpt-4o-2024-11-20",
            "messages": [
                {
                    "content": [
                        {
                            "text": "Hello",
                            "type": "text",
                        },
                        {
                            "image_url": {
                                "url": "data:image/png;base64,data",
                            },
                            "type": "image_url",
                        },
                    ],
                    "role": "user",
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "hello_01fc056eed58c88fe1c507fcd84dd4b7",
                    "strict": True,
                    "schema": {"type": "object"},
                },
            },
            "stream": False,
            "temperature": 0.0,
        }

    async def test_max_message_length(self, httpx_mock: HTTPXMock, azure_openai_provider: AzureOpenAIProvider):
        httpx_mock.add_response(
            url="https://workflowai-azure-oai-staging-eastus.openai.azure.com/openai/deployments/gpt-4o-2024-11-20/chat/completions?api-version=2024-12-01-preview",
            status_code=400,
            json={"error": {"code": "string_above_max_length", "message": "The string is too long"}},
        )

        with pytest.raises(MaxTokensExceededError) as e:
            await azure_openai_provider.complete(
                [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.GPT_4O_2024_11_20, max_tokens=10, temperature=0),
                output_factory=_output_factory,
            )

        assert e.value.store_task_run
        assert len(httpx_mock.get_requests()) == 1


class TestStandardizeMessages:
    def test_standardize_messages(self) -> None:
        # test is a little verbose for no reason since the standar messages are openai messages....
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What's in this image?"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/image1.jpg"}},
                ],
            },
            {"role": "assistant", "content": "The image shows a beautiful sunset over a beach."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Can you compare it with this one?"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/image2.jpg"}},
                ],
            },
            {"role": "assistant", "content": "The second image depicts a snowy mountain landscape."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Can you also compare it with transcription of this one?"},
                    {"type": "input_audio", "input_audio": {"data": "data", "format": "wav"}},
                ],
            },
        ]
        expected: list[StandardMessage] = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What's in this image?"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/image1.jpg"}},
                ],
            },
            {"role": "assistant", "content": "The image shows a beautiful sunset over a beach."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Can you compare it with this one?"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/image2.jpg"}},
                ],
            },
            {"role": "assistant", "content": "The second image depicts a snowy mountain landscape."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Can you also compare it with transcription of this one?"},
                    {"type": "audio_url", "audio_url": {"url": "data:audio/wav;base64,data"}},
                ],
            },
        ]
        assert AzureOpenAIProvider.standardize_messages(messages) == expected


class TestExtractStreamDelta:
    def test_extract_stream_delta(self, azure_openai_provider: AzureOpenAIProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        delta = azure_openai_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            b'{"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","usage": {"prompt_tokens": 35, "completion_tokens": 109, "total_tokens": 144},"choices":[{"index":0,"delta":{"content":"\\"greeting\\": \\"Hello James!\\"\\n}"},"logprobs":null,"finish_reason":null}]}',
            raw_completion,
            {},
        )
        assert delta.content == '"greeting": "Hello James!"\n}'
        assert raw_completion.usage == LLMUsage(prompt_token_count=35, completion_token_count=109)

    def test_done(self, azure_openai_provider: AzureOpenAIProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        delta = azure_openai_provider._extract_stream_delta(b"[DONE]", raw_completion, {})  # pyright: ignore[reportPrivateUsage]
        assert delta.content == ""


class TestRequiresDownloadingFile:
    @pytest.mark.parametrize(
        "file",
        (
            FileWithKeyPath(url="url", content_type="audio/wav", key_path=[]),
            FileWithKeyPath(url="url", content_type=None, format="audio", key_path=[]),
        ),
    )
    def test_requires_downloading_file(self, file: FileWithKeyPath):
        assert AzureOpenAIProvider.requires_downloading_file(file, Model.GPT_4O_MINI_2024_07_18)

    @pytest.mark.parametrize(
        "file",
        (
            FileWithKeyPath(url="url", content_type="image/png", key_path=[]),
            FileWithKeyPath(url="url", format="image", key_path=[]),
        ),
    )
    def test_does_not_require_downloading_file(self, file: FileWithKeyPath):
        assert not AzureOpenAIProvider.requires_downloading_file(file, Model.GPT_4O_MINI_2024_07_18)


class TestPrepareCompletion:
    async def test_role_before_content(self, azure_openai_provider: AzureOpenAIProvider):
        """Test that the 'role' key appears before 'content' in the prepared request."""
        request = cast(
            CompletionRequest,
            azure_openai_provider._build_request(  # pyright: ignore[reportPrivateUsage]
                messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.GPT_4O_2024_11_20, max_tokens=10, temperature=0),
                stream=False,
            ),
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


class TestUnknownError:
    @pytest.fixture
    def unknown_error_fn(self, azure_openai_provider: AzureOpenAIProvider):
        # Wrapper to avoid having to silence the private warning
        # and instantiate the response
        def _build_unknown_error(payload: str | dict[str, Any]):
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            res = Response(status_code=400, text=payload)
            return azure_openai_provider._unknown_error(res)  # pyright: ignore[reportPrivateUsage]

        return _build_unknown_error

    def test_max_tokens_error(self, unknown_error_fn: Callable[[dict[str, Any]], ProviderError]):
        payload = {
            "error": {
                "code": "string_above_max_length",
                "message": "bliblu",
                "param": None,
                "type": "invalid_request_error",
            },
        }
        assert isinstance(unknown_error_fn(payload), MaxTokensExceededError)

    def test_structured_generation(self, unknown_error_fn: Callable[[dict[str, Any]], ProviderError]):
        payload = {
            "error": {
                "code": "invalid_request_error",
                "message": "Invalid schema ",
                "param": "response_format",
                "type": "invalid_request_error",
            },
        }
        assert isinstance(unknown_error_fn(payload), StructuredGenerationError)

    def test_structured_generation_no_code(self, unknown_error_fn: Callable[[dict[str, Any]], ProviderError]):
        payload = {
            "error": {
                "code": None,
                "message": "Invalid parameter: 'response_format' of type 'json_schema' is not supported with this model. Learn more about supported models at the Structured Outputs guide: https://platform.openai.com/docs/guides/structured-outputs,",
                "param": None,
                "type": "invalid_request_error",
            },
        }
        assert isinstance(unknown_error_fn(payload), StructuredGenerationError)

    def test_invalid_image_url(self, unknown_error_fn: Callable[[dict[str, Any]], ProviderError]):
        payload = {
            "error": {
                "code": "invalid_image_url",
                "message": "Timeout while downloading https://workflowai.blob.core.windows.net/workflowai-task-runs/_pdf_to_images/ca7ff3932b091569a5fbcffc28c2186cc7fc1b1d806f75df27d849290e8ed1c7.jpg.",
                "param": None,
                "type": "invalid_request_error",
            },
        }
        assert isinstance(unknown_error_fn(payload), ProviderBadRequestError)

    def test_invalid_image_format(self, unknown_error_fn: Callable[[dict[str, Any]], ProviderError]):
        payload = {
            "error": {
                "code": "invalid_image_format",
                "message": "You uploaded an unsupported image. Please make sure your image has of one the following formats: ['png', 'jpeg', 'gif', 'webp'].",
                "param": None,
                "type": "invalid_request_error",
            },
        }
        e = unknown_error_fn(payload)
        assert isinstance(e, ProviderBadRequestError)
        assert not e.capture


class TestUnsupportedParameterError:
    async def test_tools_unsupported(self, azure_openai_provider: AzureOpenAIProvider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            status_code=400,
            json={
                "error": {
                    "code": "unsupported_parameter",
                    "message": "Unsupported parameter: 'tools' is not supported with this model.",
                    "param": "tools",
                    "type": "invalid_request_error",
                },
            },
        )
        with pytest.raises(ModelDoesNotSupportMode):
            await azure_openai_provider.complete(
                [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.GPT_4O_2024_11_20, max_tokens=10, temperature=0),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            )

    async def test_tools_unsupported_no_param(self, azure_openai_provider: AzureOpenAIProvider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            status_code=400,
            json={
                "error": {
                    "code": None,
                    "message": "tools is not supported in this model. For a list of supported models, refer to https://platform.openai.com/docs/guides/function-calling#models-supporting-function-calling.",
                    "param": None,
                    "type": "invalid_request_error",
                },
            },
        )
        with pytest.raises(ModelDoesNotSupportMode):
            await azure_openai_provider.complete(
                [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.GPT_4O_2024_11_20, max_tokens=10, temperature=0),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            )


class TestDefaultModel:
    def test_default_model_multiple_deployments(self, azure_openai_provider: AzureOpenAIProvider):
        # Setup provider with test config
        azure_openai_provider._config = AzureOpenAIConfig.model_validate(  # pyright: ignore [reportPrivateUsage]
            {
                "deployments": {
                    "eastus": {
                        "api_key": "test-key-eastus",
                        "url": "https://test-eastus.openai.azure.com",
                        "models": ["gpt-4o-2024-11-20"],
                    },
                    "westus": {
                        "api_key": "test-key-westus",
                        "url": "https://test-westus.openai.azure.com",
                        "models": ["gpt-4-turbo-2024-04-09"],
                    },
                },
            },
        )

        default_model = azure_openai_provider.default_model()
        assert default_model == Model.GPT_4O_2024_11_20
