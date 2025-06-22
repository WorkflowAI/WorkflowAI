import json
from datetime import datetime, time
from typing import Any, Generic, Literal, TypeAlias, TypeVar

from pydantic import BaseModel, Field

from api.schemas.user_identifier import UserIdentifier
from api.schemas.version_properties import ShortVersionProperties
from api.services.internal_tasks.ai_engineer_service import AIEngineerReponse
from api.services.models import ModelForTask
from core.domain.agent_run import AgentRun
from core.domain.error_response import ErrorResponse
from core.domain.message import Message
from core.domain.models.model_data import FinalModelData
from core.domain.models.model_data_supports import ModelDataSupports
from core.domain.task_group import TaskGroup
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_variant import SerializableTaskVariant
from core.domain.version_environment import VersionEnvironment
from core.domain.version_major import VersionDeploymentMetadata, VersionMajor
from core.utils.fields import datetime_zero
from core.utils.token_utils import tokens_from_string

# New sorting type aliases with two-field approach
AgentSortField: TypeAlias = Literal["last_active_at", "total_cost_usd", "run_count"]
ModelSortField: TypeAlias = Literal["release_date", "quality_index", "cost"]
SortOrder: TypeAlias = Literal["asc", "desc"]


class UsefulLinks(BaseModel):
    class Link(BaseModel):
        title: str
        url: str
        description: str

    description: str = "A collection of useful link that the user can access in the browser, those link are NOT directly accessible without being authenticated in the browser"
    useful_links: list[Link]


class ConciseLatestModelResponse(BaseModel):
    id: str
    currently_points_to: str


class ConciseModelResponse(BaseModel):
    id: str
    display_name: str
    supports: list[str]
    quality_index: int
    cost_per_input_token_usd: float
    cost_per_output_token_usd: float
    release_date: str
    reasoning: bool = Field(
        description="Whether the model supports reasoning mode with step-by-step reasoning content",
    )

    @classmethod
    def from_model_data(cls, id: str, model: FinalModelData):
        SUPPORTS_WHITELIST = {
            "supports_input_image",
            "supports_input_pdf",
            "supports_input_audio",
            "supports_audio_only",
            "supports_tool_calling",
            "supports_reasoning",
        }

        provider_data = model.providers[0][1]
        return cls(
            id=id,
            display_name=model.display_name,
            supports=[
                k.removeprefix("supports_")
                for k, v in model.model_dump().items()
                if v is True and k in SUPPORTS_WHITELIST
            ],
            quality_index=model.quality_index,
            cost_per_input_token_usd=provider_data.text_price.prompt_cost_per_token,
            cost_per_output_token_usd=provider_data.text_price.completion_cost_per_token,
            release_date=model.release_date.isoformat(),
            reasoning=getattr(model, "supports_reasoning", False),
        )

    @classmethod
    def from_model_for_task(cls, model: ModelForTask):
        return cls(
            id=model.id,
            display_name=model.name,
            supports=model.modes,
            quality_index=model.quality_index,
            cost_per_input_token_usd=model.price_per_input_token_usd,
            cost_per_output_token_usd=model.price_per_output_token_usd,
            release_date=model.release_date.isoformat(),
            reasoning=False,
        )


class AgentResponse(BaseModel):
    agent_id: str = Field(description="Unique identifier for the agent")
    is_public: bool = Field(description="Whether this agent is publicly accessible")

    class AgentSchema(BaseModel):
        agent_schema_id: int = Field(description="Unique schema ID for this agent version")
        created_at: str | None = Field(default=None, description="ISO timestamp when this schema was created")
        input_json_schema: dict[str, Any] | None = Field(
            default=None,
            description="JSON schema defining the expected input structure for this agent",
        )
        output_json_schema: dict[str, Any] | None = Field(
            default=None,
            description="JSON schema defining the output structure this agent produces",
        )
        is_hidden: bool | None = Field(
            default=None,
            description="Whether this schema version is hidden from normal listings",
        )
        last_active_at: str | None = Field(description="ISO timestamp of the last time this schema was used in a run")

    schemas: list[AgentSchema] = Field(description="List of schema versions available for this agent")

    run_count: int = Field(description="Total number of runs executed for this agent in the specified time period")
    total_cost_usd: float = Field(
        description="Total cost in USD for all runs of this agent in the specified time period",
    )


class AgentResponseList(BaseModel):
    agents: list[AgentResponse]


T = TypeVar("T", bound=BaseModel)
NullableT = TypeVar("NullableT", bound=BaseModel | None)
ItemT = TypeVar("ItemT", bound=BaseModel)


class PaginationInfo(BaseModel):
    """Pagination metadata for paginated responses"""

    has_next_page: bool = Field(description="Whether there is a next page")
    next_page: int | None = Field(default=None, description="The next page number")
    max_tokens_limit: int | None = Field(default=None, description="Maximum tokens limit used for pagination")


# TODO: delete this class when all tools are migrated to the new MCPToolReturn or PaginatedMCPToolReturn
class LegacyMCPToolReturn(BaseModel):
    success: bool
    messages: list[str] | None = None
    data: dict[str, Any] | None = None
    error: str | None = None


class MCPToolReturn(BaseModel, Generic[T]):
    """Generic standardized return format for MCP tools with typed data"""

    success: bool
    messages: list[str] | None = None
    data: T | None = None
    error: str | None = None


class AIEngineerReponseWithUsefulLinks(AIEngineerReponse):
    useful_links: UsefulLinks


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
    task_variant_id: str | None

    @classmethod
    def from_domain(cls, properties: VersionMajor.Properties | TaskGroupProperties):
        return cls(
            temperature=properties.temperature or 0.0,
            instructions=properties.instructions,
            messages=properties.messages,
            task_variant_id=properties.task_variant_id,
        )


class _MinorVersion(BaseModel):
    minor: int
    id: str
    model: str

    deployments: list[_VersionDeploymentMetadata] | None

    cost_estimate_usd: float | None

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
            cost_estimate_usd=minor.cost_estimate_usd,
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
            cost_estimate_usd=cost_estimate_usd,
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
    """
    CONCEPT: Enhanced with comprehensive field descriptions as single source of truth.
    These descriptions could be automatically extracted to generate tool documentation,
    eliminating the need for manual 40+ line docstrings in tool functions.
    """

    # Core Run Information
    id: str = Field(
        description="Unique identifier for this specific run - use this to reference the run in other operations",
    )
    conversation_id: str = Field(
        description="Links this run to a broader conversation context - multiple runs can share the same conversation_id",
    )
    agent_id: str = Field(
        description="The ID of the agent that was executed for this run",
    )
    agent_schema_id: int = Field(
        description="The schema/version ID of the agent used for this run - corresponds to a specific configuration",
    )
    agent_version: AgentVersion = Field(
        description="Complete configuration details of the agent version used, including model, temperature, and instructions",
    )
    status: Literal["success", "error"] = Field(
        description="Current status of the run execution - 'success' for completed runs, 'error' for failed runs",
    )

    # Input/Output Data
    agent_input: dict[str, Any] | None = Field(
        description="Complete input data that was provided to the agent for this run - excludes internal message handling",
    )
    messages: list[Message] = Field(
        description="The complete conversation flow including user inputs and AI responses - this is the actual conversation that occurred",
    )

    # Performance Metrics
    duration_seconds: float | None = Field(
        description="Total execution time in seconds from start to completion - useful for performance analysis",
    )
    cost_usd: float | None = Field(
        description="Total cost of this run in USD based on model usage, tokens processed, and provider pricing",
    )
    created_at: datetime = Field(
        description="ISO timestamp of when the run was created/started - useful for filtering and sorting",
    )

    # Metadata and Configuration
    metadata: dict[str, Any] | None = Field(
        description="Custom metadata attached to this run - often contains user_id, environment, or application-specific data",
    )
    response_json_schema: dict[str, Any] | None = Field(
        description="JSON schema that the model was asked to respect for structured outputs - only present when using structured generation",
    )

    # Error Information
    error: Error | None = Field(
        description="Detailed error information if the run failed - includes error code, message, and debugging details",
    )

    @classmethod
    def from_domain(
        cls,
        run: AgentRun,
        version: TaskGroup | None,
        output_schema: dict[str, Any] | None,
    ):
        return cls(
            id=run.id,
            conversation_id=run.conversation_id or "",  # there is always a conversation id, or is for typing reasons
            agent_id=run.task_id,
            agent_schema_id=run.task_schema_id,
            # The version attached to the run is likely to be incomplete
            # See https://linear.app/workflowai/issue/WOR-4485/stop-storing-non-saved-versions-and-attach-them-to-runs-instead
            agent_version=AgentVersion.from_domain(version) if version else AgentVersion.from_domain(run.group),
            status="success" if run.status == "success" else "error",
            agent_input={k: v for k, v in run.task_input.items() if k != "workflowai.messages"}
            if run.task_input
            else None,
            messages=run.messages,
            duration_seconds=run.duration_seconds,
            cost_usd=run.cost_usd,
            created_at=run.created_at,
            metadata=run.metadata,
            response_json_schema=output_schema,
            error=Error.from_domain(run.error) if run.error else None,
        )
