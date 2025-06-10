import json

import pytest
from pytest_httpx import IteratorStream

from core.domain.models import Model
from tests.component.common import IntegrationTestClient
from tests.utils import fixture_bytes


@pytest.mark.parametrize(
    "file_url",
    [
        "https://iamafile.com/hello.pdf",
        # When the URL does not contain the file extension, the
        # content type is determined after the file is downloaded so the checks don't happen
        # at the same time
        "https://iamafile.com/hello",
    ],
)
async def test_claude_supports_pdfs_on_anthropic(test_client: IntegrationTestClient, file_url: str):
    # Create a task with a file
    task = await test_client.create_task(
        input_schema={
            "type": "object",
            "properties": {
                "file": {
                    "$ref": "#/$defs/File",
                },
            },
        },
    )

    test_client.httpx_mock.add_response(
        url=file_url,
        status_code=200,
        content=b"%PDFHello, world!",
    )

    # No need to mock bedrock, it should not be hit here
    # Since the message fails at the message serialization

    test_client.mock_anthropic_call(
        content_json={
            "greeting": "hello",
        },
    )

    out = await test_client.run_task_v1(
        task,
        task_input={"file": {"url": file_url}},
        model=Model.CLAUDE_3_5_SONNET_LATEST,
    )
    assert out["task_output"] == {"greeting": "hello"}

    fetched = await test_client.fetch_run(task=task, run=out)
    assert fetched["metadata"]["workflowai.providers"] == ["anthropic"]


async def test_anthropic_tool_calls_streaming(test_client: IntegrationTestClient):
    """
    Test the native tool calls feature of Anthropic in streaming mode
    - Test that the tool (Perplexity Sonar Pro) is correctly called
    - Test that the provider (Anthropic) is called twice
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
        url="https://api.anthropic.com/v1/messages",
        status_code=200,
        stream=IteratorStream(
            fixture_bytes("anthropic", "anthropic_stream_with_tools_1.txt").splitlines(
                keepends=True,
            ),
        ),
    )
    # 2 nd completion
    test_client.httpx_mock.add_response(
        url="https://api.anthropic.com/v1/messages",
        status_code=200,
        stream=IteratorStream(
            fixture_bytes("anthropic", "anthropic_stream_with_tools_2.txt").splitlines(
                keepends=True,
            ),
        ),
    )

    chunks = [
        c
        async for c in test_client.stream_run_task_v1(
            task,
            version={
                "model": Model.CLAUDE_3_5_SONNET_20241022.value,
                "instructions": "Use @perplexity-sonar-pro",
                "provider": "anthropic",
            },
        )
    ]
    assert chunks

    # Test that the tool is correctly called
    perplexity_request = test_client.httpx_mock.get_requests(url="https://api.perplexity.ai/chat/completions")
    assert len(perplexity_request) == 1
    assert (
        "What was the final score of the Utah Jazz vs Los Angeles Lakers NBA game on February 12, 2025?"
        in perplexity_request[0].read().decode()
    )

    # Test that the provider is called twice
    anthropic_requests = test_client.httpx_mock.get_requests(
        url="https://api.anthropic.com/v1/messages",
    )
    assert len(anthropic_requests) == 2
    # Test that the tool call is correctly injected in the second request provider call
    assert "131-119" in anthropic_requests[1].content.decode()
    # 1 initial messages (system not included) + 1 tool call request + 1  tool call result
    request_payload = json.loads(anthropic_requests[1].content.decode())
    assert len(request_payload["messages"]) == 3
    assert "Use perplexity-sonar-pro" in request_payload["system"]

    # Test the run's output
    assert chunks[0]["tool_calls"] == [
        {
            "id": "toolu_01D6dnPVG9x9nkvyMd24i6wc",
            "name": "@perplexity-sonar-pro",
            "input_preview": 'query: "What was the final score of the Utah Jazz vs Los Angeles Lakers NBA game on February 12, 2025?"',
            "output_preview": "-",
            "status": "in_progress",
        },
    ]
    assert (
        chunks[-1]["task_output"]["answer"]
        == "The Utah Jazz defeated the Los Angeles Lakers with a final score of 131-119 on February 12, 2025."
    )


async def test_anthropic_tool_calls(test_client: IntegrationTestClient):
    """
    Test the native tool calls feature of Anthropic
    - Test that the tool (Perplexity Sonar Pro) is correctly called
    - Test that the provider (Anthropic) is called twice
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
        url="https://api.anthropic.com/v1/messages",
        status_code=200,
        json={
            "id": "msg_01AbJ3zFAK21MAKWiRfTTsRo",
            "type": "message",
            "role": "assistant",
            "model": "claude-3-5-sonnet-20241022",
            "content": [
                {
                    "type": "text",
                    "text": "I'''ll help you find the score of the Jazz vs Lakers game from February 12th, 2025.",
                },
                {
                    "type": "tool_use",
                    "id": "toolu_01JjhxbWbH94V53QpW3DEXL9",
                    "name": "perplexity-sonar-pro",
                    "input": {
                        "query": "What was the final score of the Utah Jazz vs Los Angeles Lakers basketball game on February 12, 2025?",
                    },
                },
            ],
            "stop_reason": "tool_use",
            "stop_sequence": None,
            "usage": {
                "input_tokens": 714,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
                "output_tokens": 106,
            },
        },
    )
    # 2 nd completion
    test_client.httpx_mock.add_response(
        url="https://api.anthropic.com/v1/messages",
        status_code=200,
        json={
            "id": "msg_014y9NHcmz35iSHVb2QkrCxQ",
            "type": "message",
            "role": "assistant",
            "model": "claude-3-5-sonnet-20241022",
            "content": [
                {
                    "type": "text",
                    "text": '{\n  "answer": "The score of the latest Jazz - Lakers game of Feb 12th, 2025 is 131-119 in favor of the Utah Jazz."\n}',
                },
            ],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {
                "input_tokens": 813,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
                "output_tokens": 76,
            },
        },
    )
    res = await test_client.run_task_v1(
        task,
        version={
            "model": Model.CLAUDE_3_5_SONNET_20241022.value,
            "instructions": "Use @perplexity-sonar-pro",
            "provider": "anthropic",
        },
    )

    # Test that the tool is correctly called
    perplexity_request = test_client.httpx_mock.get_requests(url="https://api.perplexity.ai/chat/completions")
    assert len(perplexity_request) == 1
    assert (
        "What was the final score of the Utah Jazz vs Los Angeles Lakers basketball game on February 12, 2025?"
        in perplexity_request[0].read().decode()
    )

    # Test that the provider is called twice
    anthropic_requests = test_client.httpx_mock.get_requests(
        url="https://api.anthropic.com/v1/messages",
    )
    assert len(anthropic_requests) == 2
    # Test that the tool call is correctly injected in the second request provider call
    assert "131-119" in anthropic_requests[1].content.decode()
    # 1 initial messages (system not included) + 1 tool call request + 1  tool call result
    request_payload = json.loads(anthropic_requests[1].content.decode())
    assert len(request_payload["messages"]) == 3
    assert "Use perplexity-sonar-pro" in request_payload["system"]

    # Test the run's output
    assert res["tool_calls"] == [
        {
            "id": "@perplexity-sonar-pro_888d53255ea5c85ece1ec3b1f0213860",
            "name": "@perplexity-sonar-pro",
            "input_preview": 'query: "What was the final score of the Utah Jazz vs Los Angeles Lakers basketball game on February 12, 2025?"',
            "output_preview": '{"answer": "131-119"}',
        },
    ]
    assert (
        res["task_output"]["answer"]
        == "The score of the latest Jazz - Lakers game of Feb 12th, 2025 is 131-119 in favor of the Utah Jazz."
    )
