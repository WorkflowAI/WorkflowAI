import asyncio
import datetime
import os
import time
from collections.abc import Collection
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import bson
import pytest

from core.domain.agent_run import AgentRun
from core.domain.error_response import ErrorResponse
from core.domain.fields.internal_reasoning_steps import InternalReasoningStep
from core.domain.llm_completion import LLMCompletion
from core.domain.llm_usage import LLMUsage
from core.domain.models import Provider
from core.domain.search_query import (
    SearchField,
    SearchOperation,
    SearchOperationSingle,
    SearchOperator,
    SearchQuery,
    SearchQueryNested,
    SearchQuerySimple,
    SingleValueOperator,
)
from core.domain.task_run_aggregate_per_day import TaskRunAggregatePerDay
from core.domain.task_run_query import SerializableTaskRunQuery
from core.domain.tool_call import ToolCall, ToolCallRequestWithID
from core.storage.clickhouse.clickhouse_client import (
    ClickhouseClient,
)
from core.storage.clickhouse.models.runs import ClickhouseRun
from core.storage.mongo.models.task_run_document import TaskRunDocument
from core.storage.task_run_storage import RunAggregate, WeeklyRunAggregate
from core.utils.fields import datetime_factory, datetime_zero
from core.utils.schemas import FieldType
from core.utils.uuid import uuid7
from tests.models import task_group, task_run_ser
from tests.utils import fixture_bytes, fixtures_json


def read_sql_commands() -> list[str]:
    setup_sql_commands = (Path(__file__).parent / "migrations/m2025_02_10_init.sql").read_text().splitlines()
    lines_per_command: list[list[str]] = [[]]
    # Remove all lines that start with --
    for line in setup_sql_commands:
        line = line.strip()
        if not line or line.startswith("--"):
            continue
        lines_per_command[-1].append(line)
        if line.endswith(";"):
            lines_per_command.append([])

    return ["\n".join(lines) for lines in lines_per_command if lines]


async def fresh_clickhouse_client(dsn: str | None = None):
    from clickhouse_connect.driver.exceptions import DatabaseError

    if not dsn:
        dsn = os.getenv("CLICKHOUSE_TEST_CONNECTION_STRING", "clickhouse://default:admin@localhost:8123/db_test")

    if "localhost" not in dsn:
        raise ValueError("Only local testing is supported")
    client = ClickhouseClient(dsn, tenant_uid=1)

    db_name = urlparse(dsn).path.lstrip("/")

    try:
        await client.command("DROP TABLE IF EXISTS runs;")
    except DatabaseError as e:
        if f"Database {db_name} does not exist" not in str(e):
            raise e

        from clickhouse_connect.driver import create_async_client  # pyright: ignore[reportUnknownVariableType]

        raw_clt = await create_async_client(dsn=dsn.rstrip(f"/{db_name}"))
        await raw_clt.command(f"CREATE DATABASE {db_name};")  # pyright: ignore[reportUnknownMemberType]

    setup_commands = read_sql_commands()
    # Skipping settings for default user since it breaks in local dev

    assert setup_commands[0].startswith("CREATE TABLE runs"), "sanity check"
    await client.command(setup_commands[0])

    assert setup_commands[1].startswith(
        "ALTER TABLE runs ADD INDEX cache_hash_index cache_hash TYPE bloom_filter(0.01);",
    ), "sanity check"
    await client.command(setup_commands[1])

    for cmd in setup_commands[2:]:
        await client.command(cmd)

    return client


@pytest.fixture(scope="module")
async def clickhouse_client():
    return await fresh_clickhouse_client()


@pytest.fixture(scope="function", autouse=True)
async def truncate_run_table(clickhouse_client: ClickhouseClient):
    await clickhouse_client.command("TRUNCATE TABLE runs;")


def _uuid7(v: int):
    return uuid7(ms=lambda: v, rand=lambda: 0)


_TASK_TUPLE = ("task_1", 1)


async def test_insert_and_fetch_run(clickhouse_client: ClickhouseClient):
    run = task_run_ser(
        id=str(uuid7()),
        cost_usd=11,
        duration_seconds=12,
        task_uid=1,
        reasoning_steps=[InternalReasoningStep(title="test", explaination="test")],
        tool_calls=[ToolCall(id="test", tool_name="1", tool_input_dict={"test": "test"}, result="bla")],
        tool_call_requests=[ToolCallRequestWithID(id="test", tool_name="1", tool_input_dict={"test": "test"})],
        llm_completions=[
            LLMCompletion(
                messages=[{"bla": "bla"}],
                usage=LLMUsage(prompt_token_count=1, completion_token_count=1),
                provider=Provider.OPEN_AI,
            ),
        ],
    )

    await clickhouse_client.store_task_run(run, settings={"async_insert": 1, "wait_for_async_insert": 1})

    await asyncio.sleep(0.2)

    fetched_run = await clickhouse_client.fetch_task_run_resource(_TASK_TUPLE, run.id)
    assert fetched_run is not None
    assert fetched_run.id == run.id
    assert fetched_run.cost_usd == 11
    assert fetched_run.duration_seconds == 12
    assert fetched_run.reasoning_steps == run.reasoning_steps
    assert fetched_run.tool_calls == run.tool_calls
    assert fetched_run.tool_call_requests == run.tool_call_requests
    assert fetched_run.llm_completions == run.llm_completions


class TestStoreTaskRun:
    async def test_store_task_run(self, clickhouse_client: ClickhouseClient):
        # actual_run_stored in out database
        raw = bson.json_util.loads(fixture_bytes("runs/run_doc_1.json"))  # type: ignore
        run = TaskRunDocument.model_validate(raw).to_resource()
        run.task_uid = 1

        # Check that we don't throw
        await clickhouse_client.store_task_run(run)

    async def test_store_task_run_negative_overhead(self, clickhouse_client: ClickhouseClient):
        run = task_run_ser(
            id=str(uuid7()),
            overhead_seconds=-1,
        )
        # Overhead will be coherced to when storing
        await clickhouse_client.store_task_run(run)


class TestSearchTaskRun:
    @classmethod
    async def _insert_runs(cls, clickhouse_client: ClickhouseClient, *args: AgentRun):
        docs = [ClickhouseRun.from_domain(1, r) for r in args]
        for i, doc in enumerate(docs):
            doc.run_uuid = _uuid7(i + 1)
            if not doc.task_uid:
                doc.task_uid = 1

        await clickhouse_client.insert_models("runs", docs, {"async_insert": 0, "wait_for_async_insert": 0})
        return docs

    @classmethod
    async def _search(cls, clickhouse_client: ClickhouseClient, query: list[SearchQuery], task_uid: int = 1):
        return sorted(
            [r.id async for r in clickhouse_client.search_task_runs(("", task_uid), query, limit=100, offset=0)],
        )

    async def test_search(self, clickhouse_client: ClickhouseClient):
        await self._insert_runs(
            clickhouse_client,
            task_run_ser(),
            task_run_ser(task_uid=2),
        )

        r = await self._search(clickhouse_client, [])
        assert r == [str(_uuid7(1))]

        r = await self._search(clickhouse_client, [], task_uid=2)
        assert r == [str(_uuid7(2))]

    async def test_unique_by_conversation(self, clickhouse_client: ClickhouseClient):
        await self._insert_runs(
            clickhouse_client,
            task_run_ser(conversation_id=str(_uuid7(2))),
            task_run_ser(conversation_id=str(_uuid7(3))),
            task_run_ser(conversation_id=str(_uuid7(3))),
            task_run_ser(conversation_id=str(_uuid7(4))),
            task_run_ser(conversation_id=str(_uuid7(1))),
            task_run_ser(conversation_id=str(_uuid7(1))),
        )
        r = await self._search(clickhouse_client, [])
        assert r == [str(_uuid7(1)), str(_uuid7(3)), str(_uuid7(4)), str(_uuid7(6))]

    async def test_count(self, clickhouse_client: ClickhouseClient):
        await self._insert_runs(
            clickhouse_client,
            task_run_ser(),
            task_run_ser(task_uid=2),
        )

        r = await clickhouse_client.count_filtered_task_runs(("", 1), [])
        assert r == 1

        r = await clickhouse_client.count_filtered_task_runs(("", 1), [])
        assert r == 1

    @pytest.mark.parametrize(
        ("eval_hash", "expected"),
        [
            (["f0f1553134f423df626e2d797fdd005e"], [1]),
            ({"f0f1553134f423df626e2d797fdd005e"}, [1]),  # with a set
            (["f0f1553134f423df626e2d797fdd005e", "0732e90b9bb0301d4bec56ef79b5d659"], [1, 2]),  # 2 values
        ],
    )
    async def test_search_reviews(
        self,
        clickhouse_client: ClickhouseClient,
        eval_hash: Collection[str],
        expected: list[int],
    ):
        await self._insert_runs(
            clickhouse_client,
            task_run_ser(),
            task_run_ser(task_input_hash="123"),
        )

        r = await self._search(
            clickhouse_client,
            [
                SearchQuerySimple(SearchField.EVAL_HASH, operation=SearchOperationSingle(SearchOperator.IS, eval_hash)),
            ],
        )
        assert r == [str(_uuid7(i)) for i in expected]

    @pytest.mark.parametrize(
        ("schema_id", "operator", "expected"),
        [
            (1, SearchOperator.IS, [1]),
            (2, SearchOperator.IS_NOT, [1, 3]),
            (2, SearchOperator.LESS_THAN, [1]),
            (2, SearchOperator.GREATER_THAN, [3]),
        ],
    )
    async def test_search_schema_id(
        self,
        clickhouse_client: ClickhouseClient,
        schema_id: int,
        operator: SingleValueOperator,
        expected: list[int],
    ):
        await self._insert_runs(
            clickhouse_client,
            task_run_ser(task_schema_id=1),
            task_run_ser(task_schema_id=2),
            task_run_ser(task_schema_id=3),
        )

        r = await self._search(
            clickhouse_client,
            [SearchQuerySimple(SearchField.SCHEMA_ID, operation=SearchOperationSingle(operator, schema_id))],
        )
        assert r == [str(_uuid7(i)) for i in expected]

    @pytest.mark.parametrize(
        ("version", "operator", "expected"),
        [
            ("abcde", SearchOperator.IS, [1]),
            ("abcdef", SearchOperator.IS_NOT, [1]),
        ],
    )
    async def test_search_version(
        self,
        clickhouse_client: ClickhouseClient,
        version: str,
        operator: SingleValueOperator,
        expected: list[int],
    ):
        await self._insert_runs(
            clickhouse_client,
            task_run_ser(group_kwargs={"id": "abcde"}),
            task_run_ser(group_kwargs={"id": "abcdef"}),
        )

        r = await self._search(
            clickhouse_client,
            [SearchQuerySimple(SearchField.VERSION, operation=SearchOperationSingle(operator, version))],
        )
        assert r == [str(_uuid7(i)) for i in expected]

    @pytest.mark.parametrize(
        ("price", "operator", "expected"),
        [
            (10, SearchOperator.IS, [2]),
            (10, SearchOperator.LESS_THAN, [1]),
            (10, SearchOperator.GREATER_THAN, [3]),
            (10, SearchOperator.GREATER_THAN_OR_EQUAL_TO, [2, 3]),
        ],
    )
    async def test_search_price(
        self,
        clickhouse_client: ClickhouseClient,
        price: int,
        operator: SingleValueOperator,
        expected: list[int],
    ):
        await self._insert_runs(
            clickhouse_client,
            task_run_ser(cost_usd=5),
            task_run_ser(cost_usd=10),
            task_run_ser(cost_usd=20),
        )

        r = await self._search(
            clickhouse_client,
            [SearchQuerySimple(SearchField.PRICE, operation=SearchOperationSingle(operator, price))],
        )
        assert r == [str(_uuid7(i)) for i in expected]

    @pytest.mark.parametrize(
        ("latency", "operator", "expected"),
        [
            (10, SearchOperator.IS, [2]),
            (10, SearchOperator.LESS_THAN, [1]),
            (10, SearchOperator.GREATER_THAN, [3]),
        ],
    )
    async def test_search_latency(
        self,
        clickhouse_client: ClickhouseClient,
        latency: int,
        operator: SingleValueOperator,
        expected: list[int],
    ):
        await self._insert_runs(
            clickhouse_client,
            task_run_ser(duration_seconds=5),
            task_run_ser(duration_seconds=10),
            task_run_ser(duration_seconds=20),
        )

        r = await self._search(
            clickhouse_client,
            [SearchQuerySimple(SearchField.LATENCY, operation=SearchOperationSingle(operator, latency))],
        )
        assert r == [str(_uuid7(i)) for i in expected]

    @pytest.mark.parametrize(
        ("temperature", "operator", "expected"),
        [
            (0.5, SearchOperator.IS, [1]),
            (0.5, SearchOperator.LESS_THAN, [2]),
            (0.5, SearchOperator.GREATER_THAN, [3]),
        ],
    )
    async def test_search_temperature(
        self,
        clickhouse_client: ClickhouseClient,
        temperature: float,
        operator: SingleValueOperator,
        expected: list[int],
    ):
        await self._insert_runs(
            clickhouse_client,
            task_run_ser(group=task_group(properties={"temperature": 0.5})),
            task_run_ser(group=task_group(properties={"temperature": 0.2})),
            task_run_ser(group=task_group(properties={"temperature": 0.8})),
        )

        r = await self._search(
            clickhouse_client,
            [SearchQuerySimple(SearchField.TEMPERATURE, operation=SearchOperationSingle(operator, temperature))],
        )
        assert r == [str(_uuid7(i)) for i in expected]

    @pytest.mark.parametrize(
        ("model", "operator", "expected"),
        [
            ("o1-mini-2024-09-12", SearchOperator.IS, [1]),
            ("o1-mini-2024-09-12", SearchOperator.IS_NOT, [2]),
            ("o1-mini", SearchOperator.CONTAINS, [1, 2]),
            ("13", SearchOperator.NOT_CONTAINS, [1]),
        ],
    )
    async def test_search_model(
        self,
        clickhouse_client: ClickhouseClient,
        model: str,
        operator: SingleValueOperator,
        expected: list[int],
    ):
        await self._insert_runs(
            clickhouse_client,
            task_run_ser(group=task_group(properties={"model": "o1-mini-2024-09-12"})),
            task_run_ser(group=task_group(properties={"model": "o1-mini-2024-09-13"})),
        )

        r = await self._search(
            clickhouse_client,
            [SearchQuerySimple(SearchField.MODEL, operation=SearchOperationSingle(operator, model))],
        )
        assert r == [str(_uuid7(i)) for i in expected]

    @pytest.mark.parametrize(
        ("key", "value", "field_type", "operator", "expected"),
        [
            ("name", "test", "string", SearchOperator.IS, [1]),
            ("name", "test", "string", SearchOperator.IS_NOT, [2, 3, 4]),
            ("name", "T", "string", SearchOperator.CONTAINS, [1, 2]),
            ("name", None, "string", SearchOperator.IS_EMPTY, [3, 4]),
            ("values", 2, "array_length", SearchOperator.IS, [3]),
            ("values", 1, "array_length", SearchOperator.GREATER_THAN, [3, 4]),
            ("values[]", 3, "integer", SearchOperator.IS, [4]),
            ("values[]", 2, "integer", SearchOperator.GREATER_THAN_OR_EQUAL_TO, [3, 4]),
            ("array[].a", "a1", "string", SearchOperator.IS, [1]),
            ("array[].a", "a2", "string", SearchOperator.IS, [1]),
        ],
    )
    async def test_search_input(
        self,
        clickhouse_client: ClickhouseClient,
        key: str,
        value: str,
        field_type: FieldType,
        operator: SingleValueOperator,
        expected: list[int],
    ):
        await self._insert_runs(
            clickhouse_client,
            task_run_ser(task_input={"name": "test", "array": [{"a": "a1"}, {"a": "a2"}]}),
            task_run_ser(task_input={"name": "test1"}),
            task_run_ser(task_input={"values": [1, 2], "nested": {"a": "b"}}),
            task_run_ser(task_input={"values": [1, 2, 3]}),
        )

        r = await self._search(
            clickhouse_client,
            [
                SearchQueryNested(
                    SearchField.INPUT,
                    operation=SearchOperationSingle(operator, value),
                    key_path=key,
                    field_type=field_type,
                ),
            ],
        )
        assert r == [str(_uuid7(i)) for i in expected]

    @pytest.mark.parametrize(
        ("status", "operator", "expected"),
        [
            ("success", SearchOperator.IS, [1]),
            ("failure", SearchOperator.IS, [2]),
        ],
    )
    async def test_search_status(
        self,
        clickhouse_client: ClickhouseClient,
        status: str,
        operator: SingleValueOperator,
        expected: list[int],
    ):
        await self._insert_runs(
            clickhouse_client,
            task_run_ser(status="success"),
            task_run_ser(status="failure", error={"message": "test", "code": "test", "status_code": 500}),
        )

        r = await self._search(
            clickhouse_client,
            [SearchQuerySimple(SearchField.STATUS, operation=SearchOperationSingle(SearchOperator.IS, "success"))],
        )
        assert r == [str(_uuid7(1))]

    @pytest.mark.parametrize(
        ("dangerous_key",),
        [
            ("key'; DROP TABLE runs; --",),
            ("user'; DELETE FROM runs WHERE 1=1; --",),
            ("test'; UPDATE runs SET metadata='{}'; --",),
            ("normal_key'; SELECT * FROM runs; --",),
        ],
    )
    async def test_search_metadata_sql_injection_protection(
        self,
        clickhouse_client: ClickhouseClient,
        dangerous_key: str,
    ):
        """Test that SQL injection attempts in metadata keys are properly escaped."""
        # Test that our SQL injection protection works by directly inserting runs with dangerous metadata keys
        # and verifying the table isn't compromised

        inserted_runs: list[ClickhouseRun] = []

        # Create a run with dangerous metadata key
        run = task_run_ser(
            task_uid=1,
            metadata={dangerous_key: "safe_value"},
        )

        # Convert to ClickhouseRun and insert directly
        ch_run = ClickhouseRun.from_domain(1, run)
        ch_run.run_uuid = _uuid7(1)
        ch_run.created_at_date = datetime_zero()
        inserted_runs.append(ch_run)

        # Insert the runs with dangerous metadata keys
        await clickhouse_client.insert_models("runs", inserted_runs, {"async_insert": 0, "wait_for_async_insert": 0})

        # Check insertion is OK
        assert await clickhouse_client.count_filtered_task_runs(("", 1), []) == 1

        # Check search is OK

        # Verify we can still query the runs table normally
        all_runs = await self._search(
            clickhouse_client,
            [
                SearchQueryNested(
                    SearchField.METADATA,
                    operation=SearchOperationSingle(SearchOperator.IS, "safe_value"),
                    key_path=dangerous_key,
                    field_type="string",
                ),
            ],
        )
        assert len(all_runs) == 1
        # Retrieving the run should be OK
        fetched_run = await clickhouse_client.fetch_task_run_resource(("", 1), all_runs[0])
        assert fetched_run is not None
        assert fetched_run.metadata is not None
        assert fetched_run.metadata[dangerous_key] == "safe_value"

    @pytest.mark.parametrize(
        ("operation", "expected_indices"),
        [
            # TODO: check why this test fails
            # pytest.param(
            #     SearchOperationBetween(
            #         SearchOperator.IS_BETWEEN,
            #         (datetime.datetime(2024, 1, 1, 12), datetime.datetime(2024, 1, 1, 14)),
            #     ),
            #     [2, 3, 4],  # includes 12:00, 13:00, and 14:00
            #     id="between",
            # ),
            # IS_BEFORE test - excludes boundary
            pytest.param(
                SearchOperationSingle(SearchOperator.IS_BEFORE, datetime.datetime(2024, 1, 1, 12)),
                [0, 1],  # includes only 11:00
                id="before",
            ),
            # IS_AFTER test - excludes boundary
            pytest.param(
                SearchOperationSingle(SearchOperator.IS_AFTER, datetime.datetime(2024, 1, 1, 12, 1)),
                [2, 3],  # includes 13:00 and 14:00
                id="after",
            ),
        ],
    )
    async def test_search_time(
        self,
        clickhouse_client: ClickhouseClient,
        operation: SearchOperation,
        expected_indices: list[int],
    ):
        """Test searching runs by time with different operators."""
        base_time = datetime.datetime(2024, 1, 1, 12)  # noon
        runs = [
            _ck_run(created_at=base_time - datetime.timedelta(hours=1)),  # 11:00
            _ck_run(created_at=base_time),  # 12:00
            _ck_run(created_at=base_time + datetime.timedelta(hours=1)),  # 13:00
            _ck_run(created_at=base_time + datetime.timedelta(hours=2)),  # 14:00
        ]
        await clickhouse_client.insert_models("runs", runs, {"async_insert": 0, "wait_for_async_insert": 0})

        query: list[SearchQuery] = [SearchQuerySimple(SearchField.TIME, operation=operation)]
        r = await self._search(clickhouse_client, query)
        indices = {str(r.run_uuid): idx for idx, r in enumerate(runs)}
        assert sorted([indices[i] for i in r]) == expected_indices


class TestFetchCachedRun:
    async def test_fetch_cached_run(self, clickhouse_client: ClickhouseClient):
        """Test for success only runs"""
        uuid = uuid7()
        run = task_run_ser(
            status="success",
            id=str(uuid),
            task_uid=1,
            task_input={"name": "test"},
        )
        docs = [ClickhouseRun.from_domain(1, run)]
        assert docs[0].cache_hash == "4984014be755b9be7f3cbe9c23fea69a", "sanity"
        await clickhouse_client.insert_models("runs", docs, {"async_insert": 0, "wait_for_async_insert": 0})

        fetched_run = await clickhouse_client.fetch_cached_run(_TASK_TUPLE, 1, run.task_input_hash, run.group.id, None)
        assert fetched_run
        assert fetched_run.id == str(uuid)
        assert fetched_run.llm_completions is None

    async def test_fetch_cached_run_ordered(self, clickhouse_client: ClickhouseClient):
        """Check that the most recent run is returned for cache"""

        # Create an insert a run 1
        now_ms = int(time.time() * 1000)
        uuid1 = uuid7(ms=lambda: now_ms - 1)
        run1 = task_run_ser(id=str(uuid1), task_uid=1, task_input={"name": "test"}, task_output={"output": 1})

        await clickhouse_client.insert_models(
            "runs",
            [ClickhouseRun.from_domain(1, run1)],
            {"async_insert": 0, "wait_for_async_insert": 0},
        )
        fetched_run = await clickhouse_client.fetch_cached_run(
            _TASK_TUPLE,
            1,
            run1.task_input_hash,
            run1.group.id,
            None,
        )
        assert fetched_run
        assert fetched_run.id == str(uuid1)

        # Create and insert a run 2 that has the same input hash but was created 1ms later than run 1
        uuid2 = uuid7(ms=lambda: now_ms)
        assert uuid2 > uuid1, "sanity"

        run2 = task_run_ser(id=str(uuid2), task_uid=1, task_input={"name": "test"}, task_output={"output": 2})
        await clickhouse_client.insert_models(
            "runs",
            [ClickhouseRun.from_domain(1, run2)],
            {"async_insert": 0, "wait_for_async_insert": 0},
        )

        fetched_run = await clickhouse_client.fetch_cached_run(
            _TASK_TUPLE,
            1,
            run1.task_input_hash,
            run1.group.id,
            None,
        )
        assert fetched_run
        assert fetched_run.id == str(uuid2)

    async def test_fetch_cached_run_fail(self, clickhouse_client: ClickhouseClient):
        """Test when we are not fetching success only runs"""
        uuid = uuid7()
        run = task_run_ser(
            id=str(uuid),
            task_uid=1,
            task_input={"name": "test"},
            status="failure",
            error=ErrorResponse.Error(message="test", code="test", status_code=500),
        )

        docs = [ClickhouseRun.from_domain(1, run)]
        assert docs[0].cache_hash == "4984014be755b9be7f3cbe9c23fea69a", "sanity"
        await clickhouse_client.insert_models("runs", docs, {"async_insert": 0, "wait_for_async_insert": 0})

        fetched_run = await clickhouse_client.fetch_cached_run(_TASK_TUPLE, 1, run.task_input_hash, run.group.id, None)
        assert fetched_run is None

        fetched_run = await clickhouse_client.fetch_cached_run(
            _TASK_TUPLE,
            1,
            run.task_input_hash,
            run.group.id,
            None,
            success_only=False,
        )
        assert fetched_run is not None

    async def test_fetch_cached_run_success_only_no_output(self, clickhouse_client: ClickhouseClient):
        """Successful runs can have no output in case of tool calls for example. This tests ensure
        that empty outputs are not returned when success only is requested.
        This tests also checks"""
        now_ms = int(time.time() * 1000)
        uuid1 = uuid7(ms=lambda: now_ms - 1)
        run1 = task_run_ser(id=str(uuid1), task_uid=1, task_input={"name": "test"}, task_output={"output": 1})
        uuid2 = uuid7(ms=lambda: now_ms)
        run2 = task_run_ser(id=str(uuid2), task_uid=1, task_input={"name": "test"}, task_output={})

        await clickhouse_client.insert_models(
            "runs",
            [ClickhouseRun.from_domain(1, run1), ClickhouseRun.from_domain(1, run2)],
            {"async_insert": 0, "wait_for_async_insert": 0},
        )

        # Sanity check, fetch the first run with success only = False to make sure we get the latest run
        fetched_run = await clickhouse_client.fetch_cached_run(
            _TASK_TUPLE,
            1,
            run1.task_input_hash,
            run1.group.id,
            None,
            success_only=False,
        )
        assert fetched_run
        assert fetched_run.id == str(uuid2)

        # Now fetch the run with success only = True to make sure we get the first run
        fetched_run = await clickhouse_client.fetch_cached_run(
            _TASK_TUPLE,
            1,
            run1.task_input_hash,
            run1.group.id,
            None,
            success_only=True,
        )
        assert fetched_run
        assert fetched_run.id == str(uuid1)


def _ck_run(task_uid: int = 1, tenant_uid: int = 1, created_at: datetime.datetime | None = None, **kwargs: Any):
    uuid = uuid7() if created_at is None else uuid7(ms=lambda: int(created_at.timestamp() * 1000))
    run = task_run_ser(
        id=str(uuid),
        task_uid=task_uid,
        created_at=created_at or datetime_factory(),
        **kwargs,
    )
    return ClickhouseRun.from_domain(tenant_uid, run)


class TestAggregateTaskMetadataFields:
    async def test_aggregate_task_metadata_fields(self, clickhouse_client: ClickhouseClient):
        models = [
            _ck_run(metadata={"a": "b"}),
            _ck_run(metadata={"a": "1", "c": "d"}),
            _ck_run(metadata={"a": "2", "c": "d", "e": "f"}),
            _ck_run(metadata={"a": "3", "c": "d", "e": "f", "g": "h"}),
            _ck_run(task_uid=2, metadata={"r": "s"}),
            _ck_run(tenant_uid=2, metadata={"s": "s"}),
        ]
        await clickhouse_client.insert_models("runs", models, {"async_insert": 0, "wait_for_async_insert": 0})

        fields = {k: sorted(v) async for k, v in clickhouse_client.aggregate_task_metadata_fields(("", 1))}
        assert fields == {"a": ["1", "2", "3", "b"], "c": ["d"], "e": ["f"], "g": ["h"]}

    async def test_exclude_prefix(self, clickhouse_client: ClickhouseClient):
        models = [
            _ck_run(metadata={"a": "b"}),
            _ck_run(metadata={"a": "1", "c": "d"}),
            _ck_run(metadata={"a": "2", "c": "d", "e": "f"}),
            _ck_run(metadata={"workflowai.a": "b"}),
            _ck_run(metadata={"workflowai.a": "1", "c": "d"}),
            _ck_run(metadata={"workflowai.a": "2", "c": "d", "e": "f"}),
        ]
        await clickhouse_client.insert_models("runs", models, {"async_insert": 0, "wait_for_async_insert": 0})

        fields = {
            k: sorted(v) async for k, v in clickhouse_client.aggregate_task_metadata_fields(("", 1), "workflowai.")
        }
        assert fields == {"a": ["1", "2", "b"], "c": ["d"], "e": ["f"]}

    async def test_max_runs(self, clickhouse_client: ClickhouseClient):
        models = [
            _ck_run(metadata={"a": "b"}),
            _ck_run(metadata={"a": "1", "c": "d"}),
            _ck_run(metadata={"a": "2", "c": "d", "e": "f"}),
        ]
        await clickhouse_client.insert_models("runs", models, {"async_insert": 0, "wait_for_async_insert": 0})
        fields = {
            k: sorted(v)
            async for k, v in clickhouse_client.aggregate_task_metadata_fields(("", 1), "workflowai.", max_values=1)
        }
        assert len(fields) == 1
        assert len(fields["a"]) == 1
        assert fields["a"][0] in {"b", "1", "2"}


def _qs(task_uid: int = 1, exp: list[int] = [1, 2, 3, 4, 5], **kwargs: Any):
    # TODO: it would be nice to return pytest.param here but it creates discovery errors where computing a simple id
    return (
        task_uid,
        exp,
        SerializableTaskRunQuery(task_id="", **kwargs),
    )


class TestFetchTaskRunResources:
    @pytest.mark.parametrize(
        ("task_uid", "expected", "query"),
        [
            _qs(exp=[0, 1, 2, 3, 4]),
            _qs(exp=[0, 2, 3, 4], status={"success"}),
            _qs(exp=[1], task_input_hashes={"10e98b24438459b86a3ddd72b495cfb3"}),
            # TODO: we should add a real test for unique by, the test data does not include duplicate values
            _qs(exp=[1], task_input_hashes={"10e98b24438459b86a3ddd72b495cfb3"}, unique_by={"task_input_hash"}),
            _qs(
                exp=[1],
                task_input_hashes={"10e98b24438459b86a3ddd72b495cfb3"},
                unique_by={"task_input_hash", "task_output_hash"},
            ),
            _qs(
                exp=[1, 2],
                task_input_hashes={"10e98b24438459b86a3ddd72b495cfb3", "c0629dbc56e3fbaa6c0620155270966f"},
            ),
            _qs(
                exp=[1],
                task_schema_id=2,
                task_input_hashes={"10e98b24438459b86a3ddd72b495cfb3"},
                task_output_hashes={"0a5a3c773e3f8def55c94f90ad1b4d7b"},
            ),
            _qs(exp=[1, 2, 4], metadata={"provider": "openai"}),
        ],
    )
    async def test_fetch_task_run_resources(
        self,
        clickhouse_client: ClickhouseClient,
        task_uid: int,
        expected: list[int],
        query: SerializableTaskRunQuery,
    ):
        docs = fixtures_json("runs/searchable_runs.json")
        docs = [ClickhouseRun.model_validate(d) for d in docs]
        await clickhouse_client.insert_models("runs", docs, {"async_insert": 0, "wait_for_async_insert": 0})

        doc_map = {str(d.run_uuid): idx for idx, d in enumerate(docs)}
        r = [doc_map[r.id] async for r in clickhouse_client.fetch_task_run_resources(task_uid, query)]
        assert r == expected

    async def test_unique_version_ids(self, clickhouse_client: ClickhouseClient):
        hash_arg: dict[str, Any] = {
            "task_input_hash": "input1",
            "task_output_hash": "output1",
        }
        await clickhouse_client.insert_models(
            "runs",
            [
                _ck_run(task_schema_id=3, cost_usd=102.0),
                _ck_run(**hash_arg),
                _ck_run(group_id="v2", **hash_arg),
                _ck_run(group_id="v3", **hash_arg),
                # Not included because the input hash is different
                _ck_run(group_id="v4", task_input_hash="1", task_output_hash="output1"),
                # Not included because the output hash is different
                _ck_run(group_id="v5", task_input_hash="input1", task_output_hash="1"),
            ],
            {"async_insert": 0, "wait_for_async_insert": 0},
        )

        q = SerializableTaskRunQuery(
            task_id="task_id",
            task_schema_id=1,
            task_input_hashes={"input1"},
            task_output_hash="output1",
            unique_by={"version_id"},
            include_fields={"version_id"},
        )
        version_ids = {run.group.id async for run in clickhouse_client.fetch_task_run_resources(1, q)}
        assert version_ids == {"group_alias", "v2", "v3"}

        q.group_ids = {"v2", "v3"}

        version_ids = {run.group.id async for run in clickhouse_client.fetch_task_run_resources(1, q)}
        assert version_ids == {"v2", "v3"}


def _llm_completion(prompt_token_count: int, completion_token_count: int):
    return LLMCompletion(
        messages=[],
        usage=LLMUsage(prompt_token_count=prompt_token_count, completion_token_count=completion_token_count),
        provider=Provider.OPEN_AI,
    )


class TestAggregateTokenCounts:
    async def test_aggregate_token_counts(self, clickhouse_client: ClickhouseClient):
        await clickhouse_client.insert_models(
            "runs",
            [
                _ck_run(llm_completions=[_llm_completion(12, 20)]),
                _ck_run(llm_completions=[_llm_completion(15, 25)]),
                _ck_run(llm_completions=[_llm_completion(9, 15)]),
            ],
            {"async_insert": 0, "wait_for_async_insert": 0},
        )
        result = await clickhouse_client.aggregate_token_counts(("", 1), 1)
        expected_prompt_avg = (12 + 15 + 9) / 3
        expected_completion_avg = (20 + 25 + 15) / 3
        assert result["average_prompt_tokens"] == expected_prompt_avg
        assert result["average_completion_tokens"] == expected_completion_avg

    async def test_aggregate_token_counts_excluded_models(self, clickhouse_client: ClickhouseClient):
        task_runs = [
            _ck_run(llm_completions=[_llm_completion(12, 20)]),
            _ck_run(llm_completions=[_llm_completion(13, 200)], model="o1-preview-2024-09-12"),
            _ck_run(llm_completions=[_llm_completion(14, 201)], model="o1-mini-2024-09-12"),
        ]
        await clickhouse_client.insert_models("runs", task_runs, {"async_insert": 0, "wait_for_async_insert": 0})

        result = await clickhouse_client.aggregate_token_counts(
            ("", 1),
            1,
            excluded_models=["o1-preview-2024-09-12", "o1-mini-2024-09-12"],
        )

        assert result["average_prompt_tokens"] == 12
        assert result["average_completion_tokens"] == 20

    async def test_aggregate_token_counts_included_models(self, clickhouse_client: ClickhouseClient):
        task_runs = [
            _ck_run(llm_completions=[_llm_completion(12, 20)]),
            _ck_run(llm_completions=[_llm_completion(13, 200)], model="o1-preview-2024-09-12"),
            _ck_run(llm_completions=[_llm_completion(14, 201)], model="o1-mini-2024-09-12"),
        ]
        await clickhouse_client.insert_models("runs", task_runs, {"async_insert": 0, "wait_for_async_insert": 0})

        result = await clickhouse_client.aggregate_token_counts(
            ("", 1),
            1,
            included_models=["o1-preview-2024-09-12", "o1-mini-2024-09-12"],
        )
        assert result["average_prompt_tokens"] == (13 + 14) / 2
        assert result["average_completion_tokens"] == (200 + 201) / 2


class TestAggregateTaskRunCosts:
    async def test_aggregate_task_run_costs(self, clickhouse_client: ClickhouseClient):
        await clickhouse_client.insert_models(
            "runs",
            [
                _ck_run(cost_usd=100, created_at=datetime.datetime(2024, 1, 1)),
                _ck_run(cost_usd=200, created_at=datetime.datetime(2024, 1, 2)),
                _ck_run(cost_usd=300, created_at=datetime.datetime(2024, 1, 3)),
            ],
            {"async_insert": 0, "wait_for_async_insert": 0},
        )
        result = [
            r async for r in clickhouse_client.aggregate_task_run_costs(1, SerializableTaskRunQuery(task_id="task_id"))
        ]
        assert result == [
            TaskRunAggregatePerDay(date=datetime.date(2024, 1, 1), total_count=1, total_cost_usd=100),
            TaskRunAggregatePerDay(date=datetime.date(2024, 1, 2), total_count=1, total_cost_usd=200),
            TaskRunAggregatePerDay(date=datetime.date(2024, 1, 3), total_count=1, total_cost_usd=300),
        ]


class TestAggregateRuns:
    # TODO[clickhouse]: add a test with filters
    async def test_aggregate_runs(self, clickhouse_client: ClickhouseClient):
        await clickhouse_client.insert_models(
            "runs",
            [
                # Another tenant, should be ignored
                _ck_run(tenant_uid=2, cost_usd=110.75),
                # Another task schema, should be ignored
                _ck_run(task_schema_id=3, cost_usd=102.0),
                _ck_run(
                    cost_usd=1.0,
                    task_input_hash="i1",
                    task_output_hash="o1",
                    duration_seconds=1,
                ),
                # Insert a run for a duplicate input & output, it should be ignored
                _ck_run(
                    cost_usd=1.0,
                    task_input_hash="i1",
                    task_output_hash="o1",
                    duration_seconds=1,
                ),
                # Insert a run for a duplicate input, it should NOT be ignored
                _ck_run(cost_usd=2.0, task_input_hash="i1"),
                # User review should prime,
                _ck_run(cost_usd=6.0, error={"message": "test"}, status="failure"),
                # no review
                _ck_run(cost_usd=1.0),
                _ck_run(group_id="2", cost_usd=1, duration_seconds=2),
            ],
            {"async_insert": 0, "wait_for_async_insert": 0},
        )

        agg = await clickhouse_client.aggregate_runs(("", 1), 1, set(), None)
        for v in agg.values():
            v["eval_hashes"] = sorted(v["eval_hashes"])

        assert agg == {
            "group_alias": RunAggregate(
                average_cost_usd=pytest.approx(2.2, abs=0.01),  # type: ignore
                average_duration_seconds=1.0,
                total_run_count=5,
                failed_run_count=1,
                eval_hashes=[
                    "8d0705a43526930ebcce6a561e63efc8",
                    "f0f1553134f423df626e2d797fdd005e",
                    "f0f1553134f423df626e2d797fdd005e",
                    "f0fb628f228fe1bbf00db390ff350f7b",
                    "f0fb628f228fe1bbf00db390ff350f7b",
                ],
            ),
            "2": RunAggregate(
                average_cost_usd=1.0,
                average_duration_seconds=2.0,
                total_run_count=1,
                failed_run_count=0,
                eval_hashes=["f0f1553134f423df626e2d797fdd005e"],
            ),
        }

    async def test_duplicate_input_output(self, clickhouse_client: ClickhouseClient):
        runs = [
            _ck_run(task_input_hash="i1", task_output_hash="o1", group_id="1"),
            _ck_run(task_input_hash="i1", task_output_hash="o1", group_id="2"),
        ]
        await clickhouse_client.insert_models("runs", runs, {"async_insert": 0, "wait_for_async_insert": 0})

        agg = await clickhouse_client.aggregate_runs(("", 1), 1, set(), None)

        assert agg == {
            "1": RunAggregate(
                average_cost_usd=0.0,
                average_duration_seconds=1.0,
                total_run_count=1,
                failed_run_count=0,
                eval_hashes=["f0fb628f228fe1bbf00db390ff350f7b"],
            ),
            "2": RunAggregate(
                average_cost_usd=0.0,
                average_duration_seconds=1.0,
                total_run_count=1,
                failed_run_count=0,
                eval_hashes=["f0fb628f228fe1bbf00db390ff350f7b"],
            ),
        }

    async def test_aggregate_runs_with_filters(self, clickhouse_client: ClickhouseClient):
        # Create test data with different input hashes and group IDs
        runs = [
            _ck_run(task_input_hash="i1", task_output_hash="o1", group_id="v1", cost_usd=1.0, duration_seconds=10),
            _ck_run(task_input_hash="i2", task_output_hash="o2", group_id="v1", cost_usd=2.0, duration_seconds=20),
            _ck_run(task_input_hash="i3", task_output_hash="o3", group_id="v2", cost_usd=3.0, duration_seconds=30),
            _ck_run(task_input_hash="i4", task_output_hash="o4", group_id="v3", cost_usd=4.0, duration_seconds=40),
        ]
        await clickhouse_client.insert_models("runs", runs, {"async_insert": 0, "wait_for_async_insert": 0})

        # Test filtering by input hashes
        agg = await clickhouse_client.aggregate_runs(("", 1), 1, {"i1", "i2"}, None)
        for v in agg.values():
            v["eval_hashes"] = sorted(v["eval_hashes"])

        assert agg == {
            "v1": RunAggregate(
                average_cost_usd=1.5,
                average_duration_seconds=15.0,
                total_run_count=2,
                failed_run_count=0,
                eval_hashes=["25a840ee59d16a897cd3c27bd55d1db5", "f0fb628f228fe1bbf00db390ff350f7b"],
            ),
        }

        # Test filtering by group IDs
        agg = await clickhouse_client.aggregate_runs(("", 1), 1, set(), {"v2", "v3"})
        for v in agg.values():
            v["eval_hashes"] = sorted(v["eval_hashes"])

        assert agg == {
            "v2": RunAggregate(
                average_cost_usd=3.0,
                average_duration_seconds=30.0,
                total_run_count=1,
                failed_run_count=0,
                eval_hashes=["31d8859c3f9d4e9a4bd2dc163bb2c3d6"],
            ),
            "v3": RunAggregate(
                average_cost_usd=4.0,
                average_duration_seconds=40.0,
                total_run_count=1,
                failed_run_count=0,
                eval_hashes=["31bea3e3766fb0f2b5f8d13bca6ab627"],
            ),
        }

        # Test filtering by both input hashes and group IDs
        agg = await clickhouse_client.aggregate_runs(("", 1), 1, {"i1", "i3"}, {"v1", "v2"})
        for v in agg.values():
            v["eval_hashes"] = sorted(v["eval_hashes"])

        assert agg == {
            "v1": RunAggregate(
                average_cost_usd=1.0,
                average_duration_seconds=10.0,
                total_run_count=1,
                failed_run_count=0,
                eval_hashes=["f0fb628f228fe1bbf00db390ff350f7b"],
            ),
            "v2": RunAggregate(
                average_cost_usd=3.0,
                average_duration_seconds=30.0,
                total_run_count=1,
                failed_run_count=0,
                eval_hashes=["31d8859c3f9d4e9a4bd2dc163bb2c3d6"],
            ),
        }


class TestFetchRun:
    async def test_include_status(self, clickhouse_client: ClickhouseClient):
        run = _ck_run(status="success")
        await clickhouse_client.insert_models(
            "runs",
            [run],
            {"async_insert": 0, "wait_for_async_insert": 0},
        )
        run = await clickhouse_client.fetch_task_run_resource(("bla", 1), str(run.run_uuid), include={"status"})
        assert run.status == "success"
        assert run.task_id == "bla"

    async def test_include_version_iteration(self, clickhouse_client: ClickhouseClient):
        run = _ck_run(group_id="1", version_iteration=1)
        await clickhouse_client.insert_models(
            "runs",
            [run],
            {"async_insert": 0, "wait_for_async_insert": 0},
        )
        run = await clickhouse_client.fetch_task_run_resource(
            ("bla", 1),
            str(run.run_uuid),
            include={"group.iteration"},
        )
        assert run.group.iteration == 1


class TestRunCountByVersionId:
    async def test_run_count_by_version_id(self, clickhouse_client: ClickhouseClient):
        # Create test data with different version IDs and dates
        now = datetime.datetime(2024, 1, 1)
        runs = [
            # These should be counted (same agent, after from_date)
            _ck_run(task_uid=1, group_id="v1", created_at=now),
            _ck_run(task_uid=1, group_id="v1", created_at=now),
            _ck_run(task_uid=1, group_id="v2", created_at=now),
            # Different agent, should not be counted
            _ck_run(task_uid=2, group_id="v1", created_at=now),
            # Before from_date, should not be counted
            _ck_run(task_uid=1, group_id="v1", created_at=now - datetime.timedelta(days=2)),
            # Different tenant, should not be counted
            _ck_run(tenant_uid=2, task_uid=1, group_id="v1", created_at=now),
        ]
        await clickhouse_client.insert_models("runs", runs, {"async_insert": 0, "wait_for_async_insert": 0})

        counts = {
            r.version_id: r.run_count
            async for r in clickhouse_client.run_count_by_version_id(1, now - datetime.timedelta(days=1))
        }
        assert counts == {"v1": 2, "v2": 1}

    async def test_run_count_by_version_id_empty(self, clickhouse_client: ClickhouseClient):
        # Test with no data
        now = datetime.datetime(2024, 1, 1)
        counts = {r.version_id: r.run_count async for r in clickhouse_client.run_count_by_version_id(1, now)}
        assert counts == {}

    async def test_run_count_by_version_id_date_boundary(self, clickhouse_client: ClickhouseClient):
        # Test exact date boundary behavior
        boundary_date = datetime.datetime(2024, 1, 1, 12, 0)  # Noon on Jan 1st
        runs = [
            # 1 second before boundary
            _ck_run(task_uid=1, group_id="v1", created_at=boundary_date - datetime.timedelta(seconds=1)),
            # Exactly at boundary
            _ck_run(task_uid=1, group_id="v1", created_at=boundary_date),
            # 1 second after boundary
            _ck_run(task_uid=1, group_id="v1", created_at=boundary_date + datetime.timedelta(seconds=1)),
        ]
        await clickhouse_client.insert_models("runs", runs, {"async_insert": 0, "wait_for_async_insert": 0})

        # Should only include runs at or after boundary_date
        counts = {r.version_id: r.run_count async for r in clickhouse_client.run_count_by_version_id(1, boundary_date)}
        assert counts == {"v1": 2}


class TestRunCountByAgentUid:
    async def test_run_count_by_agent_uid(self, clickhouse_client: ClickhouseClient):
        # Create test data with different agent UIDs and dates
        now = datetime.datetime(2024, 1, 1)
        runs = [
            # These should be counted (after from_date)
            _ck_run(task_uid=1, created_at=now, cost_usd=10.0),
            _ck_run(task_uid=1, created_at=now, cost_usd=20.0),  # avg cost for task_uid 1: 15.0
            _ck_run(task_uid=2, created_at=now, cost_usd=30.0),
            _ck_run(task_uid=2, created_at=now, cost_usd=40.0),  # avg cost for task_uid 2: 35.0
            _ck_run(task_uid=3, created_at=now, cost_usd=50.0),  # avg cost for task_uid 3: 50.0
            # Before from_date, should not be counted
            _ck_run(task_uid=1, created_at=now - datetime.timedelta(days=2), cost_usd=100.0),
            _ck_run(task_uid=2, created_at=now - datetime.timedelta(days=2), cost_usd=200.0),
            # Different tenant, should not be counted
            _ck_run(tenant_uid=2, task_uid=1, created_at=now, cost_usd=300.0),
            _ck_run(tenant_uid=2, task_uid=2, created_at=now, cost_usd=400.0),
        ]
        await clickhouse_client.insert_models("runs", runs, {"async_insert": 0, "wait_for_async_insert": 0})

        results = {
            r.agent_uid: (r.run_count, r.total_cost_usd)
            async for r in clickhouse_client.run_count_by_agent_uid(now - datetime.timedelta(days=1))
        }
        assert results == {
            1: (2, pytest.approx(30.0)),  # pyright: ignore [reportUnknownMemberType]
            2: (2, pytest.approx(70.0)),  # pyright: ignore [reportUnknownMemberType]
            3: (1, pytest.approx(50.0)),  # pyright: ignore [reportUnknownMemberType]
        }

    async def test_run_count_by_agent_uid_empty(self, clickhouse_client: ClickhouseClient):
        # Test with no data
        now = datetime.datetime(2024, 1, 1)
        results = {
            r.agent_uid: (r.run_count, r.total_cost_usd) async for r in clickhouse_client.run_count_by_agent_uid(now)
        }
        assert results == {}

    async def test_run_count_by_agent_uid_date_boundary(self, clickhouse_client: ClickhouseClient):
        # Test exact date boundary behavior
        boundary_date = datetime.datetime(2024, 1, 1, 12, 0)  # Noon on Jan 1st
        runs = [
            # 1 second before boundary
            _ck_run(task_uid=1, created_at=boundary_date - datetime.timedelta(seconds=1), cost_usd=10.0),
            # Exactly at boundary
            _ck_run(task_uid=1, created_at=boundary_date, cost_usd=20.0),
            _ck_run(task_uid=2, created_at=boundary_date, cost_usd=30.0),
            # 1 second after boundary
            _ck_run(task_uid=1, created_at=boundary_date + datetime.timedelta(seconds=1), cost_usd=40.0),
            _ck_run(task_uid=2, created_at=boundary_date + datetime.timedelta(seconds=1), cost_usd=50.0),
        ]
        await clickhouse_client.insert_models("runs", runs, {"async_insert": 0, "wait_for_async_insert": 0})

        # Should only include runs at or after boundary_date
        results = {
            r.agent_uid: (r.run_count, r.total_cost_usd)
            async for r in clickhouse_client.run_count_by_agent_uid(boundary_date)
        }
        assert results == {
            1: (2, pytest.approx(60.0)),  # pyright: ignore [reportUnknownMemberType]
            2: (2, pytest.approx(80.0)),  # pyright: ignore [reportUnknownMemberType]
        }

    async def test_run_count_by_agent_uid_is_active(self, clickhouse_client: ClickhouseClient):
        # Test filtering by is_active parameter
        now = datetime.datetime(2024, 1, 1)
        runs = [
            # Active runs
            _ck_run(task_uid=1, created_at=now, cost_usd=10.0, is_active=True),
            _ck_run(task_uid=2, created_at=now, cost_usd=20.0, is_active=True),
            # Inactive runs
            _ck_run(task_uid=1, created_at=now, cost_usd=30.0, is_active=False),
            _ck_run(task_uid=3, created_at=now, cost_usd=40.0, is_active=False),
            # Mixed agent with both active and inactive runs
            _ck_run(task_uid=4, created_at=now, cost_usd=50.0, is_active=True),
            _ck_run(task_uid=4, created_at=now, cost_usd=60.0, is_active=False),
        ]
        await clickhouse_client.insert_models("runs", runs, {"async_insert": 0, "wait_for_async_insert": 0})

        # Get only active runs
        active_results = {
            r.agent_uid: (r.run_count, r.total_cost_usd)
            async for r in clickhouse_client.run_count_by_agent_uid(now, is_active=True)
        }
        assert active_results == {
            1: (1, pytest.approx(10.0)),  # pyright: ignore [reportUnknownMemberType]
            2: (1, pytest.approx(20.0)),  # pyright: ignore [reportUnknownMemberType]
            4: (1, pytest.approx(50.0)),  # pyright: ignore [reportUnknownMemberType]
        }

        # Get all runs (default behavior with is_active=None)
        all_results = {
            r.agent_uid: (r.run_count, r.total_cost_usd) async for r in clickhouse_client.run_count_by_agent_uid(now)
        }
        assert all_results == {
            1: (2, pytest.approx(40.0)),  # pyright: ignore [reportUnknownMemberType]
            2: (1, pytest.approx(20.0)),  # pyright: ignore [reportUnknownMemberType]
            3: (1, pytest.approx(40.0)),  # pyright: ignore [reportUnknownMemberType]
            4: (2, pytest.approx(110.0)),  # pyright: ignore [reportUnknownMemberType]
        }

    async def test_run_count_by_agent_uid_with_from_and_to_date(self, clickhouse_client: ClickhouseClient):
        # Test with both from_date and to_date parameters
        base_date = datetime.datetime(2024, 1, 15, 12, 0)  # Noon on Jan 15th

        # Create dates spanning 30 days
        dates = [
            base_date - datetime.timedelta(days=25),  # Jan 21 - outside range
            base_date - datetime.timedelta(days=20),  # Jan 26 - inside range
            base_date - datetime.timedelta(days=15),  # Jan 31 - inside range
            base_date - datetime.timedelta(days=10),  # Feb 5 - inside range
            base_date - datetime.timedelta(days=5),  # Feb 10 - outside range
        ]

        # Create runs on these dates
        runs = [
            _ck_run(task_uid=1, created_at=dates[0], cost_usd=10.0),  # Too early, should not be counted
            _ck_run(task_uid=2, created_at=dates[1], cost_usd=20.0),  # Should be counted
            _ck_run(task_uid=3, created_at=dates[2], cost_usd=30.0),  # Should be counted
            _ck_run(task_uid=3, created_at=dates[3], cost_usd=40.0),  # Should be counted
            _ck_run(task_uid=4, created_at=dates[4], cost_usd=50.0),  # Too late, should not be counted
        ]
        await clickhouse_client.insert_models("runs", runs, {"async_insert": 0, "wait_for_async_insert": 0})

        # Define date range for 20 days ago to 6 days ago
        from_date = base_date - datetime.timedelta(days=21)  # Just before the earliest run we want to include
        to_date = base_date - datetime.timedelta(days=6)  # Just after the latest run we want to include

        # Count runs within the date range
        results = {
            r.agent_uid: (r.run_count, r.total_cost_usd)
            async for r in clickhouse_client.run_count_by_agent_uid(from_date, to_date)
        }

        # Should include agent UIDs 2 and 3, but not 1 or 4
        assert results == {
            2: (1, pytest.approx(20.0)),  # pyright: ignore [reportUnknownMemberType]
            3: (2, pytest.approx(70.0)),  # pyright: ignore [reportUnknownMemberType]
        }
        assert 1 not in results
        assert 4 not in results

    async def test_run_count_by_agent_uid_with_agent_uids_filter(self, clickhouse_client: ClickhouseClient):
        # Test filtering by agent_uids parameter
        now = datetime.datetime(2024, 1, 1)
        runs = [
            # Create runs for different agent UIDs
            _ck_run(task_uid=1, created_at=now, cost_usd=10.0),
            _ck_run(task_uid=1, created_at=now, cost_usd=20.0),  # Total for task_uid 1: 30.0
            _ck_run(task_uid=2, created_at=now, cost_usd=30.0),
            _ck_run(task_uid=3, created_at=now, cost_usd=60.0),
        ]
        await clickhouse_client.insert_models("runs", runs, {"async_insert": 0, "wait_for_async_insert": 0})

        # Test filtering by specific agent UIDs
        results = {
            r.agent_uid: (r.run_count, r.total_cost_usd)
            async for r in clickhouse_client.run_count_by_agent_uid(now, agent_uids={1, 3})
        }
        assert results == {
            1: (2, pytest.approx(30.0)),  # pyright: ignore [reportUnknownMemberType]
            3: (1, pytest.approx(60.0)),  # pyright: ignore [reportUnknownMemberType]
        }
        # Should not include agents 2 and 5
        assert 2 not in results

    async def test_run_count_by_agent_uid_with_single_agent_uid(self, clickhouse_client: ClickhouseClient):
        # Test filtering by a single agent UID
        now = datetime.datetime(2024, 1, 1)
        runs = [
            _ck_run(task_uid=1, created_at=now, cost_usd=10.0),
            _ck_run(task_uid=1, created_at=now, cost_usd=20.0),
            _ck_run(task_uid=2, created_at=now, cost_usd=30.0),
            _ck_run(task_uid=3, created_at=now, cost_usd=40.0),
        ]
        await clickhouse_client.insert_models("runs", runs, {"async_insert": 0, "wait_for_async_insert": 0})

        # Test filtering by single agent UID
        results = {
            r.agent_uid: (r.run_count, r.total_cost_usd)
            async for r in clickhouse_client.run_count_by_agent_uid(now, agent_uids={2})
        }
        assert results == {
            2: (1, pytest.approx(30.0)),  # pyright: ignore [reportUnknownMemberType]
        }
        # Should not include other agents
        assert 1 not in results
        assert 3 not in results

    async def test_run_count_by_agent_uid_with_nonexistent_agent_uids(self, clickhouse_client: ClickhouseClient):
        # Test filtering by agent UIDs that don't exist
        now = datetime.datetime(2024, 1, 1)
        runs = [
            _ck_run(task_uid=1, created_at=now, cost_usd=10.0),
            _ck_run(task_uid=2, created_at=now, cost_usd=20.0),
        ]
        await clickhouse_client.insert_models("runs", runs, {"async_insert": 0, "wait_for_async_insert": 0})

        # Test filtering by non-existent agent UIDs
        results = {
            r.agent_uid: (r.run_count, r.total_cost_usd)
            async for r in clickhouse_client.run_count_by_agent_uid(now, agent_uids={99, 100})
        }
        assert results == {}

    async def test_run_count_by_agent_uid_combined_filters(self, clickhouse_client: ClickhouseClient):
        # Test agent_uids combined with other filters (is_active, date range)
        now = datetime.datetime(2024, 1, 1)
        runs = [
            # Active runs
            _ck_run(task_uid=1, created_at=now, cost_usd=10.0, is_active=True),
            _ck_run(task_uid=2, created_at=now, cost_usd=20.0, is_active=True),
            _ck_run(task_uid=3, created_at=now, cost_usd=30.0, is_active=True),
            # Inactive runs
            _ck_run(task_uid=1, created_at=now, cost_usd=40.0, is_active=False),
            _ck_run(task_uid=2, created_at=now, cost_usd=50.0, is_active=False),
            # Runs outside date range
            _ck_run(task_uid=1, created_at=now - datetime.timedelta(days=2), cost_usd=60.0, is_active=True),
            _ck_run(task_uid=2, created_at=now - datetime.timedelta(days=2), cost_usd=70.0, is_active=True),
        ]
        await clickhouse_client.insert_models("runs", runs, {"async_insert": 0, "wait_for_async_insert": 0})

        # Test combined filters: specific agent UIDs + active only + date range
        results = {
            r.agent_uid: (r.run_count, r.total_cost_usd)
            async for r in clickhouse_client.run_count_by_agent_uid(
                now,
                agent_uids={1, 2},
                is_active=True,
            )
        }
        assert results == {
            1: (1, pytest.approx(10.0)),  # pyright: ignore [reportUnknownMemberType]
            2: (1, pytest.approx(20.0)),  # pyright: ignore [reportUnknownMemberType]
        }
        # Should not include agent 3 (not in agent_uids) or inactive runs
        assert 3 not in results


class TestWeeklyRunAggregate:
    def _start_of_week(self):
        base_date = datetime_factory()
        # Ensure we start on a Sunday
        while base_date.weekday() != 6:  # Clickhouse starts weeks on Sunday
            base_date -= datetime.timedelta(days=1)
        return base_date

    async def test_weekly_run_aggregate(self, clickhouse_client: ClickhouseClient):
        # Create test data with runs spread across different weeks
        base_date = self._start_of_week()
        runs = [
            # Current week
            _ck_run(created_at=base_date, overhead_seconds=0.1),
            # Different tenant, should be take into account
            _ck_run(tenant_uid=2, created_at=base_date, overhead_seconds=0.2),
            # Previous week
            _ck_run(created_at=base_date - datetime.timedelta(days=2), overhead_seconds=0.05),
            _ck_run(created_at=base_date - datetime.timedelta(days=3), overhead_seconds=0.1),
            _ck_run(created_at=base_date - datetime.timedelta(days=4), overhead_seconds=0.15),
            # Week - 2
            _ck_run(created_at=base_date - datetime.timedelta(days=8), overhead_seconds=0.06),
            _ck_run(created_at=base_date - datetime.timedelta(days=9), overhead_seconds=0.12),
            # Week - 3
            _ck_run(created_at=base_date - datetime.timedelta(days=15), overhead_seconds=0.14),
        ]
        await clickhouse_client.insert_models("runs", runs, {"async_insert": 0, "wait_for_async_insert": 0})

        # Test with 3 weeks of data
        results = [r async for r in clickhouse_client.weekly_run_aggregate(3)]

        assert results == [
            WeeklyRunAggregate(
                start_of_week=base_date.date() - datetime.timedelta(days=21),
                run_count=1,
                overhead_ms=140,
            ),
            WeeklyRunAggregate(
                start_of_week=base_date.date() - datetime.timedelta(days=14),
                run_count=2,
                overhead_ms=90,
            ),
            WeeklyRunAggregate(
                start_of_week=base_date.date() - datetime.timedelta(days=7),
                run_count=3,
                overhead_ms=100,
            ),
            WeeklyRunAggregate(
                start_of_week=base_date.date(),
                run_count=2,
                overhead_ms=150,
            ),
        ]

    async def test_weekly_run_aggregate_empty(self, clickhouse_client: ClickhouseClient):
        # Test with no data
        results = [r async for r in clickhouse_client.weekly_run_aggregate(2)]
        assert len(results) == 0

    async def test_weekly_run_aggregate_zero_overhead(self, clickhouse_client: ClickhouseClient):
        """Check that the overhead is ignored when it is 0"""
        base_date = self._start_of_week()
        runs = [
            # Week with a run with no overhead
            _ck_run(created_at=base_date, overhead_seconds=0),
            _ck_run(created_at=base_date, overhead_seconds=0.1),
            # Creating a week with only 0 overhead
            _ck_run(created_at=base_date - datetime.timedelta(days=3), overhead_seconds=0),
        ]
        await clickhouse_client.insert_models("runs", runs, {"async_insert": 0, "wait_for_async_insert": 0})

        results = [r async for r in clickhouse_client.weekly_run_aggregate(2)]
        assert results == [
            WeeklyRunAggregate(
                start_of_week=base_date.date() - datetime.timedelta(days=7),
                run_count=1,
                overhead_ms=0,
            ),
            WeeklyRunAggregate(
                start_of_week=base_date.date(),
                run_count=2,
                overhead_ms=100,
            ),
        ]
