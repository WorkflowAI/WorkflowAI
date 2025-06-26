import asyncio
import contextlib
import json
import os
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
from core.domain.models.model_data_mapping import MODEL_DATAS
from core.domain.models.model_provider_data_mapping import OPENAI_PROVIDER_DATA
from core.providers.factory.local_provider_factory import LocalProviderFactory
from core.providers.google.google_provider_domain import (
    Candidate,
    CompletionResponse,
    Content,
    Part,
    UsageMetadata,
)
from core.utils.ids import id_uint32
from tests.component.common import (
    LEGACY_TEST_JWT,
    IntegrationTestClient,
    create_task,
    extract_stream_chunks,
    fetch_run,
    gemini_url,
    get_amplitude_events,
    list_groups,
    mock_openai_call,
    mock_vertex_call,
    openai_endpoint,
    result_or_raise,
    run_task_v1,
    stream_run_task_v1,
    task_schema_url,
    vertex_url,
    wait_for_completed_tasks,
)
from tests.utils import approx, fixture_bytes, fixtures_json, request_json_body


async def test_run_with_metadata(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    test_client.mock_vertex_call(
        publisher="google",
        model="gemini-1.5-pro-002",
        latency=0.01,
    )

    # Run the task the first time
    task_run = await test_client.run_task_v1(
        task,
        task_input={"name": "John", "age": 30},
        model=Model.GEMINI_1_5_PRO_002,
        metadata={"key1": "value1", "key2": "value2"},
    )

    # Check returned cost
    assert task_run["cost_usd"] == pytest.approx(0.000169, abs=1e-6)  # pyright: ignore[reportUnknownMemberType]

    await test_client.wait_for_completed_tasks()

    # Check groups
    groups = (await test_client.get(task_schema_url(task, "groups")))["items"]
    assert len(groups) == 1
    assert groups[0]["properties"]["model"] == "gemini-1.5-pro-002"
    assert "provider" not in groups[0]["properties"]
    assert groups[0]["run_count"] == 1

    # Fetch the task run

    fetched_task_run = await test_client.get(f"/chiefofstaff.ai/agents/greet/runs/{task_run['id']}")

    assert fetched_task_run["metadata"]["workflowai.inference_seconds"]

    assert fetched_task_run["metadata"]["key1"] == "value1"
    assert fetched_task_run["metadata"]["key2"] == "value2"
    assert fetched_task_run["metadata"]["workflowai.vertex_api_region"] == "us-central1"
    assert fetched_task_run["metadata"]["workflowai.providers"] == ["google"]
    assert fetched_task_run["metadata"]["workflowai.provider"] == "google"

    await test_client.wait_for_completed_tasks()

    amplitude_events = await get_amplitude_events(test_client.httpx_mock)
    assert len(amplitude_events) == 1
    event = amplitude_events[0]

    org = await test_client.get("/_/organization/settings")

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
    assert usage["prompt_cost_usd"] == approx(0.00001875, abs=1e-10)  # pyright: ignore [reportUnknownMemberType]
    assert usage["completion_cost_usd"] == approx(0.00011)  # 11 * 0.000010
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
    assert chunks[-1]["cost_usd"] == approx(35 * 0.0000025 + 109 * 0.000010)
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

        test_client.reset_httpx_mock(assert_all_responses_were_requested=False)

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


async def test_run_with_500_error(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    # Add an evaluator to the task
    test_client.mock_openai_call(status_code=500)
    test_client.mock_openai_call(status_code=500, provider="azure_openai")

    # Run the task the first time
    with pytest.raises(HTTPStatusError) as e:
        await test_client.run_task_v1(
            task=task,
            task_input={"name": "John", "age": 30},
            model="gpt-4o-2024-11-20",
        )
    assert e.value.response.status_code == 424

    await test_client.wait_for_completed_tasks()

    events = await get_amplitude_events(test_client.httpx_mock)
    assert len(events) == 1, "did not get amplitude event"
    assert events[0]["event_properties"]["error_code"] == "provider_internal_error"


async def test_run_schema_insufficient_credits(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
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
        is_reusable=True,
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

    with pytest.raises(HTTPStatusError) as e:
        await run_task_v1(
            int_api_client,
            task_id="greet",
            task_schema_id=1,
            task_input={"name": "John", "age": 30},
            model="gpt-4o-2024-11-20",
        )

    assert e.value.response.status_code == 402


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
        is_reusable=True,
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

    # URL is never fetched
    # httpx_mock.add_response(url=file_url, content=b"1234")

    run = await run_task_v1(
        int_api_client,
        task_id=task["task_id"],
        task_schema_id=task["task_schema_id"],
        private_fields=["task_input.image"],
        task_input={
            "image": {
                "url": file_url,
            },
        },
    )

    await wait_for_completed_tasks(patched_broker)

    fetched_run = await fetch_run(int_api_client, task, run=run)
    assert fetched_run["task_input"] == {}


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
                "model": Model.LLAMA_3_3_70B.value,  # model that does not support tool calling
                "instructions": "Use @perplexity-sonar-pro",  # instructions that triggers tool calling activation
            },
        )

    content_json = json.loads(exc_info.value.response.content)
    assert content_json["error"]["status_code"] == 400
    assert content_json["error"]["code"] == "model_does_not_support_mode"
    assert content_json["error"]["message"] == "llama-3.3-70b does not support tool calling"


async def test_tool_calling_not_supported_streaming(test_client: IntegrationTestClient):
    """Tests that the correct error is raised when the model does not support tool calling"""
    task = await test_client.create_task()

    chunks = [
        c
        async for c in test_client.stream_run_task_v1(
            task,
            version={
                "model": Model.LLAMA_3_3_70B.value,  # model that does not support tool calling
                "instructions": "Use @perplexity-sonar-pro",  # instructions that triggers tool calling activation
            },
        )
    ]
    assert chunks
    assert chunks[0]["error"]["status_code"] == 400
    assert chunks[0]["error"]["code"] == "model_does_not_support_mode"
    assert chunks[0]["error"]["message"] == "llama-3.3-70b does not support tool calling"


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

    test_client.mock_internal_task("detect-chain-of-thought", task_output={"should_use_chain_of_thought": False})

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


async def test_unknown_error_invalid_argument_max_tokens(test_client: IntegrationTestClient):
    task = await test_client.create_task()
    test_client.reset_httpx_mock()

    test_client.httpx_mock.add_response(
        status_code=400,
        json={
            "error": {
                "code": 400,
                "status": "INVALID_ARGUMENT",
                "message": "The input token count (1189051) exceeds the maximum number of tokens allowed (1000000).",
            },
        },
    )

    version = await test_client.create_version(
        task,
        {"model": Model.GEMINI_1_5_FLASH_002},
    )
    with pytest.raises(HTTPStatusError) as exc_info:
        await test_client.run_task_v1(task, version=version["iteration"])

    content_json = json.loads(exc_info.value.response.content)
    assert content_json["error"]["code"] == "max_tokens_exceeded"
    assert (
        content_json["error"]["message"]
        == "The input token count (1189051) exceeds the maximum number of tokens allowed (1000000)."
    )


async def test_latest_model(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    test_client.mock_vertex_call(model=MODEL_DATAS[Model.GEMINI_1_5_FLASH_LATEST].model)  # type:ignore

    run = await test_client.run_task_v1(task, model=Model.GEMINI_1_5_FLASH_LATEST)
    fetched_run = await test_client.fetch_run(task, run_id=run["id"])

    assert fetched_run["cost_usd"] > 0
    assert fetched_run["llm_completions"][0]["usage"]["model_context_window_size"] > 0


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

    test_client.mock_openai_call()

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

    test_client.mock_openai_call(status_code=400, json={"error": {"message": "This should not happen"}})
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


class TestMultiProviderConfigs:
    # Patch a factory that has multiple providers for anthropic and fireworks
    @pytest.fixture(autouse=True)
    def multi_provider_factory(self):
        with patch.dict(
            os.environ,
            {
                "FIREWORKS_API_KEY": "fw_api_key_0",
                "FIREWORKS_API_KEY_1": "fw_api_key_1",
                "FIREWORKS_API_KEY_2": "fw_api_key_2",
                "ANTHROPIC_API_KEY": "anthropic_api_key_0",
                "ANTHROPIC_API_KEY_1": "anthropic_api_key_1",
                "ANTHROPIC_API_KEY_2": "anthropic_api_key_2",
            },
        ):
            factory = LocalProviderFactory()
            assert len(list(factory.get_providers(Provider.FIREWORKS))) == 3, "sanity fireworks"
            assert len(list(factory.get_providers(Provider.ANTHROPIC))) == 3, "sanity anthropic"
            with patch("core.runners.workflowai.workflowai_runner.WorkflowAIRunner.provider_factory", new=factory):
                yield factory

    @pytest.fixture()
    def patched_shuffle(self):
        idx = 0

        # Patch the shuffle with a deterministic round robin for the first item
        def _shuffle(iterable: list[Any]):
            if not iterable:
                return
            nonlocal idx
            val = iterable[0]
            iterable[0] = iterable[idx % len(iterable)]
            iterable[idx % len(iterable)] = val
            idx += 1

        with patch("random.shuffle", side_effect=_shuffle) as mock_shuffle:
            yield mock_shuffle

    async def test_multi_fireworks_providers(
        self,
        test_client: IntegrationTestClient,
        httpx_mock: HTTPXMock,
        patched_shuffle: Mock,
    ):
        """Check that the provider keys are correctly round robin-ed for fireworks"""
        task = await test_client.create_task(output_schema={"properties": {"city": {"type": "string"}}})

        count_by_api_key: dict[str, int] = {}

        def _callback(request: httpx.Request):
            assert request.headers["Authorization"].startswith("Bearer fw_api_key_")
            key = request.headers["Authorization"].removeprefix("Bearer fw_api_key_")
            count = count_by_api_key.get(key, 0)
            count_by_api_key[key] = count + 1
            return httpx.Response(status_code=200, json=fixtures_json("fireworks", "completion.json"))

        httpx_mock.add_callback(
            url="https://api.fireworks.ai/inference/v1/chat/completions",
            method="POST",
            callback=_callback,
            is_reusable=True,
        )

        for _ in range(10):
            await test_client.run_task_v1(task, model=Model.DEEPSEEK_R1_2501, use_cache="never", autowait=False)

        assert len(count_by_api_key) == 3, "sanity"
        keys = list(count_by_api_key.keys())
        assert keys == ["0", "1", "2"]
        assert [count_by_api_key[key] for key in keys] == [4, 3, 3]

    async def test_multi_fireworks_providers_with_errors(
        self,
        test_client: IntegrationTestClient,
        httpx_mock: HTTPXMock,
        patched_shuffle: Mock,
    ):
        """Check that the provider keys are correctly round robin-ed for fireworks
        and falls through whenever we hit a rate limit"""
        task = await test_client.create_task(output_schema={"properties": {"city": {"type": "string"}}})

        used_api_key: list[int] = []
        # We return a 429 every other call for each api key

        def _callback(request: httpx.Request):
            assert request.headers["Authorization"].startswith("Bearer fw_api_key_")
            key = request.headers["Authorization"].removeprefix("Bearer fw_api_key_")
            used_api_key.append(int(key))

            # Provider 1 returns a 429
            if key == "1":
                return httpx.Response(status_code=429)

            # Provider 2 returns a 500
            if key == "2":
                return httpx.Response(status_code=500)

            return httpx.Response(status_code=200, json=fixtures_json("fireworks", "completion.json"))

        httpx_mock.add_callback(
            url="https://api.fireworks.ai/inference/v1/chat/completions",
            method="POST",
            callback=_callback,
            is_reusable=True,
        )

        for _ in range(3):
            with contextlib.suppress(HTTPStatusError):
                await test_client.run_task_v1(task, model=Model.DEEPSEEK_R1_2501, use_cache="never", autowait=False)

        assert used_api_key == [
            # 1
            0,  # Call to provider 0 succeeds
            # 2
            1,  # Provider 1 so 429, second one in line is Provider 0
            0,
            # 3
            2,  # Provider 2 so 500, no fallback
        ]

    async def test_multi_anthropic_providers(
        self,
        test_client: IntegrationTestClient,
        multi_provider_factory: LocalProviderFactory,
        httpx_mock: HTTPXMock,
        patched_shuffle: Mock,
    ):
        """Anthropic we only shuffle the subsequent calls if the first call returns a 429"""
        task = await test_client.create_task(output_schema={"properties": {}})
        used_api_key: list[int] = []
        return_429 = False

        def _callback(request: httpx.Request):
            assert request.headers["x-api-key"].startswith("anthropic_api_key_")
            key = request.headers["x-api-key"].removeprefix("anthropic_api_key_")
            used_api_key.append(int(key))

            # Provider 0 returns a 429 every other call
            if key == "0":
                nonlocal return_429
                should_return_429 = return_429
                return_429 = not return_429
                if should_return_429:
                    return httpx.Response(status_code=429)

            return httpx.Response(status_code=200, json=fixtures_json("anthropic", "completion.json"))

        httpx_mock.add_callback(
            url="https://api.anthropic.com/v1/messages",
            method="POST",
            callback=_callback,
            is_reusable=True,
        )

        for _ in range(4):
            await test_client.run_task_v1(task, model=Model.CLAUDE_3_5_SONNET_LATEST, use_cache="never", autowait=False)

        assert used_api_key == [
            # 0
            0,  # First call to provider succeeds
            # 1
            0,  # Provider 0 so 429, second one in line is Provider 1
            1,
            # 2
            0,
            # 3
            0,
            2,
        ]

    async def test_fallback_to_other_provider(
        self,
        test_client: IntegrationTestClient,
        multi_provider_factory: LocalProviderFactory,
        httpx_mock: HTTPXMock,
    ):
        # Anthropic returns a 503
        httpx_mock.add_response(
            url="https://api.anthropic.com/v1/messages",
            method="POST",
            status_code=503,
        )

        # But we fallback to bedrock
        httpx_mock.add_response(
            url="https://bedrock-runtime.us-west-2.amazonaws.com/model/us.anthropic.claude-3-5-sonnet-20241022-v2:0/converse",
            method="POST",
            json=fixtures_json("bedrock", "completion.json"),
        )

        task = await test_client.create_task()

        res = await test_client.run_task_v1(
            task,
            model=Model.CLAUDE_3_5_SONNET_20241022,
            use_cache="never",
            autowait=False,
        )
        assert res

        # We only called anthropic once
        assert len(httpx_mock.get_requests(url="https://api.anthropic.com/v1/messages")) == 1

        await test_client.wait_for_completed_tasks()

        run = await test_client.fetch_run(task, run_id=res["id"])
        assert run["metadata"]["workflowai.providers"] == ["anthropic", "amazon_bedrock"]

    async def test_fallback_on_payment_required(
        self,
        test_client: IntegrationTestClient,
        multi_provider_factory: LocalProviderFactory,
        httpx_mock: HTTPXMock,
    ):
        # First config returns an invalid config (here payment required but would be the same with 401 or 403)
        httpx_mock.add_response(
            url="https://api.anthropic.com/v1/messages",
            method="POST",
            status_code=402,
        )

        # But we fallback to the next anthropic provider
        httpx_mock.add_response(
            url="https://api.anthropic.com/v1/messages",
            method="POST",
            json=fixtures_json("anthropic", "completion.json"),
        )

        task = await test_client.create_task(output_schema={"properties": {}})

        res = await test_client.run_task_v1(
            task,
            model=Model.CLAUDE_3_5_SONNET_20241022,
            use_cache="never",
            autowait=False,
        )
        assert res

        # We only called anthropic once
        assert len(httpx_mock.get_requests(url="https://api.anthropic.com/v1/messages")) == 2

        await test_client.wait_for_completed_tasks()

        run = await test_client.fetch_run(task, run_id=res["id"])
        assert run["metadata"]["workflowai.providers"] == ["anthropic", "anthropic"]


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


async def test_empty_strings_are_not_stripped(test_client: IntegrationTestClient):
    """Check that we do not strip empty strings from the output when the model explicitly returns them
    except if they have a format
    """
    # Create a task with an output schema with an optional string
    task = await test_client.create_task(
        output_schema={
            "properties": {
                "greeting": {"type": "string"},
                "date": {"type": "string", "format": "date"},
            },
        },
    )
    test_client.mock_openai_call(json_content={"greeting": "", "date": ""})

    res = await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20, task_input={"name": "John"})
    assert res
    assert res["task_output"]["greeting"] == ""
    assert "date" not in res["task_output"]


async def test_invalid_unicode_chars(test_client: IntegrationTestClient):
    task = await test_client.create_task()
    test_client.mock_openai_call(bytes=fixture_bytes("openai", "invalid_unicode_chars.json"))

    expected_str = "The🐀 meaning of life is Préparation de co😁mmande."

    res = await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20)
    assert res["task_output"]["greeting"] == expected_str, "invalid output from run"

    # Checking that the run was properly stored
    # Trying to make sure we din't get a surrogate not allowed
    # It would be nice to test with invalid surrogates, but it is hard to reproduce a failing payload
    fetched = await test_client.fetch_run(task, run_id=res["id"])
    assert fetched["task_output"]["greeting"] == expected_str, "invalid output from fetch"


async def test_with_raw_code_in_template(test_client: IntegrationTestClient):
    """Check that when we have a partial template we don't fail runs. This is to allow having instructions that look
    like a template but are not since our template parsing is not perfect for now"""
    task = await test_client.create_task()
    test_client.mock_openai_call()

    test_client.mock_internal_task("detect-chain-of-thought", task_output={"should_use_chain_of_thought": False})

    version = await test_client.create_version_v1(
        task,
        version_properties={
            "model": Model.GPT_41_NANO_2025_04_14,
            "instructions": "Please generate a valid jinja template. Using variables like {{ i_am_a_variable_not_in_the_input }}!"
            "Please generate a valid jinja template. Using variables like {% raw %}{{ i_am_a_variable_not_in_the_input }}, {%if invalid_condition %}{% endraw %}!",
        },
    )

    res = await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20, version=version["id"])
    assert res
    assert res["task_output"]["greeting"] == "Hello James!"

    request = test_client.httpx_mock.get_request(url=openai_endpoint())
    assert request
    payload = json.loads(request.content)["messages"]
    assert len(payload) == 2
    # Instructions are passed in the first message
    assert (
        "Please generate a valid jinja template. Using variables like {{ i_am_a_variable_not_in_the_input }}, {%if invalid_condition %}!"
        in payload[0]["content"]
    )


async def test_bad_request(test_client: IntegrationTestClient):
    """Check that the run is correctly stored"""
    test_client.mock_openai_call(status_code=400, json={"error": {"message": "Bad request"}})
    task = await test_client.create_task()
    with pytest.raises(HTTPStatusError) as e:
        await test_client.run_task_v1(task, version={"model": Model.GPT_4O_2024_11_20, "provider": "openai"})
    error_body = e.value.response.json()
    assert e.value.response.status_code == 400
    assert error_body["error"]["message"] == "Bad request"
    run_id = error_body["id"]
    run = await test_client.fetch_run(task, run_id=run_id)
    assert run
    # Check that the run is stored correctly
    assert run["status"] == "failure"
    assert "task_output" in run
    assert not run["task_output"]


@pytest.mark.parametrize("use_deployment", [True, False])
async def test_with_model_fallback_on_rate_limit(test_client: IntegrationTestClient, use_deployment: bool):
    task = await test_client.create_agent_v1()
    run_kwargs: dict[str, Any] = (
        {"model": Model.CLAUDE_3_5_SONNET_20241022} if not use_deployment else {"version": "production"}
    )

    if use_deployment:
        version = await test_client.create_version_v1(task, {"model": Model.CLAUDE_3_5_SONNET_20241022})
        await test_client.post(
            f"/v1/_/agents/{task['id']}/versions/{version['id']}/deploy",
            json={"environment": "production"},
        )

    # Anthropic and bedrock always return a 429 so we will proceed with model fallback
    test_client.mock_anthropic_call(status_code=429, is_reusable=True)
    test_client.mock_bedrock_call(model=Model.CLAUDE_3_5_SONNET_20241022, status_code=429, is_reusable=True)

    # OpenAI returns a 200
    test_client.mock_openai_call(is_reusable=True)

    # Disable fallback -> we will raise
    with pytest.raises(HTTPStatusError) as e:
        await test_client.run_task_v1(task, use_fallback="never", **run_kwargs)
    assert e.value.response.status_code == 429

    # Auto fallback will use openai
    run1 = await test_client.run_task_v1(task, use_fallback=None, **run_kwargs)
    completions1 = (await test_client.fetch_completions(task, run_id=run1["id"]))["completions"]
    assert len(completions1) == 3
    assert [(c["model"], c["provider"], len(c["messages"]), c.get("cost_usd")) for c in completions1] == [
        (Model.CLAUDE_3_5_SONNET_20241022, Provider.ANTHROPIC, 2, None),
        (Model.CLAUDE_3_5_SONNET_20241022, Provider.AMAZON_BEDROCK, 2, None),
        (Model.GPT_41_2025_04_14, Provider.OPEN_AI, 2, approx((10 * 2 + 11 * 8) / 1_000_000)),
    ]

    # And manual fallback can be used to switch to a different model
    run2 = await test_client.run_task_v1(
        task,
        use_fallback=[Model.O3_2025_04_16],
        use_cache="never",
        **run_kwargs,
    )
    completions2 = (await test_client.fetch_completions(task, run_id=run2["id"]))["completions"]
    assert len(completions2) == 3
    assert [(c["model"], c["provider"], len(c["messages"]), c.get("cost_usd")) for c in completions2] == [
        (Model.CLAUDE_3_5_SONNET_20241022, Provider.ANTHROPIC, 2, None),
        (Model.CLAUDE_3_5_SONNET_20241022, Provider.AMAZON_BEDROCK, 2, None),
        (Model.O3_2025_04_16, Provider.OPEN_AI, 2, approx((10 * 2 + 11 * 8) / 1_000_000)),
    ]


@pytest.mark.parametrize("use_deployment", [True, False])
async def test_with_model_fallback_on_failed_generation(test_client: IntegrationTestClient, use_deployment: bool):
    task = await test_client.create_agent_v1()
    run_kwargs: dict[str, Any] = (
        {"model": Model.CLAUDE_3_5_SONNET_20241022} if not use_deployment else {"version": "production"}
    )

    if use_deployment:
        version = await test_client.create_version_v1(task, {"model": Model.CLAUDE_3_5_SONNET_20241022})
        await test_client.post(
            f"/v1/_/agents/{task['id']}/versions/{version['id']}/deploy",
            json={"environment": "production"},
        )

    # Anthropic returns an invalid JSON
    test_client.mock_anthropic_call(
        status_code=200,
        # Not a JSON
        raw_content="hello",
        usage={"input_tokens": 10, "output_tokens": 10},
        is_reusable=True,
    )

    # OpenAI returns a 200
    test_client.mock_openai_call(is_reusable=True)

    # Disable fallback -> we will raise the failed error
    with pytest.raises(HTTPStatusError) as e:
        await test_client.run_task_v1(task, use_fallback="never", **run_kwargs)
    assert e.value.response.status_code == 400

    # Auto fallback will use openai
    run1 = await test_client.run_task_v1(task, use_fallback=None, **run_kwargs)
    completions1 = (await test_client.fetch_completions(task, run_id=run1["id"]))["completions"]
    assert len(completions1) == 3
    assert [(c["model"], c["provider"], len(c["messages"]), c.get("cost_usd")) for c in completions1] == [
        (Model.CLAUDE_3_5_SONNET_20241022, Provider.ANTHROPIC, 2, approx(10 * (3 + 15) / 1_000_000)),
        # Second time we retry with different messages
        (Model.CLAUDE_3_5_SONNET_20241022, Provider.ANTHROPIC, 4, approx(10 * (3 + 15) / 1_000_000)),
        (Model.GPT_41_2025_04_14, Provider.OPEN_AI, 2, approx((10 * 2 + 11 * 8) / 1_000_000)),
    ]

    # And manual fallback can be used to switch to a different model
    run2 = await test_client.run_task_v1(
        task,
        use_fallback=[Model.O3_2025_04_16],
        use_cache="never",
        **run_kwargs,
    )
    completions2 = (await test_client.fetch_completions(task, run_id=run2["id"]))["completions"]
    assert len(completions2) == 3
    assert [(c["model"], c["provider"], len(c["messages"]), c.get("cost_usd")) for c in completions2] == [
        (Model.CLAUDE_3_5_SONNET_20241022, Provider.ANTHROPIC, 2, approx(10 * (3 + 15) / 1_000_000)),
        # Second time we retry with different messages
        (Model.CLAUDE_3_5_SONNET_20241022, Provider.ANTHROPIC, 4, approx(10 * (3 + 15) / 1_000_000)),  # 2 + 2
        (Model.O3_2025_04_16, Provider.OPEN_AI, 2, approx((10 * 2 + 11 * 8) / 1_000_000)),
    ]


async def test_preserve_credits(test_client: IntegrationTestClient):
    """Check that we indeed preserve credits when correctly configured"""

    task = await test_client.create_agent_v1()

    # First set up a provder that preserves credits
    test_client.mock_openai_call()
    created = await test_client.post(
        "/organization/settings/providers",
        json={"provider": "openai", "api_key": "hello", "preserve_credits": True},
    )
    config_id = created["id"]
    await test_client.wait_for_completed_tasks()

    org = await test_client.get_org()
    assert org["current_credits_usd"] == 10

    test_client.mock_openai_call(usage={"prompt_tokens": 10000, "completion_tokens": 10000})
    run = await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20)
    run_cost = 10000 * 0.0000025 + 10000 * 0.000010
    assert run["cost_usd"] == approx(run_cost)

    await test_client.wait_for_completed_tasks()
    org = await test_client.get_org()
    assert org["current_credits_usd"] == 10  # credits should not have been touched

    # Now delete the provider config
    await test_client.delete(f"/organization/settings/providers/{config_id}")
    await test_client.wait_for_completed_tasks()
    org = await test_client.get_org()
    assert org["current_credits_usd"] == 10
    assert not org.get("providers")

    # Add a new config that does not preserve credits
    test_client.mock_openai_call()
    await test_client.post(
        "/organization/settings/providers",
        json={"provider": "openai", "api_key": "hello", "preserve_credits": False},
    )

    await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20)
    org = await test_client.get_org()
    assert org["current_credits_usd"] == 10, "sanity"

    test_client.mock_openai_call(usage={"prompt_tokens": 10000, "completion_tokens": 10000})
    run1 = await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20, use_cache="never")
    assert run1["cost_usd"] == approx(run_cost)

    await test_client.wait_for_completed_tasks()
    org = await test_client.get_org()
    assert org["current_credits_usd"] == approx(10 - run_cost)


async def test_with_invalid_base64_data(test_client: IntegrationTestClient):
    """Check that we handle invalid base64 data correctly by returning an error immediately
    and not forwarding the request to the provider"""

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
        await test_client.run_task_v1(
            task,
            model=Model.GPT_4O_2024_11_20,
            task_input={"image": {"data": "bla"}},
        )
    assert e.value.response.status_code == 400
    assert e.value.response.json()["error"]["code"] == "invalid_file"

    # I should get the same error if I use a URL
    with pytest.raises(HTTPStatusError) as e:
        await test_client.run_task_v1(
            task,
            model=Model.GPT_4O_2024_11_20,
            task_input={"image": {"url": "data:image/png;base64,bla"}},
        )
    assert e.value.response.status_code == 400
    assert e.value.response.json()["error"]["code"] == "invalid_file"


async def test_with_inlined_files_with_url(test_client: IntegrationTestClient):
    # Create an agent with a file input
    task = await test_client.create_agent_v1(
        input_schema={
            "type": "object",
            "format": "messages",
            "properties": {"image_url": {"$ref": "#/$defs/Image"}},
        },
    )
    test_client.httpx_mock.add_response(
        url="https://example.com/image.png",
        content=b"Hello, world!",
    )
    # Create a version with templated variables
    version = await test_client.create_version_v1(
        task,
        {
            "model": Model.GPT_4O_2024_11_20,
            "messages": [
                {"role": "user", "content": [{"text": "Describe this image {{ image_url }}"}]},
            ],
        },
    )

    # Run the version
    test_client.mock_openai_call(is_reusable=True)

    run = await test_client.run_task_v1(
        task,
        version=version["id"],
        task_input={"image_url": {"url": "https://example.com/image.png"}},
    )
    assert run
    assert run["task_output"]["greeting"] == "Hello James!"

    # Check that the file was inlined
    request = test_client.httpx_mock.get_request(url="https://api.openai.com/v1/chat/completions")
    assert request
    body = json.loads(request.content)
    assert len(body["messages"]) == 1

    assert body["messages"][0]["content"] == [
        {
            "type": "text",
            "text": "Describe this image ",
        },
        {
            "type": "image_url",
            "image_url": {"url": "https://example.com/image.png"},
        },
    ]

    # Do the same thing with data
    run = await test_client.run_task_v1(
        task,
        version=version["id"],
        task_input={"image_url": {"data": "helloi==", "content_type": "image/png"}},
    )

    # Check that the file was inlined
    requests = test_client.httpx_mock.get_requests(url="https://api.openai.com/v1/chat/completions")
    assert len(requests) == 2
    request = requests[-1]
    body = json.loads(request.content)
    assert len(body["messages"]) == 1
    assert body["messages"][0]["content"] == [
        {
            "type": "text",
            "text": "Describe this image ",
        },
        {
            "type": "image_url",
            "image_url": {"url": "data:image/png;base64,helloi=="},
        },
    ]


async def test_with_messages(test_client: IntegrationTestClient):
    """There was an issue with a conflict with the use of a key named messages in the input schema
    for non proxy agents"""
    task = await test_client.create_task(
        input_schema={
            "type": "object",
            "properties": {"messages": {"type": "string"}},
        },
    )
    test_client.mock_openai_call()
    run = await test_client.run_task_v1(task, task_input={"messages": "world"})
    assert run


@pytest.mark.parametrize("google_status", [500, 429])
async def test_no_model_fallback_on_provider_internal_error_gemini(
    test_client: IntegrationTestClient,
    google_status: int,
):
    task = await test_client.create_task()

    # Vertex is only configured on a single region here so we only need to mock one call
    test_client.mock_vertex_call(
        model=Model.GEMINI_1_5_PRO_002,
        status_code=google_status,  # Force an error
        url=vertex_url(Model.GEMINI_1_5_PRO_002.value),
        is_reusable=True,
    )

    # Gemini will also return a 500
    test_client.mock_vertex_call(
        model=Model.GEMINI_1_5_PRO_002,
        status_code=google_status,  # Force an  error
        url=gemini_url(Model.GEMINI_1_5_PRO_002.value),
        is_reusable=True,
    )

    # OpenAI will return a 200
    test_client.mock_openai_call()

    res = await test_client.run_task_v1(
        task,
        model=Model.GEMINI_1_5_PRO_002,
        use_fallback=None,  # auto
    )

    assert res

    vertex_reqs = test_client.httpx_mock.get_requests(url=vertex_url(Model.GEMINI_1_5_PRO_002.value))
    gemini_reqs = test_client.httpx_mock.get_requests(url=gemini_url(Model.GEMINI_1_5_PRO_002.value))
    openai_reqs = test_client.httpx_mock.get_requests(url=openai_endpoint())
    assert len(vertex_reqs) >= 1
    assert len(gemini_reqs) >= 1
    assert len(openai_reqs) == 1


async def test_old_reasoning_models_are_remapped(test_client: IntegrationTestClient):
    """The reasoning effort was previously included in the model ID. This test makes
    sure that when using a model with a reasoning effort it is correctly mapped to the
    right version"""

    # Use deprecated model
    agent = await test_client.create_agent_v1()
    test_client.mock_openai_call()

    run = await test_client.run_task_v1(
        agent,
        model=Model.O3_2025_04_16_LOW_REASONING_EFFORT,
    )
    assert run

    version = await test_client.fetch_version(agent, version_id=run["version"]["id"])
    assert version["properties"]["model"] == Model.O3_2025_04_16
    assert version["properties"]["reasoning_effort"] == "low"

    openai_request = test_client.httpx_mock.get_request(url=openai_endpoint())
    assert openai_request
    body = json.loads(openai_request.content)
    assert body["model"] == Model.O3_2025_04_16
    assert body["reasoning_effort"] == "low"
