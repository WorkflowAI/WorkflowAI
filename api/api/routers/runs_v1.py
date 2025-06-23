from datetime import datetime
from logging import getLogger
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.dependencies.services import (
    ModelsServiceDep,
    RunFeedbackGeneratorDep,
    RunsSearchServiceDep,
    RunsServiceDep,
    VersionsServiceDep,
)
from api.dependencies.task_info import TaskInfoDep, TaskTupleDep
from api.schemas.api_tool_call_request import APIToolCallRequest
from api.schemas.reasoning_step import ReasoningStep
from api.schemas.version_properties import ShortVersionProperties
from api.services.runs.runs_service import LLMCompletionsResponse
from api.services.tool_call_service import ToolCallResultPreviewResponse, ToolCallService
from api.tags import RouteTags
from core.domain.agent_run import AgentRun, AgentRunBase
from core.domain.error_response import ErrorCode, ErrorResponse
from core.domain.page import Page
from core.domain.search_query import FieldQuery, SearchOperator
from core.domain.task_group import TaskGroup
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.types import AgentInput, AgentOutput
from core.storage import ObjectNotFoundException
from core.utils.iter_utils import safe_map_optional
from core.utils.schemas import FieldType
from core.utils.stream_response_utils import safe_streaming_response

router = APIRouter(prefix="/v1/{tenant}/agents/{agent_id}/runs", tags=[RouteTags.RUNS])

_logger = getLogger(__name__)


class SearchTaskRunsRequest(BaseModel):
    class Query(BaseModel):
        # Must be a valid keypath
        field_name: str = Field(pattern=r"^[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)*$")
        operator: SearchOperator
        values: list[Any]
        type: FieldType | None = None

    field_queries: list[FieldQuery] | None = Field(
        default=None,
        description="Optional list of field queries for searching task runs",
    )

    limit: int = 20
    offset: int = 0


class _BaseRunV1(BaseModel):
    id: str = Field(description="the id of the task run")
    task_id: str = Field(description="the id of the task")
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
    status: Literal["success", "failure"]
    duration_seconds: float | None
    cost_usd: float | None

    created_at: datetime = Field(description="The time the task run was created")

    user_review: Literal["positive", "negative"] | None
    ai_review: Literal["positive", "negative", "unsure", "in_progress"] | None

    class Feedback(BaseModel):
        outcome: Literal["positive", "negative"]
        annotation: Literal["resolved", "incorrect", "correct"] | None

    feedback: list[Feedback] | None = None

    feedback_token: str = Field(
        description="A signed token that can be used to post feedback from a client side application",
    )


class RunItemV1(_BaseRunV1):
    task_input_preview: str = Field(description="A preview of the input data")
    task_output_preview: str = Field(description="A preview of the output data")

    class Error(BaseModel):
        code: ErrorCode | str
        message: str

        @classmethod
        def from_domain(cls, error: ErrorResponse.Error):
            return cls(
                code=error.code,
                message=error.message,
            )

    error: Error | None

    @classmethod
    def from_domain(cls, run: AgentRunBase, feedback_token: str):
        return cls(
            id=run.id,
            task_id=run.task_id,
            task_input_preview=run.task_input_preview,
            task_output_preview=run.task_output_preview,
            task_schema_id=run.task_schema_id,
            version=cls.Version.from_domain(run.group),
            status=run.status,
            error=cls.Error.from_domain(run.error) if run.error else None,
            duration_seconds=run.duration_seconds,
            cost_usd=run.cost_usd,
            created_at=run.created_at,
            user_review=run.user_review,
            ai_review=run.ai_review,
            feedback_token=feedback_token,
        )


@router.post("/search", response_model_exclude_none=True)
async def search_runs(
    request: SearchTaskRunsRequest,
    service: RunsSearchServiceDep,
    task: TaskInfoDep,
    feedback_token_generator: RunFeedbackGeneratorDep,
) -> Page[RunItemV1]:
    if not task:
        raise ObjectNotFoundException("Task not found")
    return await service.search_task_runs(
        (task.task_id, task.uid),
        request.field_queries,
        request.limit,
        request.offset,
        lambda run: RunItemV1.from_domain(run, feedback_token_generator(run.id)),
    )


class RunV1(_BaseRunV1):
    task_input: AgentInput
    task_output: AgentOutput

    reasoning_steps: list[ReasoningStep] | None

    class Error(BaseModel):
        code: ErrorCode | str
        message: str

        details: dict[str, Any] | None

        @classmethod
        def from_domain(cls, error: ErrorResponse.Error):
            return cls(
                code=error.code,
                message=error.message,
                details=error.details,
            )

    error: Error | None

    tool_call_requests: list[APIToolCallRequest] | None = Field(
        description="Tool calls that should be executed client side.",
    )

    conversation_id: str | None

    # TODO: add details field that contains part of the internal metadata
    # see https://linear.app/workflowai/issue/WOR-5044/fetch-run-details-mcp-tool-missing-deployment-environment-information#comment-d84e92a4

    # TODO: Reference to documentation page about metadata: [URL will change soon]
    metadata: dict[str, Any] | None = Field(
        description="User defined metadata passed to the completion request",
    )

    @classmethod
    def from_domain_task_run(cls, run: AgentRun, feedback_token: str):
        return cls(
            id=run.id,
            task_id=run.task_id,
            task_input=run.task_input,
            task_output=run.task_output,
            task_schema_id=run.task_schema_id,
            version=cls.Version.from_domain(run.group),
            status=run.status,
            error=cls.Error.from_domain(run.error) if run.error else None,
            duration_seconds=run.duration_seconds,
            cost_usd=run.cost_usd,
            created_at=run.created_at,
            user_review=run.user_review,
            ai_review=run.ai_review,
            reasoning_steps=safe_map_optional(run.reasoning_steps, ReasoningStep.from_domain, logger=_logger),
            tool_call_requests=safe_map_optional(
                run.tool_call_requests,
                APIToolCallRequest.from_domain,
                logger=_logger,
            ),
            feedback_token=feedback_token,
            conversation_id=run.conversation_id,
            metadata=run.metadata,
        )


@router.get(
    "/latest",
    description="Retrieve the latest run for a task and optionally a schema",
    response_model_exclude_none=True,
)
async def get_latest_run(
    task_tuple: TaskTupleDep,
    runs_service: RunsServiceDep,
    feedback_token_generator: RunFeedbackGeneratorDep,
    schema_id: Annotated[int | None, Query(ge=1)] = None,
    is_success: Annotated[bool | None, Query()] = None,
) -> RunV1:
    run = await runs_service.latest_run(task_tuple, schema_id, is_success)
    return RunV1.from_domain_task_run(run, feedback_token_generator(run.id))


@router.get("/{run_id}", response_model_exclude_none=True)
async def get_run(
    task_tuple: TaskTupleDep,
    run_id: str,
    runs_service: RunsServiceDep,
    feedback_token_generator: RunFeedbackGeneratorDep,
) -> RunV1:
    run = await runs_service.run_by_id(task_tuple, run_id, exclude={"llm_completions"})
    return RunV1.from_domain_task_run(run, feedback_token_generator(run.id))


# We use response_model_exclude_none to hide the empty field in standard messages, payload
# (ex: is tool call input when not needed in the tool call response, when there is an id for the tool call.)
@router.get("/{run_id}/completions", response_model_exclude_none=True)
async def get_llm_completions(
    task_tuple: TaskTupleDep,
    run_id: str,
    runs_service: RunsServiceDep,
) -> LLMCompletionsResponse:
    return await runs_service.llm_completions_by_id(task_tuple, run_id)


class CreateVersionResponse(BaseModel):
    id: str
    # TODO[versionsv1]: Remove this once the usage of iteration is removed
    iteration: int = Field(deprecated=True)
    semver: tuple[int, int] | None
    properties: TaskGroupProperties

    @classmethod
    def from_domain(cls, version: TaskGroup):
        return cls(
            id=version.id,
            iteration=version.iteration,
            semver=version.semver,
            properties=version.properties,
        )


@router.post("/{run_id}/version/save")
async def save_run_version(
    task_tuple: TaskTupleDep,
    run_id: str,
    runs_service: RunsServiceDep,
    versions_service: VersionsServiceDep,
) -> CreateVersionResponse:
    version_id = (await runs_service.run_by_id(task_tuple, run_id, include={"version_id"})).group.id
    grp = await versions_service.save_version(task_tuple[0], version_id)
    return CreateVersionResponse.from_domain(grp)


@router.post(
    "/{run_id}/tools/previews/result",
    responses={
        200: {
            "content": {
                "text/event-stream": {
                    "schema": ToolCallResultPreviewResponse.model_json_schema(),
                },
            },
        },
    },
)
async def get_tool_call_result_preview(
    task_tuple: TaskTupleDep,
    run_id: str,
    runs_service: RunsServiceDep,
    versions_service: VersionsServiceDep,
    models_service: ModelsServiceDep,
) -> StreamingResponse:
    run = await runs_service.run_by_id(task_tuple, run_id)
    version = await versions_service.get_version(task_tuple, run.group.id, models_service)

    return safe_streaming_response(
        lambda: ToolCallService().stream_tool_call_result_preview(run, version),
    )
