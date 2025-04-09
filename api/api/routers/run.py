import logging
import uuid
from collections.abc import Sequence
from typing import Any, Literal, override

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field, TypeAdapter, field_validator, model_validator

from api.dependencies.analytics import UserPropertiesDep
from api.dependencies.path_params import TaskID, TaskSchemaID
from api.dependencies.run import AuthorTenantDep
from api.dependencies.security import (
    ProviderSettingsDep,
    UserOrganizationDep,
    key_ring_dependency,
    tenant_dependency,
)
from api.dependencies.services import (
    FileStorageDep,
    GroupServiceDep,
    RunFeedbackGeneratorDep,
    RunServiceDep,
    RunsServiceDep,
)
from api.dependencies.task_ban import check_task_banned_dependency
from api.dependencies.task_info import TaskTupleDep
from api.errors import prettify_errors
from api.routers._common import DeprecatedVersionReference
from api.schemas.api_tool_call_request import APIToolCallRequest
from api.schemas.reasoning_step import ReasoningStep
from api.tags import RouteTags
from api.utils import get_start_time
from core.domain.agent_run import AgentRun
from core.domain.major_minor import MajorMinor
from core.domain.run_output import RunOutput
from core.domain.task_group import TaskGroupIdentifier
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.tool_call import ToolCall, ToolCallOutput
from core.domain.types import CacheUsage
from core.domain.version_environment import VersionEnvironment
from core.domain.version_reference import VersionReference as DomainVersionReference
from core.utils.fields import id_factory
from core.utils.iter_utils import safe_map_optional
from core.utils.models.previews import compute_preview
from core.utils.uuid import is_uuid7, uuid7

router = APIRouter(
    dependencies=[Depends(tenant_dependency), Depends(key_ring_dependency), Depends(check_task_banned_dependency)],
    tags=[RouteTags.RUN],
)
task_router = APIRouter(deprecated=True, include_in_schema=False)
agent_router = APIRouter()

_logger = logging.getLogger("RunRouter")


VersionReference = int | VersionEnvironment | TaskGroupProperties | TaskGroupIdentifier


def version_reference_to_domain(version: VersionReference) -> DomainVersionReference:
    if isinstance(version, TaskGroupProperties):
        return DomainVersionReference(properties=version)

    if isinstance(version, str):
        try:
            return DomainVersionReference(version=VersionEnvironment(version))
        except ValueError:
            pass

        if semver := MajorMinor.from_string(version):
            return DomainVersionReference(version=semver)

        # the hash is a 16 byte hex string so it could technically be a very long number
        if len(version) == 32:
            return DomainVersionReference(version=version)

        try:
            return DomainVersionReference(version=int(version))
        except ValueError:
            pass

    return DomainVersionReference(version=version)


class RunRequest(BaseModel):
    task_input: dict[str, Any]

    version: VersionReference

    id: str = Field(
        default_factory=lambda: str(uuid7()),
        description="An optional id, must be a valid uuid7. If not provided a uuid7 will be generated",
    )

    stream: bool = False

    use_cache: CacheUsage = "auto"

    metadata: dict[str, Any] | None = Field(default=None, description="Additional metadata to store with the task run.")

    private_fields: set[Literal["task_input", "task_input"] | str] | None = Field(
        default=None,
        description="Fields marked as private will not be saved, none by default.",
    )

    @field_validator("id")
    def validate_id(cls, v: str):
        # TODO: remove if there are no warnings
        try:
            uid = uuid.UUID(v)
        except ValueError:
            _logger.warning("Invalid uuid for run id", extra={"run_id": v})
            return v

        if not is_uuid7(uid):
            _logger.warning("UUID is not a valid uuid7", extra={"run_id": v})

        return v


class _RunResponseCommon(BaseModel):
    id: str
    task_output: dict[str, Any]

    tool_call_requests: list[APIToolCallRequest] | None = Field(
        description="Tool calls that should be executed client side.",
    )

    reasoning_steps: list[ReasoningStep] | None = Field(
        description="A list of reasoning steps that were taken during the run."
        "Available for reasoning models or when the version used has chain of thoughts enabled",
    )


class RunResponse(_RunResponseCommon):
    class Version(BaseModel):
        id: str
        properties: TaskGroupProperties

    version: Version
    duration_seconds: float | None
    cost_usd: float | None

    metadata: dict[str, Any] | None

    class ToolCall(BaseModel):
        id: str
        name: str = Field(description="The name of the tool that was executed")
        input_preview: str = Field(description="A preview of the input to the tool")
        output_preview: str | None = Field(description="A preview of the output of the tool")
        error: str | None = Field(description="The error that occurred during the tool call if any")

        @classmethod
        def from_domain(cls, tool_call: ToolCall):
            # TODO: preview result as well
            return cls(
                id=tool_call.id,
                name=tool_call.tool_name,
                input_preview=tool_call.input_preview,
                output_preview=compute_preview(tool_call.result) if tool_call.result else None,
                error=tool_call.error if tool_call.error else None,
            )

    tool_calls: list[ToolCall] | None = Field(
        description="A list of tools that were executed during the run.",
    )

    feedback_token: str = Field(
        description="A signed token that can be used to post feedback from a client side application",
    )

    @classmethod
    def from_domain(cls, task_run: AgentRun, feedback_token: str):
        """
        Converts a domain object to a stored task run
        """
        return cls(
            id=task_run.id,
            task_output=task_run.task_output,
            version=cls.Version(
                id=task_run.group.id,
                properties=task_run.group.properties
                if task_run.version_changed
                else task_run.group.properties.simplified(),
            ),
            duration_seconds=task_run.duration_seconds,
            cost_usd=task_run.cost_usd,
            metadata=task_run.metadata,
            tool_calls=safe_map_optional(task_run.tool_calls, cls.ToolCall.from_domain, logger=_logger),
            tool_call_requests=safe_map_optional(
                task_run.tool_call_requests,
                APIToolCallRequest.from_domain,
                logger=_logger,
            ),
            reasoning_steps=safe_map_optional(task_run.reasoning_steps, ReasoningStep.from_domain, logger=_logger),
            feedback_token=feedback_token,
        )

    @override
    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        # Overriding the default value for exclude_none to be True

        if "exclude_none" not in kwargs:
            kwargs["exclude_none"] = True

        return super().model_dump(*args, **kwargs)


class RunResponseStreamChunk(_RunResponseCommon):
    """A streamed chunk for a run request. The final chunk will be a RunResponse object."""

    class ToolCall(BaseModel):
        """A tool that was executed during the run"""

        id: str
        name: str = Field(description="The name of the tool that was executed")
        status: Literal["in_progress", "success", "failed"] = Field(description="The status of the tool")
        input_preview: str = Field(description="A preview of the input to the tool")
        output_preview: str | None = Field(
            description="A preview of the output of the tool, only available if the tool has successfully finished",
        )

        @classmethod
        def from_domain(cls, tool_call: ToolCall):
            if tool_call.error:
                status = "failed"
            elif tool_call.result:
                status = "success"
            else:
                status = "in_progress"

            return cls(
                id=tool_call.id,
                name=tool_call.tool_name,
                input_preview=tool_call.input_preview,
                output_preview=tool_call.output_preview,
                status=status,
            )

    tool_calls: list[ToolCall] | None = Field(
        description="A list of WorkflowAI tool calls that are executed during the run."
        "The full object is sent whenever the tool calls status changes and all hosted tools are sent in the final payload."
        "In most cases, a tool will then be sent when the execution starts with status 'in_progress'"
        "and the final result preview with status 'success' or 'failed'.",
    )

    @classmethod
    def from_stream(cls, id: str, output: RunOutput):
        return cls(
            id=id,
            task_output=output.task_output,
            tool_calls=safe_map_optional(output.tool_calls, cls.ToolCall.from_domain, logger=_logger),
            tool_call_requests=safe_map_optional(
                output.tool_call_requests,
                APIToolCallRequest.from_domain,
                logger=_logger,
            ),
            reasoning_steps=safe_map_optional(output.reasoning_steps, ReasoningStep.from_domain, logger=_logger),
        )


_RUN_RESPONSE_V1: dict[int | str, dict[str, Any]] = {
    200: {
        "content": {
            "application/json": {
                "schema": RunResponse.model_json_schema(),
            },
            "text/event-stream": {
                "schema": TypeAdapter(RunResponseStreamChunk | RunResponse).json_schema(),
            },
        },
    },
}


@task_router.post(
    "/v1/{tenant}/tasks/{task_id}/schemas/{task_schema_id}/run",
    responses=_RUN_RESPONSE_V1,
    response_model_exclude_none=True,
)
@agent_router.post(
    "/v1/{tenant}/agents/{task_id}/schemas/{task_schema_id}/run",
    responses=_RUN_RESPONSE_V1,
    response_model_exclude_none=True,
)
async def run_task(
    body: RunRequest,
    task_id: TaskID,
    task_schema_id: TaskSchemaID,
    run_service: RunServiceDep,
    groups_service: GroupServiceDep,
    author_tenant: AuthorTenantDep,
    provider_settings: ProviderSettingsDep,
    user_org: UserOrganizationDep,
    feedback_token_generator: RunFeedbackGeneratorDep,
    request: Request,
) -> Response:
    reference = version_reference_to_domain(body.version)

    with prettify_errors(user_org, task_id, task_schema_id, reference):
        runner, is_different_version = await groups_service.sanitize_groups_for_internal_runner(
            task_id=task_id,
            task_schema_id=task_schema_id,
            reference=reference,
            provider_settings=provider_settings,
        )

    return await run_service.run(
        task_input=body.task_input,
        runner=runner,
        task_run_id=body.id,
        cache=body.use_cache,
        metadata=body.metadata,
        trigger="user",
        author_tenant=author_tenant,
        serializer=lambda run: RunResponse.from_domain(run, feedback_token_generator(run.id)),
        stream_last_chunk=True,
        stream_serializer=RunResponseStreamChunk.from_stream if body.stream else None,
        store_inline=False,
        private_fields=body.private_fields,
        # We don't pass the source here, it is only used when storing the run inline
        is_different_version=is_different_version,
        start_time=get_start_time(request),
    )


class RunReplyRequest(BaseModel):
    version: VersionReference | None = Field(
        default=None,
        description="The version of the task to reply to. If not provided the latest version is used.",
    )

    user_message: str | None = None

    class ToolCallResult(BaseModel):
        id: str
        output: Any | None = None
        error: str | None = None

        def to_domain(self):
            return ToolCallOutput(id=self.id, output=self.output, error=self.error)

    tool_results: Sequence[ToolCallResult] | None = None

    metadata: dict[str, Any] | None = None

    stream: bool = False

    @model_validator(mode="after")
    def validate_reply(self):
        if not self.user_message and not self.tool_results:
            raise ValueError("No user message or tool calls found in reply")
        return self


@agent_router.post(
    "/v1/{tenant}/agents/{task_id}/runs/{run_id}/reply",
    responses=_RUN_RESPONSE_V1,
    response_model_exclude_none=True,
    description="Reply to a run. The tool use results or added message are appended to the messages of the "
    "requested run and a new run is triggered with the updated messages.",
)
async def reply_to_run(
    body: RunReplyRequest,
    run_service: RunServiceDep,
    groups_service: GroupServiceDep,
    runs_service: RunsServiceDep,
    run_id: str,
    task_tuple: TaskTupleDep,
    user_org: UserOrganizationDep,
    provider_settings: ProviderSettingsDep,
    feedback_token_generator: RunFeedbackGeneratorDep,
    request: Request,
):
    previous_run = await runs_service.run_by_id(task_tuple, run_id, exclude={"task_output"}, max_wait_ms=400)
    if body.version:
        reference = version_reference_to_domain(body.version)
    else:
        reference = DomainVersionReference(properties=previous_run.group.properties)

    with prettify_errors(user_org, task_tuple[0], previous_run.task_schema_id, reference):
        runner, is_different_version = await groups_service.sanitize_groups_for_internal_runner(
            task_id=task_tuple[0],
            task_schema_id=previous_run.task_schema_id,
            reference=reference,
            provider_settings=provider_settings,
        )

    # TODO: the run service should have a stream and a non stream version
    # so that it can return pydantic models instead of just a Response object
    # as it makes testing a lot more annoying
    return await run_service.reply(
        runner=runner,
        to_run=previous_run,
        user_message=body.user_message,
        tool_calls=[r.to_domain() for r in body.tool_results] if body.tool_results else None,
        metadata=body.metadata,
        stream_serializer=RunResponseStreamChunk.from_stream if body.stream else None,
        serializer=lambda run: RunResponse.from_domain(run, feedback_token_generator(run.id)),
        is_different_version=is_different_version,
        start_time=get_start_time(request),
    )


# -------------------------------------------------------------------------------------------------
# Only deprecated methods below, no need to update
# -------------------------------------------------------------------------------------------------


# Deprecated: only used in previous run endpoint
class RunTaskStreamChunk(BaseModel):
    run_id: str
    task_output: dict[str, Any]

    @classmethod
    def from_stream(cls, run_id: str, task_output: RunOutput):
        return cls(run_id=run_id, task_output=task_output.task_output)


class DeprecatedRunRequest(BaseModel):
    task_input: dict[str, Any] = Field(..., description="The input of the task. Must match the input schema")

    group: DeprecatedVersionReference

    id: str = Field(
        default_factory=id_factory,
        description="An optional id. If not provided a uuid will be generated",
    )

    stream: bool = False

    use_cache: CacheUsage = "auto"

    metadata: dict[str, Any] | None = Field(default=None, description="Additional metadata to store with the task run.")


_DEPRECATED_RUN_RESPONSE: dict[int | str, dict[str, Any]] = {
    200: {
        "content": {
            "application/json": {
                "schema": AgentRun.model_json_schema(),
            },
            "text/event-stream": {
                "schema": RunTaskStreamChunk.model_json_schema(),
            },
        },
    },
}


@task_router.post(
    "/tasks/{task_id}/schemas/{task_schema_id}/run",
    description="Run a task with a group id",
    responses=_DEPRECATED_RUN_RESPONSE,
    deprecated=True,
    include_in_schema=False,
)
@task_router.post(
    "/{tenant}/tasks/{task_id}/schemas/{task_schema_id}/run",
    description="Run a task with a group id",
    responses=_DEPRECATED_RUN_RESPONSE,
    deprecated=True,
)
async def run_schema(
    body: DeprecatedRunRequest,
    task_id: TaskID,
    task_schema_id: TaskSchemaID,
    run_service: RunServiceDep,
    groups_service: GroupServiceDep,
    author_tenant: AuthorTenantDep,
    provider_settings: ProviderSettingsDep,
    user_properties: UserPropertiesDep,
    user_org: UserOrganizationDep,
    file_storage: FileStorageDep,
    request: Request,
) -> Response:
    _logger.warning("Deprecated run endpoint used")

    version_ref = body.group.to_domain()

    with prettify_errors(user_org, task_id, task_schema_id, version_ref):
        runner, _ = await groups_service.sanitize_groups_for_internal_runner(
            task_id=task_id,
            task_schema_id=task_schema_id,
            reference=version_ref,
            provider_settings=provider_settings,
        )

    return await run_service.run(
        task_input=body.task_input,
        runner=runner,
        task_run_id=body.id,
        cache=body.use_cache,
        metadata=body.metadata,
        trigger="user",
        author_tenant=author_tenant,
        source=user_properties.client_source,
        stream_serializer=RunTaskStreamChunk.from_stream if body.stream else None,
        serializer=lambda run: run,
        file_storage=file_storage,
        store_inline=True,
        start_time=get_start_time(request),
    )


router.include_router(task_router)
router.include_router(agent_router)
