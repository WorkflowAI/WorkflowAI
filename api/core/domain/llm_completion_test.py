from typing import Any

import pytest

from core.domain.llm_completion import LLMCompletion
from core.domain.llm_usage import LLMUsage
from core.domain.message import MessageDeprecated
from core.domain.models import Provider
from core.domain.tool_call import ToolCallRequestWithID
from core.providers.base.models import StandardMessage


def _llm_completion(
    messages: list[dict[str, Any]],
    usage: LLMUsage,
    response: str | None = None,
    tool_calls: list[ToolCallRequestWithID] | None = None,
):
    return LLMCompletion(
        messages=messages,
        usage=usage,
        response=response,
        tool_calls=tool_calls,
        provider=Provider.OPEN_AI,
    )


class TestLLMCompletionToMessages:
    def test_to_messages_with_response(self):
        completion = _llm_completion(
            messages=[{"role": "user", "content": "Hello world"}],
            response="Hello back!",
            usage=LLMUsage(),
        )

        messages = completion.to_deprecated_messages()
        assert len(messages) == 2
        assert messages[0].role == MessageDeprecated.Role.USER
        assert messages[0].content == "Hello world"
        assert messages[1].role == MessageDeprecated.Role.ASSISTANT
        assert messages[1].content == "Hello back!"

    def test_to_messages_without_response(self):
        completion = _llm_completion(
            messages=[{"role": "system", "content": "System prompt"}, {"role": "user", "content": "User message"}],
            response=None,
            usage=LLMUsage(),
        )

        messages = completion.to_deprecated_messages()
        assert len(messages) == 2
        assert messages[0].role == MessageDeprecated.Role.SYSTEM
        assert messages[0].content == "System prompt"
        assert messages[1].role == MessageDeprecated.Role.USER
        assert messages[1].content == "User message"

    def test_to_messages_with_complex_content(self):
        standard_msg: StandardMessage = {
            "role": "user",
            "content": [
                {"type": "text", "text": "First line"},
                {"type": "text", "text": "Second line"},
                {
                    "type": "image_url",
                    "image_url": {"url": "http://example.com/image.jpg"},
                },
            ],
        }

        completion = LLMCompletion(
            messages=[standard_msg],  # pyright: ignore [reportArgumentType]
            response="Got your message with image",
            usage=LLMUsage(),
            provider=Provider.OPEN_AI,
        )

        messages = completion.to_deprecated_messages()
        assert len(messages) == 2
        assert messages[0].role == MessageDeprecated.Role.USER
        assert messages[0].content == "First line\nSecond line"
        assert messages[0].files is not None
        assert len(messages[0].files) == 1
        assert messages[0].files[0].url == "http://example.com/image.jpg"
        assert messages[1].role == MessageDeprecated.Role.ASSISTANT
        assert messages[1].content == "Got your message with image"

    def test_with_tool_calls_and_response(self):
        completion = _llm_completion(
            messages=[{"role": "user", "content": "Hello world"}],
            response="Hello back!",
            usage=LLMUsage(),
            tool_calls=[ToolCallRequestWithID(id="1", tool_name="test_tool", tool_input_dict={"arg1": "value1"})],
        )

        messages = completion.to_deprecated_messages()
        assert messages == [
            MessageDeprecated(content="Hello world", role=MessageDeprecated.Role.USER),
            MessageDeprecated(
                content="Hello back!",
                role=MessageDeprecated.Role.ASSISTANT,
                tool_call_requests=[
                    ToolCallRequestWithID(id="1", tool_name="test_tool", tool_input_dict={"arg1": "value1"}),
                ],
            ),
        ]


class TestIncurCost:
    @pytest.mark.parametrize(
        ("response", "completion_token_count", "completion_image_count"),
        [
            pytest.param("Hello back!", None, None, id="usage not computed"),
            pytest.param("", None, None, id="usage not computed but empty response"),
            pytest.param(None, 10, 0, id="no response but completion tokens"),
            pytest.param(None, 0, 1, id="no response but completion image"),
        ],
    )
    def test_incur_cost(
        self,
        response: str,
        completion_token_count: int | None,
        completion_image_count: int | None,
    ):
        completion = _llm_completion(
            messages=[{"role": "user", "content": "Hello world"}],
            response=response,
            usage=LLMUsage(
                completion_token_count=completion_token_count,
                completion_image_count=completion_image_count,
            ),
        )
        assert completion.should_incur_cost()

    @pytest.mark.parametrize(
        ("response", "completion_token_count", "completion_image_count"),
        [
            pytest.param(None, 0, 0, id="no response and no completion tokens and no completion images"),
        ],
    )
    def test_no_incur_cost(
        self,
        response: str,
        completion_token_count: int | None,
        completion_image_count: int | None,
    ):
        completion = _llm_completion(
            messages=[{"role": "user", "content": "Hello world"}],
            response=response,
            usage=LLMUsage(
                completion_token_count=completion_token_count,
                completion_image_count=completion_image_count,
            ),
        )
        assert not completion.should_incur_cost()
