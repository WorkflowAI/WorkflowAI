import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from api.services._utils import apply_reviews
from core.domain.agent_run import AgentRunBase
from core.domain.errors import BadRequestError
from core.domain.major_minor import MajorMinor
from core.domain.models import Model
from core.domain.page import Page
from core.domain.search_query import (
    FieldQuery,
    ReviewSearchOptions,
    SearchField,
    SearchFieldOption,
    SearchOperationBetween,
    SearchOperationSingle,
    SearchOperator,
    SearchQueryNested,
    SearchQuerySimple,
    SimpleSearchField,
    SingleValueOperator,
    StatusSearchOptions,
)
from core.domain.task_group import TaskGroupQuery
from core.domain.version_environment import VersionEnvironment
from core.storage import TaskTuple
from core.storage.backend_storage import BackendStorage
from core.storage.task_group_storage import TaskGroupStorage
from core.storage.task_run_storage import TaskRunStorage
from core.utils.generics import BM
from core.utils.schemas import FieldType, JsonSchema


class RunsSearchService:
    def __init__(
        self,
        storage: BackendStorage,
    ):
        self._storage = storage
        self._logger = logging.getLogger(__name__)

    @classmethod
    def _review_search_field(cls):
        return SearchFieldOption(
            field_name=SearchField.REVIEW,
            operators=[SearchOperator.IS],
            # TODO: enum for review possibility should be elsewhere
            suggestions=[o.value for o in ReviewSearchOptions],
            type="string",
        )

    @classmethod
    def _schema_search_field(cls, latest_schema_idx: int):
        return SearchFieldOption(
            field_name=SearchField.SCHEMA_ID,
            operators=SearchOperator.number_operators(),
            suggestions=list(i for i in range(latest_schema_idx, 0, -1)) or None,
            type="number",
        )

    _DEPLOYMENT_MAP = {
        "Production": VersionEnvironment.PRODUCTION,
        "Staging": VersionEnvironment.STAGING,
        "Dev": VersionEnvironment.DEV,
    }

    @classmethod
    def _version_search_field(cls, all_semvers: list[MajorMinor] | None):
        base = list(cls._DEPLOYMENT_MAP.keys())
        if all_semvers:
            base.extend(semver.to_string() for semver in sorted(all_semvers, key=lambda x: (-x.major, -x.minor)))
        return SearchFieldOption(
            field_name=SearchField.VERSION,
            operators=SearchOperator.equals_operators(),
            suggestions=base,
            type="string",
        )

    @classmethod
    def _map_version(cls, version: str):
        try:
            return cls._DEPLOYMENT_MAP[version]
        except KeyError:
            pass

        if version.isdigit():
            return int(version)

        if semver := MajorMinor.from_string(version):
            return semver

        return version

    @classmethod
    def _price_search_field(cls):
        return SearchFieldOption(
            field_name=SearchField.PRICE,
            operators=SearchOperator.number_operators(),
            type="number",
        )

    @classmethod
    def _latency_search_field(cls):
        return SearchFieldOption(
            field_name=SearchField.LATENCY,
            operators=SearchOperator.number_operators(),
            type="number",
        )

    @classmethod
    def _status_search_field(cls):
        return SearchFieldOption(
            field_name=SearchField.STATUS,
            operators=[SearchOperator.IS],
            type="string",
            suggestions=[o.value for o in StatusSearchOptions],
        )

    # TODO[search]:  make sure we return temperaturs within brackets
    # def _process_temperature_field_query(self, field_query: FieldQuery) -> FieldQuery:
    #     temp_value = (
    #         self.TEMPERATURE_MAP[field_query.values[0]]
    #         if field_query.values[0] in self.TEMPERATURE_MAP
    #         else float(field_query.values[0])
    #     )

    #     lower_bound = max(0.0, round(temp_value - 0.05, 2))
    #     upper_bound = min(1.0, round(temp_value + 0.04, 2))
    #     field_query.values = [lower_bound, upper_bound]

    #     if field_query.operator == SearchOperator.IS:
    #         field_query.operator = SearchOperator.IS_BETWEEN
    #     elif field_query.operator == SearchOperator.IS_NOT:
    #         field_query.operator = SearchOperator.IS_NOT_BETWEEN

    #     return field_query
    @classmethod
    def _temperature_to_string(cls, temperature: float):
        match temperature:
            case 0:
                return "Precise"
            case 0.5:
                return "Balanced"
            case 1.0:
                return "Creative"
            case _:
                return f"{temperature:.1f}"

    @classmethod
    def _temperature_to_float(cls, temperature: str):
        match temperature:
            case "Precise":
                return 0.0
            case "Balanced":
                return 0.5
            case "Creative":
                return 1.0
            case _:
                try:
                    return float(temperature)
                except ValueError:
                    raise BadRequestError(f"Invalid temperature: {temperature}")

    @classmethod
    def _temperature_search_field(cls):
        return SearchFieldOption(
            field_name=SearchField.TEMPERATURE,
            operators=SearchOperator.equals_operators(),
            type="string",
            suggestions=list(cls._temperature_to_string(i / 10) for i in range(0, 11)),
        )

    @classmethod
    def _model_search_field(cls):
        return SearchFieldOption(
            field_name=SearchField.MODEL,
            operators=SearchOperator.string_operators(),
            type="string",
            suggestions=[m.value for m in Model],
        )

    _SOURCE_MAP = {
        "my app": True,
        "WorkflowAI": False,
    }

    @classmethod
    def _map_source(cls, source: str):
        return cls._SOURCE_MAP[source]

    @classmethod
    def _source_search_field(cls):
        return SearchFieldOption(
            field_name=SearchField.SOURCE,
            operators=SearchOperator.equals_operators(),
            type="string",
            # TODO: enum for source possibility should be elsewhere
            suggestions=list(cls._SOURCE_MAP.keys()),
        )

    @classmethod
    def _time_search_field(cls):
        return SearchFieldOption(
            field_name=SearchField.TIME,
            operators=SearchOperator.date_operators(),
            type="date",
        )

    _EMPTY_KEYWORD = "Empty"

    @classmethod
    def _fields_from_schema(cls, field: SearchField, schema: dict[str, Any]):
        for key, field_type, _ in JsonSchema(schema).fields_iterator([]):
            suggestions: list[Any] | None = None

            match field_type:
                case "number" | "integer":
                    operators = SearchOperator.number_operators()
                    suggestions = [cls._EMPTY_KEYWORD]
                case "string":
                    operators = SearchOperator.string_operators()
                    suggestions = [cls._EMPTY_KEYWORD]
                case "boolean":
                    operators = SearchOperator.equals_operators()
                    suggestions = [cls._EMPTY_KEYWORD, True, False]
                case "date":
                    operators = SearchOperator.date_operators()
                case "array":
                    field_type = "array_length"
                    key = [*key, "length"]
                    operators = SearchOperator.number_operators()
                    suggestions = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
                case _:
                    # Otherwise the field is not supported
                    continue

            yield SearchFieldOption(
                field_name=field,
                type=field_type,
                operators=operators,
                suggestions=suggestions,
                key_path=".".join(key).replace(".[]", "[]"),
            )
        # Whenever we are dealing with messages or message, we allow searching through the raw input / output
        # TODO: we should use the SerializableTaskIO functions instead
        # TODO: we should add tests for searching through messages
        if (format := schema.get("format")) and format in {"messages", "message"}:
            yield SearchFieldOption(
                field_name=field,
                type="string",
                operators=[SearchOperator.CONTAINS, SearchOperator.NOT_CONTAINS],
            )

    @classmethod
    async def _list_all_semvers(cls, task_groups: TaskGroupStorage, task_id: str) -> list[MajorMinor]:
        return [
            g.semver
            async for g in task_groups.list_task_groups(
                TaskGroupQuery(task_id=task_id, is_saved=True),
                include=["semver"],
            )
            if g.semver  # should always be true anyway given the search above
        ]

    @classmethod
    async def _task_metadata_fields(cls, storage: TaskRunStorage, task_id: TaskTuple):
        return [
            SearchFieldOption(
                field_name=SearchField.METADATA,
                type="string",
                operators=SearchOperator.string_operators(),
                # We only return the first 30 suggestions to avoid overwhelming the frontend
                suggestions=suggestions[:30],
                key_path=field,
            )
            async for field, suggestions in storage.aggregate_task_metadata_fields(
                task_id,
                exclude_prefix="workflowai.",
            )
        ]

    async def schemas_search_fields(self, task_id: TaskTuple, task_schema_id: int):
        task_variant, latest_schema_idx, metadata_fields, all_semvers = await asyncio.gather(
            self._storage.task_variant_latest_by_schema_id(task_id[0], task_schema_id),
            self._storage.get_latest_idx(task_id[0]),
            self._task_metadata_fields(self._storage.task_runs, task_id),
            self._list_all_semvers(self._storage.task_groups, task_id[0]),
            return_exceptions=True,
        )

        if isinstance(latest_schema_idx, BaseException):
            self._logger.exception("Error getting latest schema idx", exc_info=latest_schema_idx)
            yield self._schema_search_field(0)
        else:
            yield self._schema_search_field(latest_schema_idx)

        if isinstance(all_semvers, BaseException):
            self._logger.exception("Error getting all semvers", exc_info=all_semvers)
            yield self._version_search_field(None)
        else:
            yield self._version_search_field(all_semvers)

        yield self._price_search_field()
        yield self._latency_search_field()
        yield self._status_search_field()
        yield self._temperature_search_field()
        yield self._model_search_field()
        yield self._source_search_field()
        yield self._time_search_field()
        yield self._review_search_field()

        if isinstance(task_variant, BaseException):
            self._logger.exception("Error getting task variant", exc_info=task_variant)
        else:
            # yield from is not allowed in an async function
            for f in self._fields_from_schema(SearchField.INPUT, task_variant.input_schema.json_schema):
                yield f
            for f in self._fields_from_schema(SearchField.OUTPUT, task_variant.output_schema.json_schema):
                yield f

        if isinstance(metadata_fields, BaseException):
            self._logger.exception("Error getting metadata fields", exc_info=metadata_fields)
        else:
            for f in metadata_fields:
                yield f

    @classmethod
    def _operation_from_query(cls, field_query: FieldQuery, map_value: Callable[[Any], Any]):
        if field_query.operator == SearchOperator.IS_NOT_BETWEEN or field_query.operator == SearchOperator.IS_BETWEEN:
            if not len(field_query.values) == 2:
                raise BadRequestError(f"Invalid number of values for {field_query.operator}")
            v1, v2 = field_query.values
            try:
                return SearchOperationBetween(field_query.operator, (map_value(v1), map_value(v2)))
            except (ValueError, KeyError, TypeError) as e:
                raise BadRequestError(f"Invalid values for {field_query.operator}: {e}")

        if not field_query.values:
            raise BadRequestError(f"No values provided for {field_query.operator}")

        value = field_query.values[0]

        if value == cls._EMPTY_KEYWORD:
            match field_query.operator:
                case SearchOperator.IS:
                    return SearchOperationSingle(SearchOperator.IS_EMPTY, None)
                case SearchOperator.IS_NOT:
                    return SearchOperationSingle(SearchOperator.IS_NOT_EMPTY, None)
                case _:
                    # Maybe someone is looking for the string "Empty" ?
                    pass

        try:
            return SearchOperationSingle(field_query.operator, map_value(value))
        except (ValueError, KeyError, TypeError) as e:
            raise BadRequestError(f"Invalid value for {field_query.operator}: {e}")

    @classmethod
    def _default_type_mapper(cls, field_type: FieldType | None) -> Callable[[Any], Any]:  # noqa: C901
        match field_type:
            case None:
                return str
            case "number":
                return float
            case "integer":
                return int
            case "string":
                return str
            case "boolean":
                return bool
            case "date":
                return datetime.fromisoformat
            case "array_length":
                return int
            case "object":
                raise ValueError("Object fields are not supported")
            case "null":
                raise ValueError("Null fields are not supported")
            case "array":
                raise ValueError("Array fields are not supported")

    @classmethod
    def _nested_field_query(cls, field_query: FieldQuery):
        name = field_query.field_name
        if field_query.type == "array_length":
            name = name.removesuffix(".length")

        splits = name.split(".", 1)
        if len(splits) != 2:
            return None

        try:
            name = SearchField(splits[0])
        except ValueError:
            return None

        if name not in {SearchField.INPUT, SearchField.OUTPUT, SearchField.METADATA}:
            return None

        return SearchQueryNested(
            name,  # pyright: ignore [reportArgumentType]
            field_query.type,
            splits[1],
            cls._operation_from_query(field_query, cls._default_type_mapper(field_query.type)),
        )

    async def _review_query(self, task_id: str, query: FieldQuery):
        try:
            option = ReviewSearchOptions(query.values[0])
        except ValueError:
            raise BadRequestError(f"Invalid review option: {query.values[0]}")
        eval_hashes = await self._storage.reviews.eval_hashes_for_review(task_id, option)
        return SearchQuerySimple(SearchField.EVAL_HASH, SearchOperationSingle(SearchOperator.IS, eval_hashes), "string")

    async def _process_field_query(self, task_id: str, field_queries: list[FieldQuery]):  # noqa: C901
        def _map_simple_query(field: SimpleSearchField, field_query: FieldQuery, map_value: Callable[[Any], Any]):
            return SearchQuerySimple(field, self._operation_from_query(field_query, map_value), field_query.type)

        version_queries: dict[MajorMinor, SingleValueOperator] = {}
        for field_query in field_queries:
            match field_query.field_name:
                case SearchField.REVIEW:
                    # TODO[search]: we should check if there are multiple review field queries
                    # Edge case though since the review search options are mutually exclusive
                    yield await self._review_query(task_id, field_query)
                    continue
                case SearchField.SCHEMA_ID:
                    yield _map_simple_query(SearchField.SCHEMA_ID, field_query, int)
                    continue
                case SearchField.VERSION:
                    operation = self._operation_from_query(field_query, self._map_version)
                    if not isinstance(operation, SearchOperationSingle):
                        raise BadRequestError(f"Invalid operation for version: {operation}")
                    if isinstance(operation.value, MajorMinor):
                        version_queries[operation.value] = operation.operator
                    else:
                        yield SearchQuerySimple(SearchField.VERSION, operation, field_query.type)
                    continue
                case SearchField.PRICE:
                    yield _map_simple_query(SearchField.PRICE, field_query, float)
                    continue
                case SearchField.LATENCY:
                    yield _map_simple_query(SearchField.LATENCY, field_query, float)
                    continue
                case SearchField.TEMPERATURE:
                    yield _map_simple_query(SearchField.TEMPERATURE, field_query, self._temperature_to_float)
                    continue
                case SearchField.MODEL:
                    yield _map_simple_query(SearchField.MODEL, field_query, str)
                    continue
                case SearchField.SOURCE:
                    yield _map_simple_query(SearchField.SOURCE, field_query, self._map_source)
                    continue
                case SearchField.TIME:
                    yield _map_simple_query(SearchField.TIME, field_query, datetime.fromisoformat)
                    continue
                case SearchField.STATUS:
                    yield _map_simple_query(SearchField.STATUS, field_query, StatusSearchOptions)
                    continue
                case SearchField.EVAL_HASH:
                    # This should not be called directly
                    yield _map_simple_query(SearchField.EVAL_HASH, field_query, lambda x: x)
                    continue
                case SearchField.INPUT | SearchField.OUTPUT:
                    # The entire input / output will be searched as string
                    yield _map_simple_query(field_query.field_name, field_query, lambda x: x)
                    continue
                case _:
                    pass
            if nested := self._nested_field_query(field_query):
                yield nested
                continue

            raise BadRequestError(f"Unsupported field: {field_query.field_name}")

        version_map = {
            g.semver: g.id
            async for g in self._storage.task_groups.list_task_groups(
                TaskGroupQuery(task_id=task_id, semvers=set(version_queries.keys())),
                include=["semver", "id"],
            )
        }
        for semver, operator in version_queries.items():
            try:
                version_id = version_map[semver]
                yield SearchQuerySimple(SearchField.VERSION, SearchOperationSingle(operator, version_id), "string")
            except KeyError:
                raise BadRequestError(f"Version {semver} not found")

    async def search_task_runs(
        self,
        task_uid: TaskTuple,
        field_queries: list[FieldQuery] | None,
        limit: int,
        offset: int,
        map: Callable[[AgentRunBase], BM],
    ) -> Page[BM]:
        fields = [f async for f in self._process_field_query(task_uid[0], field_queries)] if field_queries else None

        task_runs_storage = self._storage.task_runs

        async def _fetch_count():
            return await task_runs_storage.count_filtered_task_runs(task_uid, fields, timeout_ms=20_000)

        async def _fetch_runs():
            runs = [
                item
                async for item in self._storage.task_runs.search_task_runs(
                    task_uid,
                    fields,
                    limit,
                    offset,
                )
            ]
            # TODO[test]: add dedicated tests, for not it is tested through the runs service
            await apply_reviews(self._storage.reviews, task_uid[0], runs, self._logger)
            return [map(item) for item in runs]

        items, count = await asyncio.gather(_fetch_runs(), _fetch_count())
        return Page(items=items, count=count)

    async def search_tenant_runs(
        self,
        tenant_uid: int,
        field_queries: list[FieldQuery] | None,
        agent_ids: list[str] | None,
        limit: int,
        offset: int,
        map_fn: Callable[[AgentRunBase], BM],
    ) -> Page[BM]:
        """
        Search runs across multiple agents within a tenant.

        This method provides tenant-wide run search capability with optional agent filtering.
        Performance considerations:
        - Queries across all agents lose the task_uid ordering optimization
        - Consider using time-based filters and agent_ids filtering for better performance
        - Results are still ordered by (tenant_uid, created_at_date) which provides reasonable performance
        """
        # Convert agent_ids to task_uids for filtering if provided
        task_uids: set[int] | None = None
        if agent_ids:
            # Map agent_ids to task_uids using the tasks storage
            task_uid_map = {}
            try:
                # Use the proper storage interface to get task information
                for agent_id in agent_ids:
                    try:
                        # This will need to be implemented in the storage layer
                        # For now, we'll use a simpler approach that may need backend storage access
                        task_docs = await self._storage.find_task_by_id(agent_id)
                        if task_docs:
                            task_uid_map[agent_id] = task_docs.uid
                    except Exception:
                        # Skip invalid agent_ids
                        continue
            except Exception as e:
                self._logger.warning("Failed to map agent_ids to task_uids", extra={"error": str(e)})
                # If we can't map agent_ids, return empty result to be safe
                return Page(items=[], count=0)

            task_uids = {task_uid for task_uid in task_uid_map.values()}
            if not task_uids:
                # No valid agent_ids found, return empty result
                return Page(items=[], count=0)

        # Process field queries - similar to existing search but without task_uid constraint
        fields = [f async for f in self._process_tenant_field_query(field_queries)] if field_queries else None

        task_runs_storage = self._storage.task_runs

        async def _fetch_count():
            return await task_runs_storage.count_tenant_filtered_runs(
                tenant_uid,
                fields,
                task_uids,
                timeout_ms=20_000,
            )

        async def _fetch_runs():
            runs = [
                item
                async for item in task_runs_storage.search_tenant_runs(
                    tenant_uid,
                    fields,
                    task_uids,
                    limit,
                    offset,
                )
            ]
            # Apply reviews similar to the existing method
            if runs:
                # Group runs by task_id for efficient review loading
                runs_by_task = {}
                for run in runs:
                    task_id = run.task_id
                    if task_id not in runs_by_task:
                        runs_by_task[task_id] = []
                    runs_by_task[task_id].append(run)

                # Apply reviews for each task group
                for task_id, task_runs in runs_by_task.items():
                    await apply_reviews(self._storage.reviews, task_id, task_runs, self._logger)

            return [map_fn(item) for item in runs]

        items, count = await asyncio.gather(_fetch_runs(), _fetch_count())
        return Page(items=items, count=count)

    async def _process_tenant_field_query(self, field_queries: list[FieldQuery] | None):
        """
        Process field queries for tenant-wide searches.
        Similar to _process_field_query but without task_id scoping.
        """
        if not field_queries:
            return

        def _map_simple_query(field: SimpleSearchField, field_query: FieldQuery, map_value: Callable[[Any], Any]):
            return SearchQuerySimple(field, self._operation_from_query(field_query, map_value), field_query.type)

        version_queries: dict[MajorMinor, SingleValueOperator] = {}
        for field_query in field_queries:
            match field_query.field_name:
                case SearchField.REVIEW:
                    # Note: Review queries at tenant level need special handling
                    # as eval_hashes are task-specific
                    self._logger.warning("Review field queries not fully supported for tenant-wide searches")
                    continue
                case SearchField.SCHEMA_ID:
                    yield _map_simple_query(SearchField.SCHEMA_ID, field_query, int)
                    continue
                case SearchField.VERSION:
                    operation = self._operation_from_query(field_query, self._map_version)
                    if not isinstance(operation, SearchOperationSingle):
                        raise BadRequestError(f"Invalid operation for version: {operation}")
                    if isinstance(operation.value, MajorMinor):
                        version_queries[operation.value] = operation.operator
                    else:
                        yield SearchQuerySimple(SearchField.VERSION, operation, field_query.type)
                    continue
                case SearchField.PRICE:
                    yield _map_simple_query(SearchField.PRICE, field_query, float)
                    continue
                case SearchField.LATENCY:
                    yield _map_simple_query(SearchField.LATENCY, field_query, float)
                    continue
                case SearchField.TEMPERATURE:
                    yield _map_simple_query(SearchField.TEMPERATURE, field_query, self._temperature_to_float)
                    continue
                case SearchField.MODEL:
                    yield _map_simple_query(SearchField.MODEL, field_query, str)
                    continue
                case SearchField.SOURCE:
                    yield _map_simple_query(SearchField.SOURCE, field_query, self._map_source)
                    continue
                case SearchField.TIME:
                    yield _map_simple_query(SearchField.TIME, field_query, datetime.fromisoformat)
                    continue
                case SearchField.STATUS:
                    yield _map_simple_query(SearchField.STATUS, field_query, StatusSearchOptions)
                    continue
                case SearchField.EVAL_HASH:
                    # This should not be called directly
                    yield _map_simple_query(SearchField.EVAL_HASH, field_query, lambda x: x)
                    continue
                case SearchField.INPUT | SearchField.OUTPUT:
                    # The entire input / output will be searched as string
                    yield _map_simple_query(field_query.field_name, field_query, lambda x: x)
                    continue
                case _:
                    pass
            if nested := self._nested_field_query(field_query):
                yield nested
                continue

            raise BadRequestError(f"Unsupported field: {field_query.field_name}")

        # Handle version queries that need group_id mapping
        if version_queries:
            # For tenant-wide searches, we need to search across all task groups in the tenant
            # This is more complex than the single-task version
            self._logger.warning("Semver-based version queries are complex for tenant-wide searches and may be slow")
            # For now, we'll skip semver queries in tenant searches to avoid performance issues
            # TODO: Implement efficient semver queries for tenant-wide searches
