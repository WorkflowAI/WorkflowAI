import re

import pytest
from openai import AsyncOpenAI

from core.domain.models.models import Model
from tests.component.common import IntegrationTestClient, assert_no_warning_or_error, vertex_url, vertex_url_matcher
from tests.utils import request_json_body


async def test_tools(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    """Check that tool calls are correctly handled"""
    v_url = vertex_url_matcher(test_client.DEFAULT_VERTEX_MODEL, region="global")
    test_client.mock_vertex_call(url=v_url)

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

    call = test_client.httpx_mock.get_request(url=v_url)
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


async def test_vertex_file_limit(
    test_client: IntegrationTestClient,
    openai_client: AsyncOpenAI,
    caplog: pytest.LogCaptureFixture,
):
    # Pause the broker to make sure of which images are downloaded
    test_client.patched_broker.pause()

    test_client.mock_vertex_call(
        url=vertex_url(Model.GEMINI_2_0_FLASH_001, region="global"),
    )

    file_url_matcher = re.compile(r"^https://hello.com/world.*")
    test_client.httpx_mock.add_response(
        url=file_url_matcher,
        status_code=200,
        content=b"Hello world",
        is_reusable=True,
    )

    # Run file with 12 URLs, we should download 2 out of the 12
    res = await openai_client.chat.completions.create(
        model=f"my-agent/{Model.GEMINI_2_0_FLASH_001}",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"https://hello.com/world{i}.jpg"}} for i in range(12)
                ],
            },
        ],
    )
    assert res

    donwload_reqs = test_client.httpx_mock.get_requests(url=file_url_matcher)
    assert len(donwload_reqs) == 2

    vertex_req = test_client.httpx_mock.get_request(url=vertex_url(Model.GEMINI_2_0_FLASH_001, region="global"))
    assert vertex_req

    vertex_body = request_json_body(vertex_req)
    assert vertex_body

    parts = vertex_body["contents"][0]["parts"]
    assert len([p for p in parts if p.get("inlineData")]) == 2
    assert len([p for p in parts if p.get("fileData")]) == 10

    await test_client.patched_broker.resume()

    assert_no_warning_or_error(caplog)
