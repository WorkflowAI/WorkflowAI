import json
import unittest
from collections.abc import Callable
from typing import Any, cast

import pytest
from httpx import Response
from pytest_httpx import HTTPXMock, IteratorStream

from core.domain.fields.file import File
from core.domain.llm_usage import LLMUsage
from core.domain.message import MessageDeprecated
from core.domain.models import Model, Provider
from core.domain.structured_output import StructuredOutput
from core.providers.base.abstract_provider import RawCompletion
from core.providers.base.models import StandardMessage
from core.providers.base.provider_error import (
    ContentModerationError,
    FailedGenerationError,
    MaxTokensExceededError,
    ModelDoesNotSupportMode,
    ProviderBadRequestError,
    ProviderError,
    ProviderInternalError,
    StructuredGenerationError,
    UnknownProviderError,
)
from core.providers.base.provider_options import ProviderOptions
from core.providers.openai.openai_domain import CompletionRequest
from core.providers.openai.openai_provider import OpenAIConfig, OpenAIProvider
from core.runners.workflowai.utils import FileWithKeyPath
from tests.utils import fixture_bytes, fixtures_json


@pytest.fixture(scope="function")
def openai_provider():
    return OpenAIProvider(
        config=OpenAIConfig(api_key="test"),
    )


class TestValues(unittest.TestCase):
    def test_name(self):
        """Test the name method returns the correct Provider enum."""
        self.assertEqual(OpenAIProvider.name(), Provider.OPEN_AI)

    def test_required_env_vars(self):
        """Test the required_env_vars method returns the correct environment variables."""
        expected_vars = ["OPENAI_API_KEY"]
        self.assertEqual(OpenAIProvider.required_env_vars(), expected_vars)

    def test_supports_model(self):
        """Test the supports_model method returns True for a supported model
        and False for an unsupported model"""
        provider = OpenAIProvider()
        self.assertTrue(provider.supports_model(Model.GPT_4O_2024_11_20))
        self.assertFalse(provider.supports_model(Model.CLAUDE_3_OPUS_20240229))


class TestBuildRequest:
    def test_build_request(self, openai_provider: OpenAIProvider):
        request = openai_provider._build_request(  # pyright: ignore [reportPrivateUsage]
            messages=[
                MessageDeprecated(role=MessageDeprecated.Role.SYSTEM, content="Hello 1"),
                MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello"),
            ],
            options=ProviderOptions(model=Model.GPT_4O_2024_11_20, max_tokens=10, temperature=0),
            stream=False,
        )
        assert isinstance(request, CompletionRequest)
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
        assert request.max_completion_tokens == 10

    def test_build_request_without_max_tokens(self, openai_provider: OpenAIProvider):
        request = openai_provider._build_request(  # pyright: ignore [reportPrivateUsage]
            messages=[
                MessageDeprecated(role=MessageDeprecated.Role.SYSTEM, content="Hello 1"),
                MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello"),
            ],
            options=ProviderOptions(model=Model.GPT_4O_2024_11_20, temperature=0),
            stream=False,
        )
        assert isinstance(request, CompletionRequest)
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
        assert request.max_completion_tokens is None
        # model_data = get_model_data(Model.GPT_4O_2024_11_20)
        # if model_data.max_tokens_data.max_output_tokens:
        #     assert request.max_tokens == model_data.max_tokens_data.max_output_tokens
        # else:
        #     assert request.max_tokens == model_data.max_tokens_data.max_tokens

    def test_build_request_no_system(self, openai_provider: OpenAIProvider):
        request = cast(
            CompletionRequest,
            openai_provider._build_request(  # pyright: ignore [reportPrivateUsage]
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

    def test_build_request_with_reasoing_effort_high(self, openai_provider: OpenAIProvider):
        request = cast(
            CompletionRequest,
            openai_provider._build_request(  # pyright: ignore [reportPrivateUsage]
                messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(
                    model=Model.O1_2024_12_17_HIGH_REASONING_EFFORT,
                    max_tokens=10,
                    temperature=0,
                    output_schema={},
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
            "reasoning_effort": "high",
        }

    def test_build_request_with_reasoing_effort_medium(self, openai_provider: OpenAIProvider):
        request = cast(
            CompletionRequest,
            openai_provider._build_request(  # pyright: ignore [reportPrivateUsage]
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

    def test_build_request_with_reasoing_effort_low(self, openai_provider: OpenAIProvider):
        request = cast(
            CompletionRequest,
            openai_provider._build_request(  # pyright: ignore [reportPrivateUsage]
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

    def test_build_request_with_tool_choice_none(self, openai_provider: OpenAIProvider):
        request = cast(
            CompletionRequest,
            openai_provider._build_request(  # pyright: ignore [reportPrivateUsage]
                messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(
                    model=Model.GPT_4O_2024_11_20,
                    tool_choice="none",
                ),
                stream=False,
            ),
        )
        assert request.tool_choice == "none"

    def test_build_request_with_tool_choice_auto(self, openai_provider: OpenAIProvider):
        request = cast(
            CompletionRequest,
            openai_provider._build_request(  # pyright: ignore [reportPrivateUsage]
                messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(
                    model=Model.GPT_4O_2024_11_20,
                    tool_choice="auto",
                ),
                stream=False,
            ),
        )
        assert request.tool_choice == "auto"


def mock_openai_stream(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://api.openai.com/v1/chat/completions",
        stream=IteratorStream(
            [
                b'data: {"id":"1","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"role":"assistant","content":""},"logprobs":null,',
                b'"finish_reason":null}]}\n\ndata: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"content":"{\\n"},"logprobs":null,"finish_reason":null}]}\n\n',
                b'data: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"content":"\\"greeting\\": \\"Hello James!\\"\\n}"},"logprobs":null,"finish_reason":null}]}\n\n',
                b"data: [DONE]\n\n",
            ],
        ),
    )


class TestSingleStream:
    async def test_stream_data(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.openai.com/v1/chat/completions",
            stream=IteratorStream(
                [
                    b'data: {"id":"1","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"role":"assistant","content":""},"logprobs":null,',
                    b'"finish_reason":null}]}\n\ndata: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"content":"{\\n"},"logprobs":null,"finish_reason":null}]}\n\n',
                    b'data: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"content":"\\"greeting\\": \\"Hello James!\\"\\n}"},"logprobs":null,"finish_reason":null}]}\n\n',
                    b"data: [DONE]\n\n",
                ],
            ),
        )

        provider = OpenAIProvider()
        raw = RawCompletion(usage=LLMUsage(), response="")

        raw_chunks = provider._single_stream(  # pyright: ignore [reportPrivateUsage]
            request={"messages": [{"role": "user", "content": "Hello"}]},
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            partial_output_factory=lambda x: StructuredOutput(x),
            raw_completion=raw,
            options=ProviderOptions(model=Model.GPT_3_5_TURBO_1106, max_tokens=10, temperature=0, output_schema={}),
        )

        parsed_chunks = [o async for o in raw_chunks]

        assert len(parsed_chunks) == 2
        assert parsed_chunks[0][0] == {"greeting": "Hello James!"}
        assert parsed_chunks[1][0] == {"greeting": "Hello James!"}

        assert len(httpx_mock.get_requests()) == 1

    # TODO: check for usage and add tests for error handling

    async def test_stream_data_audios(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.openai.com/v1/chat/completions",
            stream=IteratorStream(
                [
                    b'data: {"id":"1","object":"chat.completion.chunk","created":1720404416,"model":"gpt-4o-audio-preview","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"role":"assistant","content":""},"logprobs":null,',
                    b'"finish_reason":null}]}\n\ndata: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-4o-audio-preview","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"content":"{\\n"},"logprobs":null,"finish_reason":null}]}\n\n',
                    b'data: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-4o-audio-preview","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"content":"\\"answer\\": \\"Oh it has 30 words!\\"\\n}"},"logprobs":null,"finish_reason":null}]}\n\n',
                    b"data: [DONE]\n\n",
                ],
            ),
        )

        provider = OpenAIProvider()
        raw = RawCompletion(usage=LLMUsage(), response="")

        raw_chunks = provider._single_stream(  # pyright: ignore [reportPrivateUsage]
            request={
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Can you reply to this audio?"},
                            {"type": "audio_url", "audio_url": {"url": "data:audio/wav;base64,data234avsrtgsd"}},
                        ],
                    },
                ],
            },
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            partial_output_factory=lambda x: StructuredOutput(x),
            raw_completion=raw,
            options=ProviderOptions(
                model=Model.GPT_41_2025_04_14,
                max_tokens=10,
                temperature=0,
                output_schema={},
            ),
        )

        parsed_chunks = [o async for o in raw_chunks]

        assert len(parsed_chunks) == 2
        assert parsed_chunks[0][0] == {"answer": "Oh it has 30 words!"}
        assert parsed_chunks[1][0] == {"answer": "Oh it has 30 words!"}

        assert len(httpx_mock.get_requests()) == 1

    async def test_max_message_length(self, httpx_mock: HTTPXMock, openai_provider: OpenAIProvider):
        httpx_mock.add_response(
            url="https://api.openai.com/v1/chat/completions",
            status_code=400,
            json={"error": {"code": "string_above_max_length", "message": "The string is too long"}},
        )
        raw = RawCompletion(usage=LLMUsage(), response="")

        with pytest.raises(MaxTokensExceededError) as e:
            raw_chunks = openai_provider._single_stream(  # pyright: ignore [reportPrivateUsage]
                request={"messages": [{"role": "user", "content": "Hello"}]},
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
                partial_output_factory=lambda x: StructuredOutput(x),
                raw_completion=raw,
                options=ProviderOptions(model=Model.GPT_41_2025_04_14, max_tokens=10, temperature=0),
            )
            [o async for o in raw_chunks]
        assert e.value.store_task_run is True

    async def test_invalid_json_schema(self, httpx_mock: HTTPXMock, openai_provider: OpenAIProvider):
        httpx_mock.add_response(
            url="https://api.openai.com/v1/chat/completions",
            status_code=400,
            json=fixtures_json("openai", "invalid_json_schema.json"),
        )

        raw = RawCompletion(usage=LLMUsage(), response="")

        with pytest.raises(StructuredGenerationError) as e:
            raw_chunks = openai_provider._single_stream(  # pyright: ignore [reportPrivateUsage]
                request={"messages": [{"role": "user", "content": "Hello"}]},
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
                partial_output_factory=lambda x: StructuredOutput(x),
                raw_completion=raw,
                options=ProviderOptions(model=Model.GPT_41_2025_04_14, max_tokens=10, temperature=0),
            )
            [o async for o in raw_chunks]
        assert e.value.store_task_run is True


class TestStream:
    # Tests overlap with single stream above but check the entire structure
    async def test_stream(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.openai.com/v1/chat/completions",
            stream=IteratorStream(
                [
                    b'data: {"id":"1","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"role":"assistant","content":""},"logprobs":null,',
                    b'"finish_reason":null}]}\n\ndata: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"content":"{\\n"},"logprobs":null,"finish_reason":null}]}\n\n',
                    b'data: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"content":"\\"greeting\\": \\"Hello James!\\"\\n}"},"logprobs":null,"finish_reason":null}]}\n\n',
                    b"data: [DONE]\n\n",
                ],
            ),
        )

        provider = OpenAIProvider()

        streamer = provider.stream(
            [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.GPT_3_5_TURBO_1106, max_tokens=10, temperature=0, output_schema={}),
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            partial_output_factory=lambda x: StructuredOutput(x),
        )
        chunks = [o async for o in streamer]
        assert len(chunks) == 2

        # Not sure why the pyright in the CI reports an error here
        request = httpx_mock.get_requests()[0]
        assert request.method == "POST"  # pyright: ignore reportUnknownMemberType
        body = json.loads(request.read().decode())
        assert body == {
            "max_completion_tokens": 10,
            "model": "gpt-3.5-turbo-1106",
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

    async def test_stream_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.openai.com/v1/chat/completions",
            status_code=400,
            json={"error": {"message": "blabla"}},
        )

        provider = OpenAIProvider()

        streamer = provider.stream(
            [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.GPT_3_5_TURBO_1106, max_tokens=10, temperature=0, output_schema={}),
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            partial_output_factory=lambda x: StructuredOutput(x),
        )
        # TODO: be stricter about what error is returned here
        with pytest.raises(UnknownProviderError) as e:
            [chunk async for chunk in streamer]

        assert e.value.capture
        assert str(e.value) == "blabla"

    async def test_stream_data_o1_preview(self, openai_provider: OpenAIProvider, httpx_mock: HTTPXMock):
        mock_openai_stream(httpx_mock)

        # Just checking that the o1 model actually stream
        streamer = openai_provider.stream(
            [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.O1_PREVIEW_2024_09_12, max_tokens=10, temperature=0, output_schema={}),
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            partial_output_factory=lambda x: StructuredOutput(x),
        )

        chunks = [o async for o in streamer]
        assert len(chunks) == 2


class TestComplete:
    # Tests overlap with single stream above but check the entire structure
    async def test_complete_images(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.openai.com/v1/chat/completions",
            json=fixtures_json("openai", "completion.json"),
        )

        provider = OpenAIProvider()

        o = await provider.complete(
            [
                MessageDeprecated(
                    role=MessageDeprecated.Role.USER,
                    content="Hello",
                    files=[
                        File(data="data", content_type="image/png"),
                    ],
                ),
            ],
            options=ProviderOptions(model=Model.GPT_3_5_TURBO_1106, max_tokens=10, temperature=0, output_schema={}),
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
        )
        assert o.output
        assert o.tool_calls is None
        # Not sure why the pyright in the CI reports an error here
        request = httpx_mock.get_requests()[0]
        assert request.method == "POST"  # pyright: ignore reportUnknownMemberType
        body = json.loads(request.read().decode())
        assert body == {
            "max_completion_tokens": 10,
            "model": "gpt-3.5-turbo-1106",
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
            # "store": True,
        }

    async def test_complete_audio(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.openai.com/v1/chat/completions",
            json=fixtures_json("openai", "completion.json"),
        )

        provider = OpenAIProvider()

        o = await provider.complete(
            [
                MessageDeprecated(
                    role=MessageDeprecated.Role.USER,
                    content="Hello",
                    files=[
                        File(data="data", content_type="audio/wav"),
                    ],
                ),
            ],
            options=ProviderOptions(model=Model.GPT_3_5_TURBO_1106, max_tokens=10, temperature=0, output_schema={}),
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
        )
        assert o.output
        assert o.tool_calls is None
        # Not sure why the pyright in the CI reports an error here
        request = httpx_mock.get_requests()[0]
        assert request.method == "POST"  # pyright: ignore reportUnknownMemberType
        body = json.loads(request.read().decode())
        assert body == {
            "max_completion_tokens": 10,
            "model": "gpt-3.5-turbo-1106",
            "messages": [
                {
                    "content": [
                        {
                            "text": "Hello",
                            "type": "text",
                        },
                        {
                            "input_audio": {
                                "data": "data",
                                "format": "wav",
                            },
                            "type": "input_audio",
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
            # "store": True,
        }

    async def test_complete_500(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.openai.com/v1/chat/completions",
            status_code=500,
            text="Internal Server Error",
        )

        provider = OpenAIProvider()

        with pytest.raises(ProviderInternalError) as e:
            await provider.complete(
                [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.GPT_3_5_TURBO_1106, max_tokens=10, temperature=0, output_schema={}),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            )

        details = e.value.error_response().error.details
        assert details and details.get("provider_error") == {"raw": "Internal Server Error"}

    async def test_complete_structured(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.openai.com/v1/chat/completions",
            json=fixtures_json("openai", "completion.json"),
        )
        provider = OpenAIProvider()

        o = await provider.complete(
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
                model=Model.GPT_4O_MINI_2024_07_18,
                max_tokens=10,
                temperature=0,
                task_name="hello",
                structured_generation=True,
                output_schema={"type": "object"},
            ),
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
        )
        assert o.output
        assert o.tool_calls is None

        # Not sure why the pyright in the CI reports an error here
        request = httpx_mock.get_requests()[0]
        assert request.method == "POST"  # pyright: ignore reportUnknownMemberType
        body = json.loads(request.read().decode())
        assert body == {
            "max_completion_tokens": 10,
            "model": "gpt-4o-mini-2024-07-18",
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

    async def test_complete_refusal(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.openai.com/v1/chat/completions",
            json=fixtures_json("openai", "refusal.json"),
        )
        provider = OpenAIProvider()
        with pytest.raises(ContentModerationError) as e:
            await provider.complete(
                [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.GPT_4O_2024_08_06, max_tokens=10, temperature=0, output_schema={}),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            )

        response = e.value.error_response()
        assert response.error.code == "content_moderation"
        assert response.error.status_code == 400
        assert response.error.message == "Model refused to generate a response: I'm sorry, I can't assist with that."

    async def test_complete_content_moderation(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.openai.com/v1/chat/completions",
            json=fixtures_json("openai", "content_moderation.json"),
            status_code=400,
        )

        provider = OpenAIProvider()
        with pytest.raises(ContentModerationError) as e:
            await provider.complete(
                [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.GPT_4O_2024_08_06, max_tokens=10, temperature=0),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            )

        response = e.value.error_response()
        assert response.error.code == "content_moderation"
        assert response.error.status_code == 400
        assert response.error.message.startswith("Invalid prompt: your prompt was flagged")

    async def test_complete_audio_refusal(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.openai.com/v1/chat/completions",
            json=fixtures_json("openai", "audio_refusal.json"),
            is_reusable=True,
        )

        provider = OpenAIProvider()

        with pytest.raises(FailedGenerationError) as e:
            await provider.complete(
                [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.GPT_4O_2024_08_06, max_tokens=10, temperature=0, output_schema={}),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            )

        response = e.value.error_response()
        assert response.error.code == "failed_generation"
        assert response.error.status_code == 400
        assert (
            response.error.message
            == "Model refused to generate a response: I'm sorry, but I can't analyze the tone of voice from audio files. I can help you with other tasks if you need."
        )

    async def test_max_message_length(self, httpx_mock: HTTPXMock, openai_provider: OpenAIProvider):
        httpx_mock.add_response(
            url="https://api.openai.com/v1/chat/completions",
            status_code=400,
            json={"error": {"code": "string_above_max_length", "message": "The string is too long"}},
        )

        with pytest.raises(MaxTokensExceededError) as e:
            await openai_provider.complete(
                [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.GPT_4O_2024_08_06, max_tokens=10, temperature=0),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            )

        assert e.value.store_task_run is True
        assert len(httpx_mock.get_requests()) == 1


class TestCheckValid:
    async def test_valid(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.openai.com/v1/chat/completions",
            json={
                "id": "chatcmpl-91gL0PXUwQajck2pIp284pR9o7yVo",
                "object": "chat.completion",
                "created": 1710188102,
                "model": "gpt-4",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "index": 0,
                        "message": {"role": "assistant", "content": "{}"},
                    },
                ],
                "usage": {"prompt_tokens": 35, "completion_tokens": 109, "total_tokens": 144},
                "system_fingerprint": "fp_8abb16fa4e",
            },
        )

        provider = OpenAIProvider()
        assert await provider.check_valid()

        request = httpx_mock.get_requests()[0]
        body = json.loads(request.read().decode())
        assert body["messages"] == [{"content": "Respond with an empty json", "role": "user"}]


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
        assert OpenAIProvider.standardize_messages(messages) == expected


class TestExtractStreamDelta:
    def test_extract_stream_delta(self, openai_provider: OpenAIProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        delta = openai_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            b'{"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","usage": {"prompt_tokens": 35, "completion_tokens": 109, "total_tokens": 144},"choices":[{"index":0,"delta":{"content":"\\"greeting\\": \\"Hello James!\\"\\n}"},"logprobs":null,"finish_reason":null}]}',
            raw_completion,
            {},
        )
        assert delta.content == '"greeting": "Hello James!"\n}'
        assert raw_completion.usage == LLMUsage(prompt_token_count=35, completion_token_count=109)

    def test_done(self, openai_provider: OpenAIProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        delta = openai_provider._extract_stream_delta(b"[DONE]", raw_completion, {})  # pyright: ignore[reportPrivateUsage]
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
        assert OpenAIProvider.requires_downloading_file(file, Model.GPT_4O_2024_11_20)

    @pytest.mark.parametrize(
        "file",
        (
            FileWithKeyPath(url="url", content_type="image/png", key_path=[]),
            FileWithKeyPath(url="url", format="image", key_path=[]),
        ),
    )
    def test_does_not_require_downloading_file(self, file: FileWithKeyPath):
        assert not OpenAIProvider.requires_downloading_file(file, Model.GPT_4O_2024_11_20)


class TestMaxTokensExceededError:
    async def test_max_tokens_exceeded_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.openai.com/v1/chat/completions",
            json=fixtures_json("openai", "finish_reason_length_completion.json"),
        )

        provider = OpenAIProvider()
        with pytest.raises(MaxTokensExceededError) as e:
            await provider.complete(
                [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.GPT_4O_2024_08_06, max_tokens=10, temperature=0),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            )
        assert (
            e.value.args[0]
            == "Model returned a response with a length finish reason, meaning the maximum number of tokens was exceeded."
        )
        assert e.value.store_task_run is True
        assert len(httpx_mock.get_requests()) == 1

    async def test_max_tokens_exceeded_error_stream(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.openai.com/v1/chat/completions",
            stream=IteratorStream(
                [
                    fixture_bytes("openai", "finish_reason_length_stream_completion.txt"),
                ],
            ),
        )
        provider = OpenAIProvider()
        with pytest.raises(MaxTokensExceededError) as e:
            async for _ in provider._single_stream(  # pyright: ignore reportPrivateUsage
                {"messages": [{"role": "user", "content": "Hello"}]},
                options=ProviderOptions(model=Model.GPT_4O_2024_08_06, max_tokens=10, temperature=0),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
                partial_output_factory=lambda x: StructuredOutput(x),
                raw_completion=RawCompletion(response="", usage=LLMUsage()),
            ):
                pass

        assert (
            e.value.args[0]
            == "Model returned a response with a length finish reason, meaning the maximum number of tokens was exceeded."
        )
        assert e.value.store_task_run is True
        assert len(httpx_mock.get_requests()) == 1


class TestUnsupportedParameterError:
    async def test_tools_unsupported(self, openai_provider: OpenAIProvider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.openai.com/v1/chat/completions",
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
            await openai_provider.complete(
                [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.GPT_4O_2024_08_06, max_tokens=10, temperature=0),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            )

    async def test_tools_unsupported_no_param(self, openai_provider: OpenAIProvider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.openai.com/v1/chat/completions",
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
            await openai_provider.complete(
                [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.GPT_4O_2024_08_06, max_tokens=10, temperature=0),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            )


class TestPrepareCompletion:
    async def test_role_before_content(self, openai_provider: OpenAIProvider):
        """Test that the 'role' key appears before 'content' in the prepared request."""
        request, _ = await openai_provider._prepare_completion(  # pyright: ignore[reportPrivateUsage]
            messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.GPT_3_5_TURBO_1106, max_tokens=10, temperature=0),
            stream=False,
        )

        # Get the first message from the request
        message = request["messages"][0]

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
    def unknown_error_fn(self, openai_provider: OpenAIProvider):
        # Wrapper to avoid having to silence the private warning
        # and instantiate the response
        def _build_unknown_error(payload: str | dict[str, Any]):
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            res = Response(status_code=400, text=payload)
            return openai_provider._unknown_error(res)  # pyright: ignore[reportPrivateUsage]

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

    def test_model_does_not_support_mode(self, unknown_error_fn: Callable[[dict[str, Any]], ProviderError]):
        payload = {
            "error": {
                "code": "invalid_value",
                "message": "This model requires that either input content or output modality contain audio.",
                "param": "model",
                "type": "invalid_request_error",
            },
        }
        assert isinstance(unknown_error_fn(payload), ModelDoesNotSupportMode)

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
