import json
import math
from typing import Any

import pytest
from httpx import AsyncClient, HTTPStatusError
from pytest_httpx import HTTPXMock, IteratorStream
from taskiq import InMemoryBroker

from core.domain.models import Model, Provider
from core.domain.models.model_provider_data_mapping import OPENAI_PROVIDER_DATA
from core.utils.ids import id_uint32
from tests.component.common import (
    LEGACY_TEST_JWT,
    IntegrationTestClient,
    create_task,
    create_task_without_required_fields,
    get_amplitude_events,
    list_groups,
    mock_openai_call,
    mock_vertex_call,
    openai_endpoint,
    result_or_raise,
    run_task,
    stream_run_task,
    wait_for_completed_tasks,
)
from tests.utils import approx, fixture_bytes, request_json_body

# TODO: keeping for legacy reasons, the run v1 endpoint should be used instead


async def test_run_with_metadata_and_labels(
    httpx_mock: HTTPXMock,
    int_api_client: AsyncClient,
    patched_broker: InMemoryBroker,
):
    await create_task(int_api_client, patched_broker, httpx_mock)

    mock_vertex_call(httpx_mock, model=Model.GEMINI_2_5_PRO, latency=0.01)

    # Run the task the first time
    task_run = await run_task(
        int_api_client,
        task_id="greet",
        task_schema_id=1,
        task_input={"name": "John", "age": 30},
        group={"properties": {"model": Model.GEMINI_2_5_PRO}},
        metadata={"key1": "value1", "key2": "value2"},
    )

    assert task_run["is_active"]

    assert task_run["metadata"]["key1"] == "value1"
    assert task_run["metadata"]["key2"] == "value2"
    # assert task_run["metadata"]["workflowai.vertex_api_region"] == "us-central1"
    assert task_run["metadata"]["workflowai.providers"] == ["google"]
    assert task_run["metadata"]["workflowai.provider"] == "google"

    # Fetch the task run

    fetched = await int_api_client.get(f"/chiefofstaff.ai/agents/greet/runs/{task_run['id']}")
    assert fetched.status_code == 200
    fetched_task_run = fetched.json()

    assert fetched_task_run["metadata"]["key1"] == "value1"
    assert fetched_task_run["metadata"]["key2"] == "value2"
    # assert fetched_task_run["metadata"]["workflowai.vertex_api_region"] == "us-central1"
    assert fetched_task_run["metadata"]["workflowai.providers"] == ["google"]
    assert fetched_task_run["metadata"]["workflowai.provider"] == "google"

    await wait_for_completed_tasks(patched_broker)

    amplitude_events = await get_amplitude_events(httpx_mock)
    assert len(amplitude_events) == 1
    event = amplitude_events[0]

    org = result_or_raise(await int_api_client.get("/_/organization/settings"))
    assert event["user_id"] == org["tenant"]
    assert event["event_type"] == "org.ran.task"

    # Can't predict the value
    latency_seconds = event["event_properties"]["latency_seconds"]
    assert latency_seconds > 0

    assert event["event_properties"] == {
        "cost_usd": pytest.approx(6.45e-05, abs=0.01),  # type: ignore
        "group": {
            "few_shot": False,
            "iteration": 1,
            "model": "gemini-2.5-pro",
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

    await run_task(
        int_api_client,
        task_id="greet",
        task_schema_id=1,
        task_input={"name": "John", "age": 30},
        group={"properties": {"model": "gpt-4o-2024-05-13"}},
    )

    await wait_for_completed_tasks(patched_broker)

    org = result_or_raise(await int_api_client.get("/_/organization/settings"))
    assert org["added_credits_usd"] == 10.0
    assert org["current_credits_usd"] == 9.999865


@pytest.mark.skip(reason="deprecated endpoint")
async def test_usage_for_per_char_model(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
):
    await create_task(int_api_client, patched_broker, httpx_mock)
    mock_vertex_call(httpx_mock)

    def _check_run(task_run: dict[str, Any]):
        llm_completions: list[dict[str, Any]] = task_run["llm_completions"]
        assert len(llm_completions) == 1
        assert llm_completions[0].get("response") == '{"greeting": "Hello John!"}'
        assert llm_completions[0].get("messages")

        usage: dict[str, Any] | None = llm_completions[0].get("usage")
        assert usage
        assert usage["prompt_token_count"] == 110.25
        assert usage["completion_token_count"] == 25 / 4  # 25 chars / 4
        assert usage["model_context_window_size"] == 2097152  # from model

    # Run the task the first time
    task_run = await run_task(
        int_api_client,
        task_id="greet",
        task_schema_id=1,
        task_input={"name": "John", "age": 30},
        group={"properties": {"model": "gemini-2.5-pro"}},
    )

    _check_run(task_run)

    # Fetch the task run

    fetched = await int_api_client.get(f"/chiefofstaff.ai/agents/greet/runs/{task_run['id']}")
    assert fetched.status_code == 200
    fetched_task_run = fetched.json()

    # TODO: fetched_task_run != task_run for now :( we need to remove the domain model that's in between
    _check_run(fetched_task_run)


@pytest.mark.skip(reason="deprecated endpoint")
async def test_usage_for_per_token_model(
    test_client: IntegrationTestClient,
):
    await test_client.create_task()

    test_client.mock_vertex_call(
        publisher="meta",
        model="llama3-405b-instruct-maas",
    )

    def _check_run(task_run: dict[str, Any]):
        llm_completions: list[dict[str, Any]] = task_run["llm_completions"]
        assert len(llm_completions) == 1
        assert llm_completions[0].get("response") == '{"greeting": "Hello John!"}'
        assert llm_completions[0].get("messages")

        usage: dict[str, Any] | None = llm_completions[0].get("usage")
        assert usage
        assert usage["prompt_token_count"] == 222  # from initial usage
        assert usage["completion_token_count"] == 9  # from initial usage
        assert usage["model_context_window_size"] == 128000  # from model

    # Run the task the first time
    task_run = await run_task(
        test_client.int_api_client,
        task_id="greet",
        task_schema_id=1,
        task_input={"name": "John", "age": 30},
        group={"properties": {"provider": "google", "model": "llama-3.1-405b"}},
    )

    _check_run(task_run)

    # Fetch the task run

    fetched = await test_client.int_api_client.get(f"/chiefofstaff.ai/agents/greet/runs/{task_run['id']}")
    assert fetched.status_code == 200
    fetched_task_run = fetched.json()

    # TODO: fetched_task_run != task_run for now :( we need to remove the domain model that's in between
    _check_run(fetched_task_run)


async def test_openai_usage(httpx_mock: HTTPXMock, int_api_client: AsyncClient, patched_broker: InMemoryBroker):
    task = await create_task(int_api_client, patched_broker, httpx_mock)

    mock_openai_call(httpx_mock)

    # Run the task the first time
    task_run = await run_task(
        int_api_client,
        task_id="greet",
        task_schema_id=1,
        task_input={"name": "John", "age": 30},
        group={"properties": {"model": "gpt-4o-2024-11-20"}},
    )

    llm_completions: list[dict[str, Any]] = task_run["llm_completions"]
    assert len(llm_completions) == 1
    assert llm_completions[0].get("response") == '{"greeting": "Hello James!"}'
    assert llm_completions[0].get("messages")

    usage: dict[str, Any] | None = llm_completions[0].get("usage")
    assert usage
    assert usage["prompt_token_count"] == 10
    assert usage["completion_token_count"] == 11
    assert usage["model_context_window_size"] == 128000  # from model

    await wait_for_completed_tasks(patched_broker)

    # Check groups
    groups = await list_groups(int_api_client, task)
    assert len(groups) == 1
    assert groups[0]["properties"]["model"] == "gpt-4o-2024-11-20"
    assert groups[0]["run_count"] == 1


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

    task_run = await run_task(
        int_api_client,
        task_id="greet",
        task_schema_id=1,
        task_input={"name": "John", "age": 30},
        group={"properties": {"model": "gpt-4o-2024-11-20"}},
    )

    llm_completions: list[dict[str, Any]] = task_run["llm_completions"]
    assert len(llm_completions) == 1
    assert llm_completions[0].get("response") == '{"greeting": "Hello James!"}'
    assert llm_completions[0].get("messages")

    usage: dict[str, Any] | None = llm_completions[0].get("usage")
    assert usage
    assert usage["prompt_token_count"] == 10
    assert usage["completion_token_count"] == 11
    assert usage["prompt_token_count_cached"] == 5
    # TODO: investigate the 3*10e-16 difference
    assert math.isclose(
        usage["prompt_cost_usd"],
        0.00001875,  # 10 * 0.0000025 + 10 * 0.00000125 (50% price for cached tokens)
        rel_tol=1e-10,
    )
    assert usage["completion_cost_usd"] == approx(0.00011)  # 11 * 0.00001
    assert usage["model_context_window_size"] == approx(128000)  # from model


async def test_openai_stream(
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
                b'data: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"content":"\\"greeting\\": \\"Hello James!\\"\\n}"},"logprobs":null,"finish_reason":null}]}\n\n',
                b"data: [DONE]\n\n",
            ],
        ),
    )

    # Run the task the first time
    task_run = stream_run_task(
        int_api_client,
        task_id="greet",
        task_schema_id=1,
        task_input={"name": "John", "age": 30},
        group={"properties": {"model": "gpt-4o-2024-11-20"}},
    )
    chunks = [chunk async for chunk in task_run]
    decoded_chunk: list[dict[str, Any]] = []
    for chunk in chunks:
        assert chunk.startswith("data: ")
        assert chunk.endswith("\n\n")
        decoded = json.loads(chunk[6:-2])
        decoded_chunk.append(decoded)

    assert len(chunks) == 2
    assert "run_id" in decoded_chunk[0]
    assert decoded_chunk[0]["task_output"] == {"greeting": "Hello James!"}
    assert decoded_chunk[1]["run_id"] == decoded_chunk[0]["run_id"]

    await wait_for_completed_tasks(patched_broker)

    # Check groups
    groups = await list_groups(int_api_client, task)
    assert len(groups) == 1
    assert groups[0]["properties"]["model"] == "gpt-4o-2024-11-20"
    assert groups[0]["run_count"] == 1


async def test_run_with_500_error(httpx_mock: HTTPXMock, int_api_client: AsyncClient, patched_broker: InMemoryBroker):
    await create_task_without_required_fields(int_api_client, patched_broker, httpx_mock)

    # Add an evaluator to the task
    mock_openai_call(httpx_mock, status_code=500)
    mock_openai_call(httpx_mock, status_code=500, provider="azure_openai")

    # Run the task the first time
    with pytest.raises(HTTPStatusError) as e:
        await run_task(
            int_api_client,
            task_id="greet",
            task_schema_id=1,
            task_input={"name": "John", "age": 30},
            group={"properties": {"model": "gpt-4o-2024-11-20"}},
        )
    assert e.value.response.status_code == 424

    await wait_for_completed_tasks(patched_broker)

    events = await get_amplitude_events(httpx_mock)
    assert len(events) == 1
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

    # Get the model's cost per token for the specific model (GPT-4o-2024-11-20)
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
    run1 = await run_task(
        int_api_client,
        task_id="greet",
        task_schema_id=1,
        task_input={"name": "John", "age": 30},
        group={"properties": {"model": "gpt-4o-2024-11-20"}},
    )
    await wait_for_completed_tasks(patched_broker)
    assert pytest.approx(run1["cost_usd"], 0.001) == 6.0, "sanity"  # pyright: ignore [reportUnknownMemberType]

    # Check that credits have been reduced by $1
    org = result_or_raise(await int_api_client.get("/_/organization/settings"))
    assert pytest.approx(org["current_credits_usd"], 0.001) == 4.0  ## pyright: ignore [reportUnknownMemberType]

    # Now we should succeed again but credits will be negative
    await run_task(
        int_api_client,
        task_id="greet",
        task_schema_id=1,
        task_input={"name": "John", "age": 31},
        group={"properties": {"model": "gpt-4o-2024-11-20"}},
    )

    await wait_for_completed_tasks(patched_broker)

    org = result_or_raise(await int_api_client.get("/_/organization/settings"))
    assert pytest.approx(org["current_credits_usd"], 0.001) == -2.0  # pyright: ignore [reportUnknownMemberType]

    with pytest.raises(HTTPStatusError) as e:
        await run_task(
            int_api_client,
            task_id="greet",
            task_schema_id=1,
            task_input={"name": "John", "age": 30},
            group={"properties": {"model": "gpt-4o-2024-11-20"}},
        )

    assert e.value.response.status_code == 402


async def test_run_no_tenant_analytics(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
):
    # Check that we still get the task org name when there is no tenant in the URL
    task = await create_task(int_api_client, patched_broker, httpx_mock)
    mock_openai_call(httpx_mock)

    result_or_raise(
        await int_api_client.post(
            f"/tasks/{task['task_id']}/schemas/{task['task_schema_id']}/run",
            json={
                "group": {"properties": {"model": "gpt-4o-2024-11-20"}},
                "task_input": {"name": "John", "age": 30},
            },
        ),
    )

    await wait_for_completed_tasks(patched_broker)

    events = await get_amplitude_events(httpx_mock)
    assert len(events) == 1
    event = events[0]
    event_task = event["event_properties"]["task"]
    assert event_task["organization_id"] == "org_2iPlfJ5X4LwiQybM9qeT00YPdBe"
    assert event_task["organization_slug"] == "test-21"

    assert event["user_properties"]["organization_slug"] == "test-21"
    assert event["user_properties"]["organization_id"] == "org_2iPlfJ5X4LwiQybM9qeT00YPdBe"

    org = result_or_raise(await int_api_client.get("/_/organization/settings"))
    assert event["user_id"] == org["tenant"]


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

    res = await run_task(
        int_api_client,
        task_id=task["task_id"],
        task_schema_id=task["task_schema_id"],
        task_input={
            "image": {
                "url": "https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExYXQxbTFybW0wZWs2M3RkY3gzNXZlbXp4aHhkcTl4ZzltN2V6Y21lcCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9cw/rkFQ8LrdXcP5e/giphy.webp",
            },
        },
    )
    assert res["task_input"]["image"]["content_type"] == "image/webp"


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
        await run_task(
            int_api_client,
            task["task_id"],
            task["task_schema_id"],
            task_input={"image": {"url": "https://bla.com/file"}},
            # TODO: we should not have to force the provider here, the error should not be an unknonw provider error
            group={"properties": {"model": "gpt-4o-2024-11-20", "provider": Provider.OPEN_AI}},
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

    res = await run_task(
        int_api_client,
        task_id=task["task_id"],
        task_schema_id=task["task_schema_id"],
        task_input={
            "image": {
                "url": "https://media3.giphy.com/media/giphy",
            },
        },
    )
    assert res["task_input"]["image"]["content_type"] == "image/webp"

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

    httpx_mock.add_response(
        # Content type is not guessable from URL and neither from the data
        url="https://media3.giphy.com/media/giphy",
        content=b"not a standard image",
    )

    res = await run_task(
        int_api_client,
        task_id=task["task_id"],
        task_schema_id=task["task_schema_id"],
        task_input={
            "image": {
                "url": "https://media3.giphy.com/media/giphy",
            },
        },
    )
    assert not res["task_input"]["image"].get("content_type")

    req = httpx_mock.get_request(url=openai_endpoint())
    assert req
    req_body = request_json_body(req)

    image_url_content = req_body["messages"][1]["content"][1]  # text message is first, image message is second
    assert image_url_content["type"] == "image_url"
    # Open AI supports using a * content type so no need to block here
    assert image_url_content["image_url"]["url"] == "https://media3.giphy.com/media/giphy"


async def test_legacy_tokens(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
    integration_storage: Any,
):
    headers = {"Authorization": f"Bearer {LEGACY_TEST_JWT}"}
    # First call will fail because there is no tenant record
    # And we don't auto-create tenants based on deprecated tokens
    with pytest.raises(HTTPStatusError) as e:
        await run_task(int_api_client, task_id="greet", task_schema_id=1, headers=headers)
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
    await run_task(int_api_client, task_id=task["task_id"], task_schema_id=task["task_schema_id"], headers=headers)
