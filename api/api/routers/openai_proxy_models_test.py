from api.routers.openai_proxy_models import (
    OpenAIProxyChatCompletionRequest,
    OpenAIProxyContent,
    OpenAIProxyImageURL,
    OpenAIProxyMessage,
)
from core.domain.fields.file import File
from core.domain.message import Message, MessageContent
from core.domain.tool_call import ToolCall


class TestOpenAIProxyChatCompletionRequest:
    def test_minimal_payload(self):
        """Check that we have enough defaults to accept minimal payload"""
        payload = OpenAIProxyChatCompletionRequest.model_validate(
            {
                "messages": [{"role": "user", "content": "Hello, world!"}],
                "model": "gpt-4o",
            },
        )
        assert payload


class TestOpenAIProxyContent:
    def test_image_url_to_domain(self):
        payload = OpenAIProxyContent(
            type="image_url",
            image_url=OpenAIProxyImageURL(
                url="https://hello.com/image.png",
            ),
        )
        assert payload.to_domain() == MessageContent(file=File(url="https://hello.com/image.png"))


class TestOpenAIProxyMessageToDomain:
    def test_with_tool_calls(self):
        payload = OpenAIProxyMessage(
            role="tool",
            content="Hello, world!",
            tool_call_id="1",
        )
        assert payload.to_domain() == Message(
            role="user",
            content=[
                MessageContent(
                    tool_call_result=ToolCall(
                        id="1",
                        tool_name="",
                        tool_input_dict={},
                        result="Hello, world!",
                    ),
                ),
            ],
        )
