from openai import AsyncOpenAI

from tests.component.common import IntegrationTestClient, vertex_url_matcher
from tests.utils import request_json_body


async def test_tools(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    """Check that tool calls are correctly handled"""
    test_client.mock_vertex_call()

    res = await openai_client.chat.completions.create(
        model=f"my-agent/{test_client.DEFAULT_VERTEX_MODEL}",
        messages=[
            {"role": "user", "content": "What is the weather in Tokyo and in Paris?"},
            {
                "role": "assistant",
                "content": "Let me get the weather in tokyo first",
                "tool_calls": [
                    {
                        "id": "tool_use_01NhMGWVdTLvEuDB6Rx76hYJ",
                        "type": "function",
                        "function": {"name": "get_weather", "arguments": "Tokyo"},
                    },
                    {
                        "id": "tool_use_01NhMGWVdTLvEuDB6Rx76hYK",
                        "type": "function",
                        "function": {"name": "get_weather", "arguments": "Paris"},
                    },
                ],
            },
            {
                "role": "tool",
                "content": "The weather in Tokyo is sunny",
                "tool_call_id": "tool_use_01NhMGWVdTLvEuDB6Rx76hYJ",
            },
            {
                "role": "tool",
                "content": "The weather in Paris is sunny",
                "tool_call_id": "tool_use_01NhMGWVdTLvEuDB6Rx76hYK",
            },
        ],
    )
    assert res.choices[0].message.content

    call = test_client.httpx_mock.get_request(url=vertex_url_matcher(test_client.DEFAULT_VERTEX_MODEL))
    assert call

    payload = request_json_body(call)
    assert payload
    contents = payload["contents"]
    # Tool messages will be aggregated
    assert contents and len(payload["contents"]) == 3
    assert contents[0]["role"] == "user"
    assert contents[1]["role"] == "model"
    assert contents[2]["role"] == "user"
    tool_parts = contents[2]["parts"]
    assert tool_parts and len(tool_parts) == 2

    for part in tool_parts:
        function_response = part["functionResponse"]
        assert function_response
        assert function_response["name"] == "get_weather"
