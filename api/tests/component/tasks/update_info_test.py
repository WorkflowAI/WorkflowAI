from unittest import mock

from freezegun.api import FrozenDateTimeFactory
from httpx import AsyncClient
from pytest_httpx import HTTPXMock
from taskiq import InMemoryBroker

from tests.component.common import (
    IntegrationTestClient,
    create_task,
    get_amplitude_events,
    result_or_raise,
    wait_for_completed_tasks,
)


async def test_update_info_and_schema(
    int_api_client: AsyncClient,
    frozen_time: FrozenDateTimeFactory,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
) -> None:
    task = await create_task(int_api_client, patched_broker, httpx_mock)
    assert task["input_schema"]["version"] == "89e6b8a25b640c183f5443e1745efd89"
    assert task["input_schema"]["json_schema"] == {
        "type": "object",
        "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
        "required": ["name", "age"],
    }

    # list all agents
    task_list = result_or_raise(await int_api_client.get("/_/agents"))["items"]
    assert len(task_list) == 1

    assert task_list[0] == {
        "id": "greet",
        "description": None,
        "is_public": False,
        "name": "Greet",
        "tenant": "",
        "uid": mock.ANY,
        "versions": [
            {
                "created_at": "2024-08-12T00:00:00Z",
                "description": None,
                "input_schema": None,
                "input_schema_version": "89e6b8a25b640c183f5443e1745efd89",
                "is_hidden": False,
                # TODO: that's bad. We should include the field in the response since
                # It will be none all the time
                "output_schema": None,
                "output_schema_version": "7d4f7e6c016e7064623373ab4b5c01be",
                "schema_id": 1,
                "variant_id": "ffa888f1b7f2632199fe957f4338e030",
                "last_active_at": None,
            },
        ],
        "average_cost_usd": None,
        "run_count": None,
    }

    # Patching the name
    result_or_raise(await int_api_client.patch(f"/_/agents/{task['task_id']}", json={"name": "Greet2"}))
    new_task_list = result_or_raise(await int_api_client.get("/_/agents"))["items"]
    assert len(new_task_list) == 1
    assert new_task_list[0] == {**task_list[0], "name": "Greet2"}

    # Fetch the full schema and check that they match the created one
    schema = result_or_raise(await int_api_client.get(f"/_/agents/{task['task_id']}/schemas/1"))
    assert schema["input_schema"] == task["input_schema"]
    assert schema["output_schema"] == task["output_schema"]

    # Move time so one is older than the other
    frozen_time.tick()

    # Now add a schema that only has a metadata difference
    new_task_variant = result_or_raise(
        await int_api_client.post(
            f"_/agents/{task['task_id']}/schemas",
            json={
                "name": "Test name",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        # The description is different
                        "name": {"type": "string", "description": "A name"},
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
                "skip_generation": True,  # Do not generate instructions for this tests, instruction gen is test elsewhere
                "create_first_iteration": False,
            },
        ),
    )
    assert new_task_variant["input_schema"]["version"] == "89e6b8a25b640c183f5443e1745efd89"
    assert new_task_variant["task_schema_id"] == 1
    assert new_task_variant["id"] != task["id"]
    assert new_task_variant["task_id"] == task["task_id"]
    assert new_task_variant["name"] == "Greet2"

    # Wait for the jobs to complete
    await wait_for_completed_tasks(patched_broker)

    # Check the analytics event was emitted
    amplitude_events = await get_amplitude_events(httpx_mock)
    assert len(amplitude_events) == 1
    assert amplitude_events[0]["event_type"] == "org.edited.task_schema"

    schema = result_or_raise(await int_api_client.get(f"/_/agents/{task['task_id']}/schemas/1"))
    assert schema["input_schema"]["json_schema"]["properties"]["name"] == {"type": "string", "description": "A name"}
    assert schema["input_schema"] == new_task_variant["input_schema"]
    assert schema["output_schema"] == new_task_variant["output_schema"]
    assert schema["name"] == "Greet2"

    # Test create a new schema
    new_new_task_variant = result_or_raise(
        await int_api_client.post(
            f"_/agents/{task['task_id']}/schemas",
            json={
                "name": "Test name",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        # The description is different
                        "name2": {"type": "string", "description": "A name"},
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
                "skip_generation": True,  # Do not generate instructions for this tests, instruction gen is test elsewhere
                "create_first_iteration": False,
            },
        ),
    )
    assert new_new_task_variant["task_schema_id"] == 2
    assert schema["name"] == "Greet2"


async def test_revert_to_previous_schema(
    test_client: IntegrationTestClient,
    frozen_time: FrozenDateTimeFactory,
):
    task = await test_client.create_agent_v1()
    assert task["variant_id"] == "802a5890e100e4581e8a8174242bc4df"

    frozen_time.tick()

    new_task_variant = await test_client.post(
        "/v1/_/agents",
        json={
            "id": task["id"],
            "name": "Test name",
            "input_schema": {
                "type": "object",
                "properties": {
                    # The description is different
                    "name": {"type": "string", "description": "A name"},
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
        },
    )
    assert new_task_variant["variant_id"] == "9779163c34441000688f9ec5cea6c30e"

    # fetch the current schema
    schema = await test_client.get(f"/_/agents/{task['id']}/schemas/1")
    assert schema["input_schema"]["json_schema"]["properties"]["name"] == {"type": "string", "description": "A name"}
    assert schema["name"] == "Greet"
    assert schema["schema_id"] == 1

    frozen_time.tick()

    new_new_task_variant = await test_client.post(
        "/v1/_/agents",
        json={
            "id": task["id"],
            "name": "Test name",
            "input_schema": {
                "type": "object",
                # Schema is the same as before
                "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
                "required": ["name", "age"],
            },
            "output_schema": {
                "type": "object",
                "properties": {"greeting": {"type": "string"}},
                "required": ["greeting"],
            },
        },
    )
    # Make sure we reverted back
    assert new_new_task_variant["variant_id"] == "802a5890e100e4581e8a8174242bc4df"

    schema = await test_client.get(f"/_/agents/{task['id']}/schemas/1")
    assert schema["input_schema"]["json_schema"]["properties"]["name"] == {"type": "string"}
    assert schema["name"] == "Greet"
