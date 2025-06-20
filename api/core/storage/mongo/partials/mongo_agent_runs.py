from datetime import datetime, timezone
from typing import AsyncIterator, cast

from pydantic import ValidationError
from pymongo.errors import ExecutionTimeout
from typing_extensions import Any, override

from core.domain.agent_run import AgentRun, AgentRunBase
from core.domain.errors import OperationTimeout
from core.domain.search_query import SearchQuery
from core.domain.task_evaluation import TaskEvaluation
from core.domain.task_run_aggregate_per_day import TaskRunAggregatePerDay
from core.domain.task_run_query import (
    SerializableTaskRunField,
    SerializableTaskRunQuery,
    TaskRunQueryUniqueBy,
)
from core.storage import TaskTuple, TenantTuple
from core.storage.mongo.models.task_run_document import TaskRunDocument
from core.storage.mongo.mongo_types import AsyncCollection, UpdateType
from core.storage.mongo.partials.base_partial_storage import PartialStorage
from core.storage.mongo.utils import projection, query_set_filter
from core.storage.task_run_storage import RunAggregate, TaskRunStorage, TokenCounts, WeeklyRunAggregate


class MongoTaskRunStorage(PartialStorage[TaskRunDocument], TaskRunStorage):
    def __init__(self, tenant: TenantTuple, collection: AsyncCollection):
        super().__init__(tenant, collection, TaskRunDocument)

    @override
    def _before_update(self, update: UpdateType) -> UpdateType:
        _dict_to_update = update if isinstance(update, dict) else update[0]
        _set = _dict_to_update.setdefault("$set", {})
        if "updated_at" not in _set:
            _set["updated_at"] = datetime.now(timezone.utc)
        return update

    @override
    async def aggregate_runs(
        self,
        task_id: TaskTuple,
        task_schema_id: int,
        task_input_hashes: set[str],
        group_ids: set[str] | None,
    ):
        filter = {
            "task.id": task_id[0],
            "task.schema_id": task_schema_id,
        }
        if task_input_hashes:
            filter["task_input_hash"] = query_set_filter(task_input_hashes, True)
        if group_ids:
            filter["group.hash"] = query_set_filter(group_ids, True)
        pipeline = [
            {"$match": filter},
            {
                "$project": {
                    "version_id": "$group.hash",
                    "status": 1,
                    "cost_usd": 1,
                    "duration_seconds": 1,
                    "eval_hash": 1,
                },
            },
            {
                "$group": {
                    "_id": "$version_id",
                    "total_run_count": {"$sum": 1},
                    "failed_run_count": {"$sum": {"$cond": [{"$eq": ["$status", "failure"]}, 1, 0]}},
                    "average_cost_usd": {"$avg": "$cost_usd"},
                    "average_duration_seconds": {"$avg": "$duration_seconds"},
                    "eval_hashes": {"$addToSet": "$eval_hash"},
                },
            },
        ]

        return {doc.pop("_id"): cast(RunAggregate, doc) async for doc in self._aggregate(pipeline, timeout_ms=30_000)}

    # ------------------------------------------------------------------
    # Utils

    def _exclude_evaluator_filter(self, evaluator: TaskEvaluation.Evaluator) -> dict[str, Any]:
        # TODO: we should make only evaluator.id unique
        # The old evaluator ids are built based on the name anyway
        if evaluator.name == "eval_v2":
            return {"scores.evaluator.id": {"$ne": evaluator.id}}
        # In the future, we might want to make only the evaluator id unique
        return {"scores.evaluator.name": {"$ne": evaluator.name}}

    async def aggregate_task_run_costs(
        self,
        task_uid: int | None,
        query: SerializableTaskRunQuery,
        timeout_ms: int = 60_000,
    ) -> AsyncIterator[TaskRunAggregatePerDay]:
        filter = TaskRunDocument.build_filter(self._tenant, query)

        pipeline = [
            {"$match": filter},
            {
                "$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                    "total_count": {"$sum": 1},
                    "total_cost_usd": {
                        "$sum": "$cost_usd",
                    },
                },
            },
            {
                "$project": {
                    "date": "$_id",
                    "total_count": 1,
                    "total_cost_usd": 1,
                    "_id": 0,
                },
            },
            {"$sort": {"date": 1}},
        ]

        async for doc in self._aggregate(pipeline, timeout_ms=timeout_ms):
            yield TaskRunAggregatePerDay(
                date=datetime.fromisoformat(doc["date"]).date(),
                total_count=int(doc.get("total_count", 0)),
                total_cost_usd=float(doc.get("total_cost_usd", 0.0)),
            )

    async def aggregate_token_counts(
        self,
        task_id: TaskTuple,
        task_schema_id: int,
        excluded_models: list[str] | None = None,
        included_models: list[str] | None = None,
        maxTimeMS: int = 1_000,
    ) -> TokenCounts:
        match: dict[str, Any] = {
            "tenant": self._tenant,
            "task.id": task_id[0],
            "task.schema_id": task_schema_id,
            "status": "success",
        }

        if excluded_models and not included_models:
            match["group.properties.model"] = {"$nin": excluded_models}
        elif included_models and not excluded_models:
            match["group.properties.model"] = {"$in": included_models}
        elif included_models and excluded_models:
            match["group.properties.model"] = {"$in": included_models, "$nin": excluded_models}

        pipeline = [
            {"$match": match},
            {
                "$project": {
                    "llm_completions.usage.prompt_token_count": 1,
                    "llm_completions.usage.completion_token_count": 1,
                },
            },
            {"$limit": 100},
            {"$unwind": "$llm_completions"},
            {
                "$group": {
                    "_id": "",
                    "total_prompt_tokens": {"$sum": "$llm_completions.usage.prompt_token_count"},
                    "total_completion_tokens": {"$sum": "$llm_completions.usage.completion_token_count"},
                    "count": {"$sum": 1},
                },
            },
        ]

        try:
            result = await anext(self._aggregate(pipeline, timeout_ms=maxTimeMS))
        except (StopAsyncIteration, ExecutionTimeout):
            return TokenCounts(average_prompt_tokens=0, average_completion_tokens=0, count=0)

        if result["count"] == 0:
            return TokenCounts(average_prompt_tokens=0, average_completion_tokens=0, count=0)

        return TokenCounts(
            average_prompt_tokens=result["total_prompt_tokens"] / result["count"],
            average_completion_tokens=result["total_completion_tokens"] / result["count"],
            count=result["count"],
        )

    def _search_run_include(self) -> set[str]:
        _mapping = {
            "id": "_id",
            "task_id": "task.id",
            "task_schema_id": "task.schema_id",
        }
        # The author uid and task uid are not returned by the search since they will not exist in mongo for now
        _excludes = {"author_uid", "task_uid"}
        return {
            _mapping.get(field_name, field_name)
            for field_name in AgentRunBase.model_fields.keys()
            if field_name not in _excludes
        }

    async def search_task_runs(
        self,
        task_uid: TaskTuple,
        search_fields: list[SearchQuery] | None,
        limit: int,
        offset: int,
        timeout_ms: int = 60_000,
        include: set[SerializableTaskRunField] | None = None,
        exclude: set[SerializableTaskRunField] | None = None,
    ) -> AsyncIterator[AgentRun]:
        filter = TaskRunDocument.build_search_filter(self._tenant, task_uid[0], search_fields)
        project = projection(self._search_run_include())

        try:
            cursor = self._find(
                filter,
                projection=project,
                sort=[("created_at", -1)],
                skip=offset,
                limit=limit,
                timeout_ms=timeout_ms,
            )
            async for doc in cursor:
                yield doc.to_resource()
        except ExecutionTimeout as e:
            raise OperationTimeout() from e

    async def count_filtered_task_runs(
        self,
        task_uid: TaskTuple,
        search_fields: list[SearchQuery] | None,
        timeout_ms: int = 10_000,
    ) -> int | None:
        filter = TaskRunDocument.build_search_filter(self._tenant, task_uid[0], search_fields)
        try:
            return await self._count(filter, max_time_ms=timeout_ms)
        except ExecutionTimeout as e:
            self._logger.exception("Failed to count filtered task runs", exc_info=e, extra={"filter": filter})
            return None

    async def get_suggestions(self, task_id: str, field_names: list[str]) -> dict[str, list[Any]]:
        if not field_names:
            return {}

        field_map = {field_name.replace(".", "_"): field_name for field_name in field_names}

        pipeline = self._build_suggestions_pipeline(task_id, field_map)

        cursor = self._aggregate(pipeline)
        try:
            result = await anext(cursor)
            return {
                original_name: [s for s in result.get(sanitized_name, []) if s is not None]
                for sanitized_name, original_name in field_map.items()
            }
        except StopAsyncIteration:
            # No results found, return the original search_fields
            pass

        return {}

    def _build_suggestions_pipeline(self, task_id: str, field_map: dict[str, str]) -> list[dict[str, Any]]:
        return [
            self._build_match_stage(task_id),
            self._build_sort_stage(),
            self._build_limit_stage(),
            self._build_project_stage(field_map),
            self._build_group_stage(field_map),
            self._build_final_project_stage(field_map),
        ]

    def _build_match_stage(self, task_id: str) -> dict[str, Any]:
        return {
            "$match": {
                "tenant": self._tenant,
                "task.id": task_id,
            },
        }

    def _build_limit_stage(self) -> dict[str, Any]:
        return {"$limit": 1000}  # Limit the number of documents to process

    def _build_project_stage(self, field_map: dict[str, str]) -> dict[str, Any]:
        return {
            "$project": {
                sanitized_name: {
                    "$cond": {
                        # Handle both array and non-array fields
                        # take the values from all the arrays in the field and return them as an array
                        # or return the value as an array with one element
                        "if": {"$isArray": f"${original_name}"},
                        "then": f"${original_name}",
                        "else": [f"${original_name}"],
                    },
                }
                for sanitized_name, original_name in field_map.items()
            },
        }

    def _build_group_stage(self, field_map: dict[str, str]) -> dict[str, Any]:
        return {
            "$group": {
                "_id": None,
                **{sanitized_name: {"$addToSet": f"${sanitized_name}"} for sanitized_name in field_map},
            },
        }

    def _build_final_project_stage(self, field_map: dict[str, str]) -> dict[str, Any]:
        return {
            "$project": {
                "_id": 0,
                **{
                    sanitized_name: {
                        "$reduce": {
                            "input": f"${sanitized_name}",
                            "initialValue": [],
                            "in": {"$setUnion": ["$$value", "$$this"]},
                        },
                    }
                    for sanitized_name in field_map
                },
            },
        }

    def _build_sort_stage(self) -> dict[str, Any]:
        return {"$sort": {"created_at": -1}}

    def _final_review_update_stage(self):
        return {"$set": {"final_review": {"$ifNull": ["$user_review", "$ai_review"]}}}

    async def get_unique_version_ids_for_input_output(
        self,
        task_id: TaskTuple,
        task_schema_id: int,
        task_input_hash: str,
        task_output_hash: str,
        version_ids: set[str] | None = None,
    ) -> set[str]:
        filter: dict[str, Any] = {
            "task.id": task_id[0],
            "task.schema_id": task_schema_id,
            "task_input_hash": task_input_hash,
            "task_output_hash": task_output_hash,
        }
        if version_ids:
            filter["group.hash"] = {"$in": list(version_ids)}
        return await self._distinct(
            key="group.hash",
            filter=filter,
            hint="input_output_hashes",
        )

    async def store_task_run(self, task_run: AgentRun) -> AgentRun:
        doc = TaskRunDocument.from_resource(task_run)
        model = await self._insert_one(doc)
        return model.to_resource()

    async def count_task_runs(self, query: SerializableTaskRunQuery) -> int:
        filter = TaskRunDocument.build_filter(self._tenant, query)
        return await self._count(filter)

    def _aggregate_runs(
        self,
        filter: dict[str, Any],
        unique_by: set[TaskRunQueryUniqueBy],
        project: dict[str, Any] | None,
        limit: int | None,
        offset: int | None,
        sort_by: tuple[str, int] | None,
        timeout_ms: int | None = None,
    ):
        def _map_unique_by(unique_by: TaskRunQueryUniqueBy):
            if unique_by == "version_id":
                return "group.hash"
            return unique_by

        if len(unique_by) == 1:
            group_id = f"${_map_unique_by(next(iter(unique_by)))}"
        else:
            group_id = {k: f"${_map_unique_by(k)}" for k in unique_by}

        pipeline: list[dict[str, Any]] = [
            {"$match": filter},
            {"$sort": {"created_at": -1} if not sort_by else {sort_by[0]: sort_by[1]}},
            {"$group": {"_id": group_id, "doc": {"$first": "$$ROOT"}}},
            {"$replaceRoot": {"newRoot": "$doc"}},
        ]
        if limit:
            pipeline.append({"$limit": limit})
        if offset:
            pipeline.append({"$skip": offset})
        if project:
            pipeline.insert(1, {"$project": project})

        return self._aggregate(
            pipeline,
            timeout_ms=timeout_ms or 0,
            map_fn=TaskRunDocument.model_validate,
        )

    async def fetch_task_run_resources(
        self,
        task_uid: int,
        query: SerializableTaskRunQuery,
        timeout_ms: int | None = None,
        # A hint to the query planner to use a specific index
        hint: str | None = None,
    ) -> AsyncIterator[AgentRun]:
        filter = TaskRunDocument.build_filter(self._tenant, query)

        project = TaskRunDocument.build_project(include=query.include_fields, exclude=query.exclude_fields)
        sort_by = TaskRunDocument.build_sort(query)

        # TODO: test
        if query.unique_by:
            it = self._aggregate_runs(
                filter,
                query.unique_by,
                project,
                query.limit,
                query.offset,
                sort_by,
                timeout_ms=timeout_ms,
            )
        else:
            it = self._find(
                filter,
                projection=project,
                limit=query.limit,
                skip=query.offset,
                sort=[sort_by] if sort_by else None,
                hint=hint,
                timeout_ms=timeout_ms,
            )

        async for doc in it:
            try:
                yield doc.to_resource()
            except ValidationError as e:
                self._logger.exception(e, extra={"doc": doc})

    async def aggregate_task_metadata_fields(
        self,
        task_id: TaskTuple,
        exclude_prefix: str | None = None,
    ):
        pipeline = [
            {"$match": {"task.id": task_id[0]}},
            {"$sort": {"created_at": -1}},
            {"$limit": 100},
            {"$project": {"metadata": {"$objectToArray": "$metadata"}}},
            {"$unwind": "$metadata"},
            {"$group": {"_id": "$metadata.k", "values": {"$addToSet": "$metadata.v"}, "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]

        try:
            async for doc in self._aggregate(pipeline, timeout_ms=1000):
                field_name = f"{doc['_id']}"
                if exclude_prefix and field_name.startswith(exclude_prefix):
                    continue
                yield field_name, doc["values"]

        except ExecutionTimeout:
            pass

    async def fetch_task_run_resource(
        self,
        task_id: TaskTuple,
        id: str,
        include: set[SerializableTaskRunField] | None = None,
        exclude: set[SerializableTaskRunField] | None = None,
    ) -> AgentRun:
        doc = await self._find_one(
            {"_id": id},
            projection=TaskRunDocument.build_project(include=include, exclude=exclude),
        )
        return doc.to_resource()

    async def fetch_cached_run(
        self,
        task_id: TaskTuple,
        task_schema_id: int,
        task_input_hash: str,
        group_id: str,
        timeout_ms: int | None,
        success_only: bool = True,
    ) -> AgentRun | None:
        query = SerializableTaskRunQuery(
            task_id=task_id[0],
            task_schema_id=task_schema_id,
            task_input_hashes={task_input_hash},
            group_ids={group_id},
            limit=1,
            status={"success"} if success_only else None,
        )
        try:
            return await anext(self.fetch_task_run_resources(task_uid=task_id[1], query=query, timeout_ms=timeout_ms))
        except StopAsyncIteration:
            return None

    @override
    def run_count_by_version_id(
        self,
        agent_uid: int,
        from_date: datetime,
    ) -> AsyncIterator[TaskRunStorage.VersionRunCount]:
        raise NotImplementedError()

    @override
    def run_count_by_agent_uid(
        self,
        from_date: datetime,
        to_date: datetime | None = None,
        is_active: bool | None = None,
    ) -> AsyncIterator[TaskRunStorage.AgentRunCount]:
        raise NotImplementedError()

    @override
    def list_runs_for_memory_id(
        self,
        tenant_uid: int,
        task_uid: int,
        memory_id: str,
        limit: int = 10,
        timeout_ms: int | None = None,
    ) -> AsyncIterator[AgentRun]:
        raise NotImplementedError()

    @override
    def list_latest_runs(
        self,
        task_uid: int | None = None,
        since_date: datetime | None = None,
        is_active: bool = True,
        limit: int = 100,
    ) -> AsyncIterator[AgentRun]:
        raise NotImplementedError()

    @override
    def weekly_run_aggregate(self, week_count: int) -> AsyncIterator[WeeklyRunAggregate]:
        raise NotImplementedError()
