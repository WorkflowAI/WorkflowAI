import json
import os
import unittest
from typing import Any, cast
from unittest.mock import Mock, patch

import pytest
from httpx import Response
from pytest_httpx import HTTPXMock, IteratorStream

from core.domain.errors import (
    MaxTokensExceededError,
    ProviderInternalError,
    UnknownProviderError,
)
from core.domain.fields.file import File
from core.domain.fields.internal_reasoning_steps import InternalReasoningStep
from core.domain.llm_usage import LLMUsage
from core.domain.message import Message
from core.domain.metrics import Metric
from core.domain.models import Model, Provider
from core.domain.models.model_data import FinalModelData, MaxTokensData
from core.domain.structured_output import StructuredOutput
from core.domain.tool import Tool
from core.domain.tool_call import ToolCallRequestWithID
from core.providers.base.abstract_provider import RawCompletion
from core.providers.base.httpx_provider import ParsedResponse
from core.providers.base.models import StandardMessage
from core.providers.base.provider_options import ProviderOptions
from core.providers.base.streaming_context import ToolCallRequestBuffer
from core.providers.fireworks.fireworks_domain import (
    Choice,
    ChoiceMessage,
    CompletionRequest,
    CompletionResponse,
    FireworksToolCall,
    FireworksToolCallFunction,
    Usage,
)
from core.providers.fireworks.fireworks_provider import FireworksAIProvider, FireworksConfig
from core.runners.workflowai.utils import FileWithKeyPath
from tests.utils import fixture_bytes, fixtures_json


@pytest.fixture(scope="session")
def patch_fireworks_env_vars():
    with patch.dict(
        "os.environ",
        {
            "FIREWORKS_API_KEY": "worfklowai",
            "FIREWORKS_API_URL": "https://api.fireworks.ai/inference/v1/chat/completions",
        },
    ):
        yield


@pytest.fixture(scope="function")
def fireworks_provider():
    provider = FireworksAIProvider(
        config=FireworksConfig(
            provider=Provider.FIREWORKS,
            api_key=os.getenv("FIREWORKS_API_KEY", "test"),
            url=os.getenv("FIREWORKS_API_URL", "https://api.fireworks.ai/inference/v1/chat/completions"),
        ),
    )
    # Clearing the context
    provider._thinking_tag_context.set(None)  # pyright: ignore [reportPrivateUsage]
    return provider


class TestValues(unittest.TestCase):
    def test_name(self):
        """Test the name method returns the correct Provider enum."""
        self.assertEqual(FireworksAIProvider.name(), Provider.FIREWORKS)

    def test_required_env_vars(self):
        """Test the required_env_vars method returns the correct environment variables."""
        expected_vars = ["FIREWORKS_API_KEY"]
        self.assertEqual(FireworksAIProvider.required_env_vars(), expected_vars)

    def test_supports_model(self):
        """Test the supports_model method returns True for a supported model
        and False for an unsupported model"""
        provider = FireworksAIProvider()
        self.assertTrue(provider.supports_model(Model.LLAMA_3_3_70B))
        self.assertFalse(provider.supports_model(Model.CLAUDE_3_OPUS_20240229))


class TestBuildRequest:
    def test_build_request(self, fireworks_provider: FireworksAIProvider):
        request = cast(
            CompletionRequest,
            fireworks_provider._build_request(  # pyright: ignore [reportPrivateUsage]
                messages=[
                    Message(role=Message.Role.SYSTEM, content="Hello 1"),
                    Message(role=Message.Role.USER, content="Hello"),
                ],
                options=ProviderOptions(model=Model.LLAMA_3_3_70B, max_tokens=10, temperature=0),
                stream=False,
            ),
        )
        # The HTTPx provider does not include None values in the request body, so we need to exclude them
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
        assert request.max_tokens == 10

    # TODO[max-tokens]: Re-add test

    def test_build_request_with_max_output_tokens(self, fireworks_provider: FireworksAIProvider):
        request = cast(
            CompletionRequest,
            fireworks_provider._build_request(  # pyright: ignore [reportPrivateUsage]
                messages=[
                    Message(role=Message.Role.SYSTEM, content="Hello 1"),
                    Message(role=Message.Role.USER, content="Hello"),
                ],
                options=ProviderOptions(model=Model.LLAMA_3_3_70B, temperature=0),
                stream=False,
            ),
        )
        # The HTTPx provider does not include None values in the request body, so we need to exclude them
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
        assert request.max_tokens is not None
        # TODO[max-tokens]: Re-add test
        # if model_data.max_tokens_data.max_output_tokens:
        #     assert request.max_tokens == model_data.max_tokens_data.max_output_tokens
        # elif model_data.max_tokens_data.max_tokens:
        #     assert request.max_tokens == model_data.max_tokens_data.max_tokens


def mock_fireworks_stream(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://api.fireworks.ai/inference/v1/chat/completions",
        stream=IteratorStream(
            [
                fixture_bytes("fireworks", "stream_data_with_usage.txt"),
            ],
        ),
    )


class TestSingleStream:
    @patch("core.providers.fireworks.fireworks_provider.get_model_data")
    async def test_stream_data(self, get_model_data_mock: Mock, httpx_mock: HTTPXMock):
        get_model_data_mock.return_value = FinalModelData.model_construct(
            max_tokens_data=MaxTokensData(max_output_tokens=1234, max_tokens=1235, source=""),
        )
        httpx_mock.add_response(
            url="https://api.fireworks.ai/inference/v1/chat/completions",
            stream=IteratorStream([fixture_bytes("fireworks", "stream_data_with_usage.txt")]),
        )

        provider = FireworksAIProvider()
        raw = RawCompletion(usage=LLMUsage(), response="")

        raw_chunks = provider._single_stream(  # pyright: ignore [reportPrivateUsage]
            request={"messages": [{"role": "user", "content": "Hello"}]},
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            partial_output_factory=lambda x: StructuredOutput(x),
            raw_completion=raw,
            options=ProviderOptions(model=Model.LLAMA_3_3_70B, max_tokens=10, temperature=0),
        )

        parsed_chunks = [o async for o in raw_chunks]

        assert len(parsed_chunks) == 2
        assert parsed_chunks[0][0] == {"foo": "bar"}
        assert parsed_chunks[1][0] == {"foo": "bar"}

        req = httpx_mock.get_request(url="https://api.fireworks.ai/inference/v1/chat/completions")
        assert req

    async def test_max_message_length(self, httpx_mock: HTTPXMock, fireworks_provider: FireworksAIProvider):
        httpx_mock.add_response(
            url="https://api.fireworks.ai/inference/v1/chat/completions",
            status_code=400,
            json={"error": {"code": "string_above_max_length", "message": "The string is too long"}},
        )
        raw = RawCompletion(usage=LLMUsage(), response="")

        with pytest.raises(MaxTokensExceededError) as e:
            raw_chunks = fireworks_provider._single_stream(  # pyright: ignore [reportPrivateUsage]
                request={"messages": [{"role": "user", "content": "Hello"}]},
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
                partial_output_factory=lambda x: StructuredOutput(x),
                raw_completion=raw,
                options=ProviderOptions(model=Model.LLAMA_3_3_70B, max_tokens=10, temperature=0),
            )
            [o async for o in raw_chunks]
        assert e.value.store_task_run is False

    async def test_context_length_exceeded(self, httpx_mock: HTTPXMock, fireworks_provider: FireworksAIProvider):
        """Test the full loop when streaming that we raise an error on context_length_exceeded"""
        httpx_mock.add_response(
            url="https://api.fireworks.ai/inference/v1/chat/completions",
            status_code=400,
            json={"error": {"code": "context_length_exceeded", "message": "Max token exceeded"}},
        )
        raw = RawCompletion(usage=LLMUsage(), response="")

        with pytest.raises(MaxTokensExceededError) as e:
            raw_chunks = fireworks_provider._single_stream(  # pyright: ignore [reportPrivateUsage]
                request={"messages": [{"role": "user", "content": "Hello"}]},
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
                partial_output_factory=lambda x: StructuredOutput(x),
                raw_completion=raw,
                options=ProviderOptions(model=Model.LLAMA_3_3_70B, max_tokens=10, temperature=0),
            )
            [o async for o in raw_chunks]
        assert e.value.store_task_run is False


class TestStream:
    # Tests overlap with single stream above but check the entire structure
    @patch("core.providers.fireworks.fireworks_provider.get_model_data")
    async def test_stream(self, get_model_data_mock: Mock, httpx_mock: HTTPXMock):
        get_model_data_mock.return_value = FinalModelData.model_construct(
            max_tokens_data=MaxTokensData(max_output_tokens=1234, max_tokens=1235, source=""),
            supports_structured_output=True,
        )
        httpx_mock.add_response(
            url="https://api.fireworks.ai/inference/v1/chat/completions",
            stream=IteratorStream(
                [
                    fixture_bytes("fireworks", "stream_data_with_usage.txt"),
                ],
            ),
        )

        provider = FireworksAIProvider()

        streamer = provider.stream(
            [Message(role=Message.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.DEEPSEEK_V3_0324, temperature=0),
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            partial_output_factory=lambda x: StructuredOutput(x),
        )
        chunks = [chunk async for chunk in streamer]
        assert len(chunks) == 2

        # Not sure why the pyright in the CI reports an error here
        request = httpx_mock.get_requests()[0]
        assert request.method == "POST"  # pyright: ignore reportUnknownMemberType
        body = json.loads(request.read().decode())
        assert body == {
            "context_length_exceeded_behavior": "truncate",
            "max_tokens": 1234,
            "model": "accounts/fireworks/models/deepseek-v3-0324",
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
            "temperature": 0.0,
        }

    async def test_stream_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.fireworks.ai/inference/v1/chat/completions",
            status_code=400,
            json={"error": {"message": "blabla"}},
        )

        provider = FireworksAIProvider()

        streamer = provider.stream(
            [Message(role=Message.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.LLAMA_3_3_70B, max_tokens=10, temperature=0),
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            partial_output_factory=lambda x: StructuredOutput(x),
        )
        with pytest.raises(UnknownProviderError) as e:
            [chunk async for chunk in streamer]

        assert e.value.capture
        assert str(e.value) == "blabla"


class TestComplete:
    # Tests overlap with single stream above but check the entire structure
    async def test_complete_images(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.fireworks.ai/inference/v1/chat/completions",
            json=fixtures_json("fireworks", "completion.json"),
        )

        provider = FireworksAIProvider()

        o = await provider.complete(
            [
                Message(
                    role=Message.Role.USER,
                    content="Hello",
                    files=[
                        File(data="data", content_type="image/png"),
                    ],
                ),
            ],
            options=ProviderOptions(model=Model.LLAMA_3_2_90B_VISION_PREVIEW, max_tokens=10, temperature=0),
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
        )
        assert o.output
        assert o.tool_calls is None
        # Not sure why the pyright in the CI reports an error here
        request = httpx_mock.get_requests()[0]
        assert request.method == "POST"  # pyright: ignore reportUnknownMemberType
        body = json.loads(request.read().decode())
        assert body == {
            "context_length_exceeded_behavior": "truncate",
            "max_tokens": 10,
            "model": "accounts/fireworks/models/llama-v3p2-90b-vision-instruct",
            "messages": [
                {
                    "content": [
                        {
                            "text": "Hello",
                            "type": "text",
                        },
                        {
                            "image_url": {
                                "url": "data:image/png;base64,data#transform=inline",
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

    async def test_complete_500(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.fireworks.ai/inference/v1/chat/completions",
            status_code=500,
            text="Internal Server Error",
        )

        provider = FireworksAIProvider()

        with pytest.raises(ProviderInternalError) as e:
            await provider.complete(
                [Message(role=Message.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.LLAMA_3_3_70B, max_tokens=10, temperature=0),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            )

        details = e.value.error_response().error.details
        assert details and details.get("provider_error") == {"raw": "Internal Server Error"}

    async def test_complete_structured(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.fireworks.ai/inference/v1/chat/completions",
            json=fixtures_json("fireworks", "completion.json"),
        )
        provider = FireworksAIProvider()

        o = await provider.complete(
            [
                Message(
                    role=Message.Role.USER,
                    content="Hello",
                    files=[
                        File(data="data", content_type="image/png"),
                    ],
                ),
            ],
            options=ProviderOptions(
                model=Model.LLAMA_3_3_70B,
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

        request = httpx_mock.get_requests()[0]
        assert request.method == "POST"  # pyright: ignore reportUnknownMemberType
        body = json.loads(request.read().decode())
        assert body == {
            "context_length_exceeded_behavior": "truncate",
            "max_tokens": 10,
            "model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
            "messages": [
                {
                    "content": [
                        {
                            "text": "Hello",
                            "type": "text",
                        },
                        {
                            "image_url": {
                                "url": "data:image/png;base64,data#transform=inline",
                            },
                            "type": "image_url",
                        },
                    ],
                    "role": "user",
                },
            ],
            "response_format": {
                "type": "json_object",
                "schema": {"type": "object"},
            },
            "stream": False,
            "temperature": 0.0,
        }

    @patch("core.providers.fireworks.fireworks_provider.get_model_data")
    @pytest.mark.parametrize(
        ("max_output_tokens", "option_max_tokens", "expected"),
        [(None, None, 1234), (1235, None, 1235), (1235, 1236, 1236)],
    )
    async def test_complete_with_max_tokens(
        self,
        get_model_data_mock: Mock,
        httpx_mock: HTTPXMock,
        fireworks_provider: FireworksAIProvider,
        max_output_tokens: int | None,
        option_max_tokens: int | None,
        expected: int,
    ):
        """Check that the max tokens is correctly set in the request based on the model data, by order of priority
        - option_max_tokens
        - model data max_output_tokens
        - model data max_tokens
        Also check that we send "truncate".
        This test covers streaming and non streaming requests since the build request is called in the same way.
        """
        get_model_data_mock.return_value = FinalModelData.model_construct(
            max_tokens_data=MaxTokensData(max_output_tokens=max_output_tokens, max_tokens=1234, source=""),
        )

        httpx_mock.add_response(
            url="https://api.fireworks.ai/inference/v1/chat/completions",
            json=fixtures_json("fireworks", "completion.json"),
        )

        o = await fireworks_provider.complete(
            [
                Message(
                    role=Message.Role.USER,
                    content="Hello",
                    files=[
                        File(data="data", content_type="image/png"),
                    ],
                ),
            ],
            options=ProviderOptions(
                model=Model.LLAMA_3_3_70B,
                max_tokens=option_max_tokens,
                temperature=0,
                task_name="hello",
                structured_generation=True,
                output_schema={"type": "object"},
            ),
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
        )
        assert o.output

        request = httpx_mock.get_requests()[0]
        assert request and request.method == "POST"
        body = json.loads(request.read().decode())
        assert body["context_length_exceeded_behavior"] == "truncate"
        assert body["max_tokens"] == expected


class TestCheckValid:
    async def test_valid(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.fireworks.ai/inference/v1/chat/completions",
            json={
                "id": "chatcmpl-91gL0PXUwQajck2pIp284pR9o7yVo",
                "object": "chat.completion",
                "created": 1710188102,
                "model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
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

        provider = FireworksAIProvider()
        assert await provider.check_valid()

        request = httpx_mock.get_requests()[0]
        body = json.loads(request.read().decode())
        assert body["messages"] == [{"content": "Respond with an empty json", "role": "user"}]


class TestStandardizeMessages:
    def test_standardize_messages(self) -> None:
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
        ]
        assert FireworksAIProvider.standardize_messages(messages) == expected

    def test_standardize_messages_with_tool_messages(self) -> None:
        """Test standardization of messages including tool messages."""
        messages = [
            {
                "role": "user",
                "content": "Hello",
            },
            {
                "role": "tool",
                "tool_call_id": "test_tool",
                "content": {"arg1": "value1"},
            },
            {
                "role": "tool",
                "tool_call_id": "test_tool_2",
                "content": {"arg2": "value2"},
            },
        ]

        result = FireworksAIProvider.standardize_messages(messages)  # pyright: ignore[reportPrivateUsage]

        assert result == [
            {"role": "user", "content": "Hello"},
            {
                "role": "user",
                "content": [
                    {
                        "id": "test_tool",
                        "type": "tool_call_result",
                        "tool_name": "",
                        "tool_input_dict": None,
                        "result": {"result": {"arg1": "value1"}},
                        "error": None,
                    },
                    {
                        "id": "test_tool_2",
                        "type": "tool_call_result",
                        "tool_name": "",
                        "tool_input_dict": None,
                        "result": {"result": {"arg2": "value2"}},
                        "error": None,
                    },
                ],
            },
        ]

    def test_standardize_messages_empty_list(self) -> None:
        """Test standardization of an empty message list."""
        messages: list[dict[str, Any]] = []

        result = FireworksAIProvider.standardize_messages(messages)  # pyright: ignore[reportPrivateUsage]

        assert len(result) == 0

    def test_standardize_messages_with_consecutive_tool_messages(self) -> None:
        """Test standardization of consecutive tool messages are grouped together."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "tool", "tool_call_id": "test_tool", "content": {"arg1": "value1"}},
            {"role": "tool", "tool_call_id": "test_tool_2", "content": {"arg2": "value2"}},
            {"role": "assistant", "content": "Processing results..."},
            {"role": "tool", "tool_call_id": "test_tool_3", "content": {"arg3": "value3"}},
            {"role": "tool", "tool_call_id": "test_tool_4", "content": {"arg4": "value4"}},
        ]

        result = FireworksAIProvider.standardize_messages(messages)  # pyright: ignore[reportPrivateUsage]

        assert result == [
            {"role": "user", "content": "Hello"},
            {
                "role": "user",
                "content": [
                    {
                        "id": "test_tool",
                        "type": "tool_call_result",
                        "tool_name": "",
                        "tool_input_dict": None,
                        "result": {"result": {"arg1": "value1"}},
                        "error": None,
                    },
                    {
                        "id": "test_tool_2",
                        "type": "tool_call_result",
                        "tool_name": "",
                        "tool_input_dict": None,
                        "result": {"result": {"arg2": "value2"}},
                        "error": None,
                    },
                ],
            },
            {"role": "assistant", "content": "Processing results..."},
            {
                "role": "user",
                "content": [
                    {
                        "id": "test_tool_3",
                        "type": "tool_call_result",
                        "tool_name": "",
                        "tool_input_dict": None,
                        "result": {"result": {"arg3": "value3"}},
                        "error": None,
                    },
                    {
                        "id": "test_tool_4",
                        "type": "tool_call_result",
                        "tool_name": "",
                        "tool_input_dict": None,
                        "result": {"result": {"arg4": "value4"}},
                        "error": None,
                    },
                ],
            },
        ]


class TestExtractContent:
    def test_extract_content(self, fireworks_provider: FireworksAIProvider):
        response = CompletionResponse.model_validate_json(
            fixture_bytes("fireworks", "r1_completion_with_reasoning.json"),
        )
        content = fireworks_provider._extract_content_str(response)  # pyright: ignore[reportPrivateUsage]
        assert (
            content
            == '\n\n```json\n{\n  "greeting": "The Azure Whisper",\n  "content": "On a cloudless morning, young Mira gazed upward, mesmerized by the endless blue canvas above. \'Why is the sky blue?\' she asked her grandmother, who tended sunflowers nearby. Her grandmother smiled, recalling an old tale. \'Long ago, the sky was colorless. A lonely star wept tears of sapphire, staining the heavens to remind us of its sorrow. But over time, the stars found joy again—scattering laughter as sunlight through the blue. Now, the sky sings their story.\' Mira squinted, imagining starry tears and shimmering light. From that day, the sky felt less like emptiness and more like a secret kept between the stars and her.",\n  "moral": "Even the simplest wonders hold stories waiting to be imagined."\n}\n```'
        )

    def test_extract_reasoning_steps(self, fireworks_provider: FireworksAIProvider):
        response = CompletionResponse.model_validate_json(
            fixture_bytes("fireworks", "r1_completion_with_reasoning.json"),
        )
        reasoning_steps = fireworks_provider._extract_reasoning_steps(response)  # pyright: ignore[reportPrivateUsage]
        assert reasoning_steps == [
            InternalReasoningStep(
                explaination="Okay, let's see. The user asked for a short story based on the fact that the sky is blue. \n",
            ),
        ]


class TestExtractStreamDelta:
    def test_extract_stream_delta(self, fireworks_provider: FireworksAIProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        delta = fireworks_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            b'{"id":"39c134cd-a781-4843-bdd6-e3db43259273","object":"chat.completion.chunk","created":1734400681,"model":"accounts/fireworks/models/llama-v3p1-8b-instruct","choices":[{"index":0,"delta":{"content":"\\"greeting\\": \\"Hello James!\\"\\n}"},"finish_reason":null}],"usage":null}',
            raw_completion,
            {},
        )
        assert delta.content == '"greeting": "Hello James!"\n}'
        assert raw_completion.usage == LLMUsage(prompt_token_count=None, completion_token_count=None)

    def test_extract_stream_delta_content_null(self, fireworks_provider: FireworksAIProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        delta = fireworks_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            b'{"id":"39c134cd-a781-4843-bdd6-e3db43259273","object":"chat.completion.chunk","created":1734400681,"model":"accounts/fireworks/models/llama-v3p1-8b-instruct","choices":[{"index":0,"delta":{"content":null},"finish_reason":"stop"}],"usage":{"prompt_tokens":24,"total_tokens":32,"completion_tokens":8}}',
            raw_completion,
            {},
        )
        assert delta.content == ""
        assert raw_completion.usage == LLMUsage(prompt_token_count=24, completion_token_count=8)

    def test_extract_stream_delta_content_empty(self, fireworks_provider: FireworksAIProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        delta = fireworks_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            b'{"id": "b9840d6a-77ef-4438-aadd-1db781444101","object": "chat.completion.chunk","created": 1738030001,"model": "accounts/fireworks/models/deepseek-r1","choices": [{"index": 0,"delta": {"role": "assistant"},"finish_reason": null}],"usage": null}',
            raw_completion,
            {},
        )
        assert delta == ParsedResponse("", tool_calls=[])
        assert fireworks_provider._thinking_tag_context.get() is None  # pyright: ignore[reportPrivateUsage]

    def test_extract_stream_delta_content_thinking_tag(self, fireworks_provider: FireworksAIProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        delta = fireworks_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            b'{"id": "b9840d6a-77ef-4438-aadd-1db781444101","object": "chat.completion.chunk","created": 1738030001,"model": "accounts/fireworks/models/deepseek-r1","choices": [{"index": 0,"delta": {"content": "<think>\\n"},"finish_reason": null}],"usage": null}',
            raw_completion,
            {},
        )
        assert delta == ParsedResponse("", "\n", tool_calls=[])
        assert fireworks_provider._thinking_tag_context.get() is True  # pyright: ignore[reportPrivateUsage]

    def test_extract_stream_delta_content_thinking_tag_open_and_close(self, fireworks_provider: FireworksAIProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        delta = fireworks_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            b'{"id": "b9840d6a-77ef-4438-aadd-1db781444101","object": "chat.completion.chunk","created": 1738030001,"model": "accounts/fireworks/models/deepseek-r1","choices": [{"index": 0,"delta": {"content": "<think>\\n"},"finish_reason": null}],"usage": null}',
            raw_completion,
            {},
        )
        assert delta == ParsedResponse("", "\n", tool_calls=[])
        assert fireworks_provider._thinking_tag_context.get() is True  # pyright: ignore[reportPrivateUsage]

        delta = fireworks_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            b'{"id": "b9840d6a-77ef-4438-aadd-1db781444101","object": "chat.completion.chunk","created": 1738030001,"model": "accounts/fireworks/models/deepseek-r1","choices": [{"index": 0,"delta": {"content": "Some thoughts"},"finish_reason": null}],"usage": null}',
            raw_completion,
            {},
        )
        assert delta == ParsedResponse("", "Some thoughts", tool_calls=[])
        assert fireworks_provider._thinking_tag_context.get() is True  # pyright: ignore[reportPrivateUsage]

        delta = fireworks_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            b'{"id": "b9840d6a-77ef-4438-aadd-1db781444101","object": "chat.completion.chunk","created": 1738030001,"model": "accounts/fireworks/models/deepseek-r1","choices": [{"index": 0,"delta": {"content": "</think>"},"finish_reason": null}],"usage": null}',
            raw_completion,
            {},
        )
        assert delta == ParsedResponse("", "", tool_calls=[])
        assert fireworks_provider._thinking_tag_context.get() is False  # pyright: ignore[reportPrivateUsage]

    def test_extract_stream_delta_usage(self, fireworks_provider: FireworksAIProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        delta = fireworks_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            b'{"id":"39c134cd-a781-4843-bdd6-e3db43259273","object":"chat.completion.chunk","created":1734400681,"model":"accounts/fireworks/models/llama-v3p1-8b-instruct","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":24,"total_tokens":32,"completion_tokens":8}}',
            raw_completion,
            {},
        )
        assert delta.content == ""
        assert raw_completion.usage == LLMUsage(prompt_token_count=24, completion_token_count=8)

    def test_done(self, fireworks_provider: FireworksAIProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        delta = fireworks_provider._extract_stream_delta(b"[DONE]", raw_completion, {})  # pyright: ignore[reportPrivateUsage]
        assert delta.content == ""


class TestRequiresDownloadingFile:
    @pytest.mark.parametrize(
        "file",
        (
            FileWithKeyPath(url="url", content_type="image/png", key_path=[]),
            FileWithKeyPath(url="url", content_type=None, format="image", key_path=[]),
        ),
    )
    def test_requires_downloading_file(self, file: FileWithKeyPath):
        assert FireworksAIProvider.requires_downloading_file(file, Model.LLAMA_3_3_70B)


class TestIsSchemaSupported:
    async def test_schema_supported(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.fireworks.ai/inference/v1/chat/completions",
            json=fixtures_json("fireworks", "completion.json"),
        )

        provider = FireworksAIProvider()
        schema = fixtures_json("jsonschemas", "schema_1.json")

        with patch("core.utils.redis_cache.get_redis_client") as mock_cache:
            mock_cache.get.return_value = None
            is_supported = await provider.is_schema_supported_for_structured_generation(
                task_name="test",
                model=Model.LLAMA_3_3_70B,
                schema=schema,
            )

        assert is_supported
        request = httpx_mock.get_requests()[0]
        body = json.loads(request.read().decode())
        assert body == {
            "max_tokens": 131072,
            "temperature": 0.0,
            "model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
            "messages": [{"role": "user", "content": "Generate a test output"}],
            "response_format": {
                "type": "json_object",
                "schema": {
                    "$defs": {
                        "CalendarEventCategory": {
                            "enum": [
                                "UNSPECIFIED",
                                "IN_PERSON_MEETING",
                                "REMOTE_MEETING",
                                "FLIGHT",
                                "TO_DO",
                                "BIRTHDAY",
                            ],
                            "title": "CalendarEventCategory",
                            "type": "string",
                        },
                        "MeetingProvider": {
                            "enum": ["ZOOM", "GOOGLE_MEET", "MICROSOFT_TEAMS", "SKYPE", "OTHER"],
                            "title": "MeetingProvider",
                            "type": "string",
                        },
                    },
                    "description": 'The expected output of the EmailToCalendarProcessor. Each attribute corresponds to a question asked to the processor.\n\nThis class will be dynamically injected in the prompt as a "schema" for the LLM to enforce.',
                    "properties": {
                        "is_email_thread_about_an_event": {
                            "title": "Is Email Thread About An Event",
                            "type": "boolean",
                        },
                        "is_event_confirmed": {
                            "anyOf": [{"type": "boolean"}, {"type": "null"}],
                            "title": "Is Event Confirmed",
                        },
                        "event_category": {"anyOf": [{"$ref": "#/$defs/CalendarEventCategory"}, {"type": "null"}]},
                        "is_event_all_day": {"title": "Is Event All Day", "type": "boolean"},
                        "is_event_start_datetime_defined": {
                            "anyOf": [{"type": "boolean"}, {"type": "null"}],
                            "title": "Is Event Start Datetime Defined",
                        },
                        "event_start_datetime": {
                            "anyOf": [{"format": "date-time", "type": "string"}, {"type": "null"}],
                            "title": "Event Start Datetime",
                        },
                        "event_start_date": {
                            "anyOf": [{"format": "date", "type": "string"}, {"type": "null"}],
                            "title": "Event Start Date",
                        },
                        "is_event_end_datetime_defined": {
                            "anyOf": [{"type": "boolean"}, {"type": "null"}],
                            "title": "Is Event End Datetime Defined",
                        },
                        "event_end_datetime": {
                            "anyOf": [{"format": "date-time", "type": "string"}, {"type": "null"}],
                            "title": "Event End Datetime",
                        },
                        "event_end_date": {
                            "anyOf": [{"format": "date", "type": "string"}, {"type": "null"}],
                            "title": "Event End Date",
                        },
                        "event_title": {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "Event Title"},
                        "remote_meeting_provider": {"anyOf": [{"$ref": "#/$defs/MeetingProvider"}, {"type": "null"}]},
                        "event_location_details": {
                            "anyOf": [{"type": "string"}, {"type": "null"}],
                            "title": "Event Location Details",
                        },
                        "event_participants_emails_addresses": {
                            "anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}],
                            "title": "Event Participants Emails Addresses",
                        },
                    },
                    "required": [
                        "is_email_thread_about_an_event",
                        "is_event_confirmed",
                        "event_category",
                        "is_event_all_day",
                        "is_event_start_datetime_defined",
                        "event_start_datetime",
                        "event_start_date",
                        "is_event_end_datetime_defined",
                        "event_end_datetime",
                        "event_end_date",
                        "event_title",
                        "remote_meeting_provider",
                        "event_location_details",
                        "event_participants_emails_addresses",
                    ],
                    "title": "EmailToCalendarOutput",
                    "type": "object",
                },
            },
            "stream": False,
            "context_length_exceeded_behavior": "truncate",
        }

    async def test_schema_not_supported_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.fireworks.ai/inference/v1/chat/completions",
            status_code=400,
            json={"error": {"message": "Invalid schema format"}},
        )

        provider = FireworksAIProvider()
        schema = {"type": "invalid_schema"}

        with patch("core.utils.redis_cache.get_redis_client") as mock_cache:
            mock_cache.get.return_value = None
            is_supported = await provider.is_schema_supported_for_structured_generation(
                task_name="test",
                model=Model.GPT_4O_2024_11_20,
                schema=schema,
            )

        assert not is_supported

    async def test_schema_not_supported_exception(self, httpx_mock: HTTPXMock):
        httpx_mock.add_exception(Exception("Unexpected error"))

        provider = FireworksAIProvider()
        schema = {"type": "object"}

        with patch("core.utils.redis_cache.get_redis_client") as mock_cache:
            mock_cache.get.return_value = None
            is_supported = await provider.is_schema_supported_for_structured_generation(
                task_name="test",
                model=Model.GPT_4O_2024_11_20,
                schema=schema,
            )

        assert not is_supported


class TestMaxTokensExceeded:
    """Occurs when the generation goes beyond the max tokens"""

    async def test_max_tokens_exceeded(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.fireworks.ai/inference/v1/chat/completions",
            json=fixtures_json("fireworks", "finish_reason_length_completion.json"),
        )
        provider = FireworksAIProvider()
        with pytest.raises(MaxTokensExceededError) as e:
            await provider.complete(
                [Message(role=Message.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.LLAMA_3_3_70B, max_tokens=10, temperature=0),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            )
        assert e.value.store_task_run is True
        assert (
            e.value.args[0]
            == "Model returned a response with a LENGTH finish reason, meaning the maximum number of tokens was exceeded."
        )

    async def test_max_tokens_exceeded_stream(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.fireworks.ai/inference/v1/chat/completions",
            stream=IteratorStream(
                [
                    fixture_bytes("fireworks", "finish_reason_length_stream_completion.txt"),
                ],
            ),
        )
        provider = FireworksAIProvider()
        with pytest.raises(MaxTokensExceededError) as e:
            async for _ in provider.stream(
                [Message(role=Message.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.LLAMA_3_3_70B, max_tokens=10, temperature=0),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
                partial_output_factory=lambda x: StructuredOutput(x),
            ):
                pass
        assert e.value.store_task_run is True
        assert (
            e.value.args[0]
            == "Model returned a response with a LENGTH finish reason, meaning the maximum number of tokens was exceeded."
        )


class TestPrepareCompletion:
    async def test_role_before_content(self, fireworks_provider: FireworksAIProvider):
        """Test that the 'role' key appears before 'content' in the prepared request."""
        request = fireworks_provider._build_request(  # pyright: ignore[reportPrivateUsage]
            messages=[Message(role=Message.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.LLAMA_3_3_70B, max_tokens=10, temperature=0),
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


class TestFireworksAIProviderNativeToolCalls:
    def test_build_request_with_tool_calls(self) -> None:
        provider = FireworksAIProvider(config=FireworksConfig(provider=Provider.FIREWORKS, api_key="test"))
        messages = [
            Message(
                role=Message.Role.USER,
                content="Test content",
                tool_call_requests=[
                    ToolCallRequestWithID(
                        id="test_id_1",
                        tool_name="test_tool",
                        tool_input_dict={"key": "value"},
                    ),
                ],
            ),
        ]
        options = ProviderOptions(
            task_name="test",
            model=Model.LLAMA_3_3_70B,
            enabled_tools=[
                Tool(
                    name="test_tool",
                    description="Test tool",
                    input_schema={"type": "object", "properties": {"key": {"type": "string"}}},
                    output_schema={"type": "object", "properties": {"result": {"type": "string"}}},
                ),
            ],
        )

        request = provider._build_request(messages, options, stream=False)  # pyright: ignore[reportPrivateUsage]
        assert isinstance(request, CompletionRequest)
        assert request.tools is not None
        assert len(request.tools) == 1
        assert request.tools[0].type == "function"
        assert request.tools[0].function.name == "test_tool"
        assert request.tools[0].function.description == "Test tool"
        assert request.tools[0].function.parameters == {"type": "object", "properties": {"key": {"type": "string"}}}

    def test_extract_native_tool_calls(self) -> None:
        response = CompletionResponse(
            id="test",
            choices=[
                Choice(
                    message=ChoiceMessage(
                        role="assistant",
                        content=None,
                        tool_calls=[
                            FireworksToolCall(
                                id="test_id_1",
                                type="function",
                                function=FireworksToolCallFunction(
                                    name="test_tool",
                                    arguments='{"key": "value"}',
                                ),
                            ),
                        ],
                    ),
                ),
            ],
            usage=Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )

        provider = FireworksAIProvider(config=FireworksConfig(provider=Provider.FIREWORKS, api_key="test"))
        tool_calls = provider._extract_native_tool_calls(response)  # pyright: ignore[reportPrivateUsage]
        assert len(tool_calls) == 1
        assert tool_calls[0].id == "test_id_1"
        assert tool_calls[0].tool_name == "test_tool"
        assert tool_calls[0].tool_input_dict == {"key": "value"}

    def test_extract_content_str_with_tool_calls(self) -> None:
        provider = FireworksAIProvider(config=FireworksConfig(provider=Provider.FIREWORKS, api_key="test"))
        response = CompletionResponse(
            id="test",
            choices=[
                Choice(
                    message=ChoiceMessage(
                        role="assistant",
                        content=None,
                        tool_calls=[
                            FireworksToolCall(
                                id="test_id_1",
                                type="function",
                                function=FireworksToolCallFunction(
                                    name="test_tool",
                                    arguments='{"key": "value"}',
                                ),
                            ),
                        ],
                    ),
                ),
            ],
            usage=Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )

        content = provider._extract_content_str(response)  # pyright: ignore[reportPrivateUsage]
        assert content == ""

    def test_extract_stream_delta_with_tool_calls(self) -> None:
        provider = FireworksAIProvider(config=FireworksConfig(provider=Provider.FIREWORKS, api_key="test"))
        raw_completion = RawCompletion(response="", usage=LLMUsage(prompt_token_count=0, completion_token_count=0))

        # Test complete tool call
        sse_event = b'{"id":"test-id","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"id":"test_id_1","type":"function","function":{"name":"test_tool","arguments":"{\\"key\\": \\"value\\"}"}}]}}]}'
        parsed = provider._extract_stream_delta(sse_event, raw_completion, {})  # pyright: ignore[reportPrivateUsage]
        assert parsed.tool_calls is not None
        assert len(parsed.tool_calls) == 1
        assert parsed.tool_calls[0].id == "test_id_1"
        assert parsed.tool_calls[0].tool_name == "test_tool"
        assert parsed.tool_calls[0].tool_input_dict == {"key": "value"}

    def test_extract_stream_delta_with_tool_calls_partial(self) -> None:
        # Test partial tool call
        provider = FireworksAIProvider(config=FireworksConfig(provider=Provider.FIREWORKS, api_key="test"))
        raw_completion = RawCompletion(response="", usage=LLMUsage(prompt_token_count=0, completion_token_count=0))

        tool_call_request_buffer: dict[int, ToolCallRequestBuffer] = {}

        sse_event = b'{"id":"test-id","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"id":"test_id_1","type":"function","function":{"name":"test_tool","arguments":"{\\"key"}}]}}]}'
        parsed = provider._extract_stream_delta(sse_event, raw_completion, tool_call_request_buffer)  # pyright: ignore[reportPrivateUsage]
        assert parsed.tool_calls == []

        # Test continuation of tool call
        sse_event = b'{"id":"test-id","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\\": \\"value\\"}"}}]}}]}'
        parsed = provider._extract_stream_delta(sse_event, raw_completion, tool_call_request_buffer)  # pyright: ignore[reportPrivateUsage]
        assert parsed.tool_calls is not None
        assert len(parsed.tool_calls) == 1
        assert parsed.tool_calls[0].id == "test_id_1"
        assert parsed.tool_calls[0].tool_name == "test_tool"
        assert parsed.tool_calls[0].tool_input_dict == {"key": "value"}


class TestUnknownError:
    def test_content_length_exceeded(self, fireworks_provider: FireworksAIProvider):
        e = fireworks_provider._unknown_error(  # pyright: ignore[reportPrivateUsage]
            Response(
                status_code=400,
                text="""{
                "error": {
                    "code": "string_above_max_length",
                    "message": "The string is too long"
                }
            }""",
            ),
        )
        assert isinstance(e, MaxTokensExceededError)
        assert str(e) == "The string is too long"

    def test_context_length_exceeded(self, fireworks_provider: FireworksAIProvider):
        e = fireworks_provider._unknown_error(  # pyright: ignore[reportPrivateUsage]
            Response(
                status_code=400,
                text="""{"error": {"code": "context_length_exceeded", "message": "Max token exceeded"}}""",
            ),
        )
        assert isinstance(e, MaxTokensExceededError)
        assert str(e) == "Max token exceeded"

    def test_invalid_request_error(self, fireworks_provider: FireworksAIProvider):
        e = fireworks_provider._unknown_error(  # pyright: ignore[reportPrivateUsage]
            Response(
                status_code=400,
                text="""{"error": {"type": "invalid_request_error", "message": "Prompt is too long"}}""",
            ),
        )
        assert isinstance(e, MaxTokensExceededError)
        assert str(e) == "Prompt is too long"

    def test_prompt_too_long(self, fireworks_provider: FireworksAIProvider):
        payload = {
            "error": {
                "message": "The prompt is too long: 140963, model maximum context length: 131071,",
                "object": "truncate",
                "type": "invalid_request_error",
            },
        }
        e = fireworks_provider._unknown_error(  # pyright: ignore[reportPrivateUsage]
            Response(
                status_code=400,
                text=json.dumps(payload),
            ),
        )
        assert isinstance(e, MaxTokensExceededError)
        assert e.capture is False
        assert not e.store_task_run


class TestExtractAndLogRateLimits:
    async def test_extract_and_log_rate_limits(self, fireworks_provider: FireworksAIProvider, patch_metric_send: Mock):
        response = Response(
            status_code=200,
            headers={
                "x-ratelimit-remaining-requests": "100",
                "x-ratelimit-limit-requests": "1000",
                "x-ratelimit-remaining-tokens-prompt": "10",
                "x-ratelimit-limit-tokens-prompt": "1000",
                "x-ratelimit-remaining-tokens-generated": "20",
                "x-ratelimit-limit-tokens-generated": "1000",
            },
        )
        await fireworks_provider._extract_and_log_rate_limits(response, Model.LLAMA_3_3_70B)  # pyright: ignore[reportPrivateUsage]

        assert patch_metric_send.call_count == 3
        metrics = sorted(
            [cast(Metric, call[0][0]) for call in patch_metric_send.call_args_list],
            key=lambda x: x.tags["limit_name"],
        )

        assert all(metric.name == "provider_rate_limit" for metric in metrics)
        assert all(metric.tags["provider"] == "fireworks" for metric in metrics)
        assert all(metric.tags["model"] == "llama-3.3-70b" for metric in metrics)

        assert metrics[0].tags["limit_name"] == "input_tokens"
        assert metrics[0].gauge == 0.99
        assert metrics[1].tags["limit_name"] == "output_tokens"
        assert metrics[1].gauge == 0.98
        assert metrics[2].tags["limit_name"] == "requests"
        assert metrics[2].gauge == 0.9
