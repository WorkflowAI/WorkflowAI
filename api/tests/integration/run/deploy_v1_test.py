import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from tests.integration.common import (
    IntegrationTestClient,
    fetch_run,
    get_amplitude_events,
    openai_endpoint,
    result_or_raise,
    run_task_v1,
    task_url_v1,
)
from tests.utils import remove_none


async def test_deployed_environment(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    assert task["name"] == "Greet"
    assert task["task_id"] == "greet"
    assert task["task_schema_id"] == 1

    test_client.mock_vertex_call()
    # Run the task the first time
    task_run = await run_task_v1(
        test_client.int_api_client,
        task_id="greet",
        task_schema_id=1,
        task_input={"name": "John", "age": 30},
        model=test_client.DEFAULT_VERTEX_MODEL,
    )

    await test_client.wait_for_completed_tasks()

    fetched_task_run = await fetch_run(test_client.int_api_client, task, task_run)

    created_group = fetched_task_run["group"]
    assert created_group["iteration"] == 1
    assert remove_none(created_group["properties"]) == {
        "model": test_client.DEFAULT_VERTEX_MODEL,
        "temperature": 0.0,
    }

    # Now we should be able to deploy the group to a given environment
    res = await test_client.int_api_client.post(
        "/chiefofstaff.ai/agents/greet/schemas/1/versions/1/deploy",
        json={"environment": "production"},
    )
    assert res.status_code == 200

    await test_client.wait_for_completed_tasks()

    amplitude_events = await get_amplitude_events(test_client.httpx_mock)
    assert len(amplitude_events) == 2
    event_types = [event["event_type"] for event in amplitude_events]
    assert event_types == ["org.ran.task", "org.deployed.version"]

    assert amplitude_events[1]["event_properties"]["environment"] == "production"

    test_client.mock_vertex_call(parts=[{"text": '{"greeting": "Hello James!"}'}])

    # Run the task using the environment
    async def _run_task_by_env():
        task_run = await run_task_v1(
            test_client.int_api_client,
            task_id="greet",
            task_schema_id=1,
            task_input={"name": "James", "age": 15},
            version="production",
        )
        await test_client.wait_for_completed_tasks()
        return task_run

    task_run = await _run_task_by_env()
    # ID of the first task run when running by environment
    task_run_id_1 = task_run["id"]
    assert task_run["task_output"] == {"greeting": "Hello James!"}
    # assert task_run["version"]["properties"]["model"] == test_client.DEFAULT_VERTEX_MODEL

    fetched_task_run = await fetch_run(test_client.int_api_client, task, task_run)
    assert fetched_task_run["group"]["iteration"] == 1

    requests = test_client.httpx_mock.get_requests(url=re.compile(r".*googleapis.*"))
    assert len(requests) == 2

    # Create another group manually
    res = await test_client.int_api_client.post(
        "/chiefofstaff.ai/agents/greet/schemas/1/groups",
        json={
            "properties": {
                "model": "gpt-4o-2024-11-20",
            },
        },
    )
    manually_created_group = res.json()
    assert manually_created_group["iteration"] == 2
    assert not manually_created_group.get("aliases")

    # Switched the alias to the new group
    result_or_raise(
        await test_client.int_api_client.post(
            "/chiefofstaff.ai/agents/greet/schemas/1/versions/2/deploy",
            json={"environment": "production"},
        ),
    )

    test_client.httpx_mock.add_response(
        url=openai_endpoint(),
        json={
            "id": "1",
            "choices": [{"message": {"content": '{"greeting": "Hello James!"}'}}],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 11,
                "total_tokens": 21,
            },
        },
    )

    task_run = await _run_task_by_env()
    # assert task_run["version"]["properties"]["model"] == "gpt-4o-2024-11-20"

    fetched_task_run = await fetch_run(test_client.int_api_client, task, task_run)
    assert fetched_task_run["group"]["iteration"] == 2

    # This should really be in another test
    llm_completions: list[dict[str, Any]] = fetched_task_run["llm_completions"]
    assert len(llm_completions) == 1
    assert llm_completions[0].get("response")
    assert llm_completions[0].get("messages")

    usage: dict[str, Any] | None = llm_completions[0].get("usage")
    assert usage
    assert usage["prompt_token_count"] == 10
    assert usage["completion_token_count"] == 11
    assert usage["model_context_window_size"] == 128000  # from model

    task_run_id_2 = task_run["id"]
    # Checking that the cache was not used
    assert task_run_id_2 != task_run_id_1, "Task run ID should be different"

    requests = test_client.httpx_mock.get_requests(url=openai_endpoint())
    assert len(requests) == 1

    await asyncio.sleep(0.010)

    # For sanity check re-run to check that the cache is used
    task_run = await _run_task_by_env()
    assert task_run["id"] == task_run_id_2, "Task run ID should be the same"

    requests = test_client.httpx_mock.get_requests(url=openai_endpoint())
    assert len(requests) == 1


async def test_deployed_task_when_new_variant(test_client: IntegrationTestClient):
    # Making sure task was created in the past
    task = await test_client.create_task(creation_date=datetime.now(timezone.utc) - timedelta(hours=1))
    variant_id = task["id"]

    test_client.mock_vertex_call()
    # Run the task the first time
    task_run = await test_client.run_task_v1(
        task=task,
        task_input={"name": "John", "age": 30},
        model=test_client.DEFAULT_VERTEX_MODEL,
    )

    fetched_task_run = await fetch_run(test_client.int_api_client, task, task_run)
    assert fetched_task_run["group"]["iteration"] == 1
    assert fetched_task_run["group"]["id"] == "4b3804c632aa828c865f9f1c3b7010ae"

    # Making sure by fetching the version
    version = await test_client.get(task_url_v1(task, "versions/4b3804c632aa828c865f9f1c3b7010ae"))
    assert version["id"] == fetched_task_run["group"]["id"], "sanity"
    assert version["properties"]["task_variant_id"] == variant_id

    # Now deploy the version
    result_or_raise(
        await test_client.int_api_client.post(
            "/_/agents/greet/schemas/1/versions/1/deploy",
            json={"environment": "production"},
        ),
    )

    await test_client.wait_for_completed_tasks()

    test_client.mock_vertex_call()
    # Run using the deployemnt
    run1 = await test_client.run_task_v1(
        task=task,
        task_input={"name": "John", "age": 31},
        version="production",
    )
    # We should have the same variant id
    fetch1 = await fetch_run(test_client.int_api_client, task, run1)
    version1 = await test_client.get(task_url_v1(task, f"versions/{fetch1['group']['id']}"))
    assert version1["properties"]["task_variant_id"] == variant_id

    # Ticking the time to make sure the new variant has been created after
    await asyncio.sleep(0.010)

    # Now create a new variant by setting the description of a field

    res = result_or_raise(
        await test_client.int_api_client.post(
            f"/_/agents/{task['task_id']}/schemas",
            json={
                "name": "Greet",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "The name of the person"},
                        "age": {"type": "integer"},
                    },
                    "required": ["name", "age"],
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "greeting": {"type": "string"},
                    },
                    "required": ["greeting"],
                },
                "skip_generation": True,
                "create_first_iteration": False,
            },
        ),
    )
    # new variant id
    assert res["id"] != variant_id
    # Same schema id
    assert res["task_schema_id"] == 1

    # Now if I run using a model, it will use the new variant
    test_client.mock_vertex_call()
    run3 = await test_client.run_task_v1(
        task=task,
        task_input={"name": "John", "age": 34},
        model=test_client.DEFAULT_VERTEX_MODEL,
    )
    fetch3 = await fetch_run(test_client.int_api_client, task, run3)
    assert fetch3["group"]["iteration"] == 2
    version3 = await test_client.get(task_url_v1(task, f"versions/{fetch3['group']['id']}"))
    assert version3["properties"]["task_variant_id"] == res["id"]

    # Now re-run using the deployment
    test_client.mock_vertex_call()
    run2 = await test_client.run_task_v1(
        task=task,
        task_input={"name": "John", "age": 32},
        version="production",
    )
    fetch2 = await fetch_run(test_client.int_api_client, task, run2)
    # We should still be using the same variant id
    assert fetch2["group"]["id"] == "4b3804c632aa828c865f9f1c3b7010ae"
