from __future__ import annotations

import json
from typing import Any, cast

import pytest
from httpx import Response
from pytest_httpx import HTTPXMock, IteratorStream

from core.domain.errors import (
    FailedGenerationError,
    MaxTokensExceededError,
    ProviderBadRequestError,
    ProviderInternalError,
)
from core.domain.fields.file import File
from core.domain.llm_usage import LLMUsage
from core.domain.message import Message
from core.domain.models import Model
from core.domain.models.model_provider_datas_mapping import ANTHROPIC_PROVIDER_DATA
from core.domain.models.utils import get_model_data
from core.domain.structured_output import StructuredOutput
from core.domain.tool import Tool
from core.domain.tool_call import ToolCallRequestWithID
from core.providers.anthropic.anthropic_domain import (
    CompletionRequest,
    CompletionResponse,
    ContentBlock,
    Usage,
)
from core.providers.anthropic.anthropic_provider import AnthropicConfig, AnthropicProvider
from core.providers.base.models import RawCompletion
from core.providers.base.provider_options import ProviderOptions
from core.providers.base.streaming_context import ToolCallRequestBuffer
from tests.utils import fixture_bytes, fixtures_json, mock_aiter


@pytest.fixture(scope="function")
def anthropic_provider():
    return AnthropicProvider(
        config=AnthropicConfig(api_key="test"),
    )


def _output_factory(x: str, _: bool):
    return StructuredOutput(json.loads(x))


class TestBuildRequest:
    @pytest.mark.parametrize("model", ANTHROPIC_PROVIDER_DATA.keys())
    def test_build_request(self, anthropic_provider: AnthropicProvider, model: Model):
        request = cast(
            CompletionRequest,
            anthropic_provider._build_request(  # pyright: ignore[reportPrivateUsage]
                messages=[
                    Message(role=Message.Role.SYSTEM, content="Hello 1"),
                    Message(role=Message.Role.USER, content="Hello"),
                ],
                options=ProviderOptions(model=model, max_tokens=10, temperature=0),
                stream=False,
            ),
        )
        assert request.model_dump(include={"messages"})["messages"] == [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": "Hello 1",
                    },
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Hello",
                    },
                ],
            },
        ]
        assert request.temperature == 0
        assert request.max_tokens == 10

    @pytest.mark.parametrize("model", ANTHROPIC_PROVIDER_DATA.keys())
    def test_build_request_without_max_tokens(self, anthropic_provider: AnthropicProvider, model: Model):
        request = cast(
            CompletionRequest,
            anthropic_provider._build_request(  # pyright: ignore[reportPrivateUsage]
                messages=[
                    Message(role=Message.Role.SYSTEM, content="Hello 1"),
                    Message(role=Message.Role.USER, content="Hello"),
                ],
                options=ProviderOptions(model=model, temperature=0),
                stream=False,
            ),
        )
        model_data = get_model_data(model)
        assert request.max_tokens is not None
        if model_data.max_tokens_data.max_output_tokens:
            assert request.max_tokens == model_data.max_tokens_data.max_output_tokens
        elif model_data.max_tokens_data.max_tokens:
            assert request.max_tokens == model_data.max_tokens_data.max_tokens
        else:
            assert request.max_tokens == 1024

    @pytest.mark.parametrize("model", ANTHROPIC_PROVIDER_DATA.keys())
    def test_build_request_with_tools(self, anthropic_provider: AnthropicProvider, model: Model) -> None:
        # Import the expected Tool type

        # Use a dummy tool based on SimpleNamespace and cast it to the expected Tool type
        dummy_tool = Tool(
            name="dummy",
            description="A dummy tool",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {}},
        )

        options = ProviderOptions(model=model, max_tokens=10, temperature=0, enabled_tools=[dummy_tool])  # pyright: ignore [reportGeneralTypeIssues]
        message = Message(role=Message.Role.USER, content="Hello")

        request = cast(
            CompletionRequest,
            anthropic_provider._build_request(  # pyright: ignore[reportPrivateUsage]
                messages=[message],
                options=options,
                stream=False,
            ),
        )

        request_dict = request.model_dump()
        assert "tools" in request_dict
        tools = cast(list[dict[str, Any]], request_dict["tools"])
        assert len(tools) == 1
        tool = tools[0]
        assert tool["name"] == "dummy"
        assert tool["description"] == "A dummy tool"
        assert tool["input_schema"] == {"type": "object", "properties": {}}


class TestSingleStream:
    async def test_stream_data(self, httpx_mock: HTTPXMock, anthropic_provider: AnthropicProvider):
        httpx_mock.add_response(
            url="https://api.anthropic.com/v1/messages",
            stream=IteratorStream(
                [
                    b"data: ",
                    b'{"type":"message_start","message":{"id":"msg_01UCabT2dPX4DXxC3eRDEeTE","type":"message","role":"assistant","model":"claude-3-5-sonnet-20241022","content":[],"stop_reason":null,"stop_sequence":null,"usage":{"input_tokens":32507,"output_tokens":1}}    }\n',
                    b"dat",
                    b'a: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}         }\n',
                    b'data: {"type": "ping',
                    b'"}\n',
                    b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"{\\"response\\": \\"Looking"}            }\n',
                    b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" at Figure 2 in the"}     }\n',
                    b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" document, Claude 3."}             }\n',
                    b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"5 Sonnet "}           }\n',
                    b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"New) - the upgraded version -"} }\n',
                    b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"%- Multilingual: 48"}     }\n',
                    b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":").\\"}"}            }\n',
                    b'data: {"type":"content_block_stop","index":0  }\n',
                    b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},"usage":{"output_tokens":233}         }\n',
                    b'data: {"type":"message_stop"   }\n',
                ],
            ),
        )

        raw = RawCompletion(usage=LLMUsage(), response="")

        raw_chunks = anthropic_provider._single_stream(  # pyright: ignore[reportPrivateUsage]
            request={"messages": [{"role": "user", "content": "Hello"}]},
            output_factory=_output_factory,
            partial_output_factory=lambda x: StructuredOutput(x),
            raw_completion=raw,
            options=ProviderOptions(model=Model.CLAUDE_3_5_SONNET_20241022, max_tokens=10, temperature=0),
        )

        parsed_chunks = [o async for o in raw_chunks]

        assert len(parsed_chunks) == 8
        assert parsed_chunks[0][0] == {
            "response": "Looking at Figure 2 in the document, Claude 3.5 Sonnet New) - the upgraded version -%- Multilingual: 48).",
        }
        assert parsed_chunks[1][0] == {
            "response": "Looking at Figure 2 in the document, Claude 3.5 Sonnet New) - the upgraded version -%- Multilingual: 48).",
        }
        assert raw.usage.prompt_token_count == 32507
        assert raw.usage.completion_token_count == 233

        assert len(httpx_mock.get_requests()) == 1

    async def test_stream_data_fixture_file(self, httpx_mock: HTTPXMock, anthropic_provider: AnthropicProvider):
        httpx_mock.add_response(
            url="https://api.anthropic.com/v1/messages",
            stream=IteratorStream(
                [
                    fixture_bytes("anthropic", "stream_data_with_usage.txt"),
                ],
            ),
        )

        raw = RawCompletion(usage=LLMUsage(), response="")

        raw_chunks = anthropic_provider._single_stream(  # pyright: ignore[reportPrivateUsage]
            request={"messages": [{"role": "user", "content": "Hello"}]},
            output_factory=_output_factory,
            partial_output_factory=lambda x: StructuredOutput(x),
            raw_completion=raw,
            options=ProviderOptions(model=Model.CLAUDE_3_5_SONNET_20241022, max_tokens=10, temperature=0),
        )

        parsed_chunks = [o async for o in raw_chunks]

        assert len(parsed_chunks) == 4
        assert parsed_chunks[0][0] == {
            "response": " Looking at the human preference win rates shown in Figure 2 of the document. ",
        }
        assert parsed_chunks[1][0] == {
            "response": " Looking at the human preference win rates shown in Figure 2 of the document. ",
        }

        assert len(httpx_mock.get_requests()) == 1


class TestComplete:
    async def test_complete_pdf(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.anthropic.com/v1/messages",
            json=fixtures_json("anthropic", "completion.json"),
        )

        provider = AnthropicProvider()

        o = await provider.complete(
            [
                Message(
                    role=Message.Role.USER,
                    content="Hello",
                    files=[
                        File(data="data", content_type="application/pdf"),
                    ],
                ),
            ],
            options=ProviderOptions(model=Model.CLAUDE_3_5_SONNET_20241022, max_tokens=10, temperature=0),
            output_factory=_output_factory,
        )

        assert o.output
        assert o.tool_calls is None

        request = httpx_mock.get_requests()[0]
        assert request.method == "POST"
        body = json.loads(request.read().decode())
        assert str(body) == str(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Hello"},
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": "data",
                                },
                            },
                        ],
                    },
                ],
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 10,
                "temperature": 0.0,
                "stream": False,
            },
        )

    async def test_complete_image(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.anthropic.com/v1/messages",
            json=fixtures_json("anthropic", "completion.json"),
        )

        provider = AnthropicProvider()

        o = await provider.complete(
            [
                Message(role=Message.Role.USER, content="Hello", files=[File(content_type="image/png", data="bla")]),
            ],
            options=ProviderOptions(model=Model.CLAUDE_3_5_SONNET_20241022, max_tokens=10, temperature=0),
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
        )

        assert o.output
        assert o.tool_calls is None

        request = httpx_mock.get_requests()[0]
        assert request.method == "POST"
        body = json.loads(request.read().decode())
        assert str(body) == str(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Hello"},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": "bla",
                                },
                            },
                        ],
                    },
                ],
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 10,
                "temperature": 0.0,
                "stream": False,
            },
        )

    @pytest.mark.parametrize("model", ANTHROPIC_PROVIDER_DATA.keys())
    async def test_complete_with_max_tokens(
        self,
        httpx_mock: HTTPXMock,
        anthropic_provider: AnthropicProvider,
        model: Model,
    ):
        httpx_mock.add_response(
            url="https://api.anthropic.com/v1/messages",
            json=fixtures_json("anthropic", "completion.json"),
        )

        o = await anthropic_provider.complete(
            [Message(role=Message.Role.USER, content="Hello")],
            options=ProviderOptions(model=model, max_tokens=10, temperature=0),
            output_factory=_output_factory,
        )

        assert o.output
        assert o.tool_calls is None

        request = httpx_mock.get_requests()[0]
        assert request.method == "POST"
        body = json.loads(request.read().decode())
        assert body["max_tokens"] == 10

    @pytest.mark.parametrize("model", ANTHROPIC_PROVIDER_DATA.keys())
    async def test_complete_with_max_tokens_not_set(
        self,
        httpx_mock: HTTPXMock,
        anthropic_provider: AnthropicProvider,
        model: Model,
    ):
        httpx_mock.add_response(
            url="https://api.anthropic.com/v1/messages",
            json=fixtures_json("anthropic", "completion.json"),
        )

        o = await anthropic_provider.complete(
            [Message(role=Message.Role.USER, content="Hello")],
            options=ProviderOptions(model=model, temperature=0),
            output_factory=_output_factory,
        )

        assert o.output
        assert o.tool_calls is None

        request = httpx_mock.get_requests()[0]
        assert request.method == "POST"
        body = json.loads(request.read().decode())
        model_data = get_model_data(model)
        assert (
            body["max_tokens"] == model_data.max_tokens_data.max_output_tokens or model_data.max_tokens_data.max_tokens
        )


class TestWrapSSE:
    EXAMPLE = b"""
event: message_start
data: {"type":"message_start","message":{"id":"msg_4QpJur2dWWDjF6C758FbBw5vm12BaVipnK","type":"message","role":"assistant","content":[],"model":"claude-3-opus-20240229","stop_reason":null,"stop_sequence":null,"usage":{"input_tokens":11,"output_tokens":1}}}

event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}

event: ping
data: {"type": "ping"}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"!"}}

event: content_block_stop
data: {"type":"content_block_stop","index":0}

event: message_delta
data: {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},"usage":{"output_tokens":6}}

event: message_stop
data: {"type":"message_stop"}
"""

    async def test_wrap_sse_all_lines(self, anthropic_provider: AnthropicProvider):
        it = mock_aiter(*(self.EXAMPLE.splitlines(keepends=True)))
        wrapped = [c async for c in anthropic_provider.wrap_sse(it)]
        assert len(wrapped) == 7

    async def test_cut_event_line(self, anthropic_provider: AnthropicProvider):
        async def _basic_iterator():
            for line in self.EXAMPLE.splitlines(keepends=True):
                yield line

        wrapped = [c async for c in anthropic_provider.wrap_sse(_basic_iterator())]
        assert len(wrapped) == 7

    _SHORT_EXAMPLE = b"""event: message_start
data: hello1

event: ping

event: content_block_start
data: hello2
"""

    @pytest.mark.parametrize("cut_idx", range(len(_SHORT_EXAMPLE)))
    async def test_all_cuts(self, anthropic_provider: AnthropicProvider, cut_idx: int):
        # Check that we return the same objects no matter where we cut
        chunks = [self._SHORT_EXAMPLE[:cut_idx] + self._SHORT_EXAMPLE[cut_idx:]]
        it = mock_aiter(*chunks)
        wrapped = [c async for c in anthropic_provider.wrap_sse(it)]
        assert wrapped == [b"hello1", b"hello2"]


class TestMaxTokensExceeded:
    async def test_max_tokens_exceeded(self, anthropic_provider: AnthropicProvider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.anthropic.com/v1/messages",
            json=fixtures_json("anthropic", "finish_reason_max_tokens_completion.json"),
        )

        with pytest.raises(MaxTokensExceededError) as e:
            await anthropic_provider.complete(
                [Message(role=Message.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.CLAUDE_3_5_SONNET_20241022, max_tokens=10, temperature=0),
                output_factory=_output_factory,
            )

        assert len(httpx_mock.get_requests()) == 1
        assert e.value.args[0] == "Model returned MAX_TOKENS stop reason, the max tokens limit was exceeded."

    async def test_max_tokens_exceeded_stream(self, anthropic_provider: AnthropicProvider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.anthropic.com/v1/messages",
            stream=IteratorStream(
                [
                    fixture_bytes("anthropic", "finish_reason_max_tokens_stream_response.txt"),
                ],
            ),
        )

        raw = RawCompletion(usage=LLMUsage(), response="")

        with pytest.raises(MaxTokensExceededError) as e:
            async for _ in anthropic_provider._single_stream(  # pyright: ignore[reportPrivateUsage]
                request={"messages": [{"role": "user", "content": "Hello"}]},
                output_factory=_output_factory,
                partial_output_factory=lambda x: StructuredOutput(x),
                raw_completion=raw,
                options=ProviderOptions(model=Model.CLAUDE_3_5_SONNET_20241022, max_tokens=10, temperature=0),
            ):
                pass

        assert e.value.args[0] == "Model returned MAX_TOKENS stop reason, the max tokens limit was exceeded."


class TestPrepareCompletion:
    async def test_role_before_content(self, anthropic_provider: AnthropicProvider):
        """Test that the 'role' key appears before 'content' in the prepared request."""
        request = cast(
            CompletionRequest,
            anthropic_provider._build_request(  # pyright: ignore[reportPrivateUsage]
                messages=[Message(role=Message.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.CLAUDE_3_5_SONNET_20241022, max_tokens=10, temperature=0),
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


class TestExtractStreamDelta:
    async def test_stream_with_tools(
        self,
        anthropic_provider: AnthropicProvider,
    ):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer] = {}
        tool_calls: list[ToolCallRequestWithID] = []
        content: str = ""

        fixture_data = fixtures_json("anthropic/anthropic_with_tools_streaming_fixture.json")
        for sse in fixture_data["SSEs"]:
            delta = anthropic_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
                json.dumps(sse).encode(),
                raw_completion,
                tool_call_request_buffer,
            )
            content += delta.content
            if delta.tool_calls:
                tool_calls.extend(delta.tool_calls)

        # Verify the content and tool calls
        assert content == "I'll help you search for the latest Jazz vs Lakers game score."

        # Verify tool calls were correctly extracted
        assert tool_calls == [
            ToolCallRequestWithID(
                id="toolu_018BjmfDhLuQh15ghjQmwaWF",
                tool_name="@search-google",
                tool_input_dict={"query": "Jazz Lakers latest game score 2025"},
            ),
        ]

        # Verify usage metrics were captured
        assert raw_completion.usage == LLMUsage(
            prompt_token_count=717,
            completion_token_count=75,
        )

    async def test_stream_with_multiple_tools(
        self,
        anthropic_provider: AnthropicProvider,
    ):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer] = {}
        tool_calls: list[ToolCallRequestWithID] = []
        content: str = ""

        fixture_data = fixtures_json("anthropic/anthropic_with_multiple_tools_streaming_fixture.json")
        for sse in fixture_data["SSEs"]:
            delta = anthropic_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
                json.dumps(sse).encode(),
                raw_completion,
                tool_call_request_buffer,
            )
            content += delta.content
            if delta.tool_calls:
                tool_calls.extend(delta.tool_calls)

        # Verify the content and tool calls
        assert content == "\n\nNow I'll get all the weather information using the city code:"

        # Verify tool calls were correctly extracted
        assert tool_calls == [
            ToolCallRequestWithID(
                tool_name="get_temperature",
                tool_input_dict={"city_code": "125321"},
                id="toolu_019eEEq7enPNzjU6z6X34y7i",
            ),
            ToolCallRequestWithID(
                tool_name="get_rain_probability",
                tool_input_dict={"city_code": "125321"},
                id="toolu_01UgGE25XyALN9fmi7QD3Q8u",
            ),
            ToolCallRequestWithID(
                tool_name="get_wind_speed",
                tool_input_dict={"city_code": "125321"},
                id="toolu_01PRcJww2rnhd3BPbVdbkuXG",
            ),
            ToolCallRequestWithID(
                tool_name="get_weather_conditions",
                tool_input_dict={"city_code": "125321"},
                id="toolu_01AS6J6V1Jp6awe6vh4zf4eJ",
            ),
        ]

        # Verify usage metrics were captured
        LLMUsage(
            completion_token_count=194,
            prompt_token_count=1191.0,
        )

    def test_message_start(self, anthropic_provider: AnthropicProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        delta = anthropic_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            json.dumps(
                {
                    "type": "message_start",
                    "message": {
                        "id": "msg_123",
                        "type": "message",
                        "role": "assistant",
                        "content": [],
                        "model": "claude-3-5-sonnet-20241022",
                        "usage": {
                            "input_tokens": 100,
                            "output_tokens": 50,
                        },
                    },
                },
            ).encode(),
            raw_completion,
            {},
        )
        assert delta.content == ""
        assert raw_completion.usage == LLMUsage(prompt_token_count=100, completion_token_count=50)

    def test_content_block_start_with_tool(self, anthropic_provider: AnthropicProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer] = {}

        delta = anthropic_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            json.dumps(
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {
                        "type": "tool_use",
                        "id": "tool_123",
                        "name": "@search-google",
                    },
                },
            ).encode(),
            raw_completion,
            tool_call_request_buffer,
        )

        assert delta.content == ""
        assert len(tool_call_request_buffer) == 1

    def test_content_block_delta_with_tool_input(self, anthropic_provider: AnthropicProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        tool_call_request_buffer = {
            0: ToolCallRequestBuffer(
                id="tool_123",
                tool_name="@search-google",
                tool_input='{"query": "',
            ),
        }

        # Test partial JSON input
        delta = anthropic_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            json.dumps(
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {
                        "type": "input_json_delta",
                        "partial_json": 'latest news"}',
                    },
                },
            ).encode(),
            raw_completion,
            tool_call_request_buffer,
        )

        assert delta.content == ""
        tool_calls = delta.tool_calls
        assert tool_calls is not None
        assert len(tool_calls) == 1
        tool_call = tool_calls[0]
        assert tool_call.id == "tool_123"
        assert tool_call.tool_name == "@search-google"
        assert tool_call.tool_input_dict == {"query": "latest news"}

    def test_message_delta_with_max_tokens(self, anthropic_provider: AnthropicProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())

        with pytest.raises(MaxTokensExceededError) as exc_info:
            anthropic_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
                json.dumps(
                    {
                        "type": "message_delta",
                        "delta": {
                            "stop_reason": "max_tokens",
                            "stop_sequence": None,
                        },
                        "usage": {
                            "output_tokens": 100,
                        },
                    },
                ).encode(),
                raw_completion,
                {},
            )

        assert "Model returned MAX_TOKENS stop reason" in str(exc_info.value)
        assert raw_completion.usage == LLMUsage(completion_token_count=100)

    def test_ping_and_stop_events(self, anthropic_provider: AnthropicProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())

        # Test ping event
        delta = anthropic_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            json.dumps({"type": "ping"}).encode(),
            raw_completion,
            {},
        )
        assert delta.content == ""

        # Test message_stop event
        delta = anthropic_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            json.dumps({"type": "message_stop"}).encode(),
            raw_completion,
            {},
        )
        assert delta.content == ""

        # Test content_block_stop event
        delta = anthropic_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            json.dumps({"type": "content_block_stop", "index": 0}).encode(),
            raw_completion,
            {},
        )
        assert delta.content == ""

    def test_invalid_json(self, anthropic_provider: AnthropicProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())

        delta = anthropic_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            b"invalid json",
            raw_completion,
            {},
        )
        assert delta.content == ""

    def test_content_block_delta_with_text(self, anthropic_provider: AnthropicProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())

        delta = anthropic_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            json.dumps(
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {
                        "type": "text_delta",
                        "text": "Hello world",
                    },
                },
            ).encode(),
            raw_completion,
            {},
        )

        assert delta.content == "Hello world"
        assert delta.tool_calls == []

    def test_content_block_start_with_text(self, anthropic_provider: AnthropicProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())

        delta = anthropic_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            json.dumps(
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {
                        "type": "text",
                        "text": "",
                    },
                },
            ).encode(),
            raw_completion,
            {},
        )

        assert delta.content == ""
        assert delta.tool_calls == []

    def test_message_delta_with_stop_reason(self, anthropic_provider: AnthropicProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())

        delta = anthropic_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            json.dumps(
                {
                    "type": "message_delta",
                    "delta": {
                        "stop_reason": "end_turn",
                        "stop_sequence": None,
                    },
                    "usage": {
                        "output_tokens": 75,
                    },
                },
            ).encode(),
            raw_completion,
            {},
        )

        assert delta.content == ""
        assert raw_completion.usage == LLMUsage(completion_token_count=75)
        assert raw_completion.finish_reason == "end_turn"

    def test_missing_index_in_content_block_start(self, anthropic_provider: AnthropicProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())

        with pytest.raises(FailedGenerationError) as exc_info:
            anthropic_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
                json.dumps(
                    {
                        "type": "content_block_start",
                        "content_block": {
                            "type": "tool_use",
                            "id": "tool_123",
                            "name": "@search-google",
                        },
                    },
                ).encode(),
                raw_completion,
                {},
            )

        assert "Missing required fields in content block start" in str(exc_info.value)

    def test_content_block_delta_with_unknown_tool_call(self, anthropic_provider: AnthropicProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())

        with pytest.raises(FailedGenerationError) as exc_info:
            anthropic_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
                json.dumps(
                    {
                        "type": "content_block_delta",
                        "index": 1,
                        "delta": {
                            "type": "input_json_delta",
                            "partial_json": '{"query": "test"}',
                        },
                    },
                ).encode(),
                raw_completion,
                {},
            )

        assert "Received content block delta for unknown tool call" in str(exc_info.value)


def get_dummy_provider() -> AnthropicProvider:
    config = AnthropicConfig(api_key="dummy")
    return AnthropicProvider(config=config)


def test_extract_content_str_valid() -> None:
    provider = get_dummy_provider()
    response = CompletionResponse(
        content=[ContentBlock(type="text", text="Hello world")],
        usage=Usage(input_tokens=0, output_tokens=0),
        stop_reason=None,
    )
    text = provider._extract_content_str(response)  # pyright: ignore[reportPrivateUsage]
    assert text == "Hello world"


def test_extract_content_str_empty_content() -> None:
    provider = get_dummy_provider()
    response = CompletionResponse(
        content=[],
        usage=Usage(input_tokens=0, output_tokens=0),
        stop_reason=None,
    )
    with pytest.raises(ProviderInternalError):
        provider._extract_content_str(response)  # pyright: ignore[reportPrivateUsage]


def test_extract_content_str_max_tokens() -> None:
    provider = get_dummy_provider()
    response = CompletionResponse(
        content=[ContentBlock(type="text", text="Hello world")],
        usage=Usage(input_tokens=0, output_tokens=0),
        stop_reason="max_tokens",
    )
    with pytest.raises(MaxTokensExceededError) as exc_info:
        provider._extract_content_str(response)  # pyright: ignore[reportPrivateUsage]
    assert exc_info.value.args[0] == "Model returned MAX_TOKENS stop reason, the max tokens limit was exceeded."


class TestUnknownError:
    def test_unknown_error(self, anthropic_provider: AnthropicProvider):
        payload = {
            "error": {
                "message": "messages.1.content.1.image.source.base64: invalid base64 data",
                "type": "invalid_request_error",
            },
            "type": "error",
        }
        response = Response(status_code=400, text=json.dumps(payload))
        err = anthropic_provider._unknown_error(response)  # pyright: ignore[reportPrivateUsage]

        assert isinstance(err, ProviderBadRequestError)
        assert str(err) == "messages.1.content.1.image.source.base64: invalid base64 data"
        assert err.capture

    def test_unknown_error_max_tokens_exceeded(self, anthropic_provider: AnthropicProvider):
        payload = {
            "error": {
                "message": "prompt is too long: 201135 tokens > 200000 maximum",
                "type": "invalid_request_error",
            },
            "type": "error",
        }
        response = Response(status_code=400, text=json.dumps(payload))
        err = anthropic_provider._unknown_error(response)  # pyright: ignore[reportPrivateUsage]

        assert isinstance(err, MaxTokensExceededError)
        assert str(err) == "prompt is too long: 201135 tokens > 200000 maximum"
        assert not err.capture
