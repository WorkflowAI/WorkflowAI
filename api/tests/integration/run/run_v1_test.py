import asyncio
import json
import re
from base64 import b64encode
from typing import Any
from unittest.mock import Mock, patch

import httpx
import pytest
from httpx import AsyncClient, HTTPStatusError
from pytest_httpx import HTTPXMock, IteratorStream
from taskiq import InMemoryBroker

from core.domain.consts import METADATA_KEY_USED_MODEL
from core.domain.models import Model, Provider
from core.domain.models.model_datas_mapping import MODEL_DATAS
from core.domain.models.model_provider_datas_mapping import OPENAI_PROVIDER_DATA
from core.providers.google.google_provider_domain import (
    Candidate,
    CompletionResponse,
    Content,
    Part,
    UsageMetadata,
)
from core.utils.ids import id_uint32
from tests.integration.common import (
    LEGACY_TEST_JWT,
    IntegrationTestClient,
    create_task,
    create_task_without_required_fields,
    create_version,
    extract_stream_chunks,
    fetch_run,
    get_amplitude_requests,
    list_groups,
    mock_gemini_call,
    mock_openai_call,
    mock_vertex_call,
    openai_endpoint,
    result_or_raise,
    run_task_v1,
    stream_run_task_v1,
    task_schema_url,
    wait_for_completed_tasks,
)
from tests.utils import fixture_bytes, fixtures_json, request_json_body


async def test_run_with_metadata(
    httpx_mock: HTTPXMock,
    int_api_client: AsyncClient,
    patched_broker: InMemoryBroker,
):
    task = await create_task(int_api_client, patched_broker, httpx_mock)

    mock_vertex_call(
        httpx_mock,
        publisher="google",
        model="gemini-1.5-pro-002",
        latency=0.01,
    )

    # Run the task the first time
    task_run = await run_task_v1(
        int_api_client,
        task_id="greet",
        task_schema_id=1,
        task_input={"name": "John", "age": 30},
        model="gemini-1.5-pro-002",
        metadata={"key1": "value1", "key2": "value2"},
    )

    # Check returned cost
    assert task_run["cost_usd"] == pytest.approx(0.000169, abs=1e-6)  # pyright: ignore[reportUnknownMemberType]

    await wait_for_completed_tasks(patched_broker)

    # Check groups
    groups = await list_groups(int_api_client, task)
    assert len(groups) == 1
    assert groups[0]["properties"]["model"] == "gemini-1.5-pro-002"
    assert "provider" not in groups[0]["properties"]
    assert groups[0]["run_count"] == 1

    # Fetch the task run

    fetched = await int_api_client.get(f"/chiefofstaff.ai/agents/greet/runs/{task_run['id']}")
    assert fetched.status_code == 200
    fetched_task_run = fetched.json()

    assert fetched_task_run["metadata"]["workflowai.overhead_seconds"]
    assert fetched_task_run["metadata"]["workflowai.inference_seconds"]

    assert fetched_task_run["metadata"]["key1"] == "value1"
    assert fetched_task_run["metadata"]["key2"] == "value2"
    assert fetched_task_run["metadata"]["workflowai.vertex_api_region"] == "us-central1"
    assert fetched_task_run["metadata"]["workflowai.providers"] == ["google"]
    assert fetched_task_run["metadata"]["workflowai.provider"] == "google"

    await wait_for_completed_tasks(patched_broker)

    amplitude_requests = await get_amplitude_requests(httpx_mock)
    assert len(amplitude_requests) == 1
    event = amplitude_requests[0]["events"][0]

    org = result_or_raise(await int_api_client.get("/_/organization/settings"))

    assert event["user_id"] == org["tenant"]
    assert event["event_type"] == "org.ran.task"

    # Can't predict the value
    latency_seconds = event["event_properties"]["latency_seconds"]
    assert latency_seconds > 0

    assert event["event_properties"] == {
        "cost_usd": pytest.approx(0.000169, abs=1e-6),  # pyright: ignore[reportUnknownMemberType]
        "group": {
            "few_shot": False,
            "iteration": 1,
            "model": "gemini-1.5-pro-002",
            "temperature": 0.0,
        },
        "input_tokens_count": 110.25,
        "is_workflowai_llm_provider_key": True,
        "latency_seconds": latency_seconds,  #
        "output_tokens_count": 6.25,
        "task": {
            "id": "greet",
            "schema_id": 1,
            "organization_id": "org_2iPlfJ5X4LwiQybM9qeT00YPdBe",
            "organization_slug": "test-21",
        },
        "tokens_count": 116.5,
        "trigger": "user",
        "user": {
            "client_source": "api",
            "user_email": "guillaume@chiefofstaff.ai",
        },
    }


async def test_decrement_credits(httpx_mock: HTTPXMock, int_api_client: AsyncClient, patched_broker: InMemoryBroker):
    await create_task(int_api_client, patched_broker, httpx_mock)

    org = result_or_raise(await int_api_client.get("/_/organization/settings"))
    assert org["added_credits_usd"] == 10.0
    assert org["current_credits_usd"] == 10.0

    mock_openai_call(httpx_mock)

    await run_task_v1(
        int_api_client,
        task_id="greet",
        task_schema_id=1,
        task_input={"name": "John", "age": 30},
        model="gpt-4o-2024-05-13",
    )

    await wait_for_completed_tasks(patched_broker)

    org = result_or_raise(await int_api_client.get("/_/organization/settings"))
    assert org["added_credits_usd"] == 10.0
    assert org["current_credits_usd"] == 10.0 - 0.000135


async def test_usage_for_per_char_model(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
):
    await create_task(int_api_client, patched_broker, httpx_mock)

    httpx_mock.add_response(
        url="https://us-central1-aiplatform.googleapis.com/v1/projects/worfklowai/locations/us-central1/publishers/google/models/gemini-1.5-pro-002:generateContent",
        json=CompletionResponse(
            candidates=[Candidate(content=Content(role="model", parts=[Part(text='{"greeting": "Hello John!"}')]))],
            usageMetadata=UsageMetadata(promptTokenCount=222, candidatesTokenCount=9, totalTokenCount=231),
        ).model_dump(),
    )

    # Run the task the first time
    task_run = await run_task_v1(
        int_api_client,
        task_id="greet",
        task_schema_id=1,
        task_input={"name": "John", "age": 30},
        model="gemini-1.5-pro-002",
    )

    assert task_run["cost_usd"] == pytest.approx(0.000169, abs=1e-6)  # pyright: ignore[reportUnknownMemberType]
    assert "duration_seconds" in task_run

    await wait_for_completed_tasks(patched_broker)

    # Fetch the task run

    fetched = await int_api_client.get(f"/chiefofstaff.ai/agents/greet/runs/{task_run['id']}")
    assert fetched.status_code == 200
    fetched_task_run = fetched.json()

    llm_completions: list[dict[str, Any]] = fetched_task_run["llm_completions"]
    assert len(llm_completions) == 1
    assert llm_completions[0].get("response") == '{"greeting": "Hello John!"}'
    assert llm_completions[0].get("messages")

    usage: dict[str, Any] | None = llm_completions[0].get("usage")
    assert usage
    assert usage["prompt_token_count"] == 110.25
    assert usage["completion_token_count"] == 25 / 4  # 25 chars / 4
    assert usage["model_context_window_size"] == 2097152  # from model


async def test_usage_for_per_token_model(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
):
    await create_task(int_api_client, patched_broker, httpx_mock)

    mock_vertex_call(
        httpx_mock,
        publisher="meta",
        model="llama3-405b-instruct-maas",
        parts=[{"text": '{"greeting": "Hello John!"}', "inlineData": None}],
        usage={"promptTokenCount": 222, "candidatesTokenCount": 9, "totalTokenCount": 231},
    )

    # Run the task the first time
    task_run = await run_task_v1(
        int_api_client,
        task_id="greet",
        task_schema_id=1,
        task_input={"name": "John", "age": 30},
        version={"provider": "google", "model": "llama-3.1-405b"},
    )

    assert pytest.approx(0.001254, 0.00001) == task_run["cost_usd"]  # pyright: ignore [reportUnknownMemberType]

    await wait_for_completed_tasks(patched_broker)

    # Fetch the task run

    fetched_task_run = result_or_raise(await int_api_client.get(f"/chiefofstaff.ai/agents/greet/runs/{task_run['id']}"))

    llm_completions: list[dict[str, Any]] = fetched_task_run["llm_completions"]
    assert len(llm_completions) == 1
    assert llm_completions[0].get("response") == '{"greeting": "Hello John!"}'
    assert llm_completions[0].get("messages")

    usage: dict[str, Any] | None = llm_completions[0].get("usage")
    assert usage
    assert usage["prompt_token_count"] == 222  # from initial usage
    assert usage["completion_token_count"] == 9  # from initial usage
    assert usage["model_context_window_size"] == 128000  # from model


async def test_cost_for_zero_cost_gemini_model(
    httpx_mock: HTTPXMock,
    int_api_client: AsyncClient,
    patched_broker: InMemoryBroker,
):
    await create_task(int_api_client, patched_broker, httpx_mock)

    mock_gemini_call(httpx_mock, model="gemini-exp-1206")

    task_run = await run_task_v1(
        int_api_client,
        task_id="greet",
        task_schema_id=1,
        task_input={"name": "John", "age": 30},
        model="gemini-exp-1206",
    )

    assert task_run["cost_usd"] == 0


async def test_openai_usage(httpx_mock: HTTPXMock, int_api_client: AsyncClient, patched_broker: InMemoryBroker):
    await create_task(int_api_client, patched_broker, httpx_mock)

    mock_openai_call(httpx_mock)

    # Run the task the first time
    task_run = await run_task_v1(
        int_api_client,
        task_id="greet",
        task_schema_id=1,
        task_input={"name": "John", "age": 30},
        model="gpt-4o-2024-05-13",
    )
    await wait_for_completed_tasks(patched_broker)

    fetched_task_run = result_or_raise(await int_api_client.get(f"/chiefofstaff.ai/agents/greet/runs/{task_run['id']}"))

    llm_completions: list[dict[str, Any]] = fetched_task_run["llm_completions"]
    assert len(llm_completions) == 1
    assert llm_completions[0].get("response") == '{"greeting": "Hello James!"}'
    assert llm_completions[0].get("messages")

    usage: dict[str, Any] | None = llm_completions[0].get("usage")
    assert usage
    assert usage["prompt_token_count"] == 10
    assert usage["completion_token_count"] == 11
    assert usage["model_context_window_size"] == 128000  # from model


async def test_openai_usage_with_usage_and_cached_tokens(
    httpx_mock: HTTPXMock,
    int_api_client: AsyncClient,
    patched_broker: InMemoryBroker,
):
    await create_task(int_api_client, patched_broker, httpx_mock)

    mock_openai_call(
        httpx_mock,
        usage={
            "prompt_tokens": 10,
            "prompt_tokens_details": {"cached_tokens": 5},
            "completion_tokens": 11,
            "total_tokens": 21,
        },
    )

    task_run = await run_task_v1(
        int_api_client,
        task_id="greet",
        task_schema_id=1,
        task_input={"name": "John", "age": 30},
        model="gpt-4o-2024-11-20",
    )

    await wait_for_completed_tasks(patched_broker)

    fetched_task_run = result_or_raise(await int_api_client.get(f"/chiefofstaff.ai/agents/greet/runs/{task_run['id']}"))

    llm_completions: list[dict[str, Any]] = fetched_task_run["llm_completions"]
    assert len(llm_completions) == 1
    assert llm_completions[0].get("response") == '{"greeting": "Hello James!"}'
    assert llm_completions[0].get("messages")

    usage: dict[str, Any] | None = llm_completions[0].get("usage")
    assert usage
    assert usage["prompt_token_count"] == 10
    assert usage["completion_token_count"] == 11
    assert usage["prompt_token_count_cached"] == 5
    # 5 * 0.0000025 + 5 * 0.00000125 (50% price for cached tokens)
    assert usage["prompt_cost_usd"] == pytest.approx(0.00001875, abs=1e-10)  # pyright: ignore [reportUnknownMemberType]
    assert usage["completion_cost_usd"] == 0.00011  # 11 * 0.000010
    assert usage["model_context_window_size"] == 128000  # from model


async def test_openai_stream(
    httpx_mock: HTTPXMock,
    int_api_client: AsyncClient,
    patched_broker: InMemoryBroker,
):
    await create_task(int_api_client, patched_broker, httpx_mock)

    httpx_mock.add_response(
        url=openai_endpoint(),
        stream=IteratorStream(
            [
                b'data: {"id":"1","object":"chat.completion.chunk","created":1720404416,"model":"gpt-4o-2024-11-20","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"role":"assistant","content":""},"logprobs":null,',
                b'"finish_reason":null}]}\n\ndata: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-4o-2024-11-20","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"content":"{\\n"},"logprobs":null,"finish_reason":null}]}\n\n',
                b'data: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","usage": {"prompt_tokens": 35, "completion_tokens": 109, "total_tokens": 144},"choices":[{"index":0,"delta":{"content":"\\"greeting\\": \\"Hello James!\\"\\n}"},"logprobs":null,"finish_reason":null}]}\n\n',
                b"data: [DONE]\n\n",
            ],
        ),
    )

    # Run the task the first time
    task_run = stream_run_task_v1(
        int_api_client,
        task_id="greet",
        task_schema_id=1,
        task_input={"name": "John", "age": 30},
        model="gpt-4o-2024-11-20",
    )
    chunks = [c async for c in extract_stream_chunks(task_run)]

    await wait_for_completed_tasks(patched_broker)

    assert len(chunks) == 3
    assert chunks[0].get("id")

    for chunk in chunks[1:]:
        assert chunk.get("id") == chunks[0]["id"]

    assert chunks[-1]["task_output"] == {"greeting": "Hello James!"}
    assert chunks[-1]["cost_usd"] == 35 * 0.0000025 + 109 * 0.000010
    assert chunks[-1]["duration_seconds"] > 0


class TestChainOfThought:
    async def setup_task_and_version(
        self,
        test_client: IntegrationTestClient,
        model: str = "gemini-1.5-pro-002",
        should_use_chain_of_thought: bool = True,
    ):
        task = await test_client.create_task()

        test_client.mock_internal_task(
            "detect-chain-of-thought",
            task_output={"should_use_chain_of_thought": should_use_chain_of_thought},
        )

        version_response = await test_client.create_version(
            task=task,
            version_properties={"instructions": "some instructions", "model": model},
        )
        iteration: int = version_response["iteration"]
        assert version_response["properties"]["is_chain_of_thought_enabled"] is should_use_chain_of_thought
        return task, iteration

    async def test_run_with_steps(self, test_client: IntegrationTestClient):
        task, iteration = await self.setup_task_and_version(test_client)

        test_client.mock_vertex_call(
            model="gemini-1.5-pro-002",
            parts=[
                {
                    "text": '{"internal_agent_run_result": {"status": "success", "error": None},"internal_reasoning_steps": [{"title": "step title", "explaination": "step explaination", "output": "step output"}], "greeting": "Hello John!"}',
                    "inlineData": None,
                },
            ],
            usage={"promptTokenCount": 222, "candidatesTokenCount": 9, "totalTokenCount": 231},
        )

        task_run = await test_client.run_task_v1(
            task=task,
            task_input={"name": "John", "age": 32},
            version=iteration,
            metadata={"key1": "value1", "key2": "value2"},
        )

        # Check that "internal_reasoning_steps" is in the request body
        http_request = test_client.httpx_mock.get_request(url=re.compile(r".*googleapis.*"))
        assert http_request
        assert http_request.method == "POST"
        assert "internal_reasoning_steps" in http_request.content.decode("utf-8")

        assert task_run["task_output"] == {
            "greeting": "Hello John!",
        }
        assert task_run["reasoning_steps"] == [
            {"title": "step title", "step": "step explaination"},
        ]

        await test_client.wait_for_completed_tasks()

        fetched = await test_client.int_api_client.get(f"/v1/chiefofstaff.ai/agents/greet/runs/{task_run['id']}")
        assert fetched.status_code == 200
        fetched_task_run = fetched.json()
        assert fetched_task_run["task_output"] == {
            "greeting": "Hello John!",
        }
        assert fetched_task_run["reasoning_steps"] == [
            {"title": "step title", "step": "step explaination"},
        ]

        test_client.httpx_mock.reset(assert_all_responses_were_requested=False)

        # Re-run and trigger the cache
        cached_run = await test_client.run_task_v1(
            task=task,
            task_input={"name": "John", "age": 32},
            version=iteration,
            metadata={"key1": "value1", "key2": "value2"},
        )
        assert cached_run["reasoning_steps"] == [
            {"title": "step title", "step": "step explaination"},
        ]

    async def test_stream_with_steps(self, test_client: IntegrationTestClient):
        task, iteration = await self.setup_task_and_version(test_client, model="gpt-4o-2024-11-20")

        test_client.mock_openai_stream(
            deltas=[
                '{"internal_agent_run_result":{"status":"success","error":null},"internal_reasoning_steps":[{"title":"step ',
                'title","explaination":"step',
                ' explaination","output":"step output',
                '"}],"greeting":"Hello John!"}',
            ],
        )

        chunks = [
            c
            async for c in test_client.stream_run_task_v1(
                task=task,
                task_input={"name": "John", "age": 32},
                version=iteration,
                metadata={"key1": "value1", "key2": "value2"},
            )
        ]

        assert len(chunks) == 6
        assert chunks[0]["reasoning_steps"] == [{"title": "step "}]
        assert chunks[-1]["task_output"] == {"greeting": "Hello John!"}

        assert chunks[-1]["reasoning_steps"] == [
            {"title": "step title", "step": "step explaination"},
        ]

        # Do it again and trigger the cache
        chunks = [
            c
            async for c in test_client.stream_run_task_v1(
                task=task,
                task_input={"name": "John", "age": 32},
                version=iteration,
                metadata={"key1": "value1", "key2": "value2"},
            )
        ]

        assert len(chunks) == 2
        assert chunks[0]["task_output"] == chunks[-1]["task_output"] == {"greeting": "Hello John!"}
        assert (
            chunks[0]["reasoning_steps"]
            == chunks[-1]["reasoning_steps"]
            == [
                {"title": "step title", "step": "step explaination"},
            ]
        )

    async def test_run_without_steps(self, test_client: IntegrationTestClient):
        task, iteration = await self.setup_task_and_version(test_client, should_use_chain_of_thought=False)

        test_client.mock_vertex_call(
            model="gemini-1.5-pro-002",
            parts=[{"text": '{"greeting": "Hello John!"}', "inlineData": None}],
            usage={"promptTokenCount": 222, "candidatesTokenCount": 9, "totalTokenCount": 231},
        )

        task_run = await test_client.run_task_v1(
            task=task,
            task_input={"name": "John", "age": 30},
            version=iteration,
            metadata={"key1": "value1", "key2": "value2"},
        )

        # Check that "internal_reasoning_steps" is in the request body
        http_request = test_client.httpx_mock.get_request(url=re.compile(r".*googleapis.*"))
        assert http_request
        assert http_request.method == "POST"
        assert "internal_reasoning_steps" not in http_request.content.decode("utf-8")

        # assert task_run["version"]["properties"]["is_chain_of_thought_enabled"] is False
        assert task_run["task_output"] == {
            "greeting": "Hello John!",
        }
        assert "reasoning_steps" not in task_run

        await test_client.wait_for_completed_tasks()

        fetched = result_or_raise(
            await test_client.int_api_client.get(f"/chiefofstaff.ai/agents/greet/runs/{task_run['id']}"),
        )

        assert fetched["task_output"] == {
            "greeting": "Hello John!",
        }


async def test_run_with_500_error(httpx_mock: HTTPXMock, int_api_client: AsyncClient, patched_broker: InMemoryBroker):
    await create_task_without_required_fields(int_api_client, patched_broker, httpx_mock)

    # Add an evaluator to the task
    mock_openai_call(httpx_mock, status_code=500)
    mock_openai_call(httpx_mock, status_code=500, provider="azure_openai")

    # Run the task the first time
    with pytest.raises(HTTPStatusError) as e:
        await run_task_v1(
            int_api_client,
            task_id="greet",
            task_schema_id=1,
            task_input={"name": "John", "age": 30},
            model="gpt-4o-2024-11-20",
        )
    assert e.value.response.status_code == 424

    await wait_for_completed_tasks(patched_broker)

    requests = await get_amplitude_requests(httpx_mock)
    assert len(requests) == 1
    assert requests[0]["events"][0]["event_properties"]["error_code"] == "provider_internal_error"


@pytest.fixture(scope="function", params=[True, False])
def block_run_for_no_credits(request: pytest.FixtureRequest):
    from api.dependencies import run as run_deps

    _prev_block_run_for_no_credits = run_deps._BLOCK_RUN_FOR_NO_CREDITS  # pyright: ignore [reportPrivateUsage]
    run_deps._BLOCK_RUN_FOR_NO_CREDITS = request.param  # pyright: ignore [reportPrivateUsage]
    yield request.param
    run_deps._BLOCK_RUN_FOR_NO_CREDITS = _prev_block_run_for_no_credits  # pyright: ignore [reportPrivateUsage]


async def test_run_schema_insufficient_credits(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
    block_run_for_no_credits: bool,
):
    # Create a task with the patched broker and HTTPXMock
    await create_task(int_api_client, patched_broker, httpx_mock)

    # Fetch the organization settings before running the task
    org = result_or_raise(await int_api_client.get("/_/organization/settings"))
    assert org["current_credits_usd"] == 10.0  # Initial credits are $5.00

    # Get the model's cost per token for the specific model (GPT-4o-2024-05-13)
    model_data = OPENAI_PROVIDER_DATA[Model.GPT_4O_2024_11_20]
    prompt_cost_per_token = model_data.text_price.prompt_cost_per_token

    # Adjust the number of prompt tokens to account for floating-point precision issues
    tokens_for_one_dollar = int(round(1 / prompt_cost_per_token))

    # Mock the OpenAI API response with usage that costs slightly more than $1
    mock_openai_call(
        httpx_mock,
        usage={
            "prompt_tokens": 6 * tokens_for_one_dollar,
            "completion_tokens": 0,  # No completion tokens
        },
    )

    # Create and run a task that consumes $6 worth of prompt tokens
    run1 = await run_task_v1(
        int_api_client,
        task_id="greet",
        task_schema_id=1,
        task_input={"name": "John", "age": 30},
        model="gpt-4o-2024-11-20",
    )
    await wait_for_completed_tasks(patched_broker)
    assert pytest.approx(run1["cost_usd"], 0.001) == 6.0, "sanity"  # pyright: ignore [reportUnknownMemberType]

    # Check that credits have been reduced by $1
    org = result_or_raise(await int_api_client.get("/_/organization/settings"))
    assert pytest.approx(org["current_credits_usd"], 0.001) == 4.0  ## pyright: ignore [reportUnknownMemberType]

    # Now we should succeed again but credits will be negative
    await run_task_v1(
        int_api_client,
        task_id="greet",
        task_schema_id=1,
        task_input={"name": "John", "age": 31},
        model="gpt-4o-2024-11-20",
    )

    await wait_for_completed_tasks(patched_broker)

    org = result_or_raise(await int_api_client.get("/_/organization/settings"))
    assert pytest.approx(org["current_credits_usd"], 0.001) == -2.0  # pyright: ignore [reportUnknownMemberType]

    if block_run_for_no_credits:
        with pytest.raises(HTTPStatusError) as e:
            await run_task_v1(
                int_api_client,
                task_id="greet",
                task_schema_id=1,
                task_input={"name": "John", "age": 30},
                model="gpt-4o-2024-11-20",
            )

        assert e.value.response.status_code == 402
    else:
        await run_task_v1(
            int_api_client,
            task_id="greet",
            task_schema_id=1,
            task_input={"name": "John", "age": 30},
            model="gpt-4o-2024-11-20",
        )


async def test_run_public_task_with_different_tenant(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
):
    task = await create_task(int_api_client, patched_broker, httpx_mock)
    mock_openai_call(
        httpx_mock,
        usage={
            "prompt_tokens": int(round(2 * 1 / 0.000_002_5)),  # prompt count for 2$ on GPT_4O_2024_11ß_20
            "completion_tokens": 0,  # No completion tokens
        },
    )

    # No groups yet
    groups = await list_groups(int_api_client, task)
    assert len(groups) == 0, "sanity"

    _DIFFERENT_JWT = "eyJhbGciOiJFUzI1NiJ9.eyJ0ZW5hbnQiOiJub3RjaGllZm9mc3RhZmYuYWkiLCJzdWIiOiJndWlsbGF1bWVAbm90Y2hpZWZvZnN0YWZmLmFpIiwib3JnSWQiOiJhbm90aGVyX29ybCIsIm9yZ1NsdWciOiJhbm90aGVyLXRlc3QtMjEiLCJpYXQiOjE3MTU5ODIzNTEsImV4cCI6MTgzMjE2NjM1MX0.tGlIHc59ed_qAjXyb6aDtg16gsRVzcC6lBueU_E3k44NIO2XkBVAmN9CJO1PwUd5ldbHYsQCpw_wYMfkfW7GKw"

    other_client = AsyncClient(
        transport=int_api_client._transport,  # pyright: ignore [reportPrivateUsage]
        base_url=int_api_client.base_url,
        headers={
            "Authorization": f"Bearer {_DIFFERENT_JWT}",
        },
    )

    org_1 = result_or_raise(await int_api_client.get("/_/organization/settings"))
    assert org_1["current_credits_usd"] == 10.0, "sanity"
    assert org_1["slug"] == "test-21"  # sanity

    org_2 = result_or_raise(await other_client.get("/_/organization/settings"))
    assert org_2["current_credits_usd"] == 5.0, "sanity"
    assert org_2["slug"] == "another-test-21"  # sanity

    base_task_kwargs: dict[str, Any] = {
        "task_id": task["task_id"],
        "task_schema_id": task["task_schema_id"],
        "model": "gpt-4o-2024-11-20",
        "tenant": "test-21",
    }
    # Sanity check that we can't run the task with the other user
    with pytest.raises(HTTPStatusError) as e:
        await run_task_v1(other_client, task_input={"name": "John", "age": 30}, **base_task_kwargs)
    assert e.value.response.status_code == 404

    # Make the task public
    result_or_raise(await int_api_client.patch(f"/_/agents/{task['task_id']}", json={"is_public": True}))

    # Sanity check that we can fetch the task
    fetched_task = result_or_raise(
        await other_client.get(f"/test-21/agents/{task['task_id']}/schemas/{task['task_schema_id']}"),
    )
    assert fetched_task["name"] == "Greet"

    # Check that we can run the task with the other user
    task_run = await run_task_v1(
        other_client,
        task_input={"name": "John", "age": 31},
        **base_task_kwargs,
    )

    await wait_for_completed_tasks(patched_broker)

    fetched_task_run = result_or_raise(
        await int_api_client.get(f"/_/agents/greet/runs/{task_run['id']}"),
    )
    assert fetched_task_run["author_uid"] == org_2["uid"]
    assert fetched_task_run["group"]["iteration"] == 0

    await wait_for_completed_tasks(patched_broker)

    org_1 = result_or_raise(await int_api_client.get("/_/organization/settings"))
    assert org_1["current_credits_usd"] == 10.0, "credits should not be deducted from original organization"

    org_2 = result_or_raise(await other_client.get("/_/organization/settings"))
    assert pytest.approx(org_2["current_credits_usd"], 0.1) == 3  # pyright: ignore [reportUnknownMemberType]

    # List groups for the task
    groups = await list_groups(int_api_client, task)
    assert len(groups) == 0, "we should still not have any groups since the last one was run by another user"

    # Just for sanity, let's make sure we can run the task again with the original user
    task_run = await run_task_v1(
        int_api_client,
        task_input={"name": "John", "age": 31},
        **base_task_kwargs,
    )
    await wait_for_completed_tasks(patched_broker)
    fetched_task_run = result_or_raise(
        await int_api_client.get(f"/_/agents/greet/runs/{task_run['id']}"),
    )
    assert fetched_task_run["group"]["iteration"] == 1
    assert fetched_task_run.get("author_tenant") is None

    # Check groups
    groups = await list_groups(int_api_client, task)
    assert len(groups) == 1

    # Check that I can list runs with the other user
    runs = result_or_raise(await other_client.post("/v1/test-21/agents/greet/runs/search", json={}))
    assert len(runs["items"]) == 2


async def test_run_image(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
):
    task = await create_task(
        int_api_client,
        patched_broker,
        httpx_mock,
        input_schema={"type": "object", "properties": {"image": {"$ref": "#/$defs/File", "format": "image"}}},
    )

    mock_openai_call(httpx_mock)

    httpx_mock.add_response(
        url="https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExYXQxbTFybW0wZWs2M3RkY3gzNXZlbXp4aHhkcTl4ZzltN2V6Y21lcCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9cw/rkFQ8LrdXcP5e/giphy.webp",
        content=b"hello",
    )

    res = await run_task_v1(
        int_api_client,
        task_id=task["task_id"],
        task_schema_id=task["task_schema_id"],
        task_input={
            "image": {
                "url": "https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExYXQxbTFybW0wZWs2M3RkY3gzNXZlbXp4aHhkcTl4ZzltN2V6Y21lcCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9cw/rkFQ8LrdXcP5e/giphy.webp",
            },
        },
    )
    await wait_for_completed_tasks(patched_broker)
    fetched_task_run = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/runs/{res['id']}"),
    )
    assert fetched_task_run["task_input"]["image"]["content_type"] == "image/webp"


async def test_run_invalid_file(int_api_client: AsyncClient, httpx_mock: HTTPXMock, patched_broker: InMemoryBroker):
    task = await create_task(
        int_api_client,
        patched_broker,
        httpx_mock,
        input_schema={"type": "object", "properties": {"image": {"$ref": "#/$defs/File", "format": "image"}}},
    )

    mock_openai_call(
        httpx_mock,
        status_code=400,
        json={"error": {"message": "Image is not a valid file"}},
    )

    httpx_mock.add_response(
        # Content type is not guessable from URL but only from the data
        url="https://bla.com/file",
        content=b"1234",
    )

    with pytest.raises(HTTPStatusError) as e:
        await run_task_v1(
            int_api_client,
            task["task_id"],
            task["task_schema_id"],
            task_input={"image": {"url": "https://bla.com/file"}},
            # TODO: we should not have to force the provider here, the error should not be an unknonw provider error
            version={"model": Model.GPT_4O_2024_11_20, "provider": Provider.OPEN_AI},
        )

    assert e.value.response.status_code == 400


async def test_run_image_guessable_content_type(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
):
    task = await create_task(
        int_api_client,
        patched_broker,
        httpx_mock,
        input_schema={"type": "object", "properties": {"image": {"$ref": "#/$defs/File", "format": "image"}}},
    )

    mock_openai_call(httpx_mock)

    httpx_mock.add_response(
        # Content type is not guessable from URL but only from the data
        url="https://media3.giphy.com/media/giphy",
        content=fixture_bytes("files/test.webp"),
    )

    res = await run_task_v1(
        int_api_client,
        task_id=task["task_id"],
        task_schema_id=task["task_schema_id"],
        task_input={
            "image": {
                "url": "https://media3.giphy.com/media/giphy",
            },
        },
    )
    await wait_for_completed_tasks(patched_broker)
    fetched_task_run = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/runs/{res['id']}"),
    )
    assert fetched_task_run["task_input"]["image"]["content_type"] == "image/webp"

    req = httpx_mock.get_request(url=openai_endpoint())

    assert req
    req_body = request_json_body(req)

    image_url_content = req_body["messages"][1]["content"][1]  # text message is first, image message is second
    assert image_url_content["type"] == "image_url"
    assert image_url_content["image_url"]["url"] == "https://media3.giphy.com/media/giphy"


async def test_run_image_not_guessable_content_type(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
):
    task = await create_task(
        int_api_client,
        patched_broker,
        httpx_mock,
        input_schema={"type": "object", "properties": {"image": {"$ref": "#/$defs/File", "format": "image"}}},
    )

    mock_openai_call(httpx_mock)

    # Acquire the lock to block the callback
    lock = asyncio.Lock()
    await lock.acquire()

    async def wait_before_returning(request: httpx.Request):
        await lock.acquire()

        return httpx.Response(
            status_code=200,
            content=b"not a standard image",
        )

    httpx_mock.add_callback(
        url="https://media3.giphy.com/media/giphy",
        callback=wait_before_returning,
    )

    res = await run_task_v1(
        int_api_client,
        task_id=task["task_id"],
        task_schema_id=task["task_schema_id"],
        task_input={
            "image": {
                "url": "https://media3.giphy.com/media/giphy",
            },
        },
    )
    # Release the lock to let the callback return
    lock.release()

    await wait_for_completed_tasks(patched_broker)
    fetched_task_run = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/runs/{res['id']}"),
    )
    assert not fetched_task_run["task_input"]["image"].get("content_type")

    req = httpx_mock.get_request(url=openai_endpoint())
    assert req
    req_body = request_json_body(req)

    image_url_content = req_body["messages"][1]["content"][1]  # text message is first, image message is second
    assert image_url_content["type"] == "image_url"
    # Open AI supports using a * content type so no need to block here
    assert image_url_content["image_url"]["url"] == "https://media3.giphy.com/media/giphy"


# We previously inserted 2 runs with duplicate IDs to create a storage failure, but
# since we are going straight to clickhouse, inserting duplicate runs will not fail
# Instead, the run will be purged at a later time by clickhouse itself if the sorting key is the same.
# So to create a storage failure, we have to mock the storage to fail.
@patch("clickhouse_connect.driver.asyncclient.AsyncClient.insert", side_effect=Exception("Storage failure"))
async def test_run_storage_fails(
    mock_insert: Mock,
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
):
    """Check that the runs still go through even if the storage fails"""
    task = await create_task(int_api_client, patched_broker, httpx_mock)
    mock_openai_call(httpx_mock)

    run1 = await run_task_v1(
        int_api_client,
        task["task_id"],
        task["task_schema_id"],
        run_id="019526bf-0202-70ed-8a2f-9e1fddd02e8b",
        use_cache="never",
    )
    assert run1["id"] == "019526bf-0202-70ed-8a2f-9e1fddd02e8b"
    assert run1["task_output"] == {"greeting": "Hello James!"}
    # Run is stored as a background task
    await wait_for_completed_tasks(patched_broker)

    mock_insert.assert_awaited()
    assert mock_insert.call_count == 3  # we tried to store the run 3 times since we have 3 retries

    runs = result_or_raise(await int_api_client.get(task_schema_url(task, "runs")))["items"]
    assert len(runs) == 0


async def test_run_audio_openai(test_client: IntegrationTestClient):
    task = await test_client.create_task(
        input_schema={"type": "object", "properties": {"audio": {"$ref": "#/$defs/File", "format": "audio"}}},
    )

    test_client.mock_openai_call(provider="openai")
    run = await test_client.run_task_v1(
        task=task,
        task_input={
            "audio": {
                "content_type": "audio/mpeg",
                "data": "fefezef=",
            },
        },
        model="gpt-4o-audio-preview-2024-10-01",
    )

    await test_client.wait_for_completed_tasks()

    req = test_client.httpx_mock.get_request(
        url="https://api.openai.com/v1/chat/completions",
    )
    assert req
    req_body = request_json_body(req)

    message_1 = req_body["messages"][1]["content"][1]  # text message is first, audio message is second
    assert message_1["type"] == "input_audio"
    assert message_1["input_audio"]["format"] == "mp3"

    # Get run
    fetched_run = await test_client.fetch_run(task, run=run)
    assert fetched_run["task_input"]["audio"] == {
        "content_type": "audio/mpeg",
        "url": test_client.storage_url(
            task,
            "7f1d285a8d5bda9b6c3af1cbec3cef932204877a4bd7223fc7281c7706877905.mp3",
        ),
        "storage_url": test_client.storage_url(
            task,
            "7f1d285a8d5bda9b6c3af1cbec3cef932204877a4bd7223fc7281c7706877905.mp3",
        ),
    }
    assert fetched_run["task_output"] == {"greeting": "Hello James!"}


def read_audio_file(file_path: str) -> str:
    with open(file_path, "r") as file:
        return file.read()


async def test_openai_stream_with_audio(
    httpx_mock: HTTPXMock,
    int_api_client: AsyncClient,
    patched_broker: InMemoryBroker,
):
    await create_task(
        int_api_client,
        patched_broker,
        httpx_mock,
        input_schema={"type": "object", "properties": {"audio": {"$ref": "#/$defs/File", "format": "audio"}}},
    )

    httpx_mock.add_response(
        url="https://api.openai.com/v1/chat/completions",
        stream=IteratorStream(
            [
                b'data: {"id":"1","object":"chat.completion.chunk","created":1720404416,"model":"gpt-4o-audio-preview-2024-10-01","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"role":"assistant","content":""},"logprobs":null,',
                b'"finish_reason":null}]}\n\ndata: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"content":"{\\n"},"logprobs":null,"finish_reason":null}]}\n\n',
                b'data: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-4o-audio-preview-2024-10-01","system_fingerprint":"fp_44132a4de3","usage": {"prompt_tokens": 35, "completion_tokens": 109, "total_tokens": 144},"choices":[{"index":0,"delta":{"content":"\\"greeting\\": \\"Hello James!\\"\\n}"},"logprobs":null,"finish_reason":null}]}\n\n',
                b"data: [DONE]\n\n",
            ],
        ),
    )
    data = fixture_bytes("files/sample.mp3")

    # Run the task the first time
    task_run = stream_run_task_v1(
        int_api_client,
        task_id="greet",
        task_schema_id=1,
        task_input={
            "audio": {
                "data": b64encode(data).decode(),
                "content_type": "audio/mpeg",
            },
        },
        model="gpt-4o-audio-preview-2024-12-17",
    )
    chunks = [c async for c in extract_stream_chunks(task_run)]

    await wait_for_completed_tasks(patched_broker)

    assert len(chunks) == 3
    assert chunks[0].get("id")

    for chunk in chunks[1:]:
        assert chunk.get("id") == chunks[0]["id"]

    assert chunks[-1]["task_output"] == {"greeting": "Hello James!"}
    assert pytest.approx(0.0011775, 0.000001) == chunks[-1]["cost_usd"]  # pyright: ignore reportUnknownArgumentType
    assert chunks[-1]["duration_seconds"] > 0


async def test_legacy_tokens(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
    integration_storage: Any,
):
    # First call will fail because there is no tenant record
    # And we don't auto-create tenants based on deprecated tokens
    headers = {"Authorization": f"Bearer {LEGACY_TEST_JWT}"}
    with pytest.raises(HTTPStatusError) as e:
        await run_task_v1(int_api_client, task_id="greet", task_schema_id=1, headers=headers)
    assert e.value.response.status_code == 401

    # Now create a deprecated tenant record
    # It's deprecated because the tenant
    await integration_storage._organization_collection.insert_one(
        {
            "org_id": "org_2iPlfJ5X4LwiQybM9qeT00YPdBe",
            "tenant": "chiefofstaff.ai",
            "domain": "chiefofstaff.ai",
            "uid": id_uint32(),
            "added_credits_usd": 10,
            "current_credits_usd": 10,
        },
    )

    task = await create_task(int_api_client, patched_broker, httpx_mock)
    mock_openai_call(httpx_mock)
    await run_task_v1(int_api_client, task_id=task["task_id"], task_schema_id=task["task_schema_id"], headers=headers)


async def test_run_with_private_fields(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
):
    task = await create_task(
        int_api_client,
        patched_broker,
        httpx_mock,
        input_schema={"type": "object", "properties": {"image": {"$ref": "#/$defs/File", "format": "image"}}},
    )
    mock_openai_call(httpx_mock)

    file_url = "https://media3.giphy.com/media/giphy.png"

    httpx_mock.add_response(url=file_url, content=b"1234")

    run = await run_task_v1(
        int_api_client,
        task_id=task["task_id"],
        task_schema_id=task["task_schema_id"],
        private_fields=["task_input.image.data"],
        task_input={
            "image": {
                "url": file_url,
            },
        },
    )

    await wait_for_completed_tasks(patched_broker)

    fetched_run = await fetch_run(int_api_client, task, run=run)
    assert fetched_run["task_input"]["image"] == {
        "url": file_url,
        "content_type": "image/png",
    }


async def test_surface_default_errors(test_client: IntegrationTestClient):
    # Check we surface errors that are not a provider error like invalid file errors
    task = await test_client.create_task(
        input_schema={"type": "object", "properties": {"image": {"$ref": "#/$defs/File", "format": "image"}}},
    )

    # Sending an invalid file payload will raise an error as the first streamed chunk
    chunks = [
        c
        async for c in test_client.stream_run_task_v1(
            task,
            task_input={"image": {"storage_url": "not-a-url", "content_type": "image/png"}},
        )
    ]
    assert len(chunks) == 1
    assert chunks[0] == {
        "error": {
            "details": {
                "file": {
                    "content_type": "image/png",
                    "storage_url": "not-a-url",
                },
                "file_url": None,
            },
            "message": "No data or URL provided for image",
            "status_code": 400,
            "code": "invalid_file",
        },
    }


async def test_tool_calling_not_supported(test_client: IntegrationTestClient):
    """Tests that the correct error is raised when the model does not support tool calling"""

    task = await test_client.create_task()

    with pytest.raises(HTTPStatusError) as exc_info:
        await test_client.run_task_v1(
            task,
            version={
                "model": Model.GEMINI_2_0_FLASH_THINKING_EXP_0121.value,  # model that does not support tool calling
                "instructions": "Use @perplexity-sonar-pro",  # instructions that triggers tool calling activation
            },
        )

    content_json = json.loads(exc_info.value.response.content)
    assert content_json["error"]["status_code"] == 400
    assert content_json["error"]["code"] == "model_does_not_support_mode"
    assert content_json["error"]["message"] == "gemini-2.0-flash-thinking-exp-01-21 does not support tool calling"


async def test_tool_calling_not_supported_streaming(test_client: IntegrationTestClient):
    """Tests that the correct error is raised when the model does not support tool calling"""
    task = await test_client.create_task()

    chunks = [
        c
        async for c in test_client.stream_run_task_v1(
            task,
            version={
                "model": Model.GEMINI_2_0_FLASH_THINKING_EXP_0121.value,  # model that does not support tool calling
                "instructions": "Use @perplexity-sonar-pro",  # instructions that triggers tool calling activation
            },
        )
    ]
    assert chunks
    assert chunks[0]["error"]["status_code"] == 400
    assert chunks[0]["error"]["code"] == "model_does_not_support_mode"
    assert chunks[0]["error"]["message"] == "gemini-2.0-flash-thinking-exp-01-21 does not support tool calling"


async def test_structured_generation_failure_and_retry(
    test_client: IntegrationTestClient,
):
    # Check we surface errors that are not a provider error like invalid file errors
    task = await test_client.create_task()

    # First call will fail with a schema error
    test_client.mock_openai_call(
        status_code=400,
        json={
            "error": {
                "type": "invalid_request_error",
                "message": "Invalid schema",
                "param": "response_format",
            },
        },
    )
    # Second call will succeed
    test_client.mock_openai_call()

    await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20)

    requests = test_client.httpx_mock.get_requests(
        url=openai_endpoint(),
    )
    assert len(requests) == 2
    body1 = request_json_body(requests[0])
    body2 = request_json_body(requests[1])
    assert body1["response_format"]["type"] == "json_schema"
    assert body2["response_format"]["type"] == "json_object"


async def test_structured_generation_failure_and_retry_with_provider(
    test_client: IntegrationTestClient,
):
    # Check we surface errors that are not a provider error like invalid file errors
    task = await test_client.create_task()

    # First call will fail with a schema error
    test_client.mock_openai_call(
        status_code=400,
        json={
            "error": {
                "type": "invalid_request_error",
                "message": "Invalid schema",
                "param": "response_format",
            },
        },
        provider="openai",
    )
    # Second call will succeed
    test_client.mock_openai_call(provider="openai")

    await test_client.run_task_v1(task, version={"model": Model.GPT_4O_2024_11_20, "provider": "openai"})

    requests = test_client.httpx_mock.get_requests(url=openai_endpoint())
    assert len(requests) == 2
    body1 = request_json_body(requests[0])
    body2 = request_json_body(requests[1])
    assert body1["response_format"]["type"] == "json_schema"
    assert body2["response_format"]["type"] == "json_object"


async def test_no_provider_for_model(test_client: IntegrationTestClient):
    # Check that if we create the group before hand and use it, the run has no provider
    task = await test_client.create_task()

    group = await test_client.create_version(task, {"model": "gpt-4o-2024-11-20", "temperature": 0.5})
    assert "provider" not in group["properties"]
    assert group["properties"]["model"] == "gpt-4o-2024-11-20", "sanity"
    assert group["properties"]["temperature"] == 0.5, "sanity"
    assert group["iteration"] == 1, "sanity"

    test_client.mock_openai_call()

    # Now run the task with the group
    run = await test_client.run_task_v1(task, version=group["iteration"])
    assert run

    # Fetch the run and check the version
    fetched_run = await test_client.fetch_run(task, run_id=run["id"])
    assert fetched_run["group"]["iteration"] == 1, "sanity"
    assert not fetched_run["group"]["properties"].get("provider")

    # list groups
    groups = result_or_raise(await test_client.int_api_client.get(task_schema_url(task, "groups")))["items"]
    assert len(groups) == 1
    assert groups[0]["iteration"] == 1


async def test_latest_gemini_model(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    test_client.mock_vertex_call(model=Model.GEMINI_1_5_PRO_002)
    run = await test_client.run_task_v1(task, model=Model.GEMINI_1_5_PRO_LATEST)
    # Run will not fail here if the Gemini 1.5 Pro 002 is used since latest does not point to anything
    assert run

    # Fetch the version and check the model
    version = result_or_raise(await test_client.int_api_client.get(task_schema_url(task, "groups")))["items"][0]
    assert version["properties"]["model"] == Model.GEMINI_1_5_PRO_LATEST

    # Also fetch the run and check the model
    fetched_run = await test_client.fetch_run(task, run_id=run["id"])
    assert fetched_run["group"]["properties"]["model"] == Model.GEMINI_1_5_PRO_LATEST
    assert fetched_run["metadata"][METADATA_KEY_USED_MODEL] == Model.GEMINI_1_5_PRO_002


async def test_tool_call_recursion(test_client: IntegrationTestClient):
    task = await test_client.create_task(
        output_schema={
            "type": "object",
            "properties": {
                "greeting": {"type": "string"},
            },
        },
    )

    # Create a version that includes a tool call
    version = await test_client.create_version(
        task,
        version_properties={
            "model": Model.GPT_4O_2024_11_20,
            "instructions": "@search @browser-text",
        },
    )
    version_properties = version["properties"]
    assert set(version_properties["enabled_tools"]) == {"@search-google", "@browser-text"}

    test_client.reset_httpx_mock()

    # First call returns a tool call
    test_client.mock_openai_call(
        tool_calls_content=[
            {
                "id": "some_id",
                "type": "function",
                "function": {"name": "search-google", "arguments": '{"query": "bla"}'},
            },
        ],
    )
    # Then we return the same tool call but with an output as well
    test_client.mock_openai_call(
        json_content={
            "greeting": "Hello James!",
            "internal_agent_run_result": {"status": "success"},
        },
        tool_calls_content=[
            {
                "id": "some_id",
                "type": "function",
                "function": {"name": "search-google", "arguments": '{"query": "bla"}'},
            },
        ],
    )

    test_client.httpx_mock.add_response(
        url="https://google.serper.dev/search",
        text="blabla",
    )

    res = await test_client.run_task_v1(task, version=version["iteration"])
    assert res
    assert res["task_output"] == {
        "greeting": "Hello James!",
    }

    assert len(test_client.httpx_mock.get_requests(url="https://google.serper.dev/search")) == 1

    fetched_run = await fetch_run(test_client.int_api_client, task, res)
    assert fetched_run["task_output"] == {
        "greeting": "Hello James!",
    }

    assert len(fetched_run["llm_completions"]) == 2


async def test_tool_call_recursion_streaming(test_client: IntegrationTestClient):
    task = await test_client.create_task(
        output_schema={
            "type": "object",
            "properties": {
                "greeting": {"type": "string"},
            },
        },
    )

    # Create a version that includes a tool call
    version = await test_client.create_version(
        task,
        version_properties={
            "model": Model.GPT_4O_2024_11_20,
            "instructions": "@search @browser-text",
        },
    )
    version_properties = version["properties"]
    assert set(version_properties["enabled_tools"]) == {"@search-google", "@browser-text"}

    await test_client.wait_for_completed_tasks()

    # TODO: we should reset all callbacks here but it would break amplitude
    test_client.reset_http_requests()

    json_1: dict[str, Any] = {
        "internal_agent_run_result": {"status": "success"},
    }
    tool_call_1 = [
        {
            "index": 0,
            "id": "some_id",
            "type": "function",
            "function": {"name": "search-google", "arguments": '{"query"'},
        },
    ]
    tool_call_2 = [
        {
            "index": 0,
            "id": "some_id",
            "type": "function",
            "function": {"name": "search-google", "arguments": ': "b'},
        },
    ]
    tool_call_3 = [
        {
            "index": 0,
            "id": "some_id",
            "type": "function",
            "function": {"name": "search-google", "arguments": 'la"}'},
        },
    ]

    # First call returns a tool call
    test_client.mock_openai_stream(
        deltas=[json.dumps(json_1)],
        tool_calls_deltas=[tool_call_1, tool_call_2, tool_call_3],
    )
    json_1["greeting"] = "Hello James!"
    # Then we return the same tool call but with an output as well
    test_client.mock_openai_stream(
        deltas=[json.dumps(json_1)],
        tool_calls_deltas=[tool_call_1, tool_call_2, tool_call_3],
    )

    test_client.httpx_mock.add_response(
        url="https://google.serper.dev/search",
        text="blabla",
    )

    chunks = [c async for c in test_client.stream_run_task_v1(task, version=version["iteration"])]
    assert chunks

    assert len(test_client.httpx_mock.get_requests(url="https://google.serper.dev/search")) == 1

    fetched_run = await fetch_run(test_client.int_api_client, task, run_id=chunks[0]["id"])
    assert fetched_run["task_output"] == {
        "greeting": "Hello James!",
    }
    assert fetched_run["llm_completions"][0]["tool_calls"] == [
        {"tool_name": "@search-google", "tool_input_dict": {"query": "bla"}, "id": "some_id"},
    ]

    assert len(fetched_run["llm_completions"]) == 2


async def test_unknown_error_invalid_argument_max_tokens(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
):
    task = await create_task(int_api_client, patched_broker, httpx_mock)

    httpx_mock.add_response(
        status_code=400,
        json={
            "error": {
                "code": 400,
                "status": "INVALID_ARGUMENT",
                "message": "The input token count (1189051) exceeds the maximum number of tokens allowed (1000000).",
            },
        },
    )

    version = await create_version(
        int_api_client,
        task["task_id"],
        task["task_schema_id"],
        {"model": Model.GEMINI_1_5_FLASH_002},
    )
    with pytest.raises(HTTPStatusError) as exc_info:
        await run_task_v1(
            int_api_client,
            task_id=task["task_id"],
            task_schema_id=task["task_schema_id"],
            version=version["iteration"],
        )

    content_json = json.loads(exc_info.value.response.content)
    assert content_json["error"]["code"] == "max_tokens_exceeded"
    assert (
        content_json["error"]["message"]
        == "The input token count (1189051) exceeds the maximum number of tokens allowed (1000000)."
    )


async def test_gemini_thinking_mode_model(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
):
    task = await create_task(int_api_client, patched_broker, httpx_mock)

    version = await create_version(
        int_api_client,
        task["task_id"],
        task["task_schema_id"],
        {"model": Model.GEMINI_2_0_FLASH_THINKING_EXP_0121},
    )

    iteration = version["iteration"]

    mock_gemini_call(
        httpx_mock,
        model=Model.GEMINI_2_0_FLASH_THINKING_EXP_0121,
        api_version="v1alpha",
        json=fixtures_json("gemini", "completion_thoughts_gemini_2.0_flash_thinking_mode.json"),
    )

    run = await run_task_v1(
        int_api_client,
        task_id=task["task_id"],
        task_schema_id=task["task_schema_id"],
        task_input={"name": "John", "age": 32},
        version=iteration,
        use_cache="never",
    )

    assert (
        run["task_output"]["greeting"]
        == "Explaining how AI works is a bit like explaining how a human brain works – it's incredibly complex and the exact mechanisms are still being researched. While the underlying mechanisms can be complex, the fundamental principles of data-driven learning and pattern recognition remain central.\n"
    )

    assert (
        run["reasoning_steps"][0]["step"]
        == 'My thinking process for generating the explanation of how AI works went something like this:\n\n1. **Deconstruct the Request:** The user asked "Explain how AI works." This is a broad question, so a comprehensive yet accessible explanation is needed. I need to cover the core principles without getting bogged down in overly technical jargon.\n\n2. **Identify Key Concepts:**  I immediately thought of the fundamental building blocks of AI. This led to the identification of:\n'
    )


async def test_latest_model(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    test_client.mock_vertex_call(model=MODEL_DATAS[Model.GEMINI_1_5_FLASH_LATEST].model)  # type:ignore

    run = await test_client.run_task_v1(task, model=Model.GEMINI_1_5_FLASH_LATEST)
    fetched_run = await test_client.fetch_run(task, run_id=run["id"])

    assert fetched_run["cost_usd"] > 0
    assert fetched_run["llm_completions"][0]["usage"]["model_context_window_size"] > 0


async def test_model_pdf_image(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
):
    task = await create_task(
        int_api_client,
        patched_broker,
        httpx_mock,
        input_schema={"type": "object", "properties": {"image": {"$ref": "#/$defs/File", "format": "image"}}},
    )

    httpx_mock.add_response(
        # Content type is not guessable from URL but only from the data
        url="https://media3.giphy.com/media/giphy",
        content=fixture_bytes("files/test.png"),
    )
    httpx_mock.add_response(
        url="https://bedrock-runtime.us-west-2.amazonaws.com/model/us.anthropic.claude-3-5-sonnet-20241022-v2:0/converse",
        status_code=429,
        json={
            "message": "Rate limit exceeded",
        },
    )
    httpx_mock.add_response(
        url="https://api.anthropic.com/v1/messages",
        status_code=200,
        json={
            "id": "sdf_123",
            "type": "message",
            "role": "assistant",
            "model": "claude-3-5-sonnet-20241022",
            "content": [
                {
                    "type": "text",
                    "text": '{\n    "greeting": "Hello, how can I help you today?"\n}',
                },
            ],
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 1590,
                "output_tokens": 152,
            },
        },
    )
    res = await run_task_v1(
        int_api_client,
        task_id=task["task_id"],
        task_schema_id=task["task_schema_id"],
        task_input={
            "image": {
                "url": "https://media3.giphy.com/media/giphy",
            },
        },
        model=Model.CLAUDE_3_5_SONNET_20241022.value,
    )
    await wait_for_completed_tasks(patched_broker)

    assert res["task_output"] == {"greeting": "Hello, how can I help you today?"}
    # Cost should be (1590 * $0.000003) + (152 * $0.000015) = $0.00705
    assert pytest.approx(res["cost_usd"], abs=0.0001) == 0.00705  # pyright: ignore
    assert res["metadata"]["workflowai.provider"] == "anthropic"
    assert res["metadata"]["workflowai.providers"] == ["amazon_bedrock", "anthropic"]


async def test_partial_output(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    test_client.mock_openai_call(
        status_code=200,
        # The response is valid but the tool call failed
        json_content={
            "greeting": "Hello, how can I help you today?",
            "internal_agent_run_result": {
                "status": "failure",
                "error": {
                    "error_code": "tool_call_error",
                },
            },
        },
    )
    with pytest.raises(HTTPStatusError) as e:
        await test_client.run_task_v1(task)

    assert e.value.response.status_code == 424
    raw = e.value.response.json()
    assert raw["error"]["code"] == "agent_run_failed"

    assert raw["id"]
    assert raw["task_output"] == {"greeting": "Hello, how can I help you today?"}


async def test_with_templated_instructions(test_client: IntegrationTestClient):
    instruction_template = """You're a highly knowledgeable, brilliant, creative, empathetic assistant, and a human partner.

Here are your instructions:
- You're helping a curious person named {{ name }}. Your tone is that of a friendly human assistant.
- Your answer must be limited to {{ max_chars }} characters or {{ max_tokens }} tokens whichever is reached first.
- The current date is {{ date }}.

{% if moments_context %}
{{ moments_context }}
{% endif %}

{{ context }}

{% if faq_answer %}
You can also use the FAQ agent response if that is useful to your answer: "{{ faq_answer }}"
{% endif %}"""

    task = await test_client.create_task(
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "max_chars": {"type": "integer"},
                "max_tokens": {"type": "integer"},
                "date": {"type": "string"},
                "moments_context": {"type": "string"},
                "context": {"type": "string"},
                "faq_answer": {"type": "string"},
                "question": {"type": "string"},
            },
        },
    )

    test_client.mock_openai_call()

    run = await test_client.run_task_v1(
        task,
        task_input={
            "name": "John",
            "max_chars": 1000,
            "max_tokens": 500,
            "date": "2024-03-19",
            "context": "Some context",
            "question": "What is the meaning of life?",
        },
        version={"model": Model.GPT_4O_2024_11_20, "instructions": instruction_template},
    )

    # Check that the task input was not modified
    fetched_run = await test_client.fetch_run(task, run_id=run["id"])
    assert fetched_run["task_input"] == {
        "name": "John",
        "max_chars": 1000,
        "max_tokens": 500,
        "date": "2024-03-19",
        "context": "Some context",
        "question": "What is the meaning of life?",
    }

    request = test_client.httpx_mock.get_request(url=openai_endpoint())
    assert request
    messages: list[dict[str, Any]] = request_json_body(request)["messages"]
    assert len(messages) == 2
    assert "person named John" in messages[0]["content"]
    assert (
        '```json\n{\n  "type": "object",\n  "properties": {\n    "question": {\n      "type": "string"\n    }\n  }\n}\n```'
        in messages[0]["content"]
    )
    assert messages[1]["content"] == 'Input is:\n```json\n{\n  "question": "What is the meaning of life?"\n}\n```'

    completions = (await test_client.fetch_completions(task, run=run))["completions"]
    assert completions[0]["messages"][0]["content"] == messages[0]["content"]
    assert completions[0]["messages"][1]["content"] == messages[1]["content"]

    # Check with missing variables
    run = await test_client.run_task_v1(
        task,
        task_input={"name": "John"},
        version={"model": Model.GPT_4O_2024_11_20, "instructions": instruction_template},
    )
    assert run


async def test_fallback_on_unknown_provider(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    test_client.mock_openai_call(status_code=400, json={"error": {"message": "This should not happen"}})
    # Sanity check that we raise an unknown error here
    with pytest.raises(HTTPStatusError) as e:
        res = await test_client.run_task_v1(
            task,
            version={"model": Model.GPT_4O_2024_11_20, "provider": Provider.OPEN_AI},
        )
    assert e.value.response.status_code == 400
    assert e.value.response.json()["error"]["code"] == "unknown_provider_error"

    test_client.mock_openai_call(provider="azure_openai")

    res = await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20)
    assert res
    fetched_run = await test_client.fetch_run(task, run_id=res["id"])
    assert fetched_run["metadata"]["workflowai.providers"] == ["openai", "azure_openai"]


async def test_cache_with_image_url(test_client: IntegrationTestClient):
    """Check that the cache key is correctly computed and used when the input contains an image URL.
    Since we modify the input before storing it to add the content type and storage url, we had an issue
    where the cache key was computed based on the updated input."""

    # Create a task with an image
    task = await test_client.create_task(
        input_schema={
            "type": "object",
            "properties": {
                "image": {
                    "$ref": "#/$defs/Image",
                },
            },
        },
    )

    # Mock openai call and image response
    test_client.httpx_mock.add_response(
        url="https://media3.giphy.com/media/giphy",
        status_code=200,
        content=b"GIF87ahello",  # signature for gif
    )
    test_client.mock_openai_call()

    # Run the task with the image URL
    task_input = {
        "image": {
            "url": "https://media3.giphy.com/media/giphy",
        },
    }
    res = await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20, task_input=task_input)
    assert res

    fetched = await test_client.fetch_run(task, run_id=res["id"])
    assert fetched["task_input_hash"] == "accf4d8caf343202d6c688003bf9e163", "sanity"

    res2 = await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20, task_input=task_input)
    assert res2
    # Checking that we returned the same run and not a new one
    assert res2["id"] == res["id"]

    fetched_run = await test_client.fetch_run(task, run_id=res["id"])
    # The input contains the image URL as well as our storage
    assert fetched_run["task_input"] == {
        "image": {
            "url": "https://media3.giphy.com/media/giphy",
            "content_type": "image/gif",
            "storage_url": test_client.storage_url(
                task,
                "2801434f08433a71b4f618414724c5be7bda2bbb55b3c85f83b7c008585a61d8.gif",
            ),
        },
    }


async def test_image_not_found(test_client: IntegrationTestClient):
    # Create a task with an image
    task = await test_client.create_task(
        input_schema={
            "properties": {
                "image": {
                    "$ref": "#/$defs/Image",
                },
            },
        },
    )

    # The file does not exist
    test_client.httpx_mock.add_response(
        url="https://media3.giphy.com/media/giphy",
        status_code=404,
    )

    with pytest.raises(HTTPStatusError) as e:
        # Sending an image URL without a content type will force the runner to download the file
        await test_client.run_task_v1(
            task,
            model=Model.GEMINI_1_5_FLASH_LATEST,
            task_input={"image": {"url": "https://media3.giphy.com/media/giphy"}},
        )

    assert e.value.response.status_code == 400
    assert e.value.response.json()["error"]["code"] == "invalid_file"


async def test_invalid_base64_data(test_client: IntegrationTestClient):
    """Check that we handle invalid base64 data correctly by returning an error immediately"""
    task = await test_client.create_task(
        input_schema={
            "properties": {
                "image": {
                    "$ref": "#/$defs/Image",
                },
            },
        },
    )

    with pytest.raises(HTTPStatusError) as e:
        # Sending an image URL without a content type will force the runner to download the file
        await test_client.run_task_v1(
            task,
            model=Model.GEMINI_1_5_FLASH_LATEST,
            task_input={"image": {"data": "iamnotbase64"}},
        )

    assert e.value.response.status_code == 400
    assert e.value.response.json()["error"]["code"] == "invalid_file"
