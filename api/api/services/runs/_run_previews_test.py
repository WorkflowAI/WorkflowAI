from core.domain.task_io import SerializableTaskIO
from core.domain.tool_call import ToolCallRequest

from ._run_previews import (
    _compute_preview,  # pyright: ignore [reportPrivateUsage]
    _messages_preview,  # pyright: ignore [reportPrivateUsage]
    _tool_call_request_preview,  # pyright: ignore [reportPrivateUsage]
)


class TestMessagesPreview:
    def test_messages_preview(self):
        assert (
            _messages_preview({"messages": [{"role": "user", "content": [{"text": "Hello, world!"}]}]})
            == "Hello, world!"
        )

    def test_with_system_message(self):
        assert (
            _messages_preview(
                {
                    "messages": [
                        {"role": "system", "content": [{"text": "You are a helpful assistant."}]},
                        {"role": "user", "content": [{"text": "Hello, world!"}]},
                    ],
                },
            )
            == "Hello, world!"
        )

    def test_messages_preview_with_file(self):
        assert (
            _messages_preview(
                {"messages": [{"role": "user", "content": [{"file": {"url": "https://example.com/file.png"}}]}]},
            )
            == "[[img:https://example.com/file.png]]"
        )

    def test_system_only(self):
        assert (
            _messages_preview({"messages": [{"role": "system", "content": [{"text": "Hello, world!"}]}]})
            == "Hello, world!"
        )


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


class TestPrivateComputePreview:
    def test_with_message_replies(self):
        assert (
            _compute_preview(
                {
                    "value": "Hello, world!",
                    "workflowai.replies": [{"role": "user", "content": [{"text": "Hello, world!"}]}],
                },
                agent_io=SerializableTaskIO.from_json_schema(
                    {"format": "messages", "type": "object", "properties": {"value": {"type": "string"}}},
                ),
            )
            == 'value: "Hello, world!" | messages: Hello, world!'
        )

    def test_reply_empty_object(self):
        assert (
            _compute_preview(
                {"workflowai.replies": [], "value": "bla"},
                agent_io=SerializableTaskIO.from_json_schema(
                    {"format": "messages", "type": "object", "properties": {"value": {"type": "string"}}},
                ),
            )
            == 'value: "bla"'
        )
