from typing import Literal

import pytest

from core.domain.message import MessageDeprecated
from core.providers.base.models import (
    AudioContentDict,
    DocumentContentDict,
    ImageContentDict,
    StandardMessage,
    TextContentDict,
    ToolCallRequestDict,
    ToolCallResultDict,
    message_standard_to_domain,
    message_standard_to_domain_deprecated,
    role_domain_to_standard,
    role_standard_to_domain,
)


class TestRoleFromStandard:
    @pytest.mark.parametrize(
        "role,expected",
        [
            ("system", MessageDeprecated.Role.SYSTEM),
            ("user", MessageDeprecated.Role.USER),
            ("assistant", MessageDeprecated.Role.ASSISTANT),
            (None, MessageDeprecated.Role.USER),
        ],
    )
    def test_from_standard(self, role: Literal["system", "user", "assistant"] | None, expected: MessageDeprecated.Role):
        assert role_standard_to_domain(role) == expected

    @pytest.mark.parametrize("role", MessageDeprecated.Role)
    def test_sanity(self, role: MessageDeprecated.Role):
        assert role_standard_to_domain(role_domain_to_standard(role)) == role


class TestMessageFromStandardDeprecated:
    def test_from_standard_with_string_content(self):
        standard_msg: StandardMessage = {
            "role": "user",
            "content": "Hello world",
        }
        message = message_standard_to_domain_deprecated(standard_msg)
        assert message.role == MessageDeprecated.Role.USER
        assert message.content == "Hello world"
        assert message.files is None

    def test_from_standard_with_complex_content(self):
        text1: TextContentDict = {"type": "text", "text": "First line"}
        text2: TextContentDict = {"type": "text", "text": "Second line"}
        image: ImageContentDict = {"type": "image_url", "image_url": {"url": "http://example.com/image.jpg"}}
        doc: DocumentContentDict = {"type": "document_url", "source": {"url": "http://example.com/doc.pdf"}}
        audio: AudioContentDict = {"type": "audio_url", "audio_url": {"url": "http://example.com/audio.mp3"}}

        standard_msg: StandardMessage = {
            "role": "assistant",
            "content": [text1, text2, image, doc, audio],
        }
        message = message_standard_to_domain_deprecated(standard_msg)
        assert message.role == MessageDeprecated.Role.ASSISTANT
        assert message.content == "First line\nSecond line"
        assert message.files is not None
        assert len(message.files) == 3
        assert message.files[0].url == "http://example.com/image.jpg"
        assert message.files[1].url == "http://example.com/doc.pdf"
        assert message.files[2].url == "http://example.com/audio.mp3"

    def test_from_standard_with_missing_role(self):
        standard_msg: StandardMessage = {
            "role": None,
            "content": "Hello world",
        }
        message = message_standard_to_domain_deprecated(standard_msg)
        assert message.role == MessageDeprecated.Role.USER  # Default role
        assert message.content == "Hello world"

    def test_from_standard_with_invalid_content_type(self):
        text: TextContentDict = {"type": "text", "text": "Valid text"}
        # Note: TypedDict ensures we can't create invalid types at compile time
        # but the function should handle runtime cases gracefully
        invalid_content = {"type": "unknown_type", "data": "Some data"}  # type: ignore

        standard_msg: StandardMessage = {
            "role": "user",
            "content": [text, invalid_content],  # type: ignore
        }
        message = message_standard_to_domain_deprecated(standard_msg)
        assert message.role == MessageDeprecated.Role.USER
        assert message.content == "Valid text"

    def test_from_standard_with_malformed_content(self):
        text: TextContentDict = {"type": "text", "text": "Valid text"}
        # Malformed image content missing required nested structure
        malformed_image = {"type": "image_url", "wrong_key": {"url": "http://example.com/image.jpg"}}  # type: ignore

        standard_msg: StandardMessage = {
            "role": "user",
            "content": [text, malformed_image],  # type: ignore
        }
        message = message_standard_to_domain_deprecated(standard_msg)
        assert message.role == MessageDeprecated.Role.USER
        assert message.content == "Valid text"
        assert message.files is None  # Malformed content should be skipped

    def test_from_standard_with_tool_call_request(self):
        text: TextContentDict = {"type": "text", "text": "Some text"}
        tool_call: ToolCallRequestDict = {
            "type": "tool_call_request",
            "id": "123",
            "tool_name": "test_tool",
            "tool_input_dict": {"param": "value"},
        }

        standard_msg: StandardMessage = {
            "role": "assistant",
            "content": [text, tool_call],
        }
        message = message_standard_to_domain_deprecated(standard_msg)
        assert message.role == MessageDeprecated.Role.ASSISTANT
        assert message.content == "Some text"
        assert message.tool_call_requests is not None
        assert len(message.tool_call_requests) == 1
        assert message.tool_call_requests[0].id == "123"
        assert message.tool_call_requests[0].tool_name == "test_tool"
        assert message.tool_call_requests[0].tool_input_dict == {"param": "value"}

    def test_from_standard_with_tool_call_result(self):
        text: TextContentDict = {"type": "text", "text": "Some text"}
        tool_result: ToolCallResultDict = {
            "type": "tool_call_result",
            "id": "123",
            "tool_name": "test_tool",
            "tool_input_dict": {"param": "value"},
            "result": {"output": "success"},
            "error": None,
        }

        standard_msg: StandardMessage = {
            "role": "assistant",
            "content": [text, tool_result],
        }
        message = message_standard_to_domain_deprecated(standard_msg)
        assert message.role == MessageDeprecated.Role.ASSISTANT
        assert message.content == "Some text"
        assert message.tool_call_results is not None
        assert len(message.tool_call_results) == 1
        assert message.tool_call_results[0].id == "123"
        assert message.tool_call_results[0].tool_name == "test_tool"
        assert message.tool_call_results[0].tool_input_dict == {"param": "value"}
        assert message.tool_call_results[0].result == {"output": "success"}
        assert message.tool_call_results[0].error is None


class TestMessageFromStandard:
    def test_from_standard_with_string_content(self):
        standard_msg: StandardMessage = {
            "role": "user",
            "content": "Hello world",
        }
        message = message_standard_to_domain(standard_msg)
        assert message.role == "user"
        assert len(message.content) == 1
        assert message.content[0].text == "Hello world"

    def test_from_standard_with_complex_content(self):
        text1: TextContentDict = {"type": "text", "text": "First line"}
        text2: TextContentDict = {"type": "text", "text": "Second line"}
        image: ImageContentDict = {"type": "image_url", "image_url": {"url": "http://example.com/image.jpg"}}
        doc: DocumentContentDict = {"type": "document_url", "source": {"url": "http://example.com/doc.pdf"}}
        audio: AudioContentDict = {"type": "audio_url", "audio_url": {"url": "http://example.com/audio.mp3"}}

        standard_msg: StandardMessage = {
            "role": "assistant",
            "content": [text1, text2, image, doc, audio],
        }
        message = message_standard_to_domain(standard_msg)
        assert message.role == "assistant"
        assert len(message.content) == 5
        assert message.content[0].text == "First line"
        assert message.content[1].text == "Second line"
        assert message.content[2].file is not None
        assert message.content[2].file.url == "http://example.com/image.jpg"
        assert message.content[3].file is not None
        assert message.content[3].file.url == "http://example.com/doc.pdf"
        assert message.content[4].file is not None
        assert message.content[4].file.url == "http://example.com/audio.mp3"

    def test_from_standard_with_missing_role(self):
        standard_msg: StandardMessage = {
            "role": None,
            "content": "Hello world",
        }
        message = message_standard_to_domain(standard_msg)
        assert message.role == "user"  # Default role
        assert len(message.content) == 1
        assert message.content[0].text == "Hello world"

    def test_from_standard_with_tool_call_request(self):
        text: TextContentDict = {"type": "text", "text": "Some text"}
        tool_call: ToolCallRequestDict = {
            "type": "tool_call_request",
            "id": "123",
            "tool_name": "test_tool",
            "tool_input_dict": {"param": "value"},
        }

        standard_msg: StandardMessage = {
            "role": "assistant",
            "content": [text, tool_call],
        }
        message = message_standard_to_domain(standard_msg)
        assert message.role == "assistant"
        assert len(message.content) == 2
        assert message.content[0].text == "Some text"
        assert message.content[1].tool_call_request is not None
        assert message.content[1].tool_call_request.id == "123"
        assert message.content[1].tool_call_request.tool_name == "test_tool"
        assert message.content[1].tool_call_request.tool_input_dict == {"param": "value"}

    def test_from_standard_with_tool_call_result(self):
        text: TextContentDict = {"type": "text", "text": "Some text"}
        tool_result: ToolCallResultDict = {
            "type": "tool_call_result",
            "id": "123",
            "tool_name": "test_tool",
            "tool_input_dict": {"param": "value"},
            "result": {"output": "success"},
            "error": None,
        }

        standard_msg: StandardMessage = {
            "role": "assistant",
            "content": [text, tool_result],
        }
        message = message_standard_to_domain(standard_msg)
        assert message.role == "assistant"
        assert len(message.content) == 2
        assert message.content[0].text == "Some text"
        assert message.content[1].tool_call_result is not None
        assert message.content[1].tool_call_result.id == "123"
        assert message.content[1].tool_call_result.tool_name == "test_tool"
        assert message.content[1].tool_call_result.tool_input_dict == {"param": "value"}
        assert message.content[1].tool_call_result.result == {"output": "success"}
        assert message.content[1].tool_call_result.error is None
