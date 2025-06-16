import json

import pytest
from httpx import HTTPStatusError
from pytest_httpx import IteratorStream

from core.domain.models import Model, Provider
from tests.component.common import (
    IntegrationTestClient,
)
from tests.utils import fixture_bytes, fixtures_json


async def test_r1_thinking_streaming(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    test_client.httpx_mock.add_response(
        url="https://api.fireworks.ai/inference/v1/chat/completions",
        stream=IteratorStream(fixture_bytes("fireworks", "r1_stream_with_reasoning.txt").splitlines(keepends=True)),
    )
    chunks = [c async for c in test_client.stream_run_task_v1(task, model=Model.DEEPSEEK_R1_2501)]
    assert chunks

    assert chunks[1]["reasoning_steps"] == [{"step": "\nOkay,"}]
    assert chunks[2]["reasoning_steps"] == [{"step": "\nOkay, the user"}]

    assert len(chunks[-1]["reasoning_steps"]) == 1
    assert len(chunks[-1]["reasoning_steps"][0]["step"]) == 1284


async def test_r1_thinking_non_streaming(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    test_client.httpx_mock.add_response(
        url="https://api.fireworks.ai/inference/v1/chat/completions",
        json=fixtures_json("fireworks", "r1_completion_with_reasoning.json"),
    )
    res = await test_client.run_task_v1(task, model=Model.DEEPSEEK_R1_2501)

    assert res["task_output"]["greeting"] == "The Azure Whisper"
    assert (
        res["reasoning_steps"][0]["step"]
        == "Okay, let's see. The user asked for a short story based on the fact that the sky is blue. \n"
    )


async def test_fireworks_tool_calls_streaming(test_client: IntegrationTestClient):
    """
    Test the native tool calls feature of Fireworks for streaming mode.
    - Test that the tool (Perplexity Sonar Pro) is correctly called
    - Test that the provider (Fireworks) is called twice
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
        url="https://api.fireworks.ai/inference/v1/chat/completions",
        status_code=200,
        stream=IteratorStream(
            fixture_bytes("fireworks", "completion_tool_calls_stream_1.txt").splitlines(keepends=True),
        ),
    )
    # 2 nd completion
    test_client.httpx_mock.add_response(
        url="https://api.fireworks.ai/inference/v1/chat/completions",
        status_code=200,
        stream=IteratorStream(
            fixture_bytes("fireworks", "completion_tool_calls_stream_2.txt").splitlines(keepends=True),
        ),
    )
    chunks = [
        c
        async for c in test_client.stream_run_task_v1(
            task,
            model=Model.LLAMA_3_1_405B,
            version={"model": "llama-3.1-405b", "instructions": "Use @perplexity-sonar-pro"},
        )
    ]
    assert chunks

    # Test that the tool is correctly called
    perplexity_request = test_client.httpx_mock.get_requests(url="https://api.perplexity.ai/chat/completions")
    assert len(perplexity_request) == 1
    assert "Jazz vs Lakers score Feb 12th 2025" in perplexity_request[0].read().decode()

    # Test that the provider is called twice
    fireworks_requests = test_client.httpx_mock.get_requests(
        url="https://api.fireworks.ai/inference/v1/chat/completions",
    )
    assert len(fireworks_requests) == 2
    # Test that the tool call is correctly injected in the second request provider call
    assert "131-119" in fireworks_requests[1].content.decode()
    # 2 initial messages + 1 tool call request + 1  tool call result
    assert len(json.loads(fireworks_requests[1].content.decode())["messages"]) == 4

    # Test the run's output
    assert chunks[0]["tool_calls"] == [
        {
            "id": "call_CHdOqFrAgN1YpsG7UsYtSFHv",
            "name": "@perplexity-sonar-pro",
            "input_preview": 'query: "Jazz vs Lakers score Feb 12th 2025"',
            "output_preview": "-",
            "status": "in_progress",
        },
    ]
    assert (
        chunks[-1]["task_output"]["answer"]
        == "The Utah Jazz won the game against the Los Angeles Lakers with a score of 131-119 on February 12, 2025."
    )


async def test_fireworks_tool_calls(test_client: IntegrationTestClient):
    """
    Test the native tool calls feature of Fireworks
    - Test that the tool (Perplexity Sonar Pro) is correctly called
    - Test that the provider (Fireworks) is called twice
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
        url="https://api.fireworks.ai/inference/v1/chat/completions",
        status_code=200,
        json={
            "id": "df434f01-6188-40a1-90da-61efed27111c",
            "object": "chat.completion",
            "created": 1740129677,
            "model": "accounts/fireworks/models/llama-v3p1-405b-instruct",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_Sm93B5EljqyCCclNDjhwLU8M",
                                "type": "function",
                                "function": {
                                    "name": "perplexity-sonar-pro",
                                    "arguments": '{"query": "Jazz vs Lakers score Feb 12th 2025"}',
                                },
                            },
                        ],
                    },
                    "finish_reason": "tool_calls",
                },
            ],
            "usage": {
                "prompt_tokens": 437,
                "total_tokens": 466,
                "completion_tokens": 29,
            },
        },
    )
    # 2 nd completion
    test_client.httpx_mock.add_response(
        url="https://api.fireworks.ai/inference/v1/chat/completions",
        status_code=200,
        json={
            "id": "292f9939-95da-4cec-8b9f-454c205c7836",
            "object": "chat.completion",
            "created": 1740129681,
            "model": "accounts/fireworks/models/llama-v3p1-405b-instruct",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": '{"answer": "The score of the latest Jazz - Lakers game of Feb 12th, 2025 is 131-119 in favor of the Utah Jazz."}',
                    },
                    "finish_reason": "stop",
                },
            ],
            "usage": {
                "prompt_tokens": 1580,
                "total_tokens": 1611,
                "completion_tokens": 31,
            },
        },
    )
    res = await test_client.run_task_v1(
        task,
        model=Model.LLAMA_3_1_405B,
        version={"model": "llama-3.1-405b", "instructions": "Use @perplexity-sonar-pro"},
    )

    # Test that the tool is correctly called
    perplexity_request = test_client.httpx_mock.get_requests(url="https://api.perplexity.ai/chat/completions")
    assert len(perplexity_request) == 1
    assert "Jazz vs Lakers score Feb 12th 2025" in perplexity_request[0].read().decode()

    # Test that the provider is called twice
    fireworks_requests = test_client.httpx_mock.get_requests(
        url="https://api.fireworks.ai/inference/v1/chat/completions",
    )
    assert len(fireworks_requests) == 2
    # Test that the tool call is correctly injected in the second request provider call
    assert "131-119" in fireworks_requests[1].content.decode()
    # 2 initial messages + 1 tool call request + 1  tool call result
    assert len(json.loads(fireworks_requests[1].content.decode())["messages"]) == 4

    # Test the run's output
    assert res["tool_calls"] == [
        {
            "id": "@perplexity-sonar-pro_f7183fac8d081982e6e31028119345b2",
            "name": "@perplexity-sonar-pro",
            "input_preview": 'query: "Jazz vs Lakers score Feb 12th 2025"',
            "output_preview": '{"answer":"131-119"}',
        },
    ]
    assert (
        res["task_output"]["answer"]
        == "The score of the latest Jazz - Lakers game of Feb 12th, 2025 is 131-119 in favor of the Utah Jazz."
    )


async def test_fireworks_length_finish_reason(test_client: IntegrationTestClient):
    """Finish reason length is returned when the prompt is below the context window
    but the generation would exceed the context window"""
    task = await test_client.create_task()

    test_client.httpx_mock.add_response(
        url="https://api.fireworks.ai/inference/v1/chat/completions",
        status_code=200,
        json=fixtures_json("fireworks", "finish_reason_length_completion.json"),
    )
    with pytest.raises(HTTPStatusError) as e:
        await test_client.run_task_v1(task, version={"model": Model.LLAMA_3_1_405B, "provider": Provider.FIREWORKS})

    res = e.value.response.json()
    assert res["error"]["code"] == "max_tokens_exceeded"


async def test_fireworks_length_finish_reason_streaming(test_client: IntegrationTestClient):
    """Finish reason length is returned when the prompt is below the context window
    but the generation would exceed the context window"""
    task = await test_client.create_task()

    test_client.httpx_mock.add_response(
        url="https://api.fireworks.ai/inference/v1/chat/completions",
        status_code=200,
        stream=IteratorStream(
            fixture_bytes("fireworks", "finish_reason_length_stream_completion.txt").splitlines(keepends=True),
        ),
    )

    chunks = [
        c
        async for c in test_client.stream_run_task_v1(
            task,
            version={"model": Model.LLAMA_3_1_405B, "provider": Provider.FIREWORKS},
        )
    ]
    assert chunks

    assert chunks
    assert "error" in chunks[-1]
    assert chunks[-1]["error"]["code"] == "max_tokens_exceeded"
