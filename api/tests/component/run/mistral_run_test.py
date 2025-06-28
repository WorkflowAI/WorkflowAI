import json

from pytest_httpx import IteratorStream

from core.domain.models import Model
from tests.component.common import (
    IntegrationTestClient,
)
from tests.utils import fixture_bytes


async def test_mistral_tool_calls_streaming(test_client: IntegrationTestClient):
    """
    Test the native tool calls feature of Mistral AI for streaming mode.
    - Test that the tool (Perplexity Sonar Pro) is correctly called
    - Test that the provider (Mistral AI) is called twice
    - Test the run's output
    - Test the run's tool calls
    """

    task = await test_client.create_task(
        output_schema={"type": "object", "properties": {"answer": {"type": "string"}}},
    )

    test_client.httpx_mock.add_response(
        url="https://api.perplexity.ai/chat/completions",
        json={"answer": "131-119"},  # Does not matter
    )

    # 1 st completion
    test_client.httpx_mock.add_response(
        url="https://api.mistral.ai/v1/chat/completions",
        status_code=200,
        stream=IteratorStream(
            fixture_bytes("mistralai", "stream_completion_with_tools_1.txt").splitlines(keepends=True),
        ),
    )
    # 2 nd completion
    test_client.httpx_mock.add_response(
        url="https://api.mistral.ai/v1/chat/completions",
        status_code=200,
        stream=IteratorStream(
            fixture_bytes("mistralai", "stream_completion_with_tools_2.txt").splitlines(keepends=True),
        ),
    )
    chunks = [
        c
        async for c in test_client.stream_run_task_v1(
            task,
            version={"model": Model.MISTRAL_LARGE_2411.value, "instructions": "Use @perplexity-sonar-pro"},
        )
    ]
    assert chunks

    # Test that the tool is correctly called
    perplexity_request = test_client.httpx_mock.get_requests(url="https://api.perplexity.ai/chat/completions")
    assert len(perplexity_request) == 1
    assert (
        "What is the score of the latest Jazz - Lakers game of Feb 12th, 2025" in perplexity_request[0].read().decode()
    )

    # Test that the provider is called twice
    mistral_requests = test_client.httpx_mock.get_requests(
        url="https://api.mistral.ai/v1/chat/completions",
    )
    assert len(mistral_requests) == 2
    # Test that the tool call is correctly injected in the second request provider call
    assert "131-119" in mistral_requests[1].content.decode()
    # 2 initial messages + 1 tool call request + 1  tool call result
    assert len(json.loads(mistral_requests[1].content.decode())["messages"]) == 4

    # Test the run's output
    assert chunks[0]["tool_calls"] == [
        {
            "id": "qWvpC7maA",
            "name": "@perplexity-sonar-pro",
            "input_preview": 'query: "What is the score of the latest Jazz - Lakers game of Feb 12th, 2025"',
            "output_preview": "-",
            "status": "in_progress",
        },
    ]
    assert (
        chunks[-1]["task_output"]["answer"]
        == "The Utah Jazz defeated the Los Angeles Lakers 131-119 on February 12, 2025. Lauri Markkanen led Utah with 32 points and a season-high three steals, while Luka Dončić scored 16 points in his second game with the Lakers."
    )


async def test_mistral_tool_calls(test_client: IntegrationTestClient):
    """
    Test the native tool calls feature of Mistral AI
    - Test that the tool (Perplexity Sonar Pro) is correctly called
    - Test that the provider (Mistral AI) is called twice
    - Test the run's output
    - Test the run's tool calls
    """

    task = await test_client.create_task(
        output_schema={"type": "object", "properties": {"answer": {"type": "string"}}},
    )

    test_client.httpx_mock.add_response(
        url="https://api.perplexity.ai/chat/completions",
        json={"answer": "131-119"},  # Does not matter
    )

    # 1 st completion
    test_client.httpx_mock.add_response(
        url="https://api.mistral.ai/v1/chat/completions",
        status_code=200,
        json={
            "id": "f935f5c4e056445d8fa85c0122305ae7",
            "object": "chat.completion",
            "created": 1740146443,
            "model": "mistral-large-2411",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "CqNfSjurG",
                                "function": {
                                    "name": "perplexity-sonar-pro",
                                    "arguments": '{"query": "What is the score of the latest Jazz - Lakers game of Feb 12th, 2025"}',
                                },
                                "index": 0,
                            },
                        ],
                        "content": "",
                    },
                    "finish_reason": "tool_calls",
                },
            ],
            "usage": {
                "prompt_tokens": 418,
                "total_tokens": 467,
                "completion_tokens": 49,
            },
        },
    )
    # 2 nd completion
    test_client.httpx_mock.add_response(
        url="https://api.mistral.ai/v1/chat/completions",
        status_code=200,
        json={
            "id": "b81f666d47d94453bfeb71f4300d0f79",
            "object": "chat.completion",
            "created": 1740146451,
            "model": "mistral-large-2411",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "tool_calls": None,
                        "content": '```json\n{\n  "answer": "The Utah Jazz defeated the Los Angeles Lakers 131-119 on February 12, 2025. Lauri Markkanen led the Jazz with 32 points, while LeBron James scored 18 for the Lakers."\n}\n```',
                    },
                    "finish_reason": "stop",
                },
            ],
            "usage": {
                "prompt_tokens": 1116,
                "total_tokens": 1188,
                "completion_tokens": 72,
            },
        },
    )
    res = await test_client.run_task_v1(
        task,
        version={"model": Model.MISTRAL_LARGE_2411.value, "instructions": "Use @perplexity-sonar-pro"},
    )

    # Test that the tool is correctly called
    perplexity_request = test_client.httpx_mock.get_requests(url="https://api.perplexity.ai/chat/completions")
    assert len(perplexity_request) == 1
    assert (
        "What is the score of the latest Jazz - Lakers game of Feb 12th, 2025" in perplexity_request[0].read().decode()
    )

    # Test that the provider is called twice
    mistral_requests = test_client.httpx_mock.get_requests(
        url="https://api.mistral.ai/v1/chat/completions",
    )
    assert len(mistral_requests) == 2
    # Test that the tool call is correctly injected in the second request provider call
    assert "131-119" in mistral_requests[1].content.decode()
    # 2 initial messages + 1 tool call request + 1  tool call result
    assert len(json.loads(mistral_requests[1].content.decode())["messages"]) == 4

    # Test the run's output
    assert res["tool_calls"] == [
        {
            "id": "@perplexity-sonar-pro_465b30607cde64f606265b77bbdd3d96",
            "name": "@perplexity-sonar-pro",
            "input_preview": 'query: "What is the score of the latest Jazz - Lakers game of Feb 12th, 2025"',
            "output_preview": '{"answer":"131-119"}',
        },
    ]
    assert (
        res["task_output"]["answer"]
        == "The Utah Jazz defeated the Los Angeles Lakers 131-119 on February 12, 2025. Lauri Markkanen led the Jazz with 32 points, while LeBron James scored 18 for the Lakers."
    )
