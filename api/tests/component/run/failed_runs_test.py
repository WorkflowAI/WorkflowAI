import json
from typing import Any

from httpx import AsyncClient
from pytest_httpx import HTTPXMock, IteratorStream
from taskiq import InMemoryBroker

from core.domain.models import Provider
from tests.component.common import (
    IntegrationTestClient,
    create_task,
    fetch_run,
    mock_openai_call,
    openai_endpoint,
    result_or_raise,
    task_schema_url,
    task_schema_url_v1,
    wait_for_completed_tasks,
)


async def test_failed_run_with_unknown_error_is_stored_for_openai(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    mock_openai_call(
        httpx_mock=test_client.httpx_mock,
        status_code=400,
        json={
            "error": {
                "message": "Sorry! We've encountered an issue with repetitive patterns in your prompt. Please try again with a different prompt.",
                "type": "invalid_request_error",
                "param": "prompt",
                "code": "invalid_prompt",
            },
        },
    )
    # Forcing the provider to avoid a fallback
    # Not using the run fn to check the error message
    run_res = await test_client.int_api_client.post(
        task_schema_url_v1(task, "run"),
        json={
            "version": {"model": "gpt-4o-2024-11-20", "provider": Provider.OPEN_AI},
            "task_input": {"name": "John", "age": 30},
        },
    )

    await test_client.wait_for_completed_tasks()

    # Run the task the first time
    assert run_res.status_code == 400
    run_error_json = run_res.json()
    assert (
        run_error_json["error"]["message"]
        == "Sorry! We've encountered an issue with repetitive patterns in your prompt. Please try again with a different prompt."
    )
    assert run_error_json.get("id")

    # fetch run
    run = await fetch_run(test_client.int_api_client, task, run_id=run_error_json["id"])
    assert run["id"] == run_error_json["id"]
    assert run["status"] == "failure"
    assert run["error"]["code"] == "unknown_provider_error"
    assert run["cost_usd"] == 0
    # assert run["duration_seconds"] is None
    assert run["llm_completions"] and len(run["llm_completions"]) == 1
    msgs = run["llm_completions"][0]["messages"]
    assert len(msgs) == 2 and msgs[0]["role"] == "system" and msgs[1]["role"] == "user"
    usage = run["llm_completions"][0]["usage"]
    assert usage["prompt_token_count"] == 118.0
    assert usage["model_context_window_size"] == 128000  # from model


async def test_failed_run_invalid_output_is_stored_for_openai(
    httpx_mock: HTTPXMock,
    int_api_client: AsyncClient,
    patched_broker: InMemoryBroker,
):
    task = await create_task(int_api_client, patched_broker, httpx_mock)

    # Validate the schema output will fail
    httpx_mock.add_response(
        url=openai_endpoint(),
        json={
            "id": "1",
            "choices": [{"message": {"content": '{"greeting": 1}'}}],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 11,
                "total_tokens": 21,
            },
        },
        # 2 calls since one for structured output and one for the error
        is_reusable=True,
    )

    run_res = await int_api_client.post(
        task_schema_url_v1(task, "run"),
        json={
            "version": {"model": "gpt-4o-2024-11-20"},
            "task_input": {"name": "John", "age": 30},
            "use_fallback": "never",
        },
    )
    await wait_for_completed_tasks(patched_broker)

    # Run the task the first time
    assert run_res.status_code == 400
    run_error_json = run_res.json()
    assert run_error_json["error"]["message"] == "Task output does not match schema"
    assert run_error_json.get("id")

    # fetch run
    run = await fetch_run(int_api_client, task, run_id=run_error_json["id"])
    assert run["id"] == run_error_json["id"]
    assert run["status"] == "failure"
    assert run["error"]["code"] == "failed_generation"
    assert run["cost_usd"] > 0
    assert run["duration_seconds"] is None
    assert run["llm_completions"] and len(run["llm_completions"]) == 2
    msgs = run["llm_completions"][0]["messages"]
    assert len(msgs) == 2 and msgs[0]["role"] == "system" and msgs[1]["role"] == "user"
    usage = run["llm_completions"][0]["usage"]
    assert usage["prompt_token_count"] == 10
    assert usage["completion_token_count"] == 11
    assert usage["model_context_window_size"] == 128000  # from model

    # Fetch all runs without query params
    runs = result_or_raise(await int_api_client.get(task_schema_url(task, "runs")))["items"]
    assert len(runs) == 0

    # Fetch all runs with query params
    runs = result_or_raise(await int_api_client.get(task_schema_url(task, "runs?status=success&status=failure")))[
        "items"
    ]
    assert len(runs) == 1


async def test_failed_run_invalid_output_is_stored_for_openai_stream(
    httpx_mock: HTTPXMock,
    int_api_client: AsyncClient,
    patched_broker: InMemoryBroker,
):
    task = await create_task(int_api_client, patched_broker, httpx_mock)

    httpx_mock.add_response(
        url=openai_endpoint(),
        stream=IteratorStream(
            [
                b'data: {"id":"1","object":"chat.completion.chunk","created":1720404416,"model":"gpt-4o-2024-11-20","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"role":"assistant","content":""},"logprobs":null,',
                b'"finish_reason":null}]}\n\ndata: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-4o-2024-11-20","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"content":"{\\n"},"logprobs":null,"finish_reason":null}]}\n\n',
                b'data: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"content":"\\"greeting\\": 1\\n}"},"logprobs":null,"finish_reason":null}]}\n\n',
                b"data: [DONE]\n\n",
            ],
        ),
        # 2 calls since one for structured output and one for the error
        is_reusable=True,
    )
    async with int_api_client.stream(
        "POST",
        task_schema_url_v1(task, "run"),
        json={
            "version": {"model": "gpt-4o-2024-11-20"},
            "task_input": {"name": "John", "age": 30},
            "stream": True,
            "use_fallback": "never",
        },
    ) as response:
        response.raise_for_status()  # response should still return a 200
        chunks = [c async for c in response.aiter_text()]

    await wait_for_completed_tasks(patched_broker)
    # Run the task the first time
    assert len(chunks) == 1
    decoded = json.loads(chunks[-1][6:-2])
    assert decoded.get("error")
    assert decoded.get("task_run_id")
    # assert run_res.status_code == 400
    # run_error_json = run_res.json()
    # assert run_error_json["error"]["message"] == "Model failed to generate a valid json: at [greeting], 1 is not of type 'string'"
    # assert run_error_json.get("id")

    # fetch run
    run = await fetch_run(int_api_client, task, run_id=decoded["task_run_id"])
    assert run["id"] == decoded["task_run_id"]
    assert run["status"] == "failure"
    assert run["error"]["code"] == "invalid_generation"
    assert run["cost_usd"] > 0
    # assert run["duration_seconds"] is None

    assert run["llm_completions"] and len(run["llm_completions"]) == 2
    msgs = run["llm_completions"][0]["messages"]
    assert len(msgs) == 2 and msgs[0]["role"] == "system" and msgs[1]["role"] == "user"
    usage = run["llm_completions"][0]["usage"]
    assert usage["prompt_token_count"] == 118.0
    assert usage["model_context_window_size"] == 128000  # from model


async def test_max_context_exceeded_gemini_stream(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    # Stream 3 chunls total spelling '{"greeting": "he' and raising a MAX_TOKENS error
    test_client.mock_vertex_stream(
        deltas=[
            '{"greetin',
            'g": "h',
            ("", {"finishReason": "MAX_TOKENS"}),
        ],
        region="global",
    )

    chunks: list[dict[str, Any]] = []

    async with test_client.int_api_client.stream(
        "POST",
        task_schema_url_v1(task, "run"),
        json={
            "version": {"model": test_client.DEFAULT_VERTEX_MODEL},
            "task_input": {"name": "John", "age": 30},
            "stream": True,
        },
    ) as response:
        response.raise_for_status()  # response should still return a 200
        chunks = [json.loads(c.removeprefix(b"data: ")) async for c in response.aiter_bytes()]

    assert len(chunks) == 2
    assert chunks[1]["task_output"] == {"greeting": "h"}, "sanity"

    assert "error" in chunks[1]
    assert chunks[1]["error"]["code"] == "max_tokens_exceeded"
    assert chunks[1]["task_output"] == {"greeting": "h"}

    await test_client.wait_for_completed_tasks()

    run = await fetch_run(test_client.int_api_client, task=task, run_id=chunks[1]["task_run_id"])
    assert run["status"] == "failure"
    assert run["error"]["code"] == "max_tokens_exceeded"
    assert run["task_output"] == {"greeting": "h"}
    assert run["cost_usd"] > 0

    # TODO: check usage and llm completions


async def test_max_context_exceeded_gemini_stream_no_content(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    # Stream 3 chunls total spelling '{"greeting": "he' and raising a MAX_TOKENS error
    test_client.mock_vertex_stream(
        deltas=[
            (None, {"finishReason": "MAX_TOKENS"}),
        ],
        region="global",
    )

    chunks: list[dict[str, Any]] = []

    async with test_client.int_api_client.stream(
        "POST",
        task_schema_url_v1(task, "run"),
        json={
            "version": {"model": test_client.DEFAULT_VERTEX_MODEL},
            "task_input": {"name": "John", "age": 30},
            "stream": True,
        },
    ) as response:
        response.raise_for_status()  # response should still return a 200
        chunks = [json.loads(c.removeprefix(b"data: ")) async for c in response.aiter_bytes()]

    assert len(chunks) == 1
    # assert chunks[0]["task_output"] == {"greeting": "h"}, "sanity"

    assert "error" in chunks[0]
    assert chunks[0]["error"]["code"] == "max_tokens_exceeded"

    await test_client.wait_for_completed_tasks()

    run = await fetch_run(test_client.int_api_client, task=task, run_id=chunks[0]["task_run_id"])
    assert run["status"] == "failure"
    assert run["error"]["code"] == "max_tokens_exceeded"
    assert run["cost_usd"] != 0

    # TODO: check usage and llm completions


async def test_failed_run_azure_content_moderation(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    test_client.mock_openai_call(
        status_code=400,
        json={
            "error": {
                "message": "The response was filtered due to the prompt triggering Azure OpenAI's content management policy. Please modify your prompt and retry. To learn more about our content filtering policies please read our documentation:",
            },
        },
    )

    run_res = await test_client.int_api_client.post(
        task_schema_url_v1(task, "run"),
        json={
            "version": {"model": "gpt-4o-2024-11-20"},
            "task_input": {"name": "John", "age": 30},
            "use_fallback": "never",
        },
    )

    await test_client.wait_for_completed_tasks()

    assert run_res.status_code == 400
    run_error_json = run_res.json()
    assert (
        run_error_json["error"]["message"]
        == "The response was filtered due to the prompt triggering Azure OpenAI's content management policy. Please modify your prompt and retry. To learn more about our content filtering policies please read our documentation:"
    )
    assert run_error_json.get("id")

    assert run_error_json["error"]["code"] == "content_moderation"


async def test_failed_run_bedrock_refusal(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    test_client.httpx_mock.add_response(
        url="https://bedrock-runtime.us-west-2.amazonaws.com/model/us.anthropic.claude-3-haiku-20240307-v1:0/converse",
        status_code=400,
        json={
            "message": "Bedrock is unable to process your request.",
        },
    )
    run_res = await test_client.int_api_client.post(
        task_schema_url_v1(task, "run"),
        json={
            "version": {"model": "claude-3-haiku-20240307", "provider": Provider.AMAZON_BEDROCK},
            "task_input": {"name": "John", "age": 30},
        },
    )

    await test_client.wait_for_completed_tasks()

    run_error_json = run_res.json()
    assert run_error_json["error"]["message"] == "Bedrock is unable to process your request."
    assert run_error_json["error"]["code"] == "provider_internal_error"


async def test_failed_run_bedrock_refusal_stream(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    test_client.httpx_mock.add_response(
        url="https://bedrock-runtime.us-west-2.amazonaws.com/model/us.anthropic.claude-3-haiku-20240307-v1:0/converse-stream",
        stream=IteratorStream(
            [
                b'\x00\x00\x00\xb1\x00\x00\x00i|\xeb\'1\x0f:exception-type\x07\x00\x1bserviceUnavailableException\r:content-type\x07\x00\x10application/json\r:message-type\x07\x00\texception{"message":"Bedrock is unable to process your request."}\x89\x812}',
            ],
        ),
    )

    async with test_client.int_api_client.stream(
        "POST",
        task_schema_url_v1(task, "run"),
        json={
            "version": {"model": "claude-3-haiku-20240307", "provider": Provider.AMAZON_BEDROCK},
            "task_input": {"name": "John", "age": 30},
            "stream": True,
        },
    ) as response:
        response.raise_for_status()
        chunks = [json.loads(c.removeprefix(b"data: ")) async for c in response.aiter_bytes()]

    await test_client.wait_for_completed_tasks()

    assert len(chunks) == 1
    assert chunks[0]["error"]["message"] == "Bedrock is unable to process your request."
    assert chunks[0]["error"]["code"] == "provider_internal_error"
