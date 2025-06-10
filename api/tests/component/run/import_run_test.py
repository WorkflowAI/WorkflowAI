from typing import Any

from httpx import AsyncClient
from pytest_httpx import HTTPXMock
from taskiq import InMemoryBroker

from tests.component.common import create_organization_via_clerk, create_task, result_or_raise


async def test_new_org_credits(
    int_api_client: AsyncClient,
    patched_broker: InMemoryBroker,
    httpx_mock: HTTPXMock,
):
    await create_organization_via_clerk(int_api_client, httpx_mock, patched_broker)

    org = result_or_raise(await int_api_client.get("/test-21/organization/settings"))
    assert org["added_credits_usd"] == 5
    assert org["current_credits_usd"] == 5


async def test_import_run_with_metadata_and_labels(
    int_api_client: AsyncClient,
    patched_broker: InMemoryBroker,
    httpx_mock: HTTPXMock,
):
    await create_task(int_api_client, patched_broker, httpx_mock)

    org = result_or_raise(await int_api_client.get("/_/organization/settings"))
    assert org["added_credits_usd"] == 10.0
    assert org["current_credits_usd"] == 10.0

    payload: dict[str, Any] = {
        "group": {"properties": {"model": "not-our-model"}},
        "task_input": {"name": "John", "age": 30},
        "task_output": {"greeting": "Hello John!"},
        "metadata": {
            "key1": "value1",
        },
        "cost_usd": 1.0,
    }

    created = result_or_raise(await int_api_client.post("/chiefofstaff.ai/agents/greet/schemas/1/runs", json=payload))
    assert created["metadata"] == {"key1": "value1"}
    assert created["cost_usd"] == 1.0

    # Credits should not have been decremented
    org = result_or_raise(await int_api_client.get("/_/organization/settings"))
    assert org["added_credits_usd"] == 10.0
    assert org["current_credits_usd"] == 10.0
