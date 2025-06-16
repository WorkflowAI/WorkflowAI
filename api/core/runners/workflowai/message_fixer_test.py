# pyright: reportPrivateUsage=false

from typing import Any, Callable

import pytest

from core.domain.message import Message, MessageContent, Messages
from core.domain.tool_call import ToolCall, ToolCallRequestWithID

from .message_fixer import MessageAutofixer


class TestMessageAutofixer:
    @pytest.fixture()
    def autofix(self):
        # Just to make sure we keep the original list in place
        def _autofix(messages: list[Message]):
            cloned = Messages.with_messages(*messages).model_copy(deep=True)
            return MessageAutofixer().fix(cloned.messages)

        return _autofix

    def _content_tc_request(self, id: str = "1", name: str = "test", input_dict: Any = {"hello": "world"}):
        return MessageContent(
            tool_call_request=ToolCallRequestWithID(
                id=id,
                tool_name=name,
                tool_input_dict=input_dict,
            ),
        )

    def _content_tc_result(self, id: str = "1", name: str = "", input_dict: Any = {}, result: Any = "Hello, world!"):
        # When receiving from the OpenAI API, the tool call result name and input dict are empty
        return MessageContent(
            tool_call_result=ToolCall(
                id=id,
                tool_name=name,
                tool_input_dict=input_dict,
                result=result,
            ),
        )

    def test_text_only(self, autofix: Callable[[list[Message]], list[Message]]):
        messages = [
            Message(role="user", content=[MessageContent(text="Hello, world!")]),
            Message(role="assistant", content=[MessageContent(text="Hello, world!")]),
        ]

        assert autofix(messages) == messages

    def test_single_tool_call_request_with_result(self, autofix: Callable[[list[Message]], list[Message]]):
        """Simplest case where a tool call request is followed by a tool call result should
        be left unchanged"""

        messages = [
            Message(role="user", content=[MessageContent(text="Hello, world!")]),
            Message(
                role="assistant",
                content=[
                    MessageContent(text="Hello, world!"),
                    self._content_tc_request(),
                    MessageContent(text="Hello, world 2!"),
                ],
            ),
            Message(role="user", content=[self._content_tc_result()]),
        ]
        # Here we can't check for plain equality since the tool call result should have been
        # Updated to include the tool name and input dict
        fixed = autofix(messages)
        assert len(fixed) == len(messages)
        # First two messages should be unchanged
        assert fixed[:-1] == messages[:-1]
        # Latest message should include the tool name and input dict
        assert fixed[-1] == Message(
            role="user",
            content=[self._content_tc_result(name="test", input_dict={"hello": "world"})],
        )

    def test_multiple_tool_calls(self, autofix: Callable[[list[Message]], list[Message]]):
        messages = [
            Message(role="user", content=[MessageContent(text="Hello, world!")]),
            Message(
                role="assistant",
                content=[
                    MessageContent(text="Hello, world!"),
                    self._content_tc_request(),
                    self._content_tc_request(id="2", name="test2", input_dict={"hello": "world2"}),
                ],
            ),
            # OpenAI will return tool call results in separate messages that should be aggregated
            Message(
                role="user",
                content=[self._content_tc_result()],
            ),
            Message(
                role="user",
                content=[self._content_tc_result(id="2", result="Hello, world 2!")],
            ),
        ]

        fixed = autofix(messages)
        assert len(fixed) == 3  # one less than the original number of messages
        # First two messages should be unchanged
        assert fixed[:2] == messages[:2]
        # Latest message should contain both tool call results
        assert fixed[-1] == Message(
            role="user",
            content=[
                self._content_tc_result(name="test", input_dict={"hello": "world"}),
                self._content_tc_result(id="2", result="Hello, world 2!", name="test2", input_dict={"hello": "world2"}),
            ],
        )

    def test_tool_call_request_in_user_message(self, autofix: Callable[[list[Message]], list[Message]]):
        messages = [
            Message(role="user", content=[self._content_tc_request()]),
        ]
        with pytest.raises(ValueError, match="Only assistant messages can have tool calls"):
            autofix(messages)

    def test_duplicate_tool_call_request_id(self, autofix: Callable[[list[Message]], list[Message]]):
        messages = [
            Message(
                role="assistant",
                content=[
                    self._content_tc_request(id="dup_id"),
                    self._content_tc_request(id="dup_id"),
                ],
            ),
        ]
        with pytest.raises(ValueError, match="Tool call request dup_id .* already found"):
            autofix(messages)

    def test_tool_call_result_without_request(self, autofix: Callable[[list[Message]], list[Message]]):
        messages = [
            Message(role="user", content=[self._content_tc_result(id="orphan_id")]),
        ]
        with pytest.raises(
            ValueError,
            match="Tool call result orphan_id .* should immediately follow a tool call request",
        ):
            autofix(messages)

    def test_tool_call_result_in_assistant_message(self, autofix: Callable[[list[Message]], list[Message]]):
        messages = [
            Message(role="assistant", content=[self._content_tc_request(id="req1")]),
            Message(role="assistant", content=[self._content_tc_result(id="req1")]),
        ]
        with pytest.raises(ValueError, match="assistant messages cannot have tool call results"):
            autofix(messages)

    def test_duplicate_tool_call_result_id(self, autofix: Callable[[list[Message]], list[Message]]):
        messages = [
            Message(role="assistant", content=[self._content_tc_request(id="req1")]),
            Message(role="user", content=[self._content_tc_result(id="req1")]),
            Message(role="user", content=[self._content_tc_result(id="req1")]),  # Duplicate result
        ]
        # The autofixer will first process the valid sequence, then encounter the duplicate result.
        # The first result for "req1" will be processed, moving it to _tool_result_ids.
        # The second result for "req1" will then be seen as a duplicate.
        with pytest.raises(ValueError, match="Tool call result req1 .* already found"):
            autofix(messages)

    def test_tool_call_result_for_unknown_request_id(self, autofix: Callable[[list[Message]], list[Message]]):
        messages = [
            Message(role="assistant", content=[self._content_tc_request(id="actual_req")]),
            Message(role="user", content=[self._content_tc_result(id="unknown_req")]),
        ]
        with pytest.raises(ValueError, match="Tool call result unknown_req .* not found in previous messages"):
            autofix(messages)

    def test_content_between_tool_call_request_and_result_different_message(
        self,
        autofix: Callable[[list[Message]], list[Message]],
    ):
        messages = [
            Message(role="assistant", content=[self._content_tc_request(id="req1")]),
            Message(role="user", content=[MessageContent(text="Some other user text")]),  # Intervening content
            Message(role="user", content=[self._content_tc_result(id="req1")]),
        ]
        with pytest.raises(
            ValueError,
            match="Only tool call results are allowed in tool call turn",
        ):
            autofix(messages)

    def test_text_content_in_tool_call_result_message(self, autofix: Callable[[list[Message]], list[Message]]):
        """
        Tests that if a message starts with a tool_call_result, it cannot contain other
        non-tool_call_result content.
        """
        # Maybe we could allow and dynamically split the message in the future
        # But for now, we disallow it for simplicity. Since OpenAI sends messages
        # that only contain tool call results, we should be good
        messages = [
            Message(role="assistant", content=[self._content_tc_request(id="req1")]),
            Message(
                role="user",
                content=[
                    self._content_tc_result(id="req1"),
                    MessageContent(text="Unexpected text"),  # Mixed content
                ],
            ),
        ]
        with pytest.raises(ValueError, match="Only tool call results are allowed in tool call turn"):
            autofix(messages)

    def test_tool_call_request_after_tool_call_result_in_same_message(
        self,
        autofix: Callable[[list[Message]], list[Message]],
    ):
        """Same as mixed content except the tool call request is in the same message as the tool call result"""
        messages = [
            Message(role="assistant", content=[self._content_tc_request(id="req1")]),
            Message(
                role="user",
                content=[
                    self._content_tc_result(id="req1"),
                    self._content_tc_request(id="req2"),
                ],
            ),
        ]
        with pytest.raises(ValueError, match="Only tool call results are allowed in tool call turn"):
            autofix(messages)

    def test_text_content_after_tool_call_request_in_same_assistant_message(
        self,
        autofix: Callable[[list[Message]], list[Message]],
    ):
        """
        If an assistant message has a tool call request, and then a text content,
        this is valid. This test ensures the autofixer doesn't break this.
        The more complex case is if there's a result *then* text.
        """
        messages = [
            Message(role="user", content=[MessageContent(text="Initial prompt")]),
            Message(
                role="assistant",
                content=[
                    self._content_tc_request(id="req1"),
                    MessageContent(text="Some text after request"),
                ],
            ),
            Message(
                role="user",
                content=[self._content_tc_result(id="req1", name="test", input_dict={"hello": "world"})],
            ),
        ]
        # This should be valid, the autofixer should handle it.
        # The primary check is that it does *not* raise ValueError.
        # The fix will update the result with name and input_dict.
        fixed = autofix(messages)
        assert len(fixed) == 3
        assert fixed[0] == messages[0]
        assert fixed[1] == messages[1]
        assert fixed[2].content[0].tool_call_result is not None
        assert fixed[2].content[0].tool_call_result.id == "req1"
        assert fixed[2].content[0].tool_call_result.tool_name == "test"  # from _content_tc_request
        assert fixed[2].content[0].tool_call_result.tool_input_dict == {"hello": "world"}  # from _content_tc_request

    def test_tool_call_result_not_immediately_after_request_same_role_message(
        self,
        autofix: Callable[[list[Message]], list[Message]],
    ):
        """
        Scenario:
        Assistant: TCR1
        User: Text
        User: TCR1_Result  <-- This is invalid because of the intervening text message
        """
        messages = [
            Message(role="assistant", content=[self._content_tc_request(id="tc1")]),
            Message(role="user", content=[MessageContent(text="Hello")]),
            Message(role="user", content=[self._content_tc_result(id="tc1")]),
        ]
        with pytest.raises(
            ValueError,
            match="Only tool call results are allowed in tool call turn",
        ):
            autofix(messages)

    def test_valid_multiple_requests_then_multiple_results_interspersed_with_text_in_assistant_message(
        self,
        autofix: Callable[[list[Message]], list[Message]],
    ):
        """
        Assistant: Text1, TCR1, Text2, TCR2, Text3
        User: TCR1_Result, TCR2_Result
        This is a valid sequence.
        """
        messages = [
            Message(role="user", content=[MessageContent(text="Initial query")]),
            Message(
                role="assistant",
                content=[
                    MessageContent(text="Okay, I will do a few things."),
                    self._content_tc_request(id="tcr_a", name="tool_a", input_dict={"param": "1"}),
                    MessageContent(text="First one is on its way."),
                    self._content_tc_request(id="tcr_b", name="tool_b", input_dict={"param": "2"}),
                    MessageContent(text="Second one is also on its way."),
                ],
            ),
            Message(
                role="user",
                content=[
                    self._content_tc_result(id="tcr_a", result="Result A"),
                    self._content_tc_result(id="tcr_b", result="Result B"),
                ],
            ),
        ]
        fixed = autofix(messages)
        assert len(fixed) == 3
        assert fixed[0] == messages[0]
        assert fixed[1] == messages[1]  # Assistant message remains unchanged

        assert fixed[2].role == "user"
        assert len(fixed[2].content) == 2
        assert fixed[2].content[0].tool_call_result is not None
        assert fixed[2].content[0].tool_call_result.id == "tcr_a"
        assert fixed[2].content[0].tool_call_result.tool_name == "tool_a"
        assert fixed[2].content[0].tool_call_result.tool_input_dict == {"param": "1"}
        assert fixed[2].content[0].tool_call_result.result == "Result A"

        assert fixed[2].content[1].tool_call_result is not None
        assert fixed[2].content[1].tool_call_result.id == "tcr_b"
        assert fixed[2].content[1].tool_call_result.tool_name == "tool_b"
        assert fixed[2].content[1].tool_call_result.tool_input_dict == {"param": "2"}
        assert fixed[2].content[1].tool_call_result.result == "Result B"

    def test_unfulfilled_tool_request_followed_by_text(self, autofix: Callable[[list[Message]], list[Message]]):
        """Check that we raise an error when there's an unfulfilled tool request followed by text"""
        # This is a bit weird but it seems that it would be rejected by OpenAI. Any tool call request MUST be answered
        messages = [
            Message(role="assistant", content=[self._content_tc_request(id="req1")]),
            Message(role="user", content=[MessageContent(text="Some unrelated user text")]),
        ]
        with pytest.raises(ValueError, match="Only tool call results are allowed in tool call turn"):
            autofix(messages)

    def test_multiple_tool_requests_only_one_result_provided(self, autofix: Callable[[list[Message]], list[Message]]):
        messages = [
            Message(
                role="assistant",
                content=[
                    self._content_tc_request(id="req1", name="tool1"),
                    self._content_tc_request(id="req2", name="tool2"),
                ],
            ),
            Message(role="user", content=[self._content_tc_result(id="req1", result="Res1")]),
        ]
        with pytest.raises(ValueError, match="Tool call requests `req2` are still pending. "):
            autofix(messages)
