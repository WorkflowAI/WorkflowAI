from typing import Any

import pytest
from httpx import AsyncClient
from pytest_httpx import HTTPXMock
from taskiq import InMemoryBroker

from tests.component.common import (
    IntegrationTestClient,
    create_task,
    create_version,
    result_or_raise,
    task_url_v1,
    wait_for_completed_tasks,
)


async def test_deploy_version_not_found(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
):
    task = await create_task(int_api_client, patched_broker, httpx_mock)
    res = await int_api_client.post(
        f"/chiefofstaff.ai/agents/{task['task_id']}/schemas/{task['task_schema_id']}/versions/1/deploy",
        json={"environment": "production", "provider_config_id": "config1"},
    )
    assert res.status_code == 404


# TODO: remove annotation, failure is due to internal agents being called
@pytest.mark.httpx_mock(assert_all_requests_were_expected=False)
async def test_deploy_one_version_one_environment(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
):
    task = await create_task(int_api_client, patched_broker, httpx_mock)
    assert task["task_id"] == "greet"
    assert task["task_schema_id"] == 1

    version = await create_version(
        int_api_client,
        task_id="greet",
        task_schema_id=1,
        version_properties={"instructions": "some instructions", "model": "gemini-1.5-pro-002"},
    )
    assert version["iteration"] == 1
    res = await int_api_client.post(
        "/chiefofstaff.ai/agents/greet/schemas/1/versions/1/deploy",
        json={
            "environment": "production",
        },
    )
    assert res.status_code == 200
    deployment = res.json()

    assert deployment["version_id"] == 1
    assert deployment["task_schema_id"] == task["task_schema_id"]
    assert deployment["environment"] == "production"
    assert "deployed_at" in deployment

    await wait_for_completed_tasks(patched_broker)


# TODO: remove annotation, failure is due to internal agents being called
@pytest.mark.httpx_mock(assert_all_requests_were_expected=False)
async def test_deploy_version(test_client: IntegrationTestClient):
    """Test that a version can be deployed to multiple environments and that we
    can deploy another version to override an existing deployment"""
    task = await test_client.create_task()

    # Create a version and deploy it
    version = await test_client.create_version(
        task,
        version_properties={"instructions": "some instructions", "model": "gemini-1.5-pro-002"},
        save=True,
    )
    for environment in ["dev", "staging", "production"]:
        deployment = await test_client.post(
            task_url_v1(task, f"versions/{version['id']}/deploy"),
            json={
                "environment": environment,
            },
        )
        assert deployment["environment"] == environment

    await test_client.wait_for_completed_tasks()

    res = (await test_client.get(task_url_v1(task, "versions")))["items"]
    assert len(res) == 1
    assert len(res[0]["minors"]) == 1
    assert res[0]["minors"][0]["deployments"]
    assert {d["environment"] for d in res[0]["minors"][0]["deployments"]} == {"dev", "staging", "production"}

    # Now create another, because the instructions are different it will create a new major version
    version2 = await test_client.create_version(
        task,
        version_properties={"instructions": "some instructions 1", "model": "gemini-1.5-pro-001"},
        save=True,
    )
    deployment = await test_client.post(
        task_url_v1(task, f"versions/{version2['id']}/deploy"),
        json={
            "environment": "dev",
        },
    )
    res: list[dict[str, Any]] = (await test_client.get(task_url_v1(task, "versions")))["items"]
    res.sort(key=lambda x: x["major"])
    assert len(res) == 2
    assert res[0]["major"] == 1
    assert res[1]["major"] == 2

    assert len(res[0]["minors"]) == 1
    assert res[0]["minors"][0]["deployments"]
    assert {d["environment"] for d in res[0]["minors"][0]["deployments"]} == {"staging", "production"}

    assert len(res[1]["minors"]) == 1
    assert res[1]["minors"][0]["deployments"]
    assert {d["environment"] for d in res[1]["minors"][0]["deployments"]} == {"dev"}


async def test_deploy_version_invalid_environment(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
):
    task = await create_task(int_api_client, patched_broker, httpx_mock)

    res = await int_api_client.post(
        f"/chiefofstaff.ai/agents/{task['task_id']}/schemas/{task['task_schema_id']}/versions/1/deploy",
        json={
            "environment": "invalid",
            "provider_config_id": "config1",
        },
    )
    assert res.status_code == 422  # Validation error


# TODO[versionv1]: ok to remove once we remove the old endpoint, duplicate of test_deploy_version
@pytest.mark.httpx_mock(assert_all_requests_were_expected=False)
async def test_deploy_to_multiple_environments(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
):
    task = await create_task(int_api_client, patched_broker, httpx_mock)
    version = await create_version(
        int_api_client,
        task_id=task["task_id"],
        task_schema_id=task["task_schema_id"],
        version_properties={"instructions": "some instructions", "model": "gemini-1.5-pro-002"},
    )
    res = await int_api_client.post(
        f"/chiefofstaff.ai/agents/{task['task_id']}/schemas/{task['task_schema_id']}/versions/{version['iteration']}/deploy",
        json={"environment": "dev"},
    )
    deployment = result_or_raise(res)
    assert deployment["environment"] == "dev"

    res = await int_api_client.post(
        f"/chiefofstaff.ai/agents/{task['task_id']}/schemas/{task['task_schema_id']}/versions/{version['iteration']}/deploy",
        json={"environment": "staging"},
    )
    deployment = result_or_raise(res)
    assert deployment["environment"] == "staging"

    await wait_for_completed_tasks(patched_broker)

    res = await int_api_client.get(
        f"/chiefofstaff.ai/agents/{task['task_id']}/versions/deployed",
    )
    deployments = result_or_raise(res)
    assert len(deployments["items"]) == 1
    assert len(deployments["items"][0]["deployments"]) == 2
    assert deployments["items"][0]["deployments"][1]["environment"] == "dev"
    assert deployments["items"][0]["deployments"][0]["environment"] == "staging"


# TODO[versionv1]: ok to remove once we remove the old endpoint, duplicate of test_deploy_version
@pytest.mark.httpx_mock(assert_all_requests_were_expected=False)
async def test_deploy_multiple_versions_one_environment_one_schema(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
):
    task = await create_task(int_api_client, patched_broker, httpx_mock)
    version1 = await create_version(
        int_api_client,
        task_id=task["task_id"],
        task_schema_id=task["task_schema_id"],
        version_properties={"instructions": "some instructions", "model": "gemini-1.5-pro-002"},
    )
    version2 = await create_version(
        int_api_client,
        task_id=task["task_id"],
        task_schema_id=task["task_schema_id"],
        version_properties={"instructions": "some instructions 1", "model": "gemini-1.5-pro-001"},
    )

    res = await int_api_client.post(
        f"/chiefofstaff.ai/agents/{task['task_id']}/schemas/{task['task_schema_id']}/versions/{version1['iteration']}/deploy",
        json={"environment": "dev", "provider_config_id": "config1"},
    )
    deployment1 = result_or_raise(res)
    assert deployment1["environment"] == "dev"

    res = await int_api_client.post(
        f"/chiefofstaff.ai/agents/{task['task_id']}/schemas/{task['task_schema_id']}/versions/{version2['iteration']}/deploy",
        json={"environment": "dev"},
    )
    deployment2 = result_or_raise(res)
    assert deployment2["environment"] == "dev"

    await wait_for_completed_tasks(patched_broker)

    res = await int_api_client.get(
        f"/chiefofstaff.ai/agents/{task['task_id']}/versions/deployed",
    )
    deployments = result_or_raise(res)
    assert len(deployments["items"]) == 1
    assert len(deployments["items"][0]["deployments"]) == 1
    assert deployments["items"][0]["deployments"][0]["environment"] == "dev"
    assert deployments["items"][0]["iteration"] == version2["iteration"]


# TODO[versionv1]: add a test when deploying multiple versions from multiple schemas
