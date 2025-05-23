import pytest

from core.domain.fields.file import File
from core.domain.message import MessageDeprecated
from core.domain.tool_call import ToolCallRequestWithID
from core.providers.mistral.mistral_domain import (
    CompletionChunk,
    DocumentURLChunk,
    ImageURL,
    ImageURLChunk,
    MistralAIMessage,
    MistralError,
    MistralToolCall,
    MistralToolMessage,
    TextChunk,
)
from core.providers.mistral.mistral_provider import MistralAIProvider


def test_streamed_response_init() -> None:
    # Given
    streamed = b'{"id":"chatcmpl-9iYcb4Ciq3vzot8MbmzePysMilDIT","object":"chat.completion.chunk","created":1720406545,"model":"gpt-4o-2024-05-13","system_fingerprint":"fp_d576307f90","choices":[{"index":0,"delta":{"role":"assistant","content":""},"logprobs":null,"finish_reason":null}]}'

    # When
    raw = CompletionChunk.model_validate_json(streamed)

    # Then
    assert raw.choices and raw.choices[0].delta
    assert raw.choices[0].delta.content == ""


def test_streamed_response_final() -> None:
    # Given
    streamed = b'{"id":"chatcmpl-9iYe8rHP2EGOXWywPICQw1pnrrCAz","object":"chat.completion.chunk","created":1720406640,"model":"gpt-4o-2024-05-13","system_fingerprint":"fp_4008e3b719","choices":[{"index":0,"delta":{},"logprobs":null,"finish_reason":"stop"}]}'

    # When
    raw = CompletionChunk.model_validate_json(streamed)

    # Then
    assert raw.choices and raw.choices[0].delta
    assert raw.choices[0].delta.content is None
    assert raw.choices[0].finish_reason == "stop"


@pytest.mark.parametrize(
    "payload",
    [
        """{"msg":"hello"}""",
        """{"message":"hello"}""",
        """{"message":"hello","type":"invalid_request_error"}""",
    ],
)
def test_error(payload: str) -> None:
    # When
    val = MistralError.model_validate_json(payload)

    # Then
    assert val.message == "hello"


# TODO: add tests for token count if we ever count token properly for mistral


class TestMistralAIMessage:
    def test_from_domain_simple_message(self) -> None:
        # Given
        message = MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello world")

        # When
        result = MistralAIMessage.from_domain(message)

        # Then
        assert result.role == "user"
        assert result.content == "Hello world"
        assert result.tool_calls is None

    def test_from_domain_with_image(self) -> None:
        # Given
        message = MessageDeprecated(
            role=MessageDeprecated.Role.USER,
            content="Check this image",
            files=[File(url="https://example.com/image.jpg", content_type="image/jpeg")],
        )

        # When
        result = MistralAIMessage.from_domain(message)

        # Then
        assert result.role == "user"
        assert isinstance(result.content, list)
        assert len(result.content) == 2
        assert isinstance(result.content[0], TextChunk)
        assert result.content[0].text == "Check this image"
        assert isinstance(result.content[1], ImageURLChunk)
        assert result.content[1].image_url.url == "https://example.com/image.jpg"

    def test_from_domain_with_document(self) -> None:
        # Given
        message = MessageDeprecated(
            role=MessageDeprecated.Role.USER,
            content="Check this document",
            files=[File(url="https://example.com/document.pdf", content_type="application/pdf")],
        )

        # When
        result = MistralAIMessage.from_domain(message)

        # Then
        assert result.role == "user"
        assert isinstance(result.content, list)
        assert len(result.content) == 2
        assert isinstance(result.content[0], TextChunk)
        assert result.content[0].text == "Check this document"
        assert isinstance(result.content[1], DocumentURLChunk)
        assert result.content[1].document_url == "https://example.com/document.pdf"

    def test_from_domain_with_tool_calls(self) -> None:
        # Given
        message = MessageDeprecated(
            role=MessageDeprecated.Role.ASSISTANT,
            content="Using calculator",
            tool_call_requests=[
                ToolCallRequestWithID(
                    id="123",
                    tool_name="calculator",
                    tool_input_dict={"operation": "add", "numbers": [1, 2]},
                ),
            ],
        )

        # When
        result = MistralAIMessage.from_domain(message)

        # Then
        assert result.role == "assistant"
        assert result.content == "Using calculator"
        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].function.name == "calculator"
        assert result.tool_calls[0].function.arguments == {"operation": "add", "numbers": [1, 2]}

    def test_to_standard_with_string_content(self) -> None:
        # Given
        message = MistralAIMessage(role="user", content="Hello world")

        # When
        result = message.to_standard()

        # Then
        assert result == {"role": "user", "content": "Hello world"}

    def test_to_standard_with_string_content_and_tool_calls(self) -> None:
        # Given
        message = MistralAIMessage(
            role="assistant",
            content="Using calculator",
            tool_calls=[
                MistralToolCall(
                    id="123",
                    function=MistralToolCall.Function(
                        name="calculator",
                        arguments={"operation": "add", "numbers": [1, 2]},
                    ),
                ),
            ],
        )

        # When
        result = message.to_standard()

        # Then
        assert result == {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Using calculator"},
                {
                    "type": "tool_call_request",
                    "id": "a665a4592",  # tool call id is remapped
                    "tool_name": "calculator",
                    "tool_input_dict": {"operation": "add", "numbers": [1, 2]},
                },
            ],
        }

    def test_to_standard_with_content_list(self) -> None:
        # Given
        message = MistralAIMessage(
            role="user",
            content=[
                TextChunk(text="Hello"),
                ImageURLChunk(image_url=ImageURL(url="https://example.com/image.jpg")),
            ],
        )

        # When
        result = message.to_standard()

        # Then
        assert result == {
            "role": "user",
            "content": [
                {"type": "text", "text": "Hello"},
                {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}},
            ],
        }

    def test_to_standard_with_content_list_and_tool_calls(self) -> None:
        # Given
        message = MistralAIMessage(
            role="assistant",
            content=[
                TextChunk(text="Analyzing image"),
                ImageURLChunk(image_url=ImageURL(url="https://example.com/image.jpg")),
            ],
            tool_calls=[
                MistralToolCall(
                    id="acbdefghi",
                    function=MistralToolCall.Function(
                        name="image_analyzer",
                        arguments={"image_url": "https://example.com/image.jpg"},
                    ),
                ),
            ],
        )

        # When
        result = message.to_standard()

        # Then
        assert result == {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Analyzing image"},
                {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}},
                {
                    "type": "tool_call_request",
                    "id": "acbdefghi",
                    "tool_name": "image_analyzer",
                    "tool_input_dict": {"image_url": "https://example.com/image.jpg"},
                },
            ],
        }


class TestMistralAIMessageToStandard:
    def test_to_standard_simple_without_tool_calls(self) -> None:
        """
        Verify that when there is a simple string content and no tool calls,
        to_standard returns a simple dict.
        """
        msg = MistralAIMessage(role="user", content="Hello world", tool_calls=None)
        standard = msg.to_standard()
        assert standard["role"] == "user"
        assert isinstance(standard["content"], str)
        assert standard["content"] == "Hello world"

    def test_to_standard_with_chunks_and_tool_calls(self) -> None:
        """
        Verify that when the message content is a list of chunks and there is a tool call,
        to_standard converts the chunks and appends a tool_call_request.
        """
        text_chunk = TextChunk(text="Calculation result:")
        tool_call = MistralToolCall(
            id="123456789",
            function=MistralToolCall.Function(
                name="calculator",
                arguments={"operation": "add", "numbers": [1, 2]},
            ),
            index=0,
        )
        msg = MistralAIMessage(
            role="assistant",
            content=[text_chunk],
            tool_calls=[tool_call],
        )
        standard = msg.to_standard()
        # The output is a list merging the text content and the tool call.
        assert isinstance(standard["content"], list)
        # First element: text chunk
        text_standard = standard["content"][0]
        assert text_standard == {"type": "text", "text": "Calculation result:"}
        # Second element: tool call request from the tool_calls list.
        tool_call_standard = standard["content"][1]
        expected_tool_call = {
            "type": "tool_call_request",
            "id": "123456789",
            "tool_name": "calculator",  # assuming the native_tool_name_to_internal is identity
            "tool_input_dict": {"operation": "add", "numbers": [1, 2]},
        }
        assert tool_call_standard == expected_tool_call


class TestMistralToolMessageToStandard:
    def test_tool_message_to_standard(self) -> None:
        """
        Verify that aggregating multiple tool messages using to_standard
        returns a StandardMessage with tool_call_result dictionaries.
        """
        tool_msg1 = MistralToolMessage(
            role="tool",
            tool_call_id="tool1",
            name="analyzer",
            content='{"analysis": "success"}',
        )
        tool_msg2 = MistralToolMessage(
            role="tool",
            tool_call_id="tool2",
            name="summarizer",
            content='{"summary": "all good"}',
        )
        standard = MistralToolMessage.to_standard([tool_msg1, tool_msg2])
        assert standard["role"] == "user"
        assert isinstance(standard["content"], list)
        expected_contents = [
            {
                "type": "tool_call_result",
                "id": "1bc3b0c4b",
                "tool_name": "analyzer",  # assuming identity transformation
                "tool_input_dict": None,
                "result": '{"analysis": "success"}',
                "error": None,
            },
            {
                "type": "tool_call_result",
                "id": "175ad3e3e",
                "tool_name": "summarizer",
                "tool_input_dict": None,
                "result": '{"summary": "all good"}',
                "error": None,
            },
        ]
        assert standard["content"] == expected_contents


class TestStandardizeMessagesProvider:
    def test_standardize_messages_mixed(self) -> None:
        """
        Test the provider's standardize_messages method by mixing tool messages
        with normal messages. The method groups consecutive tool messages.
        """
        # A tool message dict (for MistralToolMessage)
        tool_message = {
            "role": "tool",
            "tool_call_id": "tm1",
            "name": "calculator",
            "content": '{"result": 42}',
        }
        # A normal message dict (for MistralAIMessage)
        normal_message = {
            "role": "user",
            "content": "Hello from user",
        }
        another_normal = {
            "role": "assistant",
            "content": "Response from assistant",
        }
        messages = [tool_message, normal_message, tool_message, another_normal]
        standardized = MistralAIProvider.standardize_messages(messages)
        # Expected: first group from tool_message, followed by a normal message, then a new tool group, and finally a normal message.
        assert len(standardized) == 4

        # First message from tool group
        first = standardized[0]
        assert first["role"] == "user"
        assert isinstance(first["content"], list)
        expected_first = {
            "type": "tool_call_result",
            "id": "ad8a21601",
            "tool_name": "calculator",
            "tool_input_dict": None,
            "result": '{"result": 42}',
            "error": None,
        }
        assert first["content"][0] == expected_first

        # Second message: normal message conversion
        second = standardized[1]
        assert second["role"] == "user"
        assert second["content"] == "Hello from user"

        # Third message: new tool message group
        third = standardized[2]
        assert third["role"] == "user"
        expected_third = {
            "type": "tool_call_result",
            "id": "ad8a21601",
            "tool_name": "calculator",
            "tool_input_dict": None,
            "result": '{"result": 42}',
            "error": None,
        }
        assert third["content"][0] == expected_third

        # Fourth message: normal assistant message
        fourth = standardized[3]
        assert fourth["role"] == "assistant"
        assert fourth["content"] == "Response from assistant"
