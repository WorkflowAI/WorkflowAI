import json
from datetime import datetime, time
from typing import Any, Generic, Literal, TypeAlias, TypeVar

from pydantic import BaseModel, Field

from api.routers.mcp._mcp_utils import truncate_field, truncate_obj
from api.schemas.user_identifier import UserIdentifier
from api.schemas.version_properties import ShortVersionProperties
from api.services.models import ModelForTask
from core.domain.agent_run import AgentRun
from core.domain.error_response import ErrorResponse
from core.domain.message import Message
from core.domain.models.model_data import FinalModelData, ModelData, ModelReasoningBudget
from core.domain.models.model_data_supports import ModelDataSupports
from core.domain.models.models import Model
from core.domain.models.utils import get_model_data
from core.domain.task import SerializableTask
from core.domain.task_group import TaskGroup
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_variant import SerializableTaskVariant
from core.domain.version_environment import VersionEnvironment
from core.domain.version_major import VersionDeploymentMetadata, VersionMajor
from core.storage.task_run_storage import TaskRunStorage
from core.utils.fields import datetime_zero
from core.utils.token_utils import tokens_from_string

# New sorting type aliases with two-field approach
AgentSortField: TypeAlias = Literal["last_active_at", "total_cost_usd", "run_count"]
ModelSortField: TypeAlias = Literal["release_date", "quality_index", "speed_index", "cost"]
SortOrder: TypeAlias = Literal["asc", "desc"]


class ConciseLatestModelResponse(BaseModel):
    id: str
    currently_points_to: str


class ConciseModelSupports(BaseModel):
    input_image: bool
    input_pdf: bool
    input_audio: bool
    audio_only: bool
    tool_calling: bool
    reasoning: bool

    @classmethod
    def from_domain(cls, model_data: ModelData):
        return cls(
            input_image=model_data.supports_input_image,
            input_pdf=model_data.supports_input_pdf,
            input_audio=model_data.supports_input_audio,
            audio_only=model_data.supports_audio_only,
            tool_calling=model_data.supports_tool_calling,
            reasoning=model_data.reasoning is not None,
        )


class ConciseModelResponse(BaseModel):
    id: str
    display_name: str
    supports: ConciseModelSupports
    quality_index: int
    speed_index: int
    cost_per_input_token_usd: float
    cost_per_output_token_usd: float
    release_date: str

    class Reasoning(BaseModel):
        min_budget: int = Field(
            description="The minimum number of tokens that can be used for reasoning for the model.",
        )
        max_budget: int = Field(
            description="The maximum number of tokens that can be used for reasoning for the model.",
        )

        @classmethod
        def from_domain(cls, model: ModelReasoningBudget):
            return cls(
                min_budget=model.min,
                max_budget=model.max,
            )

    reasoning: Reasoning | None = Field(
        description="Reasoning information for the model, only provided if the model supports reasoning.",
    )

    @classmethod
    def from_model_data(cls, id: str, model: FinalModelData):
        provider_data = model.providers[0][1]
        return cls(
            id=id,
            display_name=model.display_name,
            supports=ConciseModelSupports.from_domain(model),
            quality_index=model.quality_index,
            speed_index=model.speed_index,
            cost_per_input_token_usd=provider_data.text_price.prompt_cost_per_token,
            cost_per_output_token_usd=provider_data.text_price.completion_cost_per_token,
            release_date=model.release_date.isoformat(),
            reasoning=cls.Reasoning.from_domain(model.reasoning) if model.reasoning else None,
        )

    @classmethod
    def from_model_for_task(cls, model: ModelForTask):
        return cls(
            id=model.id,
            display_name=model.name,
            # TODO:Not great to call get_model_data here. ModelForTask should just use ModelData
            supports=ConciseModelSupports.from_domain(get_model_data(Model(model.id))),
            quality_index=model.quality_index,
            speed_index=model.speed_index,
            cost_per_input_token_usd=model.price_per_input_token_usd,
            cost_per_output_token_usd=model.price_per_output_token_usd,
            release_date=model.release_date.isoformat(),
            reasoning=cls.Reasoning.from_domain(model.model_data.reasoning) if model.model_data.reasoning else None,
        )


class AgentListItem(BaseModel):
    agent_id: str = Field(description="The ID of the agent")
    is_public: bool = Field(description="Whether the agent is public")

    class AgentSchema(BaseModel):
        agent_schema_id: int = Field(description="The unique ID of this agent schema version")
        created_at: str | None = Field(default=None, description="")
        # TODO: check the name of this `is_hidden` field, maybe more "is_archived" works best
        is_hidden: bool | None = Field(default=None, description="Whether this schema version is hidden from the UI")
        last_active_at: str | None = Field(description="The last time a run was executed using this schema version")

        @classmethod
        def from_domain(cls, v: SerializableTask.PartialTaskVersion):
            return cls(
                agent_schema_id=v.schema_id,
                created_at=v.created_at.isoformat() if v.created_at else None,
                is_hidden=v.is_hidden or False,
                last_active_at=v.last_active_at.isoformat() if v.last_active_at else None,
            )

    schemas: list[AgentSchema] = Field(description="List of schema versions for this agent")

    run_count: int = Field(description="Total number of times this agent has been executed")
    total_cost_usd: float = Field(description="Total cost in USD for all runs of this agent")

    @classmethod
    def from_domain(cls, agent: SerializableTask, stats: TaskRunStorage.AgentRunCount | None):
        return cls(
            agent_id=agent.id,
            is_public=agent.is_public or False,
            schemas=[cls.AgentSchema.from_domain(v) for v in agent.versions],
            run_count=stats.run_count if stats else 0,
            total_cost_usd=stats.total_cost_usd if stats else 0,
        )


class AgentResponse(BaseModel):
    """Details about a single agent"""

    agent_id: str = Field(description="The ID of the agent")
    is_public: bool = Field(description="Whether the agent is public, meaning that it can be accessed by anyone")

    class DetailedAgentSchema(BaseModel):
        """An AgentSchema, i-e a pair of input and output JSON schemas"""

        agent_schema_id: int = Field(description="The unique ID of this agent schema version")
        created_at: str | None = None
        input_json_schema: dict[str, Any] | None
        output_json_schema: dict[str, Any] | None
        is_hidden: bool | None
        last_active_at: str | None

        @classmethod
        def from_domain(cls, v: SerializableTask.PartialTaskVersion):
            return cls(
                agent_schema_id=v.schema_id,
                created_at=v.created_at.isoformat() if v.created_at else None,
                input_json_schema=v.input_schema,
                output_json_schema=v.output_schema,
                is_hidden=v.is_hidden or False,
                last_active_at=v.last_active_at.isoformat() if v.last_active_at else None,
            )

    schemas: list[DetailedAgentSchema]

    class Deployment(BaseModel):
        """A deployment of an agent schema version"""

        schema_id: int = Field(description="The schema ID of the agent schema version that is deployed")
        version_id: str = Field(description="The version ID of the agent schema version that is deployed")
        deployed_at: datetime = Field(description="The date and time when the agent schema version was deployed")
        deployed_by: UserIdentifier | None = Field(description="The user who deployed the agent schema version")
        environment: VersionEnvironment = Field(
            description="The environment in which the agent schema version is deployed",
        )
        model: str = Field(description="The model that is used by that deployment")
        run_count: int | None = Field(description="The number of times the agent schema version has been run")
        last_active_at: datetime | None = Field(
            description="The date and time when the agent schema version was last run",
        )

        @classmethod
        def from_domain(cls, major: VersionMajor, minor: VersionMajor.Minor, deployment: VersionDeploymentMetadata):
            return cls(
                schema_id=major.schema_id,
                version_id=f"{major.major}.{minor.minor}",
                deployed_at=deployment.deployed_at,
                deployed_by=UserIdentifier.from_domain(deployment.deployed_by),
                environment=deployment.environment,
                model=minor.properties.model or "",
                run_count=minor.run_count,
                last_active_at=minor.last_active_at,
            )

    deployments: list[Deployment] = Field(description="List of deployments of this agent")

    run_count: int = Field(description="Total number of times this agent has been executed in the selected time range")
    total_cost_usd: float = Field(description="Total cost in USD for all runs of this agent in the selected time range")

    name: str | None = Field(description="The name of the agent")

    @classmethod
    def _deployment_iterator(cls, versions: list[VersionMajor]):
        for major in versions:
            for minor in major.minors:
                if not minor.deployments:
                    continue
                for deployment in minor.deployments:
                    yield major, minor, deployment

    @classmethod
    def from_domain(
        cls,
        agent: SerializableTask,
        stats: TaskRunStorage.AgentRunCount | None,
        versions: list[VersionMajor],
    ):
        return cls(
            agent_id=agent.id,
            is_public=agent.is_public or False,
            schemas=[cls.DetailedAgentSchema.from_domain(v) for v in agent.versions],
            run_count=stats.run_count if stats else 0,
            total_cost_usd=stats.total_cost_usd if stats else 0,
            name=agent.name,
            deployments=[cls.Deployment.from_domain(*d) for d in cls._deployment_iterator(versions)],
        )


T = TypeVar("T", bound=BaseModel | str)
NullableT = TypeVar("NullableT", bound=BaseModel | None)
ItemT = TypeVar("ItemT", bound=BaseModel)


class EmptyModel(BaseModel):
    """Substitute for a model that is not used in the response"""


class PaginationInfo(BaseModel):
    """Pagination metadata for paginated responses"""

    has_next_page: bool = Field(description="Whether there is a next page")
    next_page: int | None = Field(default=None, description="The next page number")
    max_tokens_limit: int | None = Field(default=None, description="Maximum tokens limit used for pagination")


class MCPToolReturn(BaseModel, Generic[T]):
    """Generic standardized return format for MCP tools with typed data"""

    success: bool
    message: str | None = None
    data: T | None = None
    error: str | None = None


class PaginatedMCPToolReturn(BaseModel, Generic[NullableT, ItemT]):
    """Generic standardized return format for MCP tools with typed data"""

    success: bool
    messages: list[str] | None = None
    data: NullableT | None = None
    items: list[ItemT] | None = None
    error: str | None = None

    pagination: PaginationInfo | None = Field(default=None, description="Pagination info when data is paginated")

    def paginate(  # noqa: C901
        self,
        max_tokens: int,
        page: int = 1,
    ) -> "PaginatedMCPToolReturn[NullableT, ItemT]":
        """
        Restricts the items size to the max tokens limit (consumed limit also takes into account the data, error & message + a buffer for the pagination info)

        Args:
            max_tokens: The maximum tokens allowed in the response
            page: The page number to return (1-based)

        Returns:
            A paginated response with the items restricted to the max tokens limit
        """
        if not self.items or max_tokens <= 0 or page < 1:
            return PaginatedMCPToolReturn[NullableT, ItemT](
                success=self.success,
                data=self.data,
                items=[],
                error=self.error,
                messages=self.messages,
                pagination=PaginationInfo(
                    has_next_page=False,
                    next_page=None,
                    max_tokens_limit=max_tokens,
                ),
            )

        # Calculate base response token count (without items)
        base_response = PaginatedMCPToolReturn[NullableT, ItemT](
            success=self.success,
            data=self.data,
            items=[],
            error=self.error,
            messages=self.messages,
            pagination=PaginationInfo(
                has_next_page=False,
                next_page=None,
                max_tokens_limit=max_tokens,
            ),
        )
        base_token_count = base_response.get_actual_token_count()

        # Reserve some buffer for pagination metadata variations
        buffer_tokens = 100
        available_tokens = max_tokens - base_token_count - buffer_tokens

        if available_tokens <= 0:
            return PaginatedMCPToolReturn[NullableT, ItemT](
                success=False,
                data=self.data,
                items=[],
                error=f"Base response exceeds token limit. Base tokens: {base_token_count}, max allowed: {max_tokens}",
                messages=self.messages,
                pagination=PaginationInfo(
                    has_next_page=False,
                    next_page=None,
                    max_tokens_limit=max_tokens,
                ),
            )

        # Calculate pages by iterating through items until we have the requested page
        current_page_num = 1
        current_page_items: list[ItemT] = []
        current_page_tokens: int = 0
        requested_page_items: list[ItemT] = []
        has_next_page = False

        for i, item in enumerate(self.items):
            # Calculate token count for this item
            item_json = json.dumps(item.model_dump(mode="json"), default=str)

            # using the GPT-4o tokenize as a reasonable estimation for the real token usage of the MCP client agent
            item_tokens: int = tokens_from_string(item_json, model="gpt-4o")

            # Check if single item exceeds available tokens
            if item_tokens > available_tokens:
                return PaginatedMCPToolReturn[NullableT, ItemT](
                    success=False,
                    data=self.data,
                    items=[],
                    error=f"Single item exceeds token limit. Item tokens: {item_tokens}, available: {available_tokens}",
                    messages=self.messages,
                    pagination=PaginationInfo(
                        has_next_page=False,
                        next_page=None,
                        max_tokens_limit=max_tokens,
                    ),
                )

            # Check if adding this item would exceed the page limit
            if current_page_tokens + item_tokens > available_tokens:
                # We've filled a page
                if current_page_num == page:
                    # This is the requested page, save it
                    requested_page_items = current_page_items
                    # Check if there's at least one more item for next page
                    has_next_page = True
                    break
                if current_page_num < page:
                    # Move to next page
                    current_page_num += 1
                    current_page_items = [item]
                    current_page_tokens = item_tokens
                else:
                    # We've passed the requested page
                    break
            else:
                # Add item to current page
                current_page_items.append(item)
                current_page_tokens += item_tokens

                # Check if this is the last item
                if i == len(self.items) - 1:
                    if current_page_num == page:
                        requested_page_items = current_page_items
                    elif current_page_num < page:
                        # Requested page doesn't exist
                        requested_page_items = []

        # If we haven't set requested_page_items yet and we're on the requested page
        if not requested_page_items and current_page_num == page and current_page_items:
            requested_page_items = current_page_items

        # Get items for requested page
        page_items = requested_page_items

        return PaginatedMCPToolReturn[NullableT, ItemT](
            success=self.success,
            data=self.data,
            items=page_items,
            error=self.error,
            messages=self.messages,
            pagination=PaginationInfo(
                has_next_page=has_next_page,
                next_page=page + 1 if has_next_page else None,
                max_tokens_limit=max_tokens,
            ),
        )

    def get_actual_token_count(self) -> int:
        """
        Calculate the actual token count of the current response.

        Args:
            model: Model name for token calculation

        Returns:
            Number of tokens in the serialized response
        """
        response_dict = self.model_dump(mode="json")
        response_json = json.dumps(response_dict, default=str)

        # using the GPT-4o tokenizer as a reasonable estimation for the real token usage of the MCP client agent
        return tokens_from_string(response_json, "gpt-4o")


class _VersionDeploymentMetadata(BaseModel):
    environment: VersionEnvironment
    deployed_at: datetime
    deployed_by: UserIdentifier | None

    @classmethod
    def from_domain(cls, deployment: VersionDeploymentMetadata):
        return cls(
            environment=deployment.environment,
            deployed_at=deployment.deployed_at,
            deployed_by=UserIdentifier.from_domain(deployment.deployed_by),
        )


class _MajorVersionProperties(BaseModel):
    temperature: float
    instructions: str | None
    messages: list[Message] | None

    @classmethod
    def from_domain(cls, properties: VersionMajor.Properties | TaskGroupProperties):
        return cls(
            temperature=properties.temperature or 0.0,
            instructions=properties.instructions,
            messages=properties.messages,
        )


class _MinorVersion(BaseModel):
    minor: int
    id: str
    model: str

    deployments: list[_VersionDeploymentMetadata] | None

    cost_estimate_per_run_usd: float | None

    last_active_at: datetime | None

    is_favorite: bool | None

    favorited_by: UserIdentifier | None

    created_by: UserIdentifier | None

    notes: str | None

    run_count: int | None

    properties: ShortVersionProperties

    @classmethod
    def from_minor(cls, minor: VersionMajor.Minor):
        return cls(
            id=minor.id,
            minor=minor.minor,
            properties=ShortVersionProperties(
                model=minor.properties.model,
                provider=minor.properties.provider,
                temperature=minor.properties.temperature,
            ),
            model=minor.properties.model,
            deployments=[_VersionDeploymentMetadata.from_domain(d) for d in minor.deployments]
            if minor.deployments
            else None,
            cost_estimate_per_run_usd=minor.cost_estimate_usd,
            last_active_at=minor.last_active_at,
            is_favorite=minor.is_favorite,
            notes=minor.notes,
            run_count=minor.run_count,
            favorited_by=UserIdentifier.from_domain(minor.favorited_by),
            created_by=UserIdentifier.from_domain(minor.created_by),
        )

    @classmethod
    def from_version(
        cls,
        version: TaskGroup,
        deployments: list[VersionDeploymentMetadata] | None,
        cost_estimate_usd: float | None,
        variant: SerializableTaskVariant | None,
    ):
        return cls(
            id=version.id,
            minor=version.semver.minor if version.semver else 0,
            model=version.properties.model or "",
            deployments=[_VersionDeploymentMetadata.from_domain(d) for d in deployments] if deployments else None,
            cost_estimate_per_run_usd=cost_estimate_usd,
            last_active_at=version.last_active_at,
            is_favorite=version.is_favorite,
            notes=version.notes,
            run_count=version.run_count,
            favorited_by=UserIdentifier.from_domain(version.favorited_by),
            created_by=UserIdentifier.from_domain(version.created_by),
            properties=ShortVersionProperties(
                model=version.properties.model,
                provider=version.properties.provider,
                temperature=version.properties.temperature,
            ),
        )


# TODO: clarify what data is needed here
class MajorVersion(BaseModel):
    major: int
    schema_id: int

    minors: list[_MinorVersion]

    created_by: UserIdentifier | None

    created_at: datetime

    properties: _MajorVersionProperties

    @classmethod
    def from_major(cls, version: VersionMajor):
        return cls(
            major=version.major,
            schema_id=version.schema_id,
            created_by=UserIdentifier.from_domain(version.created_by),
            created_at=version.created_at,
            minors=[_MinorVersion.from_minor(m) for m in version.minors],
            properties=_MajorVersionProperties.from_domain(version.properties),
        )

    @classmethod
    def from_version(
        cls,
        version: TaskGroup,
        deployments: list[VersionDeploymentMetadata] | None,
        cost_estimate_usd: float | None,
        variant: SerializableTaskVariant | None,
    ):
        return cls(
            major=version.semver.major if version.semver else 0,
            schema_id=version.schema_id,
            created_by=UserIdentifier.from_domain(version.created_by),
            created_at=version.created_at or datetime_zero(),
            minors=[_MinorVersion.from_version(version, deployments, cost_estimate_usd, variant)],
            properties=_MajorVersionProperties.from_domain(version.properties),
        )


class StandardModelResponse(BaseModel):
    """A model response compatible with the OpenAI API"""

    object: Literal["list"] = "list"

    class ModelItem(BaseModel):
        id: str
        object: Literal["model"] = "model"
        created: int
        owned_by: str
        display_name: str
        icon_url: str
        supports: dict[str, Any]

        @classmethod
        def from_model_data(cls, id: str, model: FinalModelData):
            return cls(
                id=id,
                created=int(datetime.combine(model.release_date, time(0, 0)).timestamp()),
                owned_by=model.provider_name,
                display_name=model.display_name,
                icon_url=model.icon_url,
                supports={
                    k.removeprefix("supports_"): v
                    for k, v in model.model_dump(
                        mode="json",
                        include=set(ModelDataSupports.model_fields.keys()),
                    ).items()
                },
            )

    data: list[ModelItem]


class Error(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None

    @classmethod
    def from_domain(cls, error: ErrorResponse.Error):
        return cls(
            code=error.code,
            message=error.message,
            details=error.details,
        )


class AgentVersion(BaseModel):
    id: str
    model: str
    temperature: float | None
    messages: list[Message] | None
    instructions: str | None
    top_p: float | None
    max_tokens: int | None
    frequency_penalty: float | None
    presence_penalty: float | None

    @classmethod
    def from_domain(cls, version: TaskGroup):
        return cls(
            id=version.displayed_id,  # TODO: make sure the MCP is capable of retrieving a version by its Semver
            model=version.properties.model or "",  # there is always a model
            temperature=version.properties.temperature,
            messages=version.properties.messages,
            instructions=version.properties.instructions,
            top_p=version.properties.top_p,
            max_tokens=version.properties.max_tokens,
            frequency_penalty=version.properties.frequency_penalty,
            presence_penalty=version.properties.presence_penalty,
        )


class MCPRun(BaseModel):
    """A run as returned by the MCP Server"""

    id: str
    conversation_id: str
    agent_id: str
    agent_schema_id: int
    agent_version: AgentVersion
    status: Literal[
        "success",
        "error",
    ]
    agent_input: dict[str, Any] | None
    messages: list[Message] = Field(description="The exchanged messages, including the returned assistant message")
    duration_seconds: float | None
    cost_usd: float | None
    created_at: datetime
    environment: VersionEnvironment | None = Field(
        description="The environment that was used to trigger the run, if any",
    )
    metadata: dict[str, Any] | None
    response_json_schema: dict[str, Any] | None = Field(
        description="Only present when using structured outputs. The JSON schema that the model was asked to respect",
    )
    error: Error | None = Field(description="An error returned by the model")

    url: str

    @classmethod
    def from_domain(
        cls,
        run: AgentRun,
        version: TaskGroup | None,
        output_schema: dict[str, Any] | None,
        url: str,
        truncate: bool = True,
    ):
        messages = run.messages
        # Truncation is really arbitrary for now
        # We limit:
        # - the length of the message text content to 10000 characters, ~3000 tokens
        # - the size of input data to 1000 characters, ~300 tokens. The input is repeated in the messages
        # - the size of the file data to 10 characters since base64 data is not really interesting and eats tokens fast
        # TODO: implement better truncation logic
        # Note that when we actually fetch messages from the database, the files will have a URL
        if truncate:
            for m in messages:
                for m in m.content:
                    if m.file and m.file.data:
                        # No need to pass base64 data
                        m.file.data = truncate_field(m.file.data, 10)

                    if m.text:
                        m.text = truncate_field(m.text, 10000)

        agent_input = run.task_input or None
        if agent_input:
            agent_input = {k: v for k, v in agent_input.items() if k != "workflowai.messages"}
            if truncate:
                agent_input = truncate_obj(agent_input)

        return cls(
            id=run.id,
            conversation_id=run.conversation_id or "",  # there is always a conversation id, or is for typing reasons
            agent_id=run.task_id,
            agent_schema_id=run.task_schema_id,
            # The version attached to the run is likely to be incomplete
            # See https://linear.app/workflowai/issue/WOR-4485/stop-storing-non-saved-versions-and-attach-them-to-runs-instead
            agent_version=AgentVersion.from_domain(version) if version else AgentVersion.from_domain(run.group),
            status="success" if run.status == "success" else "error",
            agent_input=agent_input,
            messages=messages,
            duration_seconds=run.duration_seconds,
            cost_usd=run.cost_usd,
            created_at=run.created_at,
            metadata=run.filtered_metadata,
            response_json_schema=output_schema,
            error=Error.from_domain(run.error) if run.error else None,
            url=url,
            environment=run.used_environment,
        )


class SearchResponse(BaseModel):
    page_content: str | None = Field(
        default=None,
        description="The content of the requested page, only present when a specific page is requested",
    )

    class QueryResult(BaseModel):
        content_snippet: str
        source_page: str

    query_results: list[QueryResult] | None = Field(
        default=None,
        description="Query results, only present when a query is provided",
    )
