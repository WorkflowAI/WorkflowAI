from collections.abc import Sequence
from datetime import date, datetime
from typing import Any, AsyncIterator, NamedTuple, NotRequired, Protocol, TypedDict

from core.domain.agent_run import AgentRun, AgentRunBase
from core.domain.search_query import SearchQuery
from core.domain.task_run_aggregate_per_day import TaskRunAggregatePerDay
from core.domain.task_run_query import SerializableTaskRunField, SerializableTaskRunQuery
from core.storage import TaskTuple


class TokenCounts(TypedDict):
    average_prompt_tokens: float
    average_completion_tokens: float
    count: int


class RunAggregate(TypedDict):
    average_cost_usd: NotRequired[float | None]
    average_duration_seconds: NotRequired[float | None]
    total_run_count: int
    failed_run_count: NotRequired[int | None]
    eval_hashes: Sequence[str]


class WeeklyRunAggregate(NamedTuple):
    start_of_week: date
    run_count: int
    overhead_ms: int


class TaskRunSystemStorage(Protocol):
    def list_runs_for_memory_id(
        self,
        tenant_uid: int,
        task_uid: int,
        memory_id: str,
        limit: int = 10,
        timeout_ms: int | None = None,
    ) -> AsyncIterator[AgentRun]: ...

    def weekly_run_aggregate(self, week_count: int) -> AsyncIterator[WeeklyRunAggregate]: ...


class TaskRunStorage(TaskRunSystemStorage):
    def aggregate_task_run_costs(
        self,
        task_uid: int | None,
        query: SerializableTaskRunQuery,
        timeout_ms: int = 60_000,
    ) -> AsyncIterator[TaskRunAggregatePerDay]: ...

    async def aggregate_token_counts(
        self,
        task_id: TaskTuple,
        task_schema_id: int,
        excluded_models: list[str] | None = None,
        included_models: list[str] | None = None,
        maxTimeMS: int = 1_000,
    ) -> TokenCounts: ...

    def search_task_runs(
        self,
        task_uid: TaskTuple,
        search_fields: list[SearchQuery] | None,
        limit: int,
        offset: int,
        timeout_ms: int = 60_000,
    ) -> AsyncIterator[AgentRunBase]: ...

    async def count_filtered_task_runs(
        self,
        task_uid: TaskTuple,
        search_fields: list[SearchQuery] | None,
        timeout_ms: int = 60_000,
    ) -> int | None: ...

    async def aggregate_runs(
        self,
        task_id: TaskTuple,
        task_schema_id: int,
        task_input_hashes: set[str],
        group_ids: set[str] | None,
    ) -> dict[str, RunAggregate]:
        """Aggregate runs by version_ids

        Args:
            task_uid (int): The task uid
            task_schema_id (int): The task schema id
            task_input_hashes (set[str]): The task input hashes
            group_ids (set[str] | None): The version ids to filter by

        Returns:
            dict[str, RunAggregate]: A dictionary of version_id to run aggregate
        """
        ...

    async def store_task_run(self, task_run: AgentRun) -> AgentRun: ...

    async def fetch_task_run_resource(
        self,
        task_id: TaskTuple,
        id: str,
        include: set[SerializableTaskRunField] | None = None,
        exclude: set[SerializableTaskRunField] | None = None,
    ) -> AgentRun: ...

    def fetch_task_run_resources(
        self,
        task_uid: int,
        query: SerializableTaskRunQuery,
        timeout_ms: int | None = None,
    ) -> AsyncIterator[AgentRun]:
        """Fetch task runs based on the provided query. The query page token should be updated in page"""
        ...

    def aggregate_task_metadata_fields(
        self,
        task_id: TaskTuple,
        exclude_prefix: str | None = None,
    ) -> AsyncIterator[tuple[str, list[Any]]]: ...

    async def fetch_cached_run(
        self,
        task_id: TaskTuple,
        task_schema_id: int,
        task_input_hash: str,
        group_id: str,
        timeout_ms: int | None,
        success_only: bool = True,
    ) -> AgentRun | None: ...

    class VersionRunCount(NamedTuple):
        version_id: str
        run_count: int

    def run_count_by_version_id(self, agent_uid: int, from_date: datetime) -> AsyncIterator[VersionRunCount]: ...

    class AgentRunCount(NamedTuple):
        agent_uid: int
        run_count: int
        total_cost_usd: float

    def run_count_by_agent_uid(
        self,
        from_date: datetime,
        to_date: datetime | None = None,
        is_active: bool | None = None,
    ) -> AsyncIterator[AgentRunCount]: ...

    def list_latest_runs(
        self,
        task_uid: int | None = None,
        since_date: datetime | None = None,
        is_active: bool = True,
        limit: int = 100,
    ) -> AsyncIterator[AgentRun]: ...

    def search_tenant_runs(
        self,
        tenant_uid: int,
        search_fields: list[SearchQuery] | None,
        task_uids: set[int] | None,
        limit: int,
        offset: int,
        timeout_ms: int = 60_000,
    ) -> AsyncIterator[AgentRunBase]:
        """
        Search runs across multiple agents within a tenant.

        Args:
            tenant_uid: The tenant UID to search within
            search_fields: Optional search field filters
            task_uids: Optional set of task UIDs to filter by (agent filtering)
            limit: Maximum number of results
            offset: Number of results to skip
            timeout_ms: Query timeout in milliseconds

        Returns:
            Async iterator of AgentRunBase objects
        """
        ...

    async def count_tenant_filtered_runs(
        self,
        tenant_uid: int,
        search_fields: list[SearchQuery] | None,
        task_uids: set[int] | None,
        timeout_ms: int = 60_000,
    ) -> int | None:
        """
        Count runs across multiple agents within a tenant matching the given filters.

        Args:
            tenant_uid: The tenant UID to search within
            search_fields: Optional search field filters
            task_uids: Optional set of task UIDs to filter by (agent filtering)
            timeout_ms: Query timeout in milliseconds

        Returns:
            Count of matching runs, or None if count cannot be determined
        """
        ...
