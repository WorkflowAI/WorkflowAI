from datetime import datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from pytest_httpx import HTTPXMock
from taskiq import InMemoryBroker

from core.storage.clickhouse.models.runs import ClickhouseRun
from core.storage.mongo.mongo_storage import MongoStorage
from tests.component.common import (
    create_task,
    result_or_raise,
)
from tests.utils import fixtures_json


async def setup_stats_task(
    int_api_client: AsyncClient,
    patched_broker: InMemoryBroker,
    httpx_mock: HTTPXMock,
):
    return await create_task(
        int_api_client,
        patched_broker,
        httpx_mock,
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "email": {"type": "string"},
            },
            "required": ["name", "age"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "greeting": {"type": "string"},
                "category": {"type": "string"},
            },
            "required": ["greeting", "category"],
        },
    )


@pytest.fixture(scope="function")
async def stats_task_with_runs(
    int_api_client: AsyncClient,
    patched_broker: InMemoryBroker,
    httpx_mock: HTTPXMock,
    integration_storage: MongoStorage,
    int_clickhouse_client: Any,
) -> dict[str, Any]:
    task = await setup_stats_task(int_api_client, patched_broker, httpx_mock)
    org = result_or_raise(await int_api_client.get("/_/organization/settings"))

    active_runs = fixtures_json("db/runs_for_stats.json")
    runs = [ClickhouseRun.model_validate(r) for r in active_runs]
    for r in runs:
        r.tenant_uid = org["uid"]
        r.task_uid = task["task_uid"]
    await int_clickhouse_client.insert_models("runs", runs, {"async_insert": 0, "wait_for_async_insert": 1})

    return task


async def perform_stats_query(
    int_api_client: AsyncClient,
    task_id: str,
    date: str,
    is_active: bool | None,
) -> dict[str, Any]:
    request_body: dict[str, Any] = {
        "created_after": datetime.strftime(
            datetime.fromisoformat(date),
            "%Y-%m-%d",
        ),
        "created_before": datetime.strftime(
            datetime.fromisoformat(date) + timedelta(days=1),
            "%Y-%m-%d",
        ),
    }
    if is_active is not None:
        request_body["is_active"] = is_active
    response = await int_api_client.get(
        f"/_/agents/{task_id}/runs/stats",
        params=request_body,
    )
    return response.json()


@pytest.mark.parametrize(
    ("date", "is_active", "expected_count", "expected_list_count", "expected_cost"),
    [
        ("2024-10-28", True, 1, 1, 0.055),
        ("2024-10-28", False, 1, 1, 0.005),
        ("2024-10-28", None, 2, 1, 0.06),
        ("2024-10-26", True, 1, 1, 0.065),
        ("2024-10-26", False, 1, 1, 0.001),
    ],
)
async def test_stats_with_queries_counts(
    int_api_client: AsyncClient,
    stats_task_with_runs: dict[str, Any],
    date: str,
    is_active: bool | None,
    expected_count: int,
    expected_list_count: int,
    expected_cost: float,
) -> None:
    """
    Unified test for searching runs with different field queries.
    Tests status, metadata, model, price, and temperature queries in a single parameterized test.
    """
    result = await perform_stats_query(
        int_api_client,
        stats_task_with_runs["task_id"],
        date,
        is_active,
    )
    assert result["data"]
    assert len(result["data"]) == expected_list_count
    if expected_list_count > 0:
        assert result["data"][0]["total_count"] == expected_count
        assert result["data"][0]["total_cost_usd"] == expected_cost
