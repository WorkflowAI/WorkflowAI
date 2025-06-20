from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field, model_validator

from api.dependencies.event_router import EventRouterDep
from api.dependencies.security import RequiredUserOrganizationDep
from api.dependencies.services import AnalyticsServiceDep
from api.dependencies.storage import StorageDep
from api.services.messages.messages_utils import json_schema_for_template
from api.tags import RouteTags
from core.domain.analytics_events.analytics_events import CreatedTaskProperties, TaskProperties
from core.domain.errors import BadRequestError
from core.domain.events import TaskSchemaCreatedEvent
from core.domain.fields.chat_message import ChatMessage
from core.domain.message import Message
from core.domain.page import Page
from core.domain.task_io import SerializableTaskIO
from core.domain.task_variant import SerializableTaskVariant
from core.utils import strings
from core.utils.fields import datetime_factory
from core.utils.schema_sanitation import streamline_schema
from core.utils.templates import InvalidTemplateError, extract_variable_schema

router = APIRouter(prefix="/v1/{tenant}/agents", tags=[RouteTags.AGENTS])


class CreateAgentRequest(BaseModel):
    id: str = Field(default="", description="The agent id, must be unique per tenant and URL safe")
    input_schema: dict[str, Any] = Field(description="The input schema for the agent")
    output_schema: dict[str, Any] = Field(description="The output schema for the agent")
    name: str = Field(
        default="",
        description="The name of the agent, if not provided, a TitleCase version of the id is used",
    )

    chat_messages: list[ChatMessage] | None = Field(
        default=None,
        description="the chat messages that originated the creation of the task, if created from the chat UI",
    )

    sanitize_schemas: bool = Field(
        default=True,
        description="""By default, the schemas are sanitized to make sure that slight changes in schema do not result
        in a new agent schema id being generated. The schema that we store is then a schema compatible with the
        original one for validation purposes.
        The sanitation includes:
        - splatting $refs that are not specific to WorkflowAI
        - replacing nullable optional fields with simply optional fields
        - ordering the `required` field
        - removing anyOf, oneOf and allOf when possible
        - adding missing type keys
        """,
    )

    @model_validator(mode="after")
    def post_validate(self):
        if self.id:
            if not strings.is_url_safe(self.id):
                raise ValueError("The agent id must be URL safe")
            if not self.name:
                self.name = strings.to_pascal_case(self.id)
        elif self.name:
            self.id = strings.slugify(self.name)
        else:
            raise ValueError("Either id or name must be provided")

        return self


class CreateAgentResponse(BaseModel):
    id: str = Field(description="A human readable, url safe id for the agent")
    uid: int = Field(description="A unique integer identifier for the agent")
    name: str = Field(description="The name of the agent")
    schema_id: int = Field(description="The id of the created schema")
    variant_id: str = Field(description="The id of the created variant")
    tenant_uid: int = Field(description="The uid of the connected tenant")


# TODO: all code below should go into a service


@router.post(
    "",
    description="Create a new agent or add a schema to an existing agent."
    "The request is idempotent so calling the endpoint multiple times will not "
    "create multiple identical agents.",
)
async def create_agent(
    request: CreateAgentRequest,
    storage: StorageDep,
    event_router: EventRouterDep,
    analytics_service: AnalyticsServiceDep,
    user_org: RequiredUserOrganizationDep,
) -> CreateAgentResponse:
    # We no longer limit on the output schema, the check will happen client side anyway
    # The task typology will be detected and models will be filtered accordingly
    variant = SerializableTaskVariant(
        id="",
        task_id=request.id,
        task_schema_id=0,
        name=request.name,
        input_schema=SerializableTaskIO.from_json_schema(request.input_schema, streamline=request.sanitize_schemas),
        output_schema=SerializableTaskIO.from_json_schema(request.output_schema, streamline=request.sanitize_schemas),
        created_at=datetime_factory(),
        creation_chat_messages=request.chat_messages,
    )

    stored, created = await storage.store_task_resource(variant, update_created_at=True)
    if created:
        event_router(
            TaskSchemaCreatedEvent(
                task_id=stored.task_id,
                task_schema_id=stored.task_schema_id,
                skip_generation=True,
            ),
        )

        # Send analytics event
        analytics_service.send_event(
            CreatedTaskProperties,
            task_properties=lambda: TaskProperties(
                id=stored.task_id,
                schema_id=stored.task_schema_id,
                organization_id=user_org.tenant if user_org else None,
                organization_name=user_org.name if user_org else None,
                organization_slug=user_org.slug if user_org else None,
            ),
        )

    return CreateAgentResponse(
        id=stored.task_id,
        name=request.name,
        schema_id=stored.task_schema_id,
        variant_id=stored.id,
        uid=stored.task_uid,
        tenant_uid=user_org.uid,
    )


class AgentStat(BaseModel):
    agent_uid: int
    run_count: int
    total_cost_usd: float


@router.get("/stats")
async def get_agent_stats(
    storage: StorageDep,
    from_date: Annotated[
        datetime | None,
        Query(description="The date to filter versions by. Defaults to 7 days ago."),
    ] = None,
) -> Page[AgentStat]:
    from_date = from_date or datetime.now() - timedelta(days=7)
    items = [
        AgentStat(agent_uid=stat.agent_uid, run_count=stat.run_count, total_cost_usd=stat.total_cost_usd)
        async for stat in storage.task_runs.run_count_by_agent_uid(from_date)
    ]
    return Page(items=items)


class ExtractTemplateRequest(BaseModel):
    template: str | None = None
    messages: list[Message] | None = None

    base_schema: dict[str, Any] | None = None


class ExtractTemplateResponse(BaseModel):
    json_schema: Mapping[str, Any] | None
    last_templated_index: int


@router.post("/{agent_id}/templates/extract")
async def extract_template(request: ExtractTemplateRequest) -> ExtractTemplateResponse:
    try:
        if request.template:
            json_schema, is_templated = extract_variable_schema(request.template)
            last_templated_index = 0 if is_templated else -1
        elif request.messages:
            json_schema, last_templated_index = json_schema_for_template(
                request.messages,
                base_schema=streamline_schema(request.base_schema) if request.base_schema else None,
            )
        else:
            raise BadRequestError("Either template or messages must be provided")
    except InvalidTemplateError as e:
        # Help users by reminding them that our templates follow Jinja2 syntax
        raise BadRequestError(
            f"Invalid template: {e.message}. Templates must use Jinja2 formatting.",
            details=e.serialize_details(),
        )
    return ExtractTemplateResponse(json_schema=json_schema, last_templated_index=last_templated_index)
