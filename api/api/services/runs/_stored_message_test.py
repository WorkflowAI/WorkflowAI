from core.domain.fields.file import File, FileWithKeyPath
from core.domain.message import MessageContent
from tests import models as test_models

from ._stored_message import StoredMessage, StoredMessages


class TestStoredMessageModelHash:
    def test_same_order_within_message_type(self):
        # A first message
        m = StoredMessage(
            role="user",
            content=[
                MessageContent(text="Hello, world!"),
                MessageContent(text="world 1"),
                MessageContent(file=File(url="https://example.com/file.txt")),
                MessageContent(text="hello", tool_call_request=test_models.tool_call_request()),
                MessageContent(tool_call_result=test_models.tool_call()),
            ],
        )
        # A second message ordered differently (ordered within a message type is maintained)
        m1 = StoredMessage(
            role="user",
            content=[
                MessageContent(file=File(url="https://example.com/file.txt")),
                MessageContent(text="hello", tool_call_request=test_models.tool_call_request()),
                MessageContent(text="Hello, world!"),
                MessageContent(text="world 1"),
                MessageContent(tool_call_result=test_models.tool_call()),
            ],
        )
        assert m.model_hash() == m1.model_hash()

    def test_different_order_within_message_type(self):
        # A first message
        m = StoredMessage(
            role="user",
            content=[
                MessageContent(text="Hello, world!"),
                MessageContent(text="world 1"),
            ],
        )
        # A second message ordered differently (ordered within a message type is maintained)
        m1 = StoredMessage(
            role="user",
            content=[
                MessageContent(text="world 1"),
                MessageContent(text="Hello, world!"),
            ],
        )
        assert m.model_hash() != m1.model_hash()

    def test_extra_file_content_is_ignored(self):
        m = StoredMessage(
            role="user",
            content=[
                MessageContent(
                    file=FileWithKeyPath(
                        format="bla",
                        url="https://example.com/file.txt",
                        key_path=["key1", "key2"],
                    ),
                ),
            ],
        )
        m1 = StoredMessage(
            role="user",
            content=[MessageContent(file=File(url="https://example.com/file.txt"))],
        )
        assert m.model_hash() == m1.model_hash()

        m1.content[0].file.url = "https://example.com/file.txt2"  # type: ignore
        assert m.model_hash() != m1.model_hash(), "sanity check"


class TestDumpForInput:
    def test_dump_for_input_with_none_field(self):
        m = StoredMessages.model_validate(
            {
                "whatever": None,
                "workflowai.messages": [
                    {
                        "role": "user",
                        "content": [{"file": {"url": "https://example.com/file"}}],
                    },
                ],
            },
        )
        assert m.dump_for_input() == {
            "whatever": None,
            "workflowai.messages": [
                {
                    "role": "user",
                    "content": [{"file": {"url": "https://example.com/file"}}],
                },
            ],
        }
