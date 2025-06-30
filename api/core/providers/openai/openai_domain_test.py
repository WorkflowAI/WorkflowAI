import json
from typing import Any, cast

import pytest

from core.domain.errors import UnpriceableRunError
from core.domain.fields.file import File
from core.domain.message import MessageDeprecated
from core.domain.models import Model
from core.domain.tool import Tool as DomainTool
from core.providers.base.models import StandardMessage, ToolCallResultDict
from core.providers.base.provider_error import FailedGenerationError, ProviderError
from core.providers.openai.openai_domain import (
    AudioContent,
    CompletionResponse,
    ImageContent,
    OpenAIError,
    OpenAIMessage,
    OpenAIToolMessage,
    StreamedResponse,
    TextContent,
    Tool,
    ToolCall,
    ToolCallFunction,
    parse_tool_call_or_raise,
)


def test_streamed_response_init():
    streamed = b'{"id":"chatcmpl-9iYcb4Ciq3vzot8MbmzePysMilDIT","object":"chat.completion.chunk","created":1720406545,"model":"gpt-4o-2024-05-13","system_fingerprint":"fp_d576307f90","choices":[{"index":0,"delta":{"role":"assistant","content":""},"logprobs":null,"finish_reason":null}]}'
    raw = StreamedResponse.model_validate_json(streamed)
    assert raw.choices[0].delta.content == ""


@pytest.mark.parametrize(
    "payload",
    [
        """{"error":{"message":"'messages' must contain the word 'json' in some form, to use 'response_format' of type 'json_object'.","type":"invalid_request_error","param":"messages","code":null}}""",
    ],
)
def test_error(payload: str):
    assert OpenAIError.model_validate_json(payload)


class TestCompletionResponse:
    def test_weird_payload(self):
        payload = {"choices": [{"message": {"refusal": None, "role": "assistant"}}]}
        assert CompletionResponse.model_validate(payload)

    def test_null_content(self):
        payload = {"choices": [{"message": {"refusal": None, "role": "assistant", "content": None}}]}
        assert CompletionResponse.model_validate(payload)


class TestStreamedResponse:
    def test_null_content(self):
        payload = {
            "choices": [
                {
                    "content_filter_results": {},
                    "delta": {"content": None, "refusal": "", "role": "assistant"},
                    "finish_reason": None,
                    "index": 0,
                    "logprobs": None,
                },
            ],
            "created": 1737500894,
            "id": "chatcmpl-AsHdu5odVgvvULSVOIYiJ3ANKcbU1",
            "model": "gpt-4o-2024-11-20",
            "object": "chat.completion.chunk",
            "system_fingerprint": "fp_f3927aa00d",
            "usage": None,
        }
        val = StreamedResponse.model_validate(payload)
        assert val.choices[0].delta.content is None

    def test_streamed_missing_content(self):
        streamed = b'{"id":"chatcmpl-9iYe8rHP2EGOXWywPICQw1pnrrCAz","object":"chat.completion.chunk","created":1720406640,"model":"gpt-4o-2024-05-13","system_fingerprint":"fp_4008e3b719","choices":[{"index":0,"delta":{},"logprobs":null,"finish_reason":"stop"}]}'
        raw = StreamedResponse.model_validate_json(streamed)
        assert raw.choices[0].delta.content is None


class TestOpenAIMessageTokenCount:
    def test_token_count_for_text_message(self):
        message = OpenAIMessage(content="Hello, world!", role="user")
        assert message.token_count(Model.GPT_4O_2024_08_06) == 4

    def test_token_count_for_text_content_message(self):
        message = OpenAIMessage(
            content=[TextContent(text="Hello, world!"), TextContent(text="Hello, world!")],
            role="user",
        )
        assert message.token_count(Model.GPT_4O_2024_08_06) == 8

    def test_token_count_for_image_message_raises(self):
        message = OpenAIMessage(
            content=[ImageContent(image_url=ImageContent.URL(url="https://example.com/image.png"))],
            role="user",
        )
        with pytest.raises(UnpriceableRunError):
            message.token_count(Model.GPT_4O_2024_08_06)


class TestOpenAIMessageWithAudio:
    def test_audio_message_content_structure(self):
        message = OpenAIMessage(
            content=[AudioContent(input_audio=AudioContent.AudioData(data="base64data", format="mp3"))],
            role="user",
        )
        assert isinstance(message.content, list)
        assert len(message.content) == 1
        assert isinstance(message.content[0], AudioContent)
        assert message.content[0].input_audio.data == "base64data"
        assert message.content[0].input_audio.format == "mp3"

    def test_audio_message_content_structure_from_file(self):
        message = OpenAIMessage(
            content=[AudioContent.from_file(File(content_type="audio/mpeg", data="base64data=="))],
            role="user",
        )
        assert isinstance(message.content, list)
        assert len(message.content) == 1
        assert isinstance(message.content[0], AudioContent)
        assert message.content[0].input_audio.data == "base64data=="
        assert message.content[0].input_audio.format == "mp3"

    def test_audio_message_content_structure_from_file_with_text(self):
        message = OpenAIMessage(
            content=[
                AudioContent.from_file(File(content_type="audio/mpeg", data="base64dataaudio1")),
                TextContent(text="Hello, world!"),
                AudioContent.from_file(File(content_type="audio/wav", data="base64dataaudio2")),
            ],
            role="user",
        )
        assert isinstance(message.content, list)
        assert len(message.content) == 3
        assert isinstance(message.content[0], AudioContent)
        assert isinstance(message.content[1], TextContent)
        assert isinstance(message.content[2], AudioContent)
        assert message.content[0].input_audio.data == "base64dataaudio1"
        assert message.content[0].input_audio.format == "mp3"
        assert message.content[1].text == "Hello, world!"
        assert message.content[2].input_audio.data == "base64dataaudio2"
        assert message.content[2].input_audio.format == "wav"

    def test_audio_message_content_structure_from_file_with_text_and_image(self):
        message = OpenAIMessage(
            content=[
                AudioContent.from_file(File(content_type="audio/mpeg", data="base64dataaudio1")),
                TextContent(text="Hello, world!"),
                ImageContent.from_file(File(content_type="image/png", data="base64dataimage1")),
            ],
            role="user",
        )
        assert isinstance(message.content, list)
        assert len(message.content) == 3
        assert isinstance(message.content[0], AudioContent)
        assert isinstance(message.content[1], TextContent)
        assert isinstance(message.content[2], ImageContent)

    def test_audio_message_from_file_unknown_format(self):
        with pytest.raises(ProviderError) as e:
            AudioContent.from_file(File(content_type="audio/flac", data="base64data=="))
        assert e.value.code == "failed_generation"
        assert e.value.status_code == 400


class TestOpenAIMessageFromDomain:
    def test_text_before_files(self):
        message = MessageDeprecated(
            content="Hello",
            files=[
                File(content_type="image/png", data="image_dat"),
                File(content_type="audio/wav", data="audio_dat"),
            ],
            role=MessageDeprecated.Role.USER,
        )
        openai_message = OpenAIMessage.from_domain(message)
        assert isinstance(openai_message.content, list)
        assert len(openai_message.content) == 3
        assert isinstance(openai_message.content[0], TextContent)
        assert openai_message.content[0].text == "Hello"
        assert isinstance(openai_message.content[1], ImageContent)
        assert isinstance(openai_message.content[2], AudioContent)


def test_parse_completion_response_with_tool_calls():
    payload = {
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_Z7KnShzI9f0vfZYUWmPMHiiD",
                            "type": "function",
                            "function": {
                                "name": "fibonacci",
                                "arguments": '{"n":10}',
                            },
                        },
                    ],
                    "refusal": None,
                },
                "logprobs": None,
                "finish_reason": "tool_calls",
            },
        ],
        "usage": {
            "prompt_tokens": 526,
            "completion_tokens": 15,
            "total_tokens": 541,
            "prompt_tokens_details": {
                "cached_tokens": 0,
                "audio_tokens": 0,
            },
            "completion_tokens_details": {
                "reasoning_tokens": 0,
                "audio_tokens": 0,
                "accepted_prediction_tokens": 0,
                "rejected_prediction_tokens": 0,
            },
        },
    }
    assert (completion := CompletionResponse.model_validate(payload))
    assert completion.choices[0].message.tool_calls == [
        ToolCall(
            id="call_Z7KnShzI9f0vfZYUWmPMHiiD",
            type="function",
            function=ToolCallFunction(name="fibonacci", arguments='{"n":10}'),
        ),
    ]


class TestOpenAIToolMessage:
    def test_to_standard_with_json_content(self) -> None:
        # Given
        messages = [
            OpenAIToolMessage(
                tool_call_id="123",
                content='{"key": "value", "number": 42}',
                role="tool",
            ),
        ]

        # When
        result: StandardMessage = OpenAIToolMessage.to_standard(messages)

        # Then
        assert result["role"] == "user"
        assert len(result["content"]) == 1
        tool_result = cast(ToolCallResultDict, result["content"][0])
        assert tool_result["type"] == "tool_call_result"
        assert tool_result["id"] == "123"
        assert tool_result["tool_name"] is None
        assert tool_result["tool_input_dict"] is None
        assert tool_result["error"] is None
        assert tool_result["result"] == {"key": "value", "number": 42}

    def test_to_standard_with_non_json_content(self) -> None:
        # Given
        messages = [
            OpenAIToolMessage(
                tool_call_id="456",
                content="plain text response",
                role="tool",
            ),
        ]

        # When
        result: StandardMessage = OpenAIToolMessage.to_standard(messages)

        # Then
        assert result["role"] == "user"
        assert len(result["content"]) == 1
        tool_result = cast(ToolCallResultDict, result["content"][0])
        assert tool_result["type"] == "tool_call_result"
        assert tool_result["id"] == "456"
        assert tool_result["tool_name"] is None
        assert tool_result["tool_input_dict"] is None
        assert tool_result["error"] is None
        assert tool_result["result"] == {"result": "plain text response"}

    def test_to_standard_with_int_content(self) -> None:
        # Given
        messages = [
            OpenAIToolMessage(
                tool_call_id="456",
                content="123",
                role="tool",
            ),
        ]

        # When
        result: StandardMessage = OpenAIToolMessage.to_standard(messages)

        # Then
        assert result["role"] == "user"
        assert len(result["content"]) == 1
        tool_result = cast(ToolCallResultDict, result["content"][0])
        assert tool_result["type"] == "tool_call_result"
        assert tool_result["id"] == "456"
        assert tool_result["tool_name"] is None
        assert tool_result["tool_input_dict"] is None
        assert tool_result["error"] is None
        assert tool_result["result"] == {"result": "123"}

    def test_to_standard_with_multiple_messages(self) -> None:
        # Given
        messages = [
            OpenAIToolMessage(
                tool_call_id="123",
                content='{"key": "value"}',
                role="tool",
            ),
            OpenAIToolMessage(
                tool_call_id="456",
                content="plain text",
                role="tool",
            ),
            OpenAIToolMessage(
                tool_call_id="789",
                content='{"array": [1, 2, 3]}',
                role="tool",
            ),
        ]

        # When
        result: StandardMessage = OpenAIToolMessage.to_standard(messages)

        # Then
        assert result["role"] == "user"
        assert len(result["content"]) == 3

        # First message
        tool_result_1 = cast(ToolCallResultDict, result["content"][0])
        assert tool_result_1["id"] == "123"
        assert tool_result_1["result"] == {"key": "value"}

        # Second message
        tool_result_2 = cast(ToolCallResultDict, result["content"][1])
        assert tool_result_2["id"] == "456"
        assert tool_result_2["result"] == {"result": "plain text"}

        # Third message
        tool_result_3 = cast(ToolCallResultDict, result["content"][2])
        assert tool_result_3["id"] == "789"
        assert tool_result_3["result"] == {"array": [1, 2, 3]}

    def test_to_standard_with_empty_messages(self) -> None:
        # Given
        messages: list[OpenAIToolMessage] = []

        # When
        result: StandardMessage = OpenAIToolMessage.to_standard(messages)

        # Then
        assert result["role"] == "user"
        assert len(result["content"]) == 0

    def test_to_standard_with_complex_json_content(self) -> None:
        # Given
        complex_json: dict[str, Any] = {
            "nested": {
                "array": [1, 2, {"key": "value"}],
                "null": None,
                "bool": True,
            },
            "empty": {},
            "list": [],
        }
        messages = [
            OpenAIToolMessage(
                tool_call_id="123",
                content=json.dumps(complex_json),
                role="tool",
            ),
        ]

        # When
        result: StandardMessage = OpenAIToolMessage.to_standard(messages)

        # Then
        assert result["role"] == "user"
        assert len(result["content"]) == 1
        tool_result = cast(ToolCallResultDict, result["content"][0])
        assert tool_result["result"] == complex_json


def test_parse_tool_call_or_raise_empty_dict() -> None:
    # Given
    arguments = "{}"

    # When
    result = parse_tool_call_or_raise(arguments)

    # Then
    assert result is None


def test_parse_tool_call_or_raise_valid_json() -> None:
    # Given
    arguments = '{"key": "value", "number": 42}'

    # When
    result = parse_tool_call_or_raise(arguments)

    # Then
    assert result == {"key": "value", "number": 42}


def test_parse_tool_call_or_raise_complex_json() -> None:
    # Given
    arguments = '{"nested": {"array": [1, 2, {"key": "value"}], "null": null, "bool": true}, "empty": {}, "list": []}'

    # When
    result = parse_tool_call_or_raise(arguments)

    # Then
    assert result == {
        "nested": {
            "array": [1, 2, {"key": "value"}],
            "null": None,
            "bool": True,
        },
        "empty": {},
        "list": [],
    }


def test_parse_tool_call_or_raise_invalid_json() -> None:
    # Given
    arguments = '{"invalid": json'

    # When/Then
    with pytest.raises(FailedGenerationError):
        parse_tool_call_or_raise(arguments)


def test_parse_tool_call_or_raise_non_dict_json() -> None:
    # Given
    arguments = '"not a dictionary"'

    # When/Then
    with pytest.raises(FailedGenerationError):
        parse_tool_call_or_raise(arguments)


class TestTool:
    def test_from_domain(self):
        tool = DomainTool(
            name="test",
            description="test",
            input_schema={"type": "object", "properties": {"test": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"test": {"type": "string"}}},
            strict=True,
        )
        openai_tool = Tool.from_domain(tool)
        assert openai_tool.type == "function"
        assert openai_tool.function.name == "test"
        assert openai_tool.function.description == "test"
        assert openai_tool.function.parameters == {"type": "object", "properties": {"test": {"type": "string"}}}
        assert openai_tool.function.strict is True
