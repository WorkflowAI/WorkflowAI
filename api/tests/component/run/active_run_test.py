import asyncio
from datetime import datetime, timezone

from httpx import AsyncClient
from pytest_httpx import HTTPXMock
from taskiq import InMemoryBroker

from tests.component.common import (
    create_group,
    create_task,
    list_groups,
    mock_openai_call,
    result_or_raise,
    run_task_v1,
    wait_for_completed_tasks,
)


async def test_run_api_default_source_active_run(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
):
    mock_openai_call(httpx_mock)

    task = await create_task(int_api_client, patched_broker, httpx_mock, name="greet")
    # No groups yet
    groups = await list_groups(int_api_client, task)
    assert len(groups) == 0, "sanity"
    group = await create_group(int_api_client, task, "gpt-4o-2024-11-20")

    task_run = await run_task_v1(
        int_api_client,
        task_id=task["task_id"],
        task_schema_id=task["task_schema_id"],
        task_input={"name": "James", "age": 31},
        model="gpt-4o-2024-11-20",
        version=group["iteration"],
    )
    await wait_for_completed_tasks(patched_broker)

    fetched_task_run = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/runs/{task_run['id']}"),
    )

    groups = await list_groups(int_api_client, task)
    assert len(groups) == 1
    assert fetched_task_run["group"]["iteration"] == 1
    assert fetched_task_run.get("author_tenant") is None
    assert fetched_task_run["is_active"] is True

    await wait_for_completed_tasks(patched_broker)
    # Check task schema
    task_schema = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/schemas/{task['task_schema_id']}"),
    )
    timenow = datetime.now(timezone.utc)
    assert task_schema["last_active_at"] is not None
    assert abs((datetime.fromisoformat(task_schema["last_active_at"]) - timenow).total_seconds()) < 0.2
    # Check groups
    groups = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/schemas/{task['task_schema_id']}/groups"),
    )
    assert len(groups["items"]) == 1

    assert groups["items"][0]["iteration"] == 1
    assert groups["items"][0]["last_active_at"] is not None
    assert abs((datetime.fromisoformat(groups["items"][0]["last_active_at"]) - timenow).total_seconds()) < 0.2

    list_tasks = result_or_raise(
        await int_api_client.get("/_/agents"),
    )
    assert len(list_tasks["items"]) == 1
    assert list_tasks["items"][0]["id"] == task["task_id"]
    assert list_tasks["items"][0]["versions"][0]["last_active_at"] is not None
    assert (
        abs((datetime.fromisoformat(list_tasks["items"][0]["versions"][0]["last_active_at"]) - timenow).total_seconds())
        < 0.2
    )

    task = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/{task['task_id']}"),
    )
    assert task["versions"][0]["last_active_at"] is not None
    assert abs((datetime.fromisoformat(task["versions"][0]["last_active_at"]) - timenow).total_seconds()) < 0.2


async def test_run_api_set_source_active_run(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
):
    mock_openai_call(httpx_mock)

    task = await create_task(int_api_client, patched_broker, httpx_mock, name="greet")
    # No groups yet
    groups = await list_groups(int_api_client, task)
    assert len(groups) == 0, "sanity"
    group = await create_group(int_api_client, task, "gpt-4o-2024-11-20")

    task_run = await run_task_v1(
        int_api_client,
        task_id=task["task_id"],
        task_schema_id=task["task_schema_id"],
        task_input={"name": "James", "age": 31},
        model="gpt-4o-2024-11-20",
        version=group["iteration"],
        headers={"x-workflowai-source": "api"},
    )
    await wait_for_completed_tasks(patched_broker)

    fetched_task_run = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/runs/{task_run['id']}"),
    )

    groups = await list_groups(int_api_client, task)
    assert len(groups) == 1
    assert fetched_task_run["group"]["iteration"] == 1
    assert fetched_task_run.get("author_tenant") is None
    assert fetched_task_run["is_active"] is True

    await wait_for_completed_tasks(patched_broker)
    # Check task schema
    task_schema = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/schemas/{task['task_schema_id']}"),
    )
    timenow = datetime.now(timezone.utc)
    assert task_schema["last_active_at"] is not None
    assert abs((datetime.fromisoformat(task_schema["last_active_at"]) - timenow).total_seconds()) < 0.2
    # Check groups
    groups = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/schemas/{task['task_schema_id']}/groups"),
    )
    assert len(groups["items"]) == 1

    assert groups["items"][0]["iteration"] == 1
    assert groups["items"][0]["last_active_at"] is not None
    assert abs((datetime.fromisoformat(groups["items"][0]["last_active_at"]) - timenow).total_seconds()) < 0.2

    list_tasks = result_or_raise(
        await int_api_client.get("/_/agents"),
    )
    assert len(list_tasks["items"]) == 1
    assert list_tasks["items"][0]["id"] == task["task_id"]
    assert list_tasks["items"][0]["versions"][0]["last_active_at"] is not None
    assert (
        abs((datetime.fromisoformat(list_tasks["items"][0]["versions"][0]["last_active_at"]) - timenow).total_seconds())
        < 0.2
    )

    task = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/{task['task_id']}"),
    )
    assert task["versions"][0]["last_active_at"] is not None
    assert abs((datetime.fromisoformat(task["versions"][0]["last_active_at"]) - timenow).total_seconds()) < 0.2


async def test_run_api_incorrect_default_source_active_run(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
):
    mock_openai_call(httpx_mock)

    task = await create_task(int_api_client, patched_broker, httpx_mock, name="greet")
    # No groups yet
    groups = await list_groups(int_api_client, task)
    assert len(groups) == 0, "sanity"
    group = await create_group(int_api_client, task, "gpt-4o-2024-11-20")

    task_run = await run_task_v1(
        int_api_client,
        task_id=task["task_id"],
        task_schema_id=task["task_schema_id"],
        task_input={"name": "James", "age": 31},
        model="gpt-4o-2024-11-20",
        version=group["iteration"],
        headers={"x-workflowai-source": "random"},
    )
    await wait_for_completed_tasks(patched_broker)

    fetched_task_run = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/runs/{task_run['id']}"),
    )

    groups = await list_groups(int_api_client, task)
    assert len(groups) == 1
    assert fetched_task_run["group"]["iteration"] == 1
    assert fetched_task_run.get("author_tenant") is None
    assert fetched_task_run["is_active"] is True

    await wait_for_completed_tasks(patched_broker)
    # Check task schema
    task_schema = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/schemas/{task['task_schema_id']}"),
    )
    timenow = datetime.now(timezone.utc)
    assert task_schema["last_active_at"] is not None
    assert abs((datetime.fromisoformat(task_schema["last_active_at"]) - timenow).total_seconds()) < 0.2
    # Check groups
    groups = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/schemas/{task['task_schema_id']}/groups"),
    )
    assert len(groups["items"]) == 1

    assert groups["items"][0]["iteration"] == 1
    assert groups["items"][0]["last_active_at"] is not None
    assert abs((datetime.fromisoformat(groups["items"][0]["last_active_at"]) - timenow).total_seconds()) < 0.2

    list_tasks = result_or_raise(
        await int_api_client.get("/_/agents"),
    )
    assert len(list_tasks["items"]) == 1
    assert list_tasks["items"][0]["id"] == task["task_id"]
    assert list_tasks["items"][0]["versions"][0]["last_active_at"] is not None
    assert (
        abs((datetime.fromisoformat(list_tasks["items"][0]["versions"][0]["last_active_at"]) - timenow).total_seconds())
        < 0.2
    )

    task = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/{task['task_id']}"),
    )
    assert task["versions"][0]["last_active_at"] is not None
    assert abs((datetime.fromisoformat(task["versions"][0]["last_active_at"]) - timenow).total_seconds()) < 0.2


async def test_run_web_source_non_active_run(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
):
    mock_openai_call(httpx_mock)
    task = await create_task(int_api_client, patched_broker, httpx_mock, name="greet")
    group = await create_group(int_api_client, task, "gpt-4o-2024-11-20")

    task_run = await run_task_v1(
        int_api_client,
        task_id=task["task_id"],
        task_schema_id=task["task_schema_id"],
        task_input={"name": "James", "age": 31},
        model="gpt-4o-2024-11-20",
        version=group["iteration"],
        headers={"x-workflowai-source": "web"},
    )
    await wait_for_completed_tasks(patched_broker)

    fetched_task_run = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/runs/{task_run['id']}"),
    )
    assert fetched_task_run["is_active"] is False

    await wait_for_completed_tasks(patched_broker)
    # Check task schema
    task_schema = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/schemas/{task['task_schema_id']}"),
    )
    assert task_schema["last_active_at"] is None
    # Check groups
    groups = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/schemas/{task['task_schema_id']}/groups"),
    )
    assert len(groups["items"]) == 1

    assert groups["items"][0]["iteration"] == 1
    assert not groups["items"][0].get("last_active_at")


async def test_run_sdk_source_active_run(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
):
    mock_openai_call(httpx_mock)
    task = await create_task(int_api_client, patched_broker, httpx_mock, name="greet")
    # No groups yet
    groups = await list_groups(int_api_client, task)
    assert len(groups) == 0, "sanity"
    group = await create_group(int_api_client, task, "gpt-4o-2024-11-20")

    task_run = await run_task_v1(
        int_api_client,
        task_id=task["task_id"],
        task_schema_id=task["task_schema_id"],
        task_input={"name": "James", "age": 31},
        model="gpt-4o-2024-11-20",
        version=group["iteration"],
        headers={"x-workflowai-source": "sdk"},
    )
    await wait_for_completed_tasks(patched_broker)

    fetched_task_run = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/runs/{task_run['id']}"),
    )
    assert fetched_task_run["group"]["iteration"] == 1
    assert fetched_task_run.get("author_tenant") is None
    assert fetched_task_run["is_active"] is True

    await wait_for_completed_tasks(patched_broker)
    # Check task schema
    task_schema = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/schemas/{task['task_schema_id']}"),
    )
    timenow = datetime.now(timezone.utc)
    assert task_schema["last_active_at"] is not None
    assert abs((datetime.fromisoformat(task_schema["last_active_at"]) - timenow).total_seconds()) < 0.2
    # Check groups
    groups = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/schemas/{task['task_schema_id']}/groups"),
    )
    assert len(groups["items"]) == 1

    assert groups["items"][0]["iteration"] == 1
    assert groups["items"][0]["last_active_at"] is not None
    assert abs((datetime.fromisoformat(groups["items"][0]["last_active_at"]) - timenow).total_seconds()) < 0.2


async def test_run_combined_source_last_active_at_test(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
):
    mock_openai_call(httpx_mock, is_reusable=True)
    task = await create_task(int_api_client, patched_broker, httpx_mock, name="greet")
    # No groups yet
    groups = await list_groups(int_api_client, task)
    assert len(groups) == 0, "sanity"
    group = await create_group(int_api_client, task, "gpt-4o-2024-11-20")

    task_run = await run_task_v1(
        int_api_client,
        task_id=task["task_id"],
        task_schema_id=task["task_schema_id"],
        task_input={"name": "James", "age": 31},
        model="gpt-4o-2024-11-20",
        version=group["iteration"],
        headers={"x-workflowai-source": "sdk"},
    )
    await wait_for_completed_tasks(patched_broker)

    fetched_task_run = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/runs/{task_run['id']}"),
    )
    assert fetched_task_run["group"]["iteration"] == 1
    assert fetched_task_run.get("author_tenant") is None
    assert fetched_task_run["is_active"] is True

    await wait_for_completed_tasks(patched_broker)
    # Check task schema
    task_schema = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/schemas/{task['task_schema_id']}"),
    )
    timefirst = datetime.now(timezone.utc)
    assert task_schema["last_active_at"] is not None
    assert abs((datetime.fromisoformat(task_schema["last_active_at"]) - timefirst).total_seconds()) < 0.2
    # Check groups
    groups = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/schemas/{task['task_schema_id']}/groups"),
    )
    assert len(groups["items"]) == 1

    assert groups["items"][0]["iteration"] == 1
    assert groups["items"][0]["last_active_at"] is not None
    assert abs((datetime.fromisoformat(groups["items"][0]["last_active_at"]) - timefirst).total_seconds()) < 0.2

    await asyncio.sleep(1)

    # TODO: Cached run does not update last_active_at/is_active status of the run. First run's details is preserved.
    task_run_pseudo = await run_task_v1(
        int_api_client,
        task_id=task["task_id"],
        task_schema_id=task["task_schema_id"],
        task_input={"name": "James", "age": 31},
        model="gpt-4o-2024-11-20",
        version=group["iteration"],
        headers={"x-workflowai-source": "web"},
    )
    await wait_for_completed_tasks(patched_broker)

    fetched_task_run = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/runs/{task_run_pseudo['id']}"),
    )
    assert fetched_task_run["group"]["iteration"] == 1
    assert fetched_task_run.get("author_tenant") is None
    assert fetched_task_run["is_active"] is True
    assert task_run_pseudo["id"] == task_run["id"]

    # Check that the last_active_at is the first run's time, as source is now WEB.
    task_run2 = await run_task_v1(
        int_api_client,
        task_id=task["task_id"],
        task_schema_id=task["task_schema_id"],
        task_input={"name": "James", "age": 30},  # trigger new run.
        model="gpt-4o-2024-11-20",
        version=group["iteration"],
        headers={"x-workflowai-source": "web"},
    )
    await wait_for_completed_tasks(patched_broker)

    fetched_task_run2 = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/runs/{task_run2['id']}"),
    )
    assert fetched_task_run2["is_active"] is False

    task_schema = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/schemas/{task['task_schema_id']}"),
    )
    assert task_schema["last_active_at"] is not None
    assert abs((datetime.fromisoformat(task_schema["last_active_at"]) - timefirst).total_seconds()) < 0.2
    groups = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/schemas/{task['task_schema_id']}/groups"),
    )
    assert len(groups["items"]) == 1

    assert groups["items"][0]["iteration"] == 1
    assert groups["items"][0]["last_active_at"] is not None
    assert abs((datetime.fromisoformat(groups["items"][0]["last_active_at"]) - timefirst).total_seconds()) < 0.2

    await asyncio.sleep(1)

    # Check that the last_active_at is the last run's time as source is now API.

    task_run3 = await run_task_v1(
        int_api_client,
        task_id=task["task_id"],
        task_schema_id=task["task_schema_id"],
        task_input={"name": "James", "age": 28},  # trigger new run.
        model="gpt-4o-2024-11-20",
        version=group["iteration"],
        headers={"x-workflowai-source": "api"},
    )
    await wait_for_completed_tasks(patched_broker)

    fetched_task_run3 = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/runs/{task_run3['id']}"),
    )
    assert fetched_task_run3["is_active"] is True

    task_schema = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/schemas/{task['task_schema_id']}"),
    )
    timefinal = datetime.now(timezone.utc)
    assert task_schema["last_active_at"] is not None
    assert abs((datetime.fromisoformat(task_schema["last_active_at"]) - timefinal).total_seconds()) < 0.2

    groups = result_or_raise(
        await int_api_client.get(f"/chiefofstaff.ai/agents/greet/schemas/{task['task_schema_id']}/groups"),
    )
    assert len(groups["items"]) == 1

    assert groups["items"][0]["iteration"] == 1
    assert groups["items"][0]["last_active_at"] is not None
    assert abs((datetime.fromisoformat(groups["items"][0]["last_active_at"]) - timefinal).total_seconds()) < 0.2
