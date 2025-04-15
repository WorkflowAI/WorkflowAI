"""Task schemas API router"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated, Any, AsyncGenerator, Literal, Self

from fastapi import APIRouter, HTTPException, Path, Query, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, BeforeValidator, Field, model_validator
from sentry_sdk import capture_exception, new_scope

from api.dependencies.event_router import EventRouterDep
from api.dependencies.latest_task_variant import TaskVariantDep
from api.dependencies.path_params import TaskID, TaskSchemaID
from api.dependencies.security import SystemStorageDep, TenantDep, UserDep, UserOrganizationDep
from api.dependencies.services import (
    AnalyticsServiceDep,
    GroupServiceDep,
    InternalTasksServiceDep,
    RunsServiceDep,
    TaskDeploymentsServiceDep,
)
from api.dependencies.task_info import TaskTupleDep
from api.errors import prettify_errors
from api.routers._common import DeprecatedVersionReference
from api.services.python_gen import RunCode, generate_full_run_code
from api.utils import error_json_response
from core.agents.task_instruction_tool_update_task import (
    TaskInstructionsToolUpdateTaskOutput,
)
from core.domain.agent_run import AgentRun
from core.domain.analytics_events.analytics_events import (
    GeneratedInputProperties,
    ImportedTaskRunEventProperties,
    VersionProperties,
)
from core.domain.error_response import ErrorResponse
from core.domain.errors import ProviderError
from core.domain.events import RunCreatedEvent
from core.domain.page import Page
from core.domain.task_example import SerializableTaskExample
from core.domain.task_group import TaskGroup
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_input import TaskInput, TaskInputFields
from core.domain.task_io import SerializableTaskIO
from core.domain.types import TaskInputDict
from core.domain.users import UserIdentifier
from core.domain.version_environment import VersionEnvironment
from core.storage.models import TaskUpdate
from core.tools import ToolKind
from core.utils.file_utils.file_utils import extract_text_from_file_base64
from core.utils.stream_response_utils import safe_streaming_response
from core.utils.streams import format_model_for_sse

from ..dependencies.storage import StorageDep
from ..dependencies.task_example_query import TaskExampleQueryDep
from ..dependencies.task_run_query import TaskRunQueryDep
from ..schemas.create_example_request import CreateExampleRequest
from ..schemas.create_task_run_request import CreateTaskRunRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents/{task_id}/schemas/{task_schema_id}")


class TaskSchemaResponse(BaseModel):
    name: str
    task_id: str
    schema_id: int
    input_schema: SerializableTaskIO
    output_schema: SerializableTaskIO
    is_hidden: bool | None = None
    last_active_at: datetime | None = None
    latest_variant_id: str | None = None


@router.get("")
async def get_task_schema(task_variant: TaskVariantDep, storage: StorageDep) -> TaskSchemaResponse:
    # Endpoint : GET /agents/{task_id}/schemas/{task_schema_id}
    # is hidden field is derived from the `task_info` collection if the schema id is in the `hidden_schemas` list
    # Return the task schema
    task_info = await storage.tasks.get_task_info(task_variant.task_id)
    is_hidden = task_variant.task_schema_id in task_info.hidden_schema_ids if task_info.hidden_schema_ids else False
    schema_details = task_info.get_schema_details(task_variant.task_schema_id)
    schema_last_active_at = schema_details["last_active_at"] if schema_details else None

    return TaskSchemaResponse(
        name=task_variant.name,
        task_id=task_variant.task_id,
        schema_id=task_variant.task_schema_id,
        input_schema=task_variant.input_schema,
        output_schema=task_variant.output_schema,
        is_hidden=is_hidden,
        last_active_at=schema_last_active_at,
        latest_variant_id=task_variant.id,
    )


class TaskSchemaUpdateRequest(BaseModel):
    is_hidden: bool | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> Self:
        if not self.model_dump(exclude_none=True):
            raise ValueError("At least one field must be set")
        return self


@router.patch("", description="Update an agent schema's hidden status")
async def update_task_schema(
    task_variant: TaskVariantDep,
    request: TaskSchemaUpdateRequest,
    storage: StorageDep,
) -> TaskSchemaResponse:
    # Endpoint : PATCH /agents/{task_id}/schemas/{task_schema_id}
    # Update the task schema's hidden status by adding it to the `hidden_schemas` list in the `task_info` collection
    # Return the updated task schema
    if request.is_hidden is not None:
        task_update = TaskUpdate()
        if request.is_hidden:
            task_update.hide_schema = task_variant.task_schema_id
        else:
            task_update.unhide_schema = task_variant.task_schema_id
        await storage.tasks.update_task(task_variant.task_id, task_update)
    return TaskSchemaResponse(
        name=task_variant.name,
        task_id=task_variant.task_id,
        schema_id=task_variant.task_schema_id,
        input_schema=task_variant.input_schema,
        output_schema=task_variant.output_schema,
        is_hidden=request.is_hidden,
    )


# ----------------------------------------------------------------------------------------
# Runs


@router.get("/runs")
async def list_task_runs(
    runs_service: RunsServiceDep,
    query: TaskRunQueryDep,
    task_uid: TaskTupleDep,
) -> Page[AgentRun]:
    # Restricting the limit to 20 if no limit is provided
    if query.limit is None:
        query.limit = 20
    if query.exclude_fields is None and query.include_fields is None:
        query.exclude_fields = {"llm_completions"}

    return await runs_service.list_runs(task_uid[1], query)


@router.post("/runs", description="Import an agent run", deprecated=True, include_in_schema=False)
async def create_task_run(
    task_variant: TaskVariantDep,
    request: CreateTaskRunRequest,
    groups_service: GroupServiceDep,
    storage: StorageDep,
    tenant: TenantDep,
    event_router: EventRouterDep,
    analytics_service: AnalyticsServiceDep,
    user: UserDep,
    user_org: UserOrganizationDep,
) -> AgentRun:
    # By default, groups created directly from the API are external
    if request.group.is_external is None:
        request.group.is_external = True
    version_ref = request.group.to_domain()
    with prettify_errors(user_org, task_variant.task_id, task_variant.task_schema_id, version_ref):
        sanitized_version = await groups_service.sanitize_version_reference(
            task_variant.task_id,
            task_variant.task_schema_id,
            reference=version_ref,
            is_external=request.group.is_external,
        )

    group = TaskGroup(
        is_external=sanitized_version.is_external,
        properties=sanitized_version.properties,
        iteration=sanitized_version.iteration or 0,
    )

    resource = request.build(task_variant, group)

    created = await storage.store_task_run_resource(
        task_variant,
        run=resource,
        user=UserIdentifier(
            user_id=user.user_id if user else None,
            user_email=user.sub if user else None,
        ),
        source=None,
    )
    event_router(RunCreatedEvent(tenant=tenant, run=created))
    analytics_service.send_event(
        lambda: ImportedTaskRunEventProperties(
            group=VersionProperties.from_domain(group),
            latency_seconds=created.duration_seconds,
            cost_usd=created.cost_usd,
        ),
    )
    return created


# ----------------------------------------------------------------------------------------
# Run a task


class GenerateInputRequest(BaseModel):
    instructions: str = ""
    base_input: dict[str, Any] | None = Field(
        default=None,
        description="The base input to migrate to the new schema",
    )
    stream: bool = False


class GenerateInputResponse(BaseModel):
    generated: dict[str, Any]


@router.post(
    "/input",
    description="Generate an input for the given agent",
    responses={
        200: {
            "content": {
                "application/json": {
                    "schema": GenerateInputResponse.model_json_schema(),
                },
                "text/event-stream": {
                    "schema": GenerateInputResponse.model_json_schema(),
                },
            },
        },
    },
)
async def generate_input(
    request: GenerateInputRequest,
    task: TaskVariantDep,
    internal_tasks_service: InternalTasksServiceDep,
    analytics_service: AnalyticsServiceDep,
    system_storage: SystemStorageDep,
) -> Response:
    analytics_service.send_event(
        lambda: GeneratedInputProperties(
            custom_instructions=request.instructions != "",
            input_count=1,
        ),
    )

    if not request.stream:
        generated = await internal_tasks_service.get_task_input(
            task,
            request.instructions,
            base_input=request.base_input,
            system_storage=system_storage,
            stream=False,
        )
        if not generated:
            return error_json_response(400, "No input generated", "invalid_generation")
        return JSONResponse(content=GenerateInputResponse(generated=generated).model_dump(mode="json"))

    async def _stream() -> AsyncGenerator[str, None]:
        try:
            iterator = await internal_tasks_service.get_task_input(
                task,
                request.instructions,
                base_input=request.base_input,
                system_storage=system_storage,
                stream=True,
            )
            async for chunk in iterator:
                yield f"data: {json.dumps(chunk)}\n\n"
        except ProviderError as e:
            # TODO: we should remove duplicated code from _stream_run in run service
            e.capture_if_needed()
            yield f"data: {e.error_response().model_dump_json()}\n\n"
        except Exception as e:
            with new_scope() as scope:
                scope.set_level("fatal")
                capture_exception(e)
            yield f"data: {ErrorResponse.internal_error().model_dump_json()}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


# ----------------------------------------------------------------------------------------
# Examples


@router.get("/examples", deprecated=True, include_in_schema=False)
async def list_examples(storage: StorageDep, query: TaskExampleQueryDep) -> Page[SerializableTaskExample]:
    # Restricting the limit to 20 if no limit is provided
    if query.limit is None:
        query.limit = 20

    async def fetch() -> list[SerializableTaskExample]:
        return [a async for a in storage.fetch_example_resources(query)]

    res, count = await asyncio.gather(fetch(), storage.count_examples(query))
    return Page(items=res, count=count)


@router.post("/examples", deprecated=True, include_in_schema=False)
async def add_example(
    request: CreateExampleRequest,
    task_variant: TaskVariantDep,
    storage: StorageDep,
    event_router: EventRouterDep,
    tenant: TenantDep,
) -> SerializableTaskExample:
    res = request.build(task_variant)
    return await storage.store_example_resource(task_variant, example=res)


# ------------------------------------------------------------------------------------------------
# Generate code


class GenerateCodeBlockResponse(BaseModel):
    class Snippet(BaseModel):
        language: Literal["python", "bash"]
        code: str

    sdk: Snippet

    class RunSnippet(BaseModel):
        language: Literal["python"] = "python"
        common: str

        class CodeBlock(BaseModel):
            imports: str
            code: str

        run: CodeBlock
        stream: CodeBlock

        @classmethod
        def from_run_code(cls, run_code: RunCode):
            return cls(
                common=run_code.common,
                run=cls.CodeBlock(imports=run_code.run.imports, code=run_code.run.code),
                stream=cls.CodeBlock(imports=run_code.stream.imports, code=run_code.stream.code),
            )

    run: Snippet | RunSnippet


class GenerateCodeBlockRequest(BaseModel):
    group_iteration: int
    group_environment: str
    example_task_run_input: dict[str, Any]
    url: str | None = None
    secondary_input: dict[str, Any] | None = None
    # Legacy flag, should be removed and be true when the frontend is updated
    separate_run_and_stream: bool = False


@router.post("/python")
async def generate_python_code_block(
    task_variant: TaskVariantDep,
    request: GenerateCodeBlockRequest,
) -> GenerateCodeBlockResponse:
    run_code = generate_full_run_code(
        task_variant,
        request.example_task_run_input,
        version=request.group_environment or request.group_iteration,
        url=request.url,
        secondary_input=request.secondary_input,
    )

    if request.separate_run_and_stream:
        return GenerateCodeBlockResponse(
            sdk=GenerateCodeBlockResponse.Snippet(language="bash", code="pip install workflowai"),
            run=GenerateCodeBlockResponse.RunSnippet.from_run_code(run_code),
        )

    return GenerateCodeBlockResponse(
        sdk=GenerateCodeBlockResponse.Snippet(language="bash", code="pip install workflowai"),
        run=GenerateCodeBlockResponse.Snippet(
            language="python",
            code=f"{run_code.run.imports}\n\n{run_code.common}\n\n{run_code.run.code}",
        ),
    )


class GenerateInputsRequest(BaseModel):
    instructions: str = ""
    group: DeprecatedVersionReference | None = Field(
        default=None,
        description="The group to use for the task run.\nBy default, a temperature of 1 is used",
    )
    count: int = Field(description="The number of inputs to generate")
    stream: bool = False


class ImportInputsRequest(BaseModel):
    inputs_text: str | None = Field(
        default=None,
        description="The text to import as input",
    )

    class File(BaseModel):
        content_type: str | None = None
        base64_data: str

    inputs_file: File | None = Field(
        default=None,
        description="An optional file to import as input.",
    )

    stream: bool = False


class ImportInputsResponse(BaseModel):
    imported_inputs: list[TaskInputDict]


class ImportInputsStreamResponse(BaseModel):
    index: int
    imported_input: TaskInputDict


@router.post(
    "/inputs/import",
    responses={
        200: {
            "content": {
                "application/json": {
                    "schema": ImportInputsResponse.model_json_schema(),
                },
                "text/event-stream": {
                    "schema": ImportInputsStreamResponse.model_json_schema(),
                },
            },
        },
    },
)
async def import_inputs(
    request: ImportInputsRequest,
    task: TaskVariantDep,
    internal_tasks_service: InternalTasksServiceDep,
) -> Response:
    if request.inputs_text is None and request.inputs_file is None:
        raise HTTPException(status_code=422, detail="Either inputs_text or inputs_file must be provided")

    inputs_data = ""

    if request.inputs_text:
        inputs_data += request.inputs_text

    if request.inputs_file:
        if inputs_data != "":
            inputs_data += "\n\n"

        inputs_data += f"Attached file content: {extract_text_from_file_base64(request.inputs_file.base64_data)}"

    if not request.stream:
        imported_inputs = await internal_tasks_service.input_import.import_input(
            task,
            inputs_data,
        )
        return JSONResponse(content=ImportInputsResponse(imported_inputs=imported_inputs).model_dump(mode="json"))

    async def _stream():
        async for index, imported_input in internal_tasks_service.input_import.stream_import_input(
            task,
            inputs_data,
        ):
            payload = ImportInputsStreamResponse(
                index=index,
                imported_input=imported_input,
            ).model_dump_json()
            logger.info(payload)
            yield f"data: {payload}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


@router.get("/inputs/{input_hash}", deprecated=True, include_in_schema=False)
async def get_input_by_hash(
    input_hash: Annotated[str, Path(description="The hash of the input")],
    storage: StorageDep,
    task_id: TaskID,
    task_schema_id: TaskSchemaID,
    exclude_fields: list[TaskInputFields] | None = Query(default=None),
) -> TaskInput:
    return await storage.task_inputs.get_input_by_hash(task_id, task_schema_id, input_hash, exclude=exclude_fields)


@router.post("/generate/description")
async def stream_task_description(
    task_id: TaskID,
    task_schema_id: TaskSchemaID,
    instructions: str,
    internal_tasks: InternalTasksServiceDep,
) -> Response:
    async def description_generator():
        async for chunk in internal_tasks.set_task_description_if_missing(
            task_id=task_id,
            task_schema_id=task_schema_id,
            instructions=instructions,
        ):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(description_generator(), media_type="text/event-stream")


class ImproveVersionRequest(BaseModel):
    # The run id that received an evaluation
    # We will use the input / output / version properties of the associated run to improve on the version properties
    task_run_id: str

    # A comment on why the task run was not optimal
    user_evaluation: str

    stream: bool = False


class ImproveVersionResponse(BaseModel):
    improved_properties: TaskGroupProperties
    changelog: str | None


@router.post(
    "/versions/improve",
    description="Improve the version properties by using a user evaluation of a given run. The run's version properties"
    ", input and outputs are used as context to generate new version properties.",
    deprecated=True,
    include_in_schema=False,
)
async def improve_prompt(
    internal_tasks: InternalTasksServiceDep,
    request: ImproveVersionRequest,
    task_id: TaskTupleDep,
) -> Response:
    def _join_changelog(changelog: list[str] | None) -> str:
        if not changelog:
            return ""
        return "- " + "\n- ".join(changelog)

    if not request.stream:
        improved_properties, changelog = await internal_tasks.improve_prompt.run(
            task_id,
            run_id=request.task_run_id,
            variant_id=None,
            instructions=None,
            user_evaluation=request.user_evaluation,
        )
        return JSONResponse(
            content=ImproveVersionResponse(
                improved_properties=improved_properties,
                changelog=_join_changelog(changelog),
            ).model_dump(mode="json"),
        )

    async def _stream():
        async for chunk in internal_tasks.improve_prompt.stream(
            task_id,
            run_id=request.task_run_id,
            variant_id=None,
            instructions=None,
            user_evaluation=request.user_evaluation,
        ):
            yield format_model_for_sse(
                ImproveVersionResponse(
                    improved_properties=chunk[0],
                    changelog=_join_changelog(chunk[1]),
                ),
            )

    return StreamingResponse(_stream(), media_type="text/event-stream")


class InstructionChunk(BaseModel):
    suggested_instructions: str


@router.get("/suggested-instructions")
async def stream_task_instructions(
    task: TaskVariantDep,
    internal_tasks: InternalTasksServiceDep,
) -> Response:
    chat_messages = task.creation_chat_messages or []

    async def _stream():
        async for chunk in await internal_tasks.stream_suggested_instructions(task=task, chat_messages=chat_messages):
            yield format_model_for_sse(InstructionChunk(suggested_instructions=chunk))

    return StreamingResponse(_stream(), media_type="text/event-stream")


class DeployVersionRequest(BaseModel):
    environment: VersionEnvironment
    provider_config_id: str | None = None


class DeployVersionResponse(BaseModel):
    task_schema_id: TaskSchemaID
    version_id: int
    environment: VersionEnvironment
    provider_config_id: str | None = None
    deployed_at: datetime


@router.post("/versions/{version_id}/deploy", deprecated=True)
async def deploy_version(
    task_schema_id: TaskSchemaID,
    task_tuple: TaskTupleDep,
    version_id: int,
    request: DeployVersionRequest,
    task_deployments_service: TaskDeploymentsServiceDep,
    user: UserDep,
) -> DeployVersionResponse:
    # Endpoint: POST /agents/{task_id}/schemas/{task_schema_id}/versions/{version_id}/deploy
    # Deploy a version to an environment.
    # Making two consecutive calls with the same version_id and environment overrides the previous deployment.
    # Call 1: POST /agents/{task_id}/schemas/{task_schema_id}/versions/{version_id}/deploy
    # task_id: test, task_schema_id: 1, version_id: 4, environment: dev, provider_config_id: 1
    # Call 2: POST /agents/{task_id}/schemas/{task_schema_id}/versions/{version_id}/deploy
    # task_id: test, task_schema_id: 1, version_id: 4, environment: dev, provider_config_id: 2
    # Call 1 config details are overwritten by Call 2 details, for the iteration 4, environment: dev
    user_identifier = UserIdentifier(user_id=user.user_id if user else "", user_email=user.sub if user else "")
    if request.provider_config_id:
        logger.warning("provider_config_id are no longer considered")
    deployment = await task_deployments_service.deploy_version(
        task_id=task_tuple,
        task_schema_id=task_schema_id,
        version_id=version_id,
        environment=request.environment,
        deployed_by=user_identifier,
    )

    return DeployVersionResponse(
        version_id=deployment.iteration,
        task_schema_id=deployment.schema_id,
        environment=deployment.environment,
        provider_config_id=None,
        deployed_at=deployment.deployed_at,
    )


class UpdateTaskInstructionsRequest(BaseModel):
    instructions: str

    # 'selected_tools' is optional because we may add other updates (e.g. shorten instructions, develop instructions, spellcheck instructions, etc.) in the future
    # in this case, 'selected_tools' could be None, but we'll have other flags (e.g. 'shorten_instructions', 'develop_instructions', 'spellcheck_instructions', etc.)
    selected_tools: list[Annotated[ToolKind, BeforeValidator(ToolKind.from_str)]] | None = Field(
        default=None,
        description="""The tools to include in the instructions. Any tool not listed here will be removed from the instructions.
        If 'selected_tools' is None, no tools will be added or removed from the instructions.""",
    )

    def is_no_op(self) -> bool:
        return self.selected_tools is None


@router.put("/instructions")
async def update_task_instructions(
    task: TaskVariantDep,
    request: UpdateTaskInstructionsRequest,
    internal_tasks: InternalTasksServiceDep,
) -> Response:
    if request.is_no_op():
        # No-op.
        return StreamingResponse(
            format_model_for_sse(TaskInstructionsToolUpdateTaskOutput(updated_task_instructions=request.instructions)),
            media_type="text/event-stream",
        )

    async def _stream() -> AsyncIterator[BaseModel]:
        async for chunk in await internal_tasks.instructions.update_task_instructions(
            task_variant=task,
            instructions=request.instructions,
            selected_tools=request.selected_tools or [],
        ):
            yield chunk

    return safe_streaming_response(_stream, media_type="text/event-stream")
