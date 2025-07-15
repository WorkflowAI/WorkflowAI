# pyright: reportPrivateUsage=false

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, cast

import pytest
from httpx import Response
from pytest_httpx import HTTPXMock, IteratorStream

from core.domain.fields.file import File
from core.domain.llm_usage import LLMUsage
from core.domain.message import MessageDeprecated
from core.domain.models import Model
from core.domain.models.model_provider_data_mapping import ANTHROPIC_PROVIDER_DATA
from core.domain.models.utils import get_model_data
from core.domain.structured_output import StructuredOutput
from core.domain.task_group_properties import ToolChoice, ToolChoiceFunction
from core.domain.tool import Tool
from core.domain.tool_call import ToolCallRequestWithID
from core.providers.anthropic.anthropic_domain import (
    AnthropicMessage,
    AntToolChoice,
    CompletionChunk,
    CompletionRequest,
    CompletionResponse,
    ContentBlock,
    SignatureDelta,
    TextContent,
    ThinkingContent,
    ThinkingDelta,
    ToolUseContent,
    Usage,
)
from core.providers.anthropic.anthropic_provider import AnthropicConfig, AnthropicProvider
from core.providers.base.models import RawCompletion
from core.providers.base.provider_error import (
    FailedGenerationError,
    MaxTokensExceededError,
    ProviderBadRequestError,
    ProviderError,
    ProviderInternalError,
    ServerOverloadedError,
)
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


class TestMaxTokens:
    @pytest.mark.parametrize(
        ("model", "requested_max_tokens", "thinking_budget", "expected_max_tokens"),
        [
            pytest.param(Model.CLAUDE_3_5_HAIKU_LATEST, 10, None, 10, id="Requested less than default, no thinking"),
            pytest.param(Model.CLAUDE_3_7_SONNET_20250219, None, None, 8192, id="Default, no thinking"),
            pytest.param(
                Model.CLAUDE_3_7_SONNET_20250219,
                50_000,
                None,
                50_000,
                id="Requested less than max, no thinking",
            ),
            pytest.param(
                Model.CLAUDE_3_7_SONNET_20250219,
                100_000,
                None,
                64_000,
                id="Requested more than max, no thinking",
            ),
            pytest.param(Model.CLAUDE_3_7_SONNET_20250219, 10, 500, 510, id="Requested with thinking budget"),
            pytest.param(Model.CLAUDE_3_7_SONNET_20250219, None, 1000, 9192, id="Default with thinking budget"),
            pytest.param(
                Model.CLAUDE_3_7_SONNET_20250219,
                50_000,
                2000,
                52_000,
                id="Requested with thinking budget less than max",
            ),
            pytest.param(
                Model.CLAUDE_3_7_SONNET_20250219,
                62_000,
                3000,
                64_000,
                id="Requested with thinking budget exceeds max",
            ),
            pytest.param(
                Model.CLAUDE_3_7_SONNET_20250219,
                100_000,
                5000,
                64_000,
                id="Both requested and thinking exceed max",
            ),
        ],
    )
    def test_max_tokens(
        self,
        anthropic_provider: AnthropicProvider,
        model: Model,
        requested_max_tokens: int | None,
        thinking_budget: int | None,
        expected_max_tokens: int,
    ):
        assert (
            anthropic_provider._max_tokens(get_model_data(model), requested_max_tokens, thinking_budget)
            == expected_max_tokens
        )

    def test_max_tokens_with_missing_model_data(self, anthropic_provider: AnthropicProvider):
        """Test that the method handles missing model max tokens by using default."""
        # Create a mock model data with no max_output_tokens
        model_data = get_model_data(Model.CLAUDE_3_7_SONNET_20250219)
        original_max_output_tokens = model_data.max_tokens_data.max_output_tokens

        # Temporarily set max_output_tokens to None to test the fallback
        model_data.max_tokens_data.max_output_tokens = None

        try:
            result = anthropic_provider._max_tokens(model_data, 1000, 500)
            # Should use DEFAULT_MAX_TOKENS (8192) as the ceiling
            assert result == 1500  # requested 1000 + thinking 500
        finally:
            # Restore original value
            model_data.max_tokens_data.max_output_tokens = original_max_output_tokens

    def test_max_tokens_with_missing_model_data_exceeds_default(self, anthropic_provider: AnthropicProvider):
        """Test that the method handles missing model max tokens when requested exceeds default."""
        # Create a mock model data with no max_output_tokens
        model_data = get_model_data(Model.CLAUDE_3_7_SONNET_20250219)
        original_max_output_tokens = model_data.max_tokens_data.max_output_tokens

        # Temporarily set max_output_tokens to None to test the fallback
        model_data.max_tokens_data.max_output_tokens = None

        try:
            result = anthropic_provider._max_tokens(model_data, 10000, 2000)
            # Should use DEFAULT_MAX_TOKENS (8192) as the ceiling
            assert result == 8192  # min(10000 + 2000, 8192) = 8192
        finally:
            # Restore original value
            model_data.max_tokens_data.max_output_tokens = original_max_output_tokens


class TestBuildRequest:
    def test_build_request(self, anthropic_provider: AnthropicProvider):
        request = cast(
            CompletionRequest,
            anthropic_provider._build_request(  # pyright: ignore[reportPrivateUsage]
                messages=[
                    MessageDeprecated(role=MessageDeprecated.Role.SYSTEM, content="Hello 1"),
                    MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello"),
                ],
                options=ProviderOptions(model=Model.CLAUDE_3_5_SONNET_20241022, max_tokens=10, temperature=0),
                stream=False,
            ),
        )
        assert request.system == "Hello 1"
        assert request.model_dump(include={"messages"})["messages"] == [
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

    def test_build_request_without_max_tokens(self, anthropic_provider: AnthropicProvider):
        request = cast(
            CompletionRequest,
            anthropic_provider._build_request(  # pyright: ignore[reportPrivateUsage]
                messages=[
                    MessageDeprecated(role=MessageDeprecated.Role.SYSTEM, content="Hello 1"),
                    MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello"),
                ],
                options=ProviderOptions(model=Model.CLAUDE_3_7_SONNET_20250219, temperature=0),
                stream=False,
            ),
        )

        assert request.max_tokens == 8192

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
        message = MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")

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

    @pytest.mark.parametrize(
        "tool_choice_option, expected_ant_tool_choice",
        [
            pytest.param("none", AntToolChoice(type="none"), id="None"),
            pytest.param("auto", AntToolChoice(type="auto"), id="AUTO"),
            pytest.param("required", AntToolChoice(type="any"), id="required"),
            pytest.param(
                ToolChoiceFunction(name="specific_tool_name"),
                AntToolChoice(type="tool", name="specific_tool_name"),
                id="TOOL_NAME",
            ),
        ],
    )
    def test_build_request_with_tool_choice(
        self,
        anthropic_provider: AnthropicProvider,
        tool_choice_option: ToolChoice | None,
        expected_ant_tool_choice: AntToolChoice,
    ):
        model = Model.CLAUDE_3_5_SONNET_20241022  # Use a specific model for simplicity
        request = cast(
            CompletionRequest,
            anthropic_provider._build_request(  # pyright: ignore[reportPrivateUsage]
                messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=model, tool_choice=tool_choice_option),
                stream=False,
            ),
        )
        assert request.tool_choice == expected_ant_tool_choice

    def test_build_request_no_messages(self, anthropic_provider: AnthropicProvider):
        request = cast(
            CompletionRequest,
            anthropic_provider._build_request(  # pyright: ignore[reportPrivateUsage]
                messages=[
                    MessageDeprecated(role=MessageDeprecated.Role.SYSTEM, content="You are a helpful assistant."),
                ],
                options=ProviderOptions(model=Model.CLAUDE_3_5_SONNET_20241022),
                stream=False,
            ),
        )
        assert request.system == "You are a helpful assistant."
        assert request.messages == [
            AnthropicMessage(role="user", content=[TextContent(text="-")]),
        ]

    def test_build_request_with_thinking_budget(self, anthropic_provider: AnthropicProvider):
        """Test that thinking budget is properly configured in requests."""
        from core.domain.models.model_data import ModelReasoningBudget
        from core.domain.models.utils import get_model_data
        from core.providers.base.provider_options import ProviderOptions

        model = Model.CLAUDE_3_5_SONNET_20241022
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
                anthropic_provider._build_request(  # pyright: ignore[reportPrivateUsage]
                    messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                    options=options,
                    stream=False,
                ),
            )

            # Check that thinking is configured
            assert request.thinking is not None
            assert request.thinking.type == "enabled"
            assert request.thinking.budget_tokens == 500

            # Check that max_tokens includes the thinking budget
            assert request.max_tokens == 1000 + 500

        finally:
            # Restore original reasoning value
            model_data.reasoning = original_reasoning

    def test_build_request_without_thinking_budget(self, anthropic_provider: AnthropicProvider):
        """Test that no thinking configuration is added when reasoning budget is not set."""
        options = ProviderOptions(
            model=Model.CLAUDE_3_5_SONNET_20241022,
            max_tokens=1000,
        )

        request = cast(
            CompletionRequest,
            anthropic_provider._build_request(  # pyright: ignore[reportPrivateUsage]
                messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=options,
                stream=False,
            ),
        )

        # Check that thinking is not configured
        assert request.thinking is None

        # Check that max_tokens is not modified
        assert request.max_tokens == 1000


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
            options=ProviderOptions(
                model=Model.CLAUDE_3_5_SONNET_20241022,
                max_tokens=10,
                temperature=0,
                output_schema={},
            ),
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
            options=ProviderOptions(
                model=Model.CLAUDE_3_5_SONNET_20241022,
                max_tokens=10,
                temperature=0,
                output_schema={},
            ),
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
                MessageDeprecated(
                    role=MessageDeprecated.Role.USER,
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
                MessageDeprecated(
                    role=MessageDeprecated.Role.USER,
                    content="Hello",
                    files=[File(content_type="image/png", data="bla=")],
                ),
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
                                    "data": "bla=",
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
            [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
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
            [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
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
                [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
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
                messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
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

    def test_raised_error(self, anthropic_provider: AnthropicProvider):
        with pytest.raises(ServerOverloadedError):
            anthropic_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
                json.dumps(
                    {
                        "type": "error",
                        "error": {"type": "overloaded_error", "message": "Server is overloaded"},
                    },
                ).encode(),
                RawCompletion(response="", usage=LLMUsage()),
                {},
            )

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
    @pytest.fixture
    def unknown_error_fn(self, anthropic_provider: AnthropicProvider):
        # Wrapper to avoid having to silence the private warning
        # and instantiate the response
        def _build_unknown_error(payload: str | dict[str, Any], status_code: int = 400):
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            res = Response(status_code=status_code, text=payload)
            return anthropic_provider._unknown_error(res)  # pyright: ignore[reportPrivateUsage]

        return _build_unknown_error

    def test_unknown_error(self, unknown_error_fn: Callable[[dict[str, Any]], ProviderError]):
        payload = {
            "error": {
                "message": "messages.1.content.1.image.source.base64: invalid base64 data",
                "type": "invalid_request_error",
            },
            "type": "error",
        }
        err = unknown_error_fn(payload)

        assert isinstance(err, ProviderBadRequestError)
        assert str(err) == "messages.1.content.1.image.source.base64: invalid base64 data"
        assert err.capture

    def test_unknown_error_max_tokens_exceeded(self, unknown_error_fn: Callable[[dict[str, Any]], ProviderError]):
        payload = {
            "error": {
                "message": "prompt is too long: 201135 tokens > 200000 maximum",
                "type": "invalid_request_error",
            },
            "type": "error",
        }
        err = unknown_error_fn(payload)

        assert isinstance(err, MaxTokensExceededError)
        assert str(err) == "prompt is too long: 201135 tokens > 200000 maximum"
        assert not err.capture

    def test_image_too_large(self, unknown_error_fn: Callable[[dict[str, Any]], ProviderError]):
        payload = {
            "error": {
                "message": "messages.1.content.1.image.source.base64: image exceeds 5 MB maximum: 6746560 bytes > 5242880 bytes",
                "type": "invalid_request_error",
            },
            "type": "error",
        }
        err = unknown_error_fn(payload)

        assert isinstance(err, ProviderBadRequestError)
        assert str(err) == "Image exceeds the maximum size"
        assert not err.capture


class TestStandardizeMessages:
    def test_with_system(self, anthropic_provider: AnthropicProvider):
        request = CompletionRequest(
            system="You are a helpful assistant.",
            messages=[AnthropicMessage(role="user", content=[TextContent(text="Hello")])],
            model="claude-3-opus-20240229",
            stream=False,
            max_tokens=100,
            temperature=0.5,
        )
        raw_prompt = anthropic_provider._raw_prompt(request.model_dump())  # pyright: ignore[reportPrivateUsage]
        standardized_prompt = AnthropicProvider.standardize_messages(raw_prompt)  # pyright: ignore[reportPrivateUsage]
        assert standardized_prompt == [  # pyright: ignore[reportPrivateUsage]
            {"role": "assistant", "content": "You are a helpful assistant."},
            {"role": "user", "content": [{"type": "text", "text": "Hello"}]},
        ]


class TestExtractReasoningSteps:
    def test_extract_reasoning_steps_with_thinking_content(self, anthropic_provider: AnthropicProvider):
        """Test extraction of reasoning steps from thinking content blocks."""
        response = CompletionResponse(
            content=[
                ContentBlock(type="text", text="Here's my response."),
                ThinkingContent(
                    type="thinking",
                    thinking="Let me think about this step by step...",
                    signature="sig_123",
                ),
                ThinkingContent(
                    type="thinking",
                    thinking="Now I need to consider another approach...",
                ),
            ],
            usage=Usage(input_tokens=100, output_tokens=50),
        )

        reasoning_steps = anthropic_provider._extract_reasoning_steps(response)  # pyright: ignore[reportPrivateUsage]

        assert reasoning_steps is not None
        assert len(reasoning_steps) == 2
        assert reasoning_steps[0].explaination == "Let me think about this step by step..."
        assert reasoning_steps[1].explaination == "Now I need to consider another approach..."

    def test_extract_reasoning_steps_without_thinking_content(self, anthropic_provider: AnthropicProvider):
        """Test extraction when there are no thinking content blocks."""
        response = CompletionResponse(
            content=[
                ContentBlock(type="text", text="Here's my response."),
                ToolUseContent(
                    type="tool_use",
                    id="tool_123",
                    name="test_tool",
                    input={"param": "value"},
                ),
            ],
            usage=Usage(input_tokens=100, output_tokens=50),
        )

        reasoning_steps = anthropic_provider._extract_reasoning_steps(response)  # pyright: ignore[reportPrivateUsage]

        assert reasoning_steps is None

    def test_extract_reasoning_steps_empty_content(self, anthropic_provider: AnthropicProvider):
        """Test extraction with empty content list."""
        response = CompletionResponse(
            content=[],
            usage=Usage(input_tokens=100, output_tokens=50),
        )

        reasoning_steps = anthropic_provider._extract_reasoning_steps(response)  # pyright: ignore[reportPrivateUsage]

        assert reasoning_steps is None


class TestThinkingStreamingDeltas:
    def test_handle_content_block_delta_with_thinking(self, anthropic_provider: AnthropicProvider):
        """Test handling of thinking deltas in streaming."""

        _raw_completion = RawCompletion(response="", usage=LLMUsage())
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer] = {}

        # Create a chunk with thinking delta
        chunk = CompletionChunk(
            type="content_block_delta",
            index=0,
            delta=ThinkingDelta(
                type="thinking_delta",
                thinking="I need to analyze this request...",
            ),
        )

        delta = anthropic_provider._handle_content_block_delta(  # pyright: ignore[reportPrivateUsage]
            chunk,
            tool_call_request_buffer,
        )

        assert delta.content == "I need to analyze this request..."
        assert delta.reasoning_steps == "I need to analyze this request..."
        assert delta.tool_calls == []

    def test_handle_content_block_delta_with_signature(self, anthropic_provider: AnthropicProvider):
        """Test handling of signature deltas in streaming."""

        _raw_completion = RawCompletion(response="", usage=LLMUsage())
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer] = {}

        # Create a chunk with signature delta
        chunk = CompletionChunk(
            type="content_block_delta",
            index=0,
            delta=SignatureDelta(
                type="signature_delta",
                signature="sig_456",
            ),
        )

        delta = anthropic_provider._handle_content_block_delta(  # pyright: ignore[reportPrivateUsage]
            chunk,
            tool_call_request_buffer,
        )

        assert delta.content == ""  # Signature deltas don't contribute to text output
        assert delta.reasoning_steps is None
        assert delta.tool_calls == []

    def test_stream_with_thinking_deltas(self, anthropic_provider: AnthropicProvider):
        """Test streaming with thinking deltas integrated."""
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer] = {}

        # Test sequence of thinking deltas
        thinking_events = [
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {
                    "type": "thinking_delta",
                    "thinking": "First, I need to understand the problem...",
                },
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {
                    "type": "thinking_delta",
                    "thinking": "Now I should consider the options...",
                },
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {
                    "type": "signature_delta",
                    "signature": "thinking_signature_123",
                },
            },
        ]

        reasoning_content = ""
        for event in thinking_events:
            delta = anthropic_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
                json.dumps(event).encode(),
                raw_completion,
                tool_call_request_buffer,
            )

            if delta.reasoning_steps:
                reasoning_content += delta.reasoning_steps

        assert reasoning_content == "First, I need to understand the problem...Now I should consider the options..."
