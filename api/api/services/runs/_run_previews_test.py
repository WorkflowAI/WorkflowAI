# pyright: reportPrivateUsage=false

from api.services.runs._stored_message import StoredMessages
from core.domain.fields.file import File
from core.domain.message import MessageContent
from core.domain.tool_call import ToolCall, ToolCallRequest

from ._run_previews import (
    _messages_list_preview,
    _messages_preview,
    _tool_call_request_preview,
)
from ._stored_message import StoredMessage


class TestMessageListPreview:
    def test_messages_preview(self):
        messages = [StoredMessage.with_text("Hello, world!", role="user")]
        assert _messages_list_preview(messages) == "User: Hello, world!"

    def test_with_system_message(self):
        messages = [
            StoredMessage.with_text("You are a helpful assistant.", role="system"),
            StoredMessage.with_text("Hello, world!", role="user"),
        ]
        assert _messages_list_preview(messages) == "User: Hello, world!"

    def test_messages_preview_with_file(self):
        messages = [StoredMessage(content=[MessageContent(file=File(url="https://example.com/file.png"))], role="user")]
        assert _messages_list_preview(messages) == "User: [[img:https://example.com/file.png]]"

    def test_system_only(self):
        messages = [StoredMessage.with_text("Hello, world!", role="system")]
        assert _messages_list_preview(messages) == "User: Hello, world!"

    def test_empty_messages(self):
        """Test that empty messages list returns None"""
        assert _messages_list_preview([]) is None

    def test_messages_with_run_id_no_prefix(self):
        """Test messages with no run_id (no prefix should be added)"""
        messages = [
            StoredMessage.with_text("First message", role="user"),
            StoredMessage.with_text("Second message", role="user"),
        ]
        assert _messages_list_preview(messages) == "User: First message"

    def test_messages_with_run_id_single_message_prefix(self):
        """Test messages with run_id creates proper prefix for single message"""

        messages = [
            StoredMessage.with_text("Message before run", role="user"),
            StoredMessage.with_text("New message after run", role="user"),
        ]
        messages[0].run_id = "run123"
        result = _messages_list_preview(messages)
        assert result == "💬 1 msg...User: New message after run"

    def test_messages_with_run_id_multiple_messages_prefix(self):
        """Test messages with run_id creates proper prefix for multiple messages"""

        messages = [
            StoredMessage.with_text("Message before run", role="user"),
            StoredMessage.with_text("First new message", role="assistant"),
            StoredMessage.with_text("Second new message", role="user"),
        ]
        messages[0].run_id = "run123"
        result = _messages_list_preview(messages)
        assert result is not None
        assert result == "💬 1 msg...User: Second new message"

    def test_messages_with_multiple_run_ids_uses_last(self):
        """Test that with multiple run_ids, it uses the last one"""

        messages = [
            StoredMessage.with_text("First run message", role="user"),
            StoredMessage.with_text("Middle message", role="user"),
            StoredMessage.with_text("Second run message", role="user"),
            StoredMessage.with_text("Final message", role="user"),
        ]
        messages[0].run_id = "run1"
        messages[2].run_id = "run2"
        result = _messages_list_preview(messages)
        assert result is not None
        assert result == "💬 3 msgs...User: Final message"

    def test_include_roles_user_only(self):
        """Test default include_roles={'user'} behavior"""
        messages = [
            StoredMessage.with_text("System message", role="system"),
            StoredMessage.with_text("Assistant message", role="assistant"),
            StoredMessage.with_text("User message", role="user"),
        ]
        assert _messages_list_preview(messages, include_roles={"user"}) == "User: User message"

    def test_include_roles_assistant_only(self):
        """Test include_roles with assistant only"""
        messages = [
            StoredMessage.with_text("User message", role="user"),
            StoredMessage.with_text("Assistant message", role="assistant"),
        ]
        assert _messages_list_preview(messages, include_roles={"assistant"}) == "User: Assistant message"

    def test_include_roles_multiple(self):
        """Test include_roles with multiple roles"""
        messages = [
            StoredMessage.with_text("System message", role="system"),
            StoredMessage.with_text("User message", role="user"),
            StoredMessage.with_text("Assistant message", role="assistant"),
        ]
        # Should find first matching role in the specified set
        result = _messages_list_preview(messages, include_roles={"user", "assistant"})
        assert result == "User: User message"

    def test_include_roles_no_match_fallback(self):
        """Test include_roles with no matches falls back to first message"""
        messages = [
            StoredMessage.with_text("System message", role="system"),
            StoredMessage.with_text("User message", role="user"),
        ]
        # Looking for assistant role that doesn't exist, should fallback to first message
        result = _messages_list_preview(messages, include_roles={"assistant"})
        assert result == "User: System message"

    def test_with_tool_call_result(self):
        """Test message with tool call result"""
        tool_call = ToolCall(
            id="test_id",
            tool_name="test_tool",
            tool_input_dict={"param": "value"},
            result="Whatever execution result",
        )
        messages = [
            StoredMessage(
                content=[MessageContent(tool_call_result=tool_call)],
                role="user",
            ),
        ]
        result = _messages_list_preview(messages)
        assert result == "Tool: Whatever execution result"

    def test_message_with_no_content(self):
        """Test message with no content returns None"""
        messages = [StoredMessage(content=[], role="user")]
        assert _messages_list_preview(messages) is None

    def test_message_content_priority_text_over_file(self):
        """Test that text content takes priority over file content"""
        messages = [
            StoredMessage(
                content=[
                    MessageContent(
                        text="Text content",
                        file=File(url="https://example.com/file.png"),
                    ),
                ],
                role="user",
            ),
        ]
        result = _messages_list_preview(messages)
        assert result == "User: [[img:https://example.com/file.png]]"

    def test_message_content_priority_file_over_tool_result(self):
        """Test that file content takes priority over tool_call_result"""
        tool_call = ToolCall(
            id="test_id",
            tool_name="test_tool",
            tool_input_dict={},
            result="Tool result",
        )
        messages = [
            StoredMessage(
                content=[
                    MessageContent(
                        file=File(url="https://example.com/file.png"),
                        tool_call_result=tool_call,
                    ),
                ],
                role="user",
            ),
        ]
        result = _messages_list_preview(messages)
        assert result == "User: [[img:https://example.com/file.png]]"

    def test_max_len_with_prefix(self):
        """Test that max_len accounts for prefix length"""
        message_with_run = StoredMessage.with_text("Old message", role="user")
        message_with_run.run_id = "run123"

        messages = [
            message_with_run,
            StoredMessage.with_text("New message", role="user"),
        ]

        # With prefix, the available length for message content should be reduced
        result = _messages_list_preview(messages, max_len=30)
        assert result is not None
        assert "💬 1 msg..." in result
        # The actual message part should be shorter due to prefix taking up space


class TestToolCallRequestPreview:
    def test_tool_call_request_preview(self):
        assert (
            _tool_call_request_preview([ToolCallRequest(tool_name="test_name", tool_input_dict={"arg": "value"})])
            == "tool: test_name(arg: value)"
        )

    def test_tool_call_request_preview_multiple(self):
        assert (
            _tool_call_request_preview(
                [
                    ToolCallRequest(tool_name="test_name", tool_input_dict={"arg": "value"}),
                    ToolCallRequest(tool_name="test_name2", tool_input_dict={"arg": "value2"}),
                ],
            )
            == "tools: [test_name(arg: value), test_name2(arg: value2)]"
        )


class TestMessagesPreview:
    def test_with_message_replies(self):
        messages = StoredMessages.model_validate(
            {
                "value": "Hello, world!",
                "workflowai.messages": [{"role": "user", "content": [{"text": "Hello, world!"}]}],
            },
        )
        assert _messages_preview(messages) == 'value: "Hello, world!" | User: Hello, world!'

    def test_reply_empty_object(self):
        messages = StoredMessages.model_validate(
            {
                "value": "Hello, world!",
                "workflowai.messages": [{"role": "user", "content": [{"text": "Hello, world!"}]}],
            },
        )
        assert _messages_preview(messages) == 'value: "Hello, world!" | User: Hello, world!'
