from .message import Message, MessageContent, Messages


class TestMessages:
    def test_with_messages(self):
        messages = Messages.with_messages(Message(role="user", content=[MessageContent(text="Hello")]))
        assert len(messages.messages) == 1

    def test_validate_by_alias(self):
        validated = Messages.model_validate(
            {
                "workflowai.messages": [
                    {
                        "role": "user",
                        "content": [
                            {"text": "Hello"},
                        ],
                    },
                ],
            },
        )
        assert len(validated.messages) == 1

    def test_messages_is_ignored(self):
        validated = Messages.model_validate({"messages": "bla"})
        assert len(validated.messages) == 0
