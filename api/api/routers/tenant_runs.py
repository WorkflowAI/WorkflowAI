from datetime import datetime
from logging import getLogger
from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from api.dependencies.security import RequiredUserOrganizationDep
from api.dependencies.services import (
    RunFeedbackGeneratorDep,
    RunsSearchServiceDep,
    RunsServiceDep,
)
from api.schemas.version_properties import ShortVersionProperties
from api.tags import RouteTags
from core.domain.agent_run import AgentRunBase
from core.domain.page import Page
from core.domain.search_query import FieldQuery
from core.domain.task_group import TaskGroup

router = APIRouter(prefix="/v1/{tenant}/runs", tags=[RouteTags.RUNS])

_logger = getLogger(__name__)


class SearchTenantRunsRequest(BaseModel):
    """Request model for searching runs across all agents in a tenant"""

    field_queries: list[FieldQuery] | None = Field(
        default=None,
        description="Optional list of field queries for searching task runs across all agents",
    )

    agent_ids: list[str] | None = Field(
        default=None,
        description="Optional list of agent IDs to filter by. If not provided, searches across all agents",
    )

    limit: int = Field(default=20, ge=1, le=100, description="Number of runs to return (max 100)")
    offset: int = Field(default=0, ge=0, description="Number of runs to skip for pagination")


class TenantRunItemV1(BaseModel):
    """A run item for tenant-wide listing with agent context"""

    id: str = Field(description="the id of the task run")
    agent_id: str = Field(description="the id of the agent that created this run")
    task_schema_id: int = Field(description="The id of the task run's schema")

    class Version(BaseModel):
        id: str = Field(
            description="The id of the version. Either a semantic version i-e 10.1 or a 32 character hexadecimal string",
        )
        iteration: int = Field(
            description="The iteration of the version. Use id instead.",
            deprecated=True,
        )
        properties: ShortVersionProperties = Field(description="The properties of the version")

        @classmethod
        def from_domain(cls, version: TaskGroup):
            return cls(
                id=version.id,
                iteration=version.iteration,
                properties=ShortVersionProperties.from_domain(version.properties),
            )

    version: Version
    status: str  # "success" | "failure"
    duration_seconds: float | None
    cost_usd: float | None

    created_at: datetime = Field(description="The time the task run was created")

    task_input_preview: str = Field(description="A preview of the input data")
    task_output_preview: str = Field(description="A preview of the output data")

    user_review: str | None = None  # "positive" | "negative" | None
    ai_review: str | None = None  # "positive" | "negative" | "unsure" | "in_progress" | None

    class Error(BaseModel):
        code: str
        message: str

    error: Error | None

    feedback_token: str = Field(
        description="A signed token that can be used to post feedback from a client side application",
    )

    @classmethod
    def from_domain(cls, run: AgentRunBase, feedback_token: str):
        return cls(
            id=run.id,
            agent_id=run.task_id,  # task_id is the agent_id in the domain
            task_input_preview=run.task_input_preview,
            task_output_preview=run.task_output_preview,
            task_schema_id=run.task_schema_id,
            version=cls.Version.from_domain(run.group),
            status=run.status,
            error=cls.Error(code=run.error.code, message=run.error.message) if run.error else None,
            duration_seconds=run.duration_seconds,
            cost_usd=run.cost_usd,
            created_at=run.created_at,
            user_review=run.user_review,
            ai_review=run.ai_review,
            feedback_token=feedback_token,
        )


@router.post("/search", response_model_exclude_none=True)
async def search_tenant_runs(
    request: SearchTenantRunsRequest,
    service: RunsSearchServiceDep,
    user_org: RequiredUserOrganizationDep,
    feedback_token_generator: RunFeedbackGeneratorDep,
) -> Page[TenantRunItemV1]:
    """
    Search runs across all agents in a tenant.

    This endpoint allows searching for runs across multiple agents within a tenant,
    providing a tenant-wide view of AI agent executions.

    **Performance Note**: This endpoint queries across all agents in the tenant,
    which may be slower than agent-specific searches due to Clickhouse ordering
    optimization being by agent_id. For optimal performance, consider:
    1. Using time-based filters to limit the search scope
    2. Limiting the number of results with the `limit` parameter
    3. Filtering by specific `agent_ids` when possible
    """
    return await service.search_tenant_runs(
        tenant_uid=user_org.uid,
        field_queries=request.field_queries,
        agent_ids=request.agent_ids,
        limit=request.limit,
        offset=request.offset,
        map_fn=lambda run: TenantRunItemV1.from_domain(run, feedback_token_generator(run.id)),
    )


@router.get("/agents", response_model_exclude_none=True)
async def get_tenant_agents_with_runs(
    user_org: RequiredUserOrganizationDep,
    runs_service: RunsServiceDep,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> list[dict[str, Any]]:
    """
    Get all agents in the tenant that have runs in the specified time period.

    This endpoint provides a summary of agents with their run counts and latest activity,
    useful for understanding which agents are active in the tenant.
    """
    return await runs_service.get_tenant_agents_summary(
        tenant_uid=user_org.uid,
        days=days,
    )
