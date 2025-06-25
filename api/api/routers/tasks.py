import logging
from datetime import datetime, timezone
from typing import Any, Optional, Self

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse, StreamingResponse
from jsonschema import SchemaError
from jsonschema.validators import validator_for  # type:ignore
from pydantic import BaseModel, Field, field_validator

from api.dependencies.analytics import UserPropertiesDep
from api.dependencies.event_router import EventRouterDep
from api.dependencies.path_params import AgentID
from api.dependencies.security import UserOrganizationDep
from api.dependencies.services import (
    AnalyticsServiceDep,
    GroupServiceDep,
    InternalTasksServiceDep,
    TaskDeploymentsServiceDep,
)
from api.dependencies.task_info import TaskTupleDep
from api.schemas.build_task_request import (
    BuildAgentIteration,
    BuildAgentRequest,
)
from api.services import tasks
from api.services.task_deployments import DeployedVersionsResponse, VersionsResponse
from api.services.task_gen import get_new_task_input_from_request
from core.agents.chat_task_schema_generation.chat_task_schema_generation_task import AgentSchemaJson
from core.agents.generate_task_preview import GenerateTaskPreviewTaskInput
from core.agents.utils import WORKFLOWAI_ENV_FOR_INTERNAL_TASKS
from core.domain.analytics_events.analytics_events import (
    CreatedTaskProperties,
    EditedTaskSchemaEventProperties,
    TaskProperties,
)
from core.domain.events import TaskChatStartedEvent, TaskSchemaCreatedEvent, TaskSchemaGeneratedEvent
from core.domain.fields.chat_message import ChatMessage
from core.domain.major_minor import MajorMinor
from core.domain.page import Page
from core.domain.task import SerializableTask
from core.domain.task_group import TaskGroupQuery
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_io import SerializableTaskIO
from core.domain.task_preview import TaskPreview
from core.domain.task_run_aggregate_per_day import TaskRunAggregatePerDay
from core.domain.task_run_query import SerializableTaskRunQuery
from core.domain.task_variant import SerializableTaskVariant
from core.domain.version_reference import VersionReference
from core.runners.workflowai import workflowai_options
from core.storage import ObjectNotFoundException
from core.storage.models import TaskUpdate
from core.tools import ToolKind
from core.utils import strings
from core.utils.schema_sanitation import (
    normalize_input_json_schema,  # pyright: ignore[reportDeprecated]
    normalize_output_json_schema,  # pyright: ignore[reportDeprecated]
)
from core.utils.schema_validation_utils import fix_non_object_root
from core.utils.stream_response_utils import safe_streaming_response
from core.utils.streams import format_model_for_sse

from ..dependencies.storage import StorageDep
from ._common import (
    INCLUDE_PRIVATE_ROUTES,
)

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents")


def _send_task_chat_started_event(request: BuildAgentRequest, event_router: EventRouterDep):
    # Case 1: First message for task creation
    if request.previous_iterations is None or len(request.previous_iterations) == 0:
        event_router(
            TaskChatStartedEvent(
                user_message=request.user_message,
            ),
        )
        return

    # Case 2: First message for task schema update
    if (
        len(request.previous_iterations) == 1
        and request.previous_iterations[0].task_schema is not None
        and request.previous_iterations[0].user_message == ""
    ):
        event_router(
            TaskChatStartedEvent(
                existing_task_name=request.previous_iterations[0].task_schema.task_name,
                user_message=request.user_message,
            ),
        )
        return

    # Case 3: Subsequent messages for task creation or task schema update
    # Do nothing as we do not want to send events for each message, only the first one


@router.post(
    "/schemas/iterate",
    description="Build a new agent based on natural language, allowing for multiple iterations",
)
async def generate_via_chat(
    request: BuildAgentRequest,
    internal_tasks: InternalTasksServiceDep,
    event_router: EventRouterDep,
    user_properties: UserPropertiesDep,
) -> Response:
    try:
        _send_task_chat_started_event(request=request, event_router=event_router)
    except Exception:
        _logger.exception("Error running _send_task_chat_started_event")

    chat_messages, existing_task = get_new_task_input_from_request(request)

    if request.stream:

        async def _stream():
            agent_schema = None
            assistant_answer = None

            async for agent_schema, assistant_answer in internal_tasks.stream_task_schema_iterations(
                chat_messages=chat_messages,
                user_email=user_properties.user_email,
                existing_task=existing_task,
                is_proxy_agent=request.is_proxy_agent,
            ):
                payload = BuildAgentIteration(
                    user_message=request.user_message,
                    assistant_answer=assistant_answer,
                    task_schema=BuildAgentIteration.AgentSchema.from_agent_schema(agent_schema)
                    if agent_schema
                    else None,
                )
                yield payload

            if agent_schema is not None and assistant_answer is not None:
                event_router(
                    TaskSchemaGeneratedEvent(
                        version_identifier=WORKFLOWAI_ENV_FOR_INTERNAL_TASKS,
                        chat_messages=chat_messages,
                        previous_task_schema=existing_task,
                        assistant_answer=assistant_answer,
                        updated_task_schema=agent_schema,
                    ),
                )

        return safe_streaming_response(_stream, media_type="text/event-stream")

    new_task_schema, assistant_answer = await internal_tasks.run_task_schema_iterations(
        chat_messages=chat_messages,
        existing_task=existing_task,
        user_email=user_properties.user_email,
    )

    if new_task_schema:
        event_router(
            TaskSchemaGeneratedEvent(
                version_identifier=WORKFLOWAI_ENV_FOR_INTERNAL_TASKS,
                chat_messages=chat_messages,
                previous_task_schema=existing_task,
                assistant_answer=assistant_answer,
                updated_task_schema=new_task_schema,
            ),
        )

    return JSONResponse(
        content=BuildAgentIteration(
            user_message=request.user_message,
            assistant_answer=assistant_answer,
            task_schema=BuildAgentIteration.AgentSchema.from_agent_schema(new_task_schema) if new_task_schema else None,
        ).model_dump(mode="json"),
    )


class GenerateTaskPreviewRequest(BaseModel):
    chat_messages: list[ChatMessage] = Field(
        description="the chat messages that originated the creation of the task to generate a preview for",
    )

    task_input_schema: dict[str, Any] = Field(
        description="the input schema of the task to generate a preview for",
    )
    task_output_schema: dict[str, Any] = Field(
        description="the output schema of the task to generate a preview for",
    )

    current_preview: TaskPreview | None = Field(
        default=None,
        description="The current task preview (input, output) to reuse and update, if already existing",
    )


class GenerateTaskPreviewResponse(BaseModel):
    preview: TaskPreview = Field(
        description="A preview (input, output) of the task",
    )


@router.post("/schemas/preview", description="Generate a preview (input, output) of the agent")
async def generate_task_preview(
    request: GenerateTaskPreviewRequest,
    internal_tasks: InternalTasksServiceDep,
) -> Response:
    async def _stream():
        async for chunk in internal_tasks.stream_generate_task_preview(
            task_input=GenerateTaskPreviewTaskInput(
                chat_messages=request.chat_messages,
                task_input_schema=request.task_input_schema,
                task_output_schema=request.task_output_schema,
                current_preview=request.current_preview,
            ),
        ):
            yield format_model_for_sse(chunk)

    return StreamingResponse(_stream(), media_type="text/event-stream")


# TODO: we should return a proper object here
@router.get("")
async def list_tasks(storage: StorageDep) -> Page[SerializableTask]:
    items = await tasks.list_tasks(storage)

    return Page(items=items)


@router.get("/{agent_id}")
async def get_task(agent_id: AgentID, storage: StorageDep) -> SerializableTask:
    return await storage.get_task(task_id=agent_id)


class BaseTaskCreateRequest(BaseModel):
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]

    @field_validator("input_schema", "output_schema")
    def check_json_schema(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            validator_for(value).check_schema(value)  # type: ignore

            _, is_non_object_root = fix_non_object_root(value)

            if is_non_object_root:
                raise ValueError(f"Root of schema must be an object (not an array or primitive type) {value}")

            return value
        except SchemaError as e:
            raise ValueError(f"Invalid json schema: {e.message}")


class CreateTaskRequest(BaseTaskCreateRequest):
    chat_messages: list[ChatMessage] | None = Field(
        default=None,
        description="the chat messages that originated the creation of the task, if created from the chat UI",
    )

    create_first_iteration: bool = Field(
        default=False,
        description="Wether or not to create a first iteration for the task, that uses the default model and LLM generated instructions",
    )

    skip_generation: bool = Field(
        default=False,
        description="Wether or not to skip the generation of the task instructions and image",
    )

    name: str = Field(..., description="the task display name")

    task_id: Optional[str] = Field(
        default=None,
        description="the task id, stable accross all variants. If not provided, an id based on the name is generated.",
    )

    def build(self, task_id: str) -> SerializableTaskVariant:
        # First building the task variant without an ID to compute the hash
        input_schema = normalize_input_json_schema(self.input_schema)  # pyright: ignore[reportDeprecated]
        output_schema = normalize_output_json_schema(self.output_schema)  # pyright: ignore[reportDeprecated]

        task_variant = SerializableTaskVariant(
            id="",
            task_id=task_id,
            task_schema_id=0,
            name=self.name,
            input_schema=SerializableTaskIO.from_json_schema(input_schema),
            output_schema=SerializableTaskIO.from_json_schema(output_schema),
            created_at=datetime.now(timezone.utc),
            creation_chat_messages=self.chat_messages,
        )
        # Computing hash of entire object by excluding variable fields
        task_variant.id = task_variant.model_hash()
        return task_variant


@router.post("", description="Create a new agent", deprecated=True, include_in_schema=False)
async def create_task(
    request: CreateTaskRequest,
    storage: StorageDep,
    group_service: GroupServiceDep,
    internal_tasks: InternalTasksServiceDep,
    event_router: EventRouterDep,
    analytics_service: AnalyticsServiceDep,
    user_org: UserOrganizationDep,
) -> SerializableTaskVariant:
    task_id = request.task_id or strings.to_kebab_case(request.name)
    task_variant = request.build(task_id)
    try:
        task_info = await storage.tasks.get_task_info(task_id=task_id)
        _logger.warning(
            "Task with id already exists. Adding a schema from POST /tasks is deprecated",
            extra={"task_id": task_id, "request": request.model_dump()},
        )
        task_variant.is_public = task_info.is_public
    except ObjectNotFoundException:
        pass

    stored, _ = await storage.store_task_resource(task_variant, update_created_at=True)

    async def create_first_iteration():
        try:
            required_tool_kinds = await internal_tasks.get_required_tool_kinds(
                task_name=request.name,
                input_json_schema=request.input_schema,
                output_json_schema=request.output_schema,
                chat_messages=request.chat_messages or [],
            )

            # Generate the default instructions for the task
            new_task_instructions = await internal_tasks.generate_agent_instructions(
                task_id=task_id,
                task_schema_id=stored.task_schema_id,
                chat_messages=request.chat_messages or [],
                task=AgentSchemaJson(
                    agent_name=request.name,
                    input_json_schema=request.input_schema,
                    output_json_schema=request.output_schema,
                ),
                required_tool_kinds=required_tool_kinds,
            )

            # Add first iteration with default instructions
            await group_service.get_or_create_group(
                task_id=task_id,
                task_schema_id=stored.task_schema_id,
                reference=VersionReference(
                    properties=TaskGroupProperties(
                        model=workflowai_options.GLOBAL_DEFAULT_MODEL,
                        instructions=new_task_instructions,
                    ),
                ),
            )
        except Exception:
            _logger.exception("Error creating first iteration", extra={"task_id": task_id})
            # Continue execution as the version creation is not mandatory for the task to work

    if request.create_first_iteration:
        await create_first_iteration()

    # Trigger the creation of the task description and image in the background
    event_router(
        TaskSchemaCreatedEvent(
            task_id=stored.task_id,
            task_schema_id=stored.task_schema_id,
            skip_generation=request.skip_generation,
        ),
    )

    # Send analytics event
    analytics_service.send_event(
        CreatedTaskProperties,
        task_properties=lambda: TaskProperties.build(task_id, stored.task_schema_id, user_org),
    )

    return stored


class CreateTaskSchemaRequest(BaseTaskCreateRequest):
    chat_messages: list[ChatMessage] | None = Field(
        default=None,
        description="the chat messages that originated the creation of the task, if created from the chat UI",
    )

    create_first_iteration: bool = Field(
        default=False,
        description="Wether or not to create a first iteration for the task, that uses the default model and LLM generated instructions",
    )

    name: str = Field(..., description="the task display name")
    skip_generation: bool = False


@router.post(
    "/{agent_id}/schemas",
    description="Create a new agent schema for a given agent id",
    deprecated=True,
    include_in_schema=False,
)
async def create_task_schema(
    agent_id: AgentID,
    request: CreateTaskSchemaRequest,
    storage: StorageDep,
    internal_tasks: InternalTasksServiceDep,
    group_service: GroupServiceDep,
    event_router: EventRouterDep,
    analytics_service: AnalyticsServiceDep,
    user_org: UserOrganizationDep,
) -> SerializableTaskVariant:
    existing_latest_task_variant = await storage.task_variants.get_latest_task_variant(agent_id)
    input_schema = normalize_input_json_schema(request.input_schema)  # pyright: ignore[reportDeprecated]
    output_schema = normalize_output_json_schema(request.output_schema)  # pyright: ignore[reportDeprecated]

    task_variant = SerializableTaskVariant(
        id="",
        task_id=agent_id,
        task_schema_id=0,  # Final schema id will be computed in 'store_task_resource'
        name="",
        input_schema=SerializableTaskIO.from_json_schema(input_schema),
        output_schema=SerializableTaskIO.from_json_schema(output_schema),
        created_at=datetime.now(timezone.utc),
        creation_chat_messages=request.chat_messages,
    )
    new_task, _ = await storage.store_task_resource(task_variant)

    async def generate_new_task_instructions(required_tool_kinds: set[ToolKind]) -> str:
        return await internal_tasks.generate_agent_instructions(
            task_id=new_task.task_id,
            task_schema_id=new_task.task_schema_id,
            chat_messages=request.chat_messages or [],
            task=AgentSchemaJson(
                agent_name=new_task.name,
                input_json_schema=new_task.input_schema.json_schema,
                output_json_schema=new_task.output_schema.json_schema,
            ),
            required_tool_kinds=required_tool_kinds,
        )

    async def get_task_instructions(required_tool_kinds: set[ToolKind]) -> str:
        if not new_task.task_schema_id > 1:
            # If it's the first schema, we generate new instructions.
            return await generate_new_task_instructions(required_tool_kinds)

        if not existing_latest_task_variant:
            # The new task is the first task variant, so we generate new instructions.
            return await generate_new_task_instructions(required_tool_kinds)

        previous_group = await storage.task_groups.get_latest_group_iteration(
            agent_id,
            existing_latest_task_variant.task_schema_id,
        )

        if previous_group is None or not previous_group.properties.instructions:
            # We could not find any instructions for the previous schema, so we generate new instructions.
            return await generate_new_task_instructions(required_tool_kinds)

        return await internal_tasks.update_task_instructions(
            initial_task_schema=AgentSchemaJson(
                agent_name=existing_latest_task_variant.name,
                input_json_schema=existing_latest_task_variant.input_schema.json_schema,
                output_json_schema=existing_latest_task_variant.output_schema.json_schema,
            ),
            initial_task_instructions=previous_group.properties.instructions,
            chat_messages=request.chat_messages or [],
            new_task_schema=AgentSchemaJson(
                agent_name=new_task.name,
                input_json_schema=new_task.input_schema.json_schema,
                output_json_schema=new_task.output_schema.json_schema,
            ),
            required_tool_kinds=required_tool_kinds,
        )

    async def migrate_instructions(required_tool_kinds: set[ToolKind]):
        try:
            task_instructions = await get_task_instructions(required_tool_kinds)

            # Add a first iteration for the new schema
            await group_service.get_or_create_group(
                task_id=agent_id,
                task_schema_id=new_task.task_schema_id,
                reference=VersionReference(
                    properties=TaskGroupProperties(
                        model=workflowai_options.GLOBAL_DEFAULT_MODEL,
                        instructions=task_instructions,
                    ),
                ),
            )
        except Exception:
            _logger.exception("Error creating iteration", extra={"agent_id": agent_id})
            # Continue execution as the version creation is not mandatory for the task to work

    if request.create_first_iteration:
        required_tool_kinds = await internal_tasks.get_required_tool_kinds(
            task_name=new_task.name,
            input_json_schema=new_task.input_schema.json_schema,
            output_json_schema=new_task.output_schema.json_schema,
            chat_messages=request.chat_messages or [],
        )
        await migrate_instructions(required_tool_kinds)

    # Trigger the creation of the task description and image in the background
    event_router(
        TaskSchemaCreatedEvent(
            task_id=new_task.task_id,
            task_schema_id=new_task.task_schema_id,
            skip_generation=request.skip_generation,
        ),
    )
    analytics_service.send_event(
        lambda: EditedTaskSchemaEventProperties(
            updated_task=TaskProperties.build(new_task.task_id, new_task.task_schema_id, user_org),
        ),
    )

    return new_task


class UpdateTaskRequest(BaseModel):
    is_public: bool | None = Field(default=None, description="whether the task is public")
    name: str | None = Field(default=None, description="the task display name")
    description: str | None = Field(default=None, description="the task description")

    def to_storage(self) -> TaskUpdate:
        return TaskUpdate(
            is_public=self.is_public,
            name=self.name,
            description=self.description,
        )


@router.patch("/{agent_id}", description="Update an agent")
async def update_task(agent_id: AgentID, request: UpdateTaskRequest, storage: StorageDep) -> None:
    await storage.tasks.update_task(agent_id, request.to_storage())


@router.delete(
    "/{agent_id}",
    description="Delete an agent by id",
    include_in_schema=INCLUDE_PRIVATE_ROUTES,
)
async def delete_task(
    agent_id: AgentID,
    storage: StorageDep,
) -> None:
    await storage.delete_task(agent_id)


class TaskStats(BaseModel):
    total_count: int
    total_cost_usd: float
    date: str

    @classmethod
    def from_domain(cls, item: TaskRunAggregatePerDay) -> Self:
        return cls(
            total_count=item.total_count,
            total_cost_usd=item.total_cost_usd,
            date=item.date.isoformat(),
        )


class TaskStatsResponse(BaseModel):
    data: list[TaskStats]


@router.get(
    "/{agent_id}/runs/stats",
    description="Get stats for agent",
)
async def get_task_stats(
    storage: StorageDep,
    task_id: TaskTupleDep,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    task_schema_id: int | None = None,
    version: str | None = None,
    is_active: bool | None = None,
) -> TaskStatsResponse:
    query = SerializableTaskRunQuery(
        task_id=task_id[0],
        task_schema_id=task_schema_id,
        created_after=created_after,
        created_before=created_before,
        is_active=is_active,
    )

    if version:
        if semver := MajorMinor.from_string(version):
            group = await storage.task_groups.get_task_group_by_id(task_id[0], semver, include=["id"])
            query.group_ids = {group.id}
        else:
            query.group_ids = {version}

    data: list[TaskStats] = []
    async for item in storage.task_runs.aggregate_task_run_costs(task_id[1], query):
        task_stat = TaskStats.from_domain(item)
        data.append(task_stat)
    return TaskStatsResponse(data=data)


class UpdateDescriptionRequest(BaseModel):
    description: str


@router.get(
    "/{agent_id}/versions/deployed",
    description="Get deployed versions for agent",
)
async def get_task_versions_deployed(
    agent_id: AgentID,
    storage: StorageDep,
    task_deployments_service: TaskDeploymentsServiceDep,
) -> Page[DeployedVersionsResponse]:
    # Endpoint : GET tasks/{agent_id}/versions/deployed

    groups = await task_deployments_service.get_task_deployments(agent_id)

    return Page(items=groups, count=len(groups))


@router.get(
    "/{agent_id}/versions",
    description="Get all versions for agent",
)
async def get_task_versions(
    agent_id: AgentID,
    storage: StorageDep,
) -> Page[VersionsResponse]:
    # Endpoint : GET tasks/{agent_id}/versions
    # Return a Page object containing the TaskGroupWithCost items
    query = TaskGroupQuery(task_id=agent_id)
    groups = [group async for group in storage.task_groups.list_task_groups(query)]
    return Page(items=[VersionsResponse.from_domain(group) for group in groups], count=len(groups))
