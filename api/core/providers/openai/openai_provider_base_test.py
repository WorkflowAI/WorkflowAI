from typing import Any

import pytest

from core.domain.errors import MaxTokensExceededError
from core.domain.llm_usage import LLMUsage
from core.domain.models import Model, Provider
from core.domain.tool_call import ToolCallRequestWithID
from core.providers.base.abstract_provider import RawCompletion
from core.providers.base.httpx_provider import ParsedResponse
from core.providers.base.streaming_context import StreamingContext
from core.providers.openai.openai_domain import (
    ChoiceDelta,
    StreamedResponse,
    StreamedToolCall,
    StreamedToolCallFunction,
    Usage,
)
from core.providers.openai.openai_provider_base import OpenAIProviderBase, OpenAIProviderBaseConfig
from tests.utils import fixtures_json


class _TestProviderConfig(OpenAIProviderBaseConfig):
    """Test implementation of OpenAIProviderBaseConfig."""

    @property
    def provider(self) -> Provider:
        return Provider.OPEN_AI


class _TestOpenAIProviderBase(OpenAIProviderBase[_TestProviderConfig]):
    """Test implementation of OpenAIProviderBase."""

    @classmethod
    def required_env_vars(cls) -> list[str]:
        return []

    @classmethod
    def name(cls) -> Provider:
        return Provider.OPEN_AI

    @classmethod
    def _default_config(cls, index: int) -> _TestProviderConfig:
        return _TestProviderConfig()

    def default_model(self) -> Model:
        return Model.GPT_3_5_TURBO_0125

    def _request_url(self, model: Model, stream: bool) -> str:
        return "test"

    async def _request_headers(self, request: dict[str, Any], url: str, model: Model) -> dict[str, str]:
        return {}


def test_extract_stream_delta_max_tokens_exceeded() -> None:
    """Test that length finish_reason raises MaxTokensExceededError."""
    provider = _TestOpenAIProviderBase()
    raw_completion = RawCompletion(
        response="",
        usage=LLMUsage(
            prompt_token_count=0,
            completion_token_count=0,
            model_context_window_size=0,
        ),
    )

    event = (
        StreamedResponse(
            choices=[
                ChoiceDelta(
                    index=0,
                    delta=ChoiceDelta.MessageDelta(content="test"),
                    finish_reason="length",
                ),
            ],
        )
        .model_dump_json()
        .encode()
    )

    with pytest.raises(MaxTokensExceededError) as exc_info:
        provider._extract_stream_delta(event, raw_completion, {})  # pyright: ignore[reportPrivateUsage]

    assert "maximum number of tokens was exceeded" in str(exc_info.value)


def test_extract_stream_delta_with_content() -> None:
    """Test successful extraction of content from stream delta."""
    provider = _TestOpenAIProviderBase()
    raw_completion = RawCompletion(
        response="",
        usage=LLMUsage(
            prompt_token_count=0,
            completion_token_count=0,
            model_context_window_size=0,
        ),
    )

    event = (
        StreamedResponse(
            choices=[
                ChoiceDelta(
                    index=0,
                    delta=ChoiceDelta.MessageDelta(content="test content"),
                    finish_reason=None,
                ),
            ],
        )
        .model_dump_json()
        .encode()
    )

    result = provider._extract_stream_delta(event, raw_completion, {})  # pyright: ignore[reportPrivateUsage]

    assert result.content == "test content"
    assert result.tool_calls == []


def test_extract_stream_delta_with_tool_calls() -> None:
    """Test successful extraction of tool calls from stream delta."""
    provider = _TestOpenAIProviderBase()
    raw_completion = RawCompletion(
        response="",
        usage=LLMUsage(
            prompt_token_count=0,
            completion_token_count=0,
            model_context_window_size=0,
        ),
    )

    event = (
        StreamedResponse(
            choices=[
                ChoiceDelta(
                    index=0,
                    delta=ChoiceDelta.MessageDelta(
                        content=None,
                        tool_calls=[
                            StreamedToolCall(
                                id="call_123",
                                type="function",
                                function=StreamedToolCallFunction(
                                    name="test_tool",
                                    arguments='{"arg1": "value1"}',
                                ),
                                index=0,
                            ),
                        ],
                    ),
                    finish_reason=None,
                ),
            ],
        )
        .model_dump_json()
        .encode()
    )

    result = provider._extract_stream_delta(event, raw_completion, tool_call_request_buffer={})  # pyright: ignore[reportPrivateUsage]

    assert result.content == ""
    assert result.tool_calls is not None
    assert len(result.tool_calls) == 1
    tool_call = result.tool_calls[0]
    assert tool_call.id == "call_123"
    assert tool_call.tool_name == "test_tool"
    assert tool_call.tool_input_dict == {"arg1": "value1"}


def test_extract_stream_delta_with_usage() -> None:
    """Test successful extraction of usage information from stream delta."""
    provider = _TestOpenAIProviderBase()
    raw_completion = RawCompletion(
        response="",
        usage=LLMUsage(
            prompt_token_count=0,
            completion_token_count=0,
            model_context_window_size=0,
        ),
    )

    event = (
        StreamedResponse(
            choices=[
                ChoiceDelta(
                    index=0,
                    delta=ChoiceDelta.MessageDelta(content="test"),
                    finish_reason=None,
                ),
            ],
            usage=Usage(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
            ),
        )
        .model_dump_json()
        .encode()
    )

    provider._extract_stream_delta(event, raw_completion, {})  # pyright: ignore[reportPrivateUsage]

    assert raw_completion.usage is not None
    assert raw_completion.usage.prompt_token_count == 10
    assert raw_completion.usage.completion_token_count == 5


def test_extract_stream_delta_empty_choices() -> None:
    """Test handling of response with empty choices."""
    provider = _TestOpenAIProviderBase()
    raw_completion = RawCompletion(
        response="",
        usage=LLMUsage(
            prompt_token_count=0,
            completion_token_count=0,
            model_context_window_size=0,
        ),
    )

    event = StreamedResponse(choices=[]).model_dump_json().encode()

    result = provider._extract_stream_delta(event, raw_completion, {})  # pyright: ignore[reportPrivateUsage]

    assert result == ParsedResponse(content="", reasoning_steps=None, tool_calls=None)


def test_standardize_messages_with_tool_messages() -> None:
    """Test standardization of messages including tool messages."""
    messages = [
        {
            "role": "user",
            "content": "Hello",
        },
        {
            "role": "tool",
            "tool_call_id": "test_tool",
            "content": '{"arg1": "value1"}',
        },
        {
            "role": "tool",
            "tool_call_id": "test_tool_2",
            "content": '{"arg2": "value2"}',
        },
    ]

    result = _TestOpenAIProviderBase.standardize_messages(messages)  # pyright: ignore[reportPrivateUsage]

    assert result == [
        {"role": "user", "content": "Hello"},
        {
            "role": "user",
            "content": [
                {
                    "id": "test_tool",
                    "type": "tool_call_result",
                    "tool_name": None,
                    "tool_input_dict": None,
                    "result": {"arg1": "value1"},
                    "error": None,
                },
                {
                    "id": "test_tool_2",
                    "type": "tool_call_result",
                    "tool_name": None,
                    "tool_input_dict": None,
                    "result": {"arg2": "value2"},
                    "error": None,
                },
            ],
        },
    ]


def test_standardize_messages_empty_list() -> None:
    """Test standardization of an empty message list."""
    messages: list[dict[str, Any]] = []

    result = _TestOpenAIProviderBase.standardize_messages(messages)  # pyright: ignore[reportPrivateUsage]

    assert len(result) == 0


def test_standardize_messages_with_consecutive_tool_messages() -> None:
    """Test standardization of consecutive tool messages are grouped together."""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "tool", "tool_call_id": "test_tool", "content": '{"arg1": "value1"}'},
        {"role": "tool", "tool_call_id": "test_tool_2", "content": '{"arg2": "value2"}'},
        {"role": "assistant", "content": "Processing results..."},
        {"role": "tool", "tool_call_id": "test_tool_3", "content": '{"arg3": "value3"}'},
        {"role": "tool", "tool_call_id": "test_tool_4", "content": '{"arg4": "value4"}'},
    ]

    result = _TestOpenAIProviderBase.standardize_messages(messages)  # pyright: ignore[reportPrivateUsage]

    assert result == [
        {"role": "user", "content": "Hello"},
        {
            "role": "user",
            "content": [
                {
                    "id": "test_tool",
                    "type": "tool_call_result",
                    "tool_name": None,
                    "tool_input_dict": None,
                    "result": {"arg1": "value1"},
                    "error": None,
                },
                {
                    "id": "test_tool_2",
                    "type": "tool_call_result",
                    "tool_name": None,
                    "tool_input_dict": None,
                    "result": {"arg2": "value2"},
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
                    "tool_name": None,
                    "tool_input_dict": None,
                    "result": {"arg3": "value3"},
                    "error": None,
                },
                {
                    "id": "test_tool_4",
                    "type": "tool_call_result",
                    "tool_name": None,
                    "tool_input_dict": None,
                    "result": {"arg4": "value4"},
                    "error": None,
                },
            ],
        },
    ]


def test_extract_stream_delta_with_incomplete_tool_call() -> None:
    """Test that incomplete JSON in tool call arguments results in no tool call being added."""
    provider = _TestOpenAIProviderBase()
    raw_completion = RawCompletion(
        response="",
        usage=LLMUsage(
            prompt_token_count=0,
            completion_token_count=0,
            model_context_window_size=0,
        ),
    )

    # Create an event with a tool call that has incomplete JSON (missing closing brace)
    event = (
        StreamedResponse(
            choices=[
                ChoiceDelta(
                    index=0,
                    delta=ChoiceDelta.MessageDelta(
                        content=None,
                        tool_calls=[
                            StreamedToolCall(
                                id="call_456",
                                type="function",
                                function=StreamedToolCallFunction(
                                    name="incomplete_tool",
                                    arguments='{"arg1": "value1"',
                                ),
                                index=0,
                            ),
                        ],
                    ),
                    finish_reason=None,
                ),
            ],
        )
        .model_dump_json()
        .encode()
    )

    result = provider._extract_stream_delta(event, raw_completion, {})  # pyright: ignore[reportPrivateUsage]

    assert result.content == ""
    assert result.tool_calls == []


def test_extract_stream_delta_consecutive_fragments() -> None:
    """Test that multiple consecutive SSE events with partial JSON fragments for a tool call are correctly accumulated to form a valid JSON tool call."""
    provider = _TestOpenAIProviderBase()
    raw_completion = RawCompletion(
        response="",
        usage=LLMUsage(
            prompt_token_count=0,
            completion_token_count=0,
            model_context_window_size=0,
        ),
    )

    # Fragments that when concatenated form a valid JSON: {"query": "latest Jazz Lakers score February 2025"}
    fragments = [
        '{"',
        "query",
        '":"',
        "latest",
        " Jazz",
        " Lakers",
        " score",
        " February",
        " 202",
        "5",
        '"}',
    ]

    stream_context = StreamingContext(RawCompletion(response="", usage=LLMUsage()))

    # Process all fragments except the last one; these should not yield a complete tool call
    for fragment in fragments[:-1]:
        event = (
            StreamedResponse(
                choices=[
                    ChoiceDelta(
                        index=0,
                        delta=ChoiceDelta.MessageDelta(
                            content=None,
                            tool_calls=[
                                StreamedToolCall(
                                    id="complex_call",
                                    type="function",
                                    function=StreamedToolCallFunction(
                                        name="complex_tool",
                                        arguments=fragment,
                                    ),
                                    index=0,
                                ),
                            ],
                        ),
                        finish_reason=None,
                    ),
                ],
            )
            .model_dump_json()
            .encode()
        )
        result = provider._extract_stream_delta(event, raw_completion, stream_context.tool_call_request_buffer)  # pyright: ignore[reportPrivateUsage]
        # Before the final fragment, no complete tool call should be formed
        assert result.tool_calls == []

    # Process the final fragment which should complete the JSON
    final_fragment = fragments[-1]
    final_event = (
        StreamedResponse(
            choices=[
                ChoiceDelta(
                    index=0,
                    delta=ChoiceDelta.MessageDelta(
                        content=None,
                        tool_calls=[
                            StreamedToolCall(
                                id="complex_call",
                                type="function",
                                function=StreamedToolCallFunction(
                                    name="complex_tool",
                                    arguments=final_fragment,
                                ),
                                index=0,
                            ),
                        ],
                    ),
                    finish_reason=None,
                ),
            ],
        )
        .model_dump_json()
        .encode()
    )
    final_result = provider._extract_stream_delta(final_event, raw_completion, stream_context.tool_call_request_buffer)  # pyright: ignore[reportPrivateUsage]

    # Now, the accumulated fragments should form a valid JSON tool call
    assert final_result.tool_calls is not None
    assert len(final_result.tool_calls) == 1
    tool_call = final_result.tool_calls[0]
    assert tool_call.id == "complex_call"
    assert tool_call.tool_name == "complex_tool"
    assert tool_call.tool_input_dict == {"query": "latest Jazz Lakers score February 2025"}


def test_extract_stream_delta_from_fixture() -> None:
    """Test processing streaming tool call events from a fixture file and verify aggregated tool calls."""
    import json

    provider = _TestOpenAIProviderBase()
    raw_completion = RawCompletion(
        response="",
        usage=LLMUsage(
            prompt_token_count=0,
            completion_token_count=0,
            model_context_window_size=0,
        ),
    )

    data = fixtures_json("openai", "stream_with_tools.json")

    # Feed each event sequentially to the provider

    tool_calls: list[ToolCallRequestWithID] = []

    stream_context = StreamingContext(RawCompletion(response="", usage=LLMUsage()))

    for event in data["events"]:
        event_bytes = json.dumps(event).encode("utf-8")
        response = provider._extract_stream_delta(event_bytes, raw_completion, stream_context.tool_call_request_buffer)  # pyright: ignore[reportPrivateUsage]
        tool_calls.extend(response.tool_calls or [])

    assert tool_calls == [
        ToolCallRequestWithID(
            tool_name="get_temperature",
            tool_input_dict={"city_code": "125321"},
            id="call_AU0Fw2imWtuWlmaLHXnwkZCQ",
        ),
        ToolCallRequestWithID(
            tool_name="get_rain_probability",
            tool_input_dict={"city_code": "125321"},
            id="call_VtkV4ZpNh3nHxS84JnCiriVj",
        ),
        ToolCallRequestWithID(
            tool_name="get_wind_speed",
            tool_input_dict={"city_code": "125321"},
            id="call_wfkYlsz09dYJvzoXn7spvgpy",
        ),
        ToolCallRequestWithID(
            tool_name="get_weather_conditions",
            tool_input_dict={"city_code": "125321"},
            id="call_3oHEEsy8LFQectXu7wTSOiPx",
        ),
    ]


@pytest.mark.parametrize(
    "messages,expected_token_count",
    [
        (
            # Single simple text message
            [{"role": "user", "content": "Hello, world!"}],
            # 3 (boilerplate) + (4 (message boilerplate) + 4 (tokens in "Hello, world!")) = 11
            11,
        ),
        (
            # Multiple text messages
            [
                {"role": "user", "content": "Hello, world!"},
                {"role": "assistant", "content": "Hi there!"},
            ],
            # 3 (boilerplate) + 2 * (4 (message boilerplate)) + 4 (tokens in "Hello, world!") + 3 (tokens in "Hi there!") = 18
            18,
        ),
        (
            # Empty message list
            [],
            # 3 (boilerplate only)
            3,
        ),
        (
            # Message with empty content
            [{"role": "user", "content": ""}],
            # 3 (boilerplate) + 4 (message boilerplate) + 0 (tokens in empty content) = 7
            7,
        ),
        (
            # Message with tool call
            [{"role": "tool", "tool_call_id": "tc_valid", "content": "Hello"}],
            8,  # 3 (boilerplate) + 4 (message boilerplate) + 1 (tool call)
        ),
        (
            # Message with tool call and other messages
            [
                {"role": "tool", "tool_call_id": "tc_valid", "content": "Hello"},
                {"role": "user", "content": "Hello, world!"},
            ],
            16,  # 3 (boilerplate) + 4 (message boilerplate) + 1 (tool call) + 4 (message boilerplate) + 4 (tokens in "Hello, world!")
        ),
    ],
)
def test_compute_prompt_token_count(messages: list[dict[str, Any]], expected_token_count: int) -> None:
    """Test token count calculation for different message configurations."""
    provider = _TestOpenAIProviderBase()
    model = Model.GPT_4O_2024_08_06

    result = provider._compute_prompt_token_count(messages, model)  # pyright: ignore[reportPrivateUsage]
    # This is a high-level smoke test that '_compute_prompt_token_count' does not raise and return a value
    assert result == expected_token_count
