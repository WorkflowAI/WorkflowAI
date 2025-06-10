import json

from openai import AsyncOpenAI

from tests.component.common import IntegrationTestClient


async def test_system_message(openai_client: AsyncOpenAI, test_client: IntegrationTestClient):
    """Test that the system message is correctly passed to Anthropic"""
    test_client.mock_anthropic_call(raw_content="Hello James!")

    res = await openai_client.chat.completions.create(
        model="claude-3-5-sonnet",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, world!"},
            {"role": "assistant", "content": "Hello James!"},
            {"role": "system", "content": "Another system message"},
            {"role": "user", "content": "Another user message"},
        ],
        extra_body={"provider": "anthropic"},  # force the provider to anthropic
    )

    assert res.choices[0].message.content == "Hello James!"

    # Check that the system message was correctly passed
    anthropic_requests = test_client.httpx_mock.get_requests(
        url=test_client.ANTHROPIC_URL,
    )
    assert len(anthropic_requests) == 1
    req = json.loads(anthropic_requests[0].content)
    assert req["system"] == "You are a helpful assistant."
    assert len(req["messages"]) == 4
    assert req["messages"][0] == {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": "Hello, world!",
            },
        ],
    }
    # Check that the system message is remapped to a user message
    assert req["messages"][2] == {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": "Another system message",
            },
        ],
    }
