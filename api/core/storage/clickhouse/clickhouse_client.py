import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, AsyncIterator, Literal, NotRequired, Sequence, TypedDict, cast, override

from clickhouse_connect.driver import create_async_client  # pyright: ignore[reportUnknownVariableType]
from clickhouse_connect.driver.asyncclient import AsyncClient
from clickhouse_connect.driver.external import ExternalData
from pydantic import BaseModel

from core.domain.agent_run import AgentRun
from core.domain.errors import InternalError
from core.domain.search_query import (
    SearchQuery,
)
from core.domain.task_run_aggregate_per_day import TaskRunAggregatePerDay
from core.domain.task_run_query import SerializableTaskRunField, SerializableTaskRunQuery
from core.storage import ObjectNotFoundException, TaskTuple
from core.storage.clickhouse.models.runs import FIELD_TO_COLUMN, ClickhouseRun
from core.storage.clickhouse.models.utils import data_and_columns, id_lower_bound
from core.storage.clickhouse.query_builder import Q, W, WhereAndClause
from core.storage.task_run_storage import RunAggregate, TaskRunStorage, TokenCounts, WeeklyRunAggregate


class ClickhouseClient(TaskRunStorage):
    _client_pools: dict[str, AsyncClient] = {}

    @classmethod
    async def get_shared_client(cls, connection_string: str) -> AsyncClient:
        if connection_string not in cls._client_pools:
            cls._client_pools[connection_string] = await create_async_client(dsn=connection_string)
        return cls._client_pools[connection_string]

    def __init__(self, connection_string: str, tenant_uid: int):
        self.connection_string = connection_string
        self._client: AsyncClient | None = None
        self.tenant_uid = tenant_uid
        self._logger = logging.getLogger(__name__)

    async def client(self) -> AsyncClient:
        if not self._client:
            self._client = await self.get_shared_client(self.connection_string)
        return self._client

    async def command(
        self,
        cmd: str,
        parameters: Sequence[Any] | dict[str, Any] | None = None,
        data: str | bytes | None = None,
        settings: dict[str, Any] | None = None,
        use_database: bool = True,
        external_data: ExternalData | None = None,
    ):
        client = await self.client()
        return await client.command(  # pyright: ignore[reportUnknownMemberType]
            cmd,
            parameters=parameters,
            # data and settings are not optional in the clickhouse_connect library but
            # have default value as None...
            data=data,  # pyright: ignore[reportArgumentType]
            settings=settings,  # pyright: ignore[reportArgumentType]
            use_database=use_database,
            external_data=external_data,
        )

    async def query(
        self,
        query: str,
        column_formats: dict[str, str | dict[str, str]] | None = None,
        parameters: list[Any] | dict[str, Any] | None = None,
    ):
        # See https://github.com/ClickHouse/clickhouse-connect/issues/141
        # It looks like right now, the async part of the stream is the connection opening
        # not the actual streaming so we should rely on query directly for now
        client = await self.client()
        return await client.query(query, column_formats=column_formats, parameters=parameters)  # pyright: ignore[reportUnknownMemberType]

    class InsertSettings(TypedDict):
        async_insert: NotRequired[Literal[0, 1]]
        wait_for_async_insert: NotRequired[Literal[0, 1]]

    async def insert_models(self, table: str, models: Sequence[BaseModel], settings: InsertSettings | None = None):
        if not models:
            return
        columns = list(models[0].__class__.model_fields.keys())

        def _row(model: BaseModel):
            dumped = model.model_dump()
            return [dumped[column] for column in columns]

        rows = [_row(m) for m in models]
        client = await self.client()
        await client.insert(table=table, column_names=columns, data=rows, settings=cast(dict[str, Any], settings))

    @override
    async def store_task_run(self, task_run: AgentRun, settings: InsertSettings | None = None):
        clickhouse_run = ClickhouseRun.from_domain(self.tenant_uid, task_run)
        data, columns = data_and_columns(clickhouse_run)
        client = await self.client()

        settings = settings or {"async_insert": 1, "wait_for_async_insert": 1}

        await client.insert(
            table="runs",
            column_names=columns,
            data=[data],
            settings=cast(dict[str, Any], settings),
        )
        return task_run

    @classmethod
    def _default_order_by(cls):
        return [
            "tenant_uid DESC",
            "created_at_date DESC",
            "task_uid DESC",
            "run_uuid DESC",
        ]

    @override
    async def search_task_runs(
        self,
        task_uid: TaskTuple | None,
        search_fields: list[SearchQuery] | None,
        limit: int,
        offset: int,
        timeout_ms: int = 60_000,
        include: set[SerializableTaskRunField] | None = None,
        exclude: set[SerializableTaskRunField] | None = None,
        unique_by_conversation: bool = True,
    ):
        columns = ClickhouseRun.select_in_search(include=include, exclude=exclude)
        where = await self._search_where(task_uid, search_fields)

        async with asyncio.timeout(timeout_ms):
            result = await self._runs(
                task_id=task_uid[0] if task_uid else None,
                select=columns,
                where=where,
                limit=limit,
                offset=offset,
                unique_by_conversation=unique_by_conversation,
            )

            for row in result:
                yield row

    def _with_tenant(self, w: W | None) -> W:
        tenant_where = W("tenant_uid", type="UInt32", value=self.tenant_uid)
        return tenant_where & w if w else tenant_where

    async def _mutate_run(self, w: W, data: dict[str, Any], sync: int = 0, sanitize: bool = True):
        # Mutations are bad in clickhouse
        # https://clickhouse.com/blog/handling-updates-and-deletes-in-clickhouse
        # However, having duplicated rows might lead to other issues
        # For now we will just update the row
        s = w.to_sql()
        if not s:
            raise InternalError("Invalid where clause")
        where, parameters = s

        def _sanitize_value(v: Any) -> str:
            if isinstance(v, str):
                return f"'{v}'"
            return str(v)

        keys = ", ".join([f"{k} = {_sanitize_value(v) if sanitize else v}" for k, v in data.items()])

        cmd = f"ALTER TABLE runs UPDATE {keys} WHERE {where}"

        await self.command(
            cmd,
            parameters=parameters,
            settings={"mutations_sync": sync},
        )

    async def _runs(
        self,
        task_id: str | None,
        select: Sequence[str] | None = None,
        where: W | None = None,
        limit: int | None = None,
        offset: int | None = None,
        order_by: Sequence[str] | None = None,
        distincts: Sequence[str] | None = None,
        unique_by_conversation: bool = False,
        prewhere: W | None = None,
    ):
        q, parameters = Q(
            "runs",
            select=select,
            where=self._with_tenant(where),
            prewhere=prewhere,
            limit=limit,
            offset=offset,
            order_by=order_by if order_by is not None else self._default_order_by(),
            distincts=distincts,
            # We use a limit by and not distinct to preserve order.
            # The returned run will be the first in a given conversation
            limit_by=("conversation_id", 1) if unique_by_conversation else None,
        )

        # print("\n", q, parameters, "\n")

        result = await self.query(
            q,
            parameters=parameters,
        )

        def _map_row(row: Sequence[Any]):
            zipped: dict[str, Any] = dict(zip(result.column_names, row))  # pyright: ignore [reportUnknownArgumentType, reportUnknownMemberType]
            return ClickhouseRun.model_validate(zipped).to_domain(task_id or "")

        return [_map_row(row) for row in result.result_rows]

    async def _search_where(self, task_id: TaskTuple | None, search_fields: list[SearchQuery] | None):
        w = W("task_uid", type="UInt32", value=task_id[1]) if task_id else WhereAndClause([])
        if search_fields:
            for q in search_fields:
                w &= ClickhouseRun.to_clause(q)
        return self._with_tenant(w)

    @override
    async def count_filtered_task_runs(
        self,
        task_uid: TaskTuple | None,
        search_fields: list[SearchQuery] | None,
        timeout_ms: int = 10_000,
    ) -> int | None:
        where = await self._search_where(task_uid, search_fields=search_fields)
        q, parameters = Q(
            "runs",
            select=["COUNT()"],
            where=where,
        )
        # print(q, parameters)
        async with asyncio.timeout(timeout_ms):
            result = await self.query(
                q,
                parameters=parameters,
            )
            return result.first_row[0]

    @override
    async def fetch_task_run_resource(
        self,
        task_id: TaskTuple,
        id: str,
        include: set[SerializableTaskRunField] | None = None,
        exclude: set[SerializableTaskRunField] | None = None,
    ) -> AgentRun:
        w = ClickhouseRun.where_by_id(task_id[1], id)
        columns = ClickhouseRun.columns(include, exclude)
        results = await self._runs(task_id[0], columns, w, limit=1)
        if not results:
            raise ObjectNotFoundException("No run by id found", extra={"task_uid": task_id[1], "id": id})
        return results[0]

    @override
    async def fetch_cached_run(
        self,
        task_id: TaskTuple,
        task_schema_id: int,
        task_input_hash: str,
        group_id: str,
        timeout_ms: int | None,
        success_only: bool = True,
    ) -> AgentRun | None:
        async with asyncio.timeout(timeout_ms):
            cache_hash = ClickhouseRun.compute_cache_hash(
                self.tenant_uid,
                task_id[1],
                version_id=group_id,
                input_hash=task_input_hash,
            )

            w = W("cache_hash", type="String", value=cache_hash)
            w &= W("task_schema_id", type="UInt16", value=task_schema_id) & W(
                "tenant_uid",
                type="UInt32",
                value=self.tenant_uid,
            )
            if success_only:
                w &= W("error_payload", type="String", value="") & W("output", type="String", value="", operator="!=")

            prewhere = W("cache_hash", type="String", value=cache_hash)

            result = await self._runs(task_id[0], ClickhouseRun.select_not_heavy(), w, prewhere=prewhere, limit=1)
            if not result:
                return None
            return result[0]

    @override
    async def aggregate_task_metadata_fields(
        self,
        task_id: TaskTuple,
        exclude_prefix: str | None = None,
        max_values: int = 300,
    ):
        date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        sql = f"""
        SELECT
            key,
            groupArrayDistinct(value) AS values
        FROM
        (
            SELECT
                arrayJoin(mapKeys(metadata)) AS key,
                metadata[key] AS value
            FROM runs
            WHERE tenant_uid = {self.tenant_uid} AND created_at_date >= '{date}' AND task_uid = {task_id[1]}
            {f"AND key NOT LIKE '{exclude_prefix}%'" if exclude_prefix else ""}
            LIMIT {max_values}
        )
        GROUP BY key
        """
        query = await self.query(sql)
        for row in query.result_rows:
            yield row[0], row[1]

    @override
    async def fetch_task_run_resources(
        self,
        task_uid: int,
        query: SerializableTaskRunQuery,
        timeout_ms: int | None = None,
    ) -> AsyncIterator[AgentRun]:
        async with asyncio.timeout(timeout_ms):
            w = ClickhouseRun.where_for_query(self.tenant_uid, task_uid, query)
            columns = ClickhouseRun.columns(query.include_fields, query.exclude_fields)

            if query.unique_by:
                distincts = [FIELD_TO_COLUMN.get(ub, ub) for ub in query.unique_by]
            else:
                distincts = None

            result = await self._runs(
                query.task_id or "",
                columns,
                w,
                limit=query.limit,
                offset=query.offset,
                distincts=distincts,
            )
            for row in result:
                yield row

    @override
    async def aggregate_token_counts(
        self,
        task_id: TaskTuple,
        task_schema_id: int,
        excluded_models: list[str] | None = None,
        included_models: list[str] | None = None,
        maxTimeMS: int = 1_000,
    ):
        w = self._with_tenant(
            W("task_uid", type="UInt32", value=task_id[1]) & W("task_schema_id", type="UInt16", value=task_schema_id),
        )
        if included_models:
            w = w & W("version_model", type="String", value=included_models)
        if excluded_models:
            w = w & W("version_model", type="String", value=excluded_models, operator="!=")

        where, parameters = w.to_sql_req()

        # Aggregate input_token_count and output_token_count
        sql = f"""
        SELECT
            avg(input_token_count) AS avg_input_token_count,
            avg(output_token_count) AS avg_output_token_count,
            count() AS total_count
        FROM runs
        WHERE {where}
        LIMIT 10000
        """

        async with asyncio.timeout(maxTimeMS):
            query = await self.query(sql, parameters=parameters)
        try:
            first_row = query.first_row
        except IndexError:
            return TokenCounts(
                average_prompt_tokens=0,
                average_completion_tokens=0,
                count=0,
            )
        return TokenCounts(
            average_prompt_tokens=first_row[0],
            average_completion_tokens=first_row[1],
            count=first_row[2],
        )

    @override
    async def aggregate_task_run_costs(
        self,
        task_uid: int | None,
        query: SerializableTaskRunQuery,
        timeout_ms: int | None = None,
    ):
        w = ClickhouseRun.where_for_query(self.tenant_uid, task_uid, query)
        raw, parameters = w.to_sql_req()

        # Aggregate date, total runs and total cost usd per day
        sql = f"""
        SELECT
            created_at_date,
            count() AS total_count,
            sum(cost_millionth_usd) AS total_cost_usd
        FROM runs
        WHERE {raw}
        GROUP BY created_at_date
        """
        async with asyncio.timeout(timeout_ms):
            res = await self.query(sql, parameters=parameters)

        for row in res.result_rows:
            yield TaskRunAggregatePerDay(
                date=row[0],
                total_count=row[1],
                total_cost_usd=ClickhouseRun.from_cost_millionth_usd(row[2]),
            )

    @override
    async def aggregate_runs(
        self,
        task_id: TaskTuple,
        task_schema_id: int,
        task_input_hashes: set[str],
        group_ids: set[str] | None,
    ):
        # Group reviews by version id
        # - first we filter when reviews is not 0
        # - then we group by version id
        w = (
            W("tenant_uid", type="UInt32", value=self.tenant_uid)
            & W("task_uid", type="UInt32", value=task_id[1])
            & W("task_schema_id", type="UInt16", value=task_schema_id)
        )
        if task_input_hashes:
            w &= W("input_hash", type="String", value=task_input_hashes)
        if group_ids:
            w &= W("version_id", type="String", value=group_ids)

        raw, parameters = w.to_sql_req()

        # See ClickhouseRun._review_clause for the mapping
        sql = f"""
        SELECT
            version_id,
            avg(cost_millionth_usd) AS average_cost_millionth_usd,
            avg(duration_ds) AS average_duration_ds,
            count() AS total_run_count,
            sum(if(error_payload != '', 1, 0)) AS failed_run_count,
            groupArray(eval_hash) AS eval_hashes
        FROM runs
        WHERE {raw}
        GROUP BY version_id
        """

        res = await self.query(sql, parameters=parameters)

        return {
            row[0].rstrip(b"\x00").decode(): RunAggregate(
                average_cost_usd=ClickhouseRun.from_cost_millionth_usd(row[1]),
                average_duration_seconds=ClickhouseRun.from_duration_ds(row[2]),
                total_run_count=row[3],
                failed_run_count=row[4],
                eval_hashes=[r.decode() for r in row[5]],
            )
            for row in res.result_rows
        }

    @override
    async def run_count_by_version_id(
        self,
        agent_uid: int,
        from_date: datetime,
    ):
        w = (
            W("tenant_uid", type="UInt32", value=self.tenant_uid)
            & W("task_uid", type="UInt32", value=agent_uid)
            & W("created_at_date", type="Date", value=from_date.strftime("%Y-%m-%d"), operator=">=")
            & W("run_uuid", type="UInt128", value=id_lower_bound(from_date), operator=">=")
        )
        raw, parameters = w.to_sql_req()
        sql = f"""
        SELECT
            version_id,
            count() AS total_count
        FROM runs
        WHERE {raw}
        GROUP BY version_id
        """
        res = await self.query(sql, parameters=parameters)

        for row in res.result_rows:
            yield TaskRunStorage.VersionRunCount(
                version_id=row[0].rstrip(b"\x00").decode(),
                run_count=row[1],
            )

    @override
    async def run_count_by_agent_uid(
        self,
        from_date: datetime,
        to_date: datetime | None = None,
        is_active: bool | None = None,
        agent_uids: set[int] | None = None,
    ) -> AsyncIterator[TaskRunStorage.AgentRunCount]:
        w = (
            W("tenant_uid", type="UInt32", value=self.tenant_uid)
            & W("created_at_date", type="Date", value=from_date.strftime("%Y-%m-%d"), operator=">=")
            & W("run_uuid", type="UInt128", value=id_lower_bound(from_date), operator=">=")
        )

        if to_date:
            w &= W("created_at_date", type="Date", value=to_date.strftime("%Y-%m-%d"), operator="<=")

        if is_active:
            w &= W("is_active", type="Boolean", value=is_active)

        if agent_uids:
            w &= W("task_uid", type="UInt32", value=agent_uids)

        raw, parameters = w.to_sql_req()
        sql = f"""
        SELECT
            task_uid,
            count() AS total_count,
            sum(cost_millionth_usd) AS total_cost_usd
        FROM runs
        WHERE {raw}
        GROUP BY task_uid
        """
        res = await self.query(sql, parameters=parameters)
        for row in res.result_rows:
            yield TaskRunStorage.AgentRunCount(
                agent_uid=row[0],
                run_count=row[1],
                total_cost_usd=ClickhouseRun.from_cost_millionth_usd(row[2]),
            )

    @override
    async def list_latest_runs(
        self,
        task_uid: int | None = None,
        since_date: datetime | None = None,
        is_active: bool = True,
        limit: int = 100,
    ) -> AsyncIterator[AgentRun]:
        w = W("tenant_uid", type="UInt32", value=self.tenant_uid)
        if task_uid:
            w &= W("task_uid", type="UInt32", value=task_uid)
        if since_date:
            w &= W("created_at_date", type="Date", value=since_date.strftime("%Y-%m-%d"), operator=">=") & W(
                "run_uuid",
                type="UInt128",
                value=id_lower_bound(since_date),
                operator=">=",
            )
        if is_active:
            w &= W("is_active", type="Boolean", value=is_active)
        runs = await self._runs(
            task_id=None,
            select=None,
            where=w,
            limit=limit,
            offset=None,
            order_by=[
                "run_uuid DESC",  # Allows for finer ordering than created_at_date
            ],
        )
        for run in runs:
            yield run

    @override
    async def list_runs_for_memory_id(
        self,
        tenant_uid: int,
        task_uid: int,
        memory_id: str,
        limit: int = 10,
        timeout_ms: int | None = None,
    ) -> AsyncIterator[AgentRun]:
        async with asyncio.timeout(timeout_ms):
            where = (
                W("tenant_uid", type="UInt32", value=tenant_uid)
                & W("task_uid", type="UInt32", value=task_uid)
                & W(
                    "metadata['memory_id']",
                    operator="=",
                    type="String",
                    value=memory_id,
                )
                & W("error_payload", type="String", value="")
                & W(
                    "output",
                    type="String",
                    value="",
                    operator="!=",
                )
            )
            columns = ClickhouseRun.columns(
                include={"task_output"},
            )
            q, parameters = Q(
                "runs",
                select=columns,
                where=where,
                limit=limit,
                offset=None,
                order_by=self._default_order_by(),
                distincts=None,
            )

            query_res = await self.query(
                q,
                parameters=parameters,
            )

            def _map_row(row: Sequence[Any]):
                zipped: dict[str, Any] = dict(zip(query_res.column_names, row))  # pyright: ignore [reportUnknownArgumentType, reportUnknownMemberType]
                return ClickhouseRun.model_validate(zipped).to_domain("")

            for row in query_res.result_rows:
                yield _map_row(row)

    @override
    async def weekly_run_aggregate(self, week_count: int):
        sql = f"""
SELECT
    toStartOfWeek(created_at_date) AS week_start,
    COUNT() AS run_count,
    AVG(NULLIF(overhead_ms, 0)) AS avg_overhead_ms
FROM
    runs
WHERE
    created_at_date >= subtractWeeks(today(), {week_count})
GROUP BY
    week_start
ORDER BY
    week_start
        """
        res = await self.query(sql)
        for row in res.result_rows:
            yield WeeklyRunAggregate(
                start_of_week=row[0],
                run_count=row[1],
                overhead_ms=int(round(row[2] or 0)),
            )
