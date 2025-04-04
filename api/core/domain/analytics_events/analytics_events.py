from abc import ABC
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, Field

from core.domain.llm_completion import total_tokens_count
from core.domain.task_group import TaskGroup
from core.domain.task_run import SerializableTaskRun
from core.domain.tenant_data import PublicOrganizationData, TenantData
from core.domain.users import UserIdentifier
from core.utils.fields import datetime_factory, id_factory


class SourceType(StrEnum):
    SDK = "sdk"
    WEB = "web"
    API = "api"

    @property
    def is_active(self) -> bool:
        return self == SourceType.API or self == SourceType.SDK


class UserProperties(BaseModel):
    user_id: str | None = Field(
        default=None,
        description="The ID of the logged user, if any (can be None when using an org level token)",
    )
    user_email: str | None = Field(
        default=None,
        description="The email of the logged user, if any (can be None when using an org level token)",
    )
    client_source: SourceType = Field(default=SourceType.API, description="The source of the event")
    client_version: str | None = Field(default=None, description="The version of the client")
    client_language: str | None = Field(
        default=None,
        description="The language of the client, when the source is 'sdk'",
    )

    def to_user_identifier(self) -> UserIdentifier:
        return UserIdentifier(
            user_id=self.user_id,
            user_email=self.user_email,
        )


class OrganizationProperties(BaseModel):
    tenant: str = Field(description="The tenant ID, which is our internal ID")
    organization_id: str | None = Field(default=None, description="The user's organization ID, immutable once created")
    organization_slug: str | None = Field(
        default=None,
        description="The user's organization slug. Can be updated by the user.",
    )
    organization_credits_usd: float | None = Field(
        default=None,
        description="The user's organization remaining credits in USD",
    )

    @classmethod
    def build(cls, tenant: TenantData):
        return cls(
            tenant=tenant.tenant,
            organization_id=tenant.org_id or None,
            organization_slug=tenant.slug or None,
            organization_credits_usd=tenant.current_credits_usd,
        )


class TaskProperties(BaseModel):
    organization_id: str | None = Field(description="The organization ID")
    organization_name: str | None = Field(description="The organization name")
    organization_slug: str | None = Field(description="The organization slug")
    id: str = Field(description="The task ID")
    schema_id: int | None = Field(None, description="The version")

    @classmethod
    def build(cls, id: str, schema_id: int | None, tenant: PublicOrganizationData | None):
        return cls(
            id=id,
            schema_id=schema_id,
            organization_id=(tenant.org_id or tenant.tenant) if tenant else None,
            organization_name=(tenant.name or None) if tenant else None,
            organization_slug=(tenant.slug or None) if tenant else None,
        )


# --- Base Task Event Properties ---


class VersionProperties(BaseModel):
    iteration: int = Field(description="The iteration number", ge=0)
    model: str | None = Field(description="The model name")
    provider: str | None = Field(description="The model provider name")
    temperature: float | None = Field(description="The temperature", ge=0)

    # See example for 'max_tokens' parameter for OpenAI: https://platform.openai.com/docs/api-reference/chat/create#chat-create-max_tokens
    max_tokens: int | None = Field(description="The maximum tokens that can be generate in the model answer", ge=0)
    few_shot: bool | None = Field(description="Whether few-shot is enabled")

    @classmethod
    def from_domain(cls, group: TaskGroup):
        return cls(
            iteration=group.iteration,
            model=group.properties.model,
            provider=group.properties.provider,
            temperature=group.properties.temperature,
            max_tokens=group.properties.max_tokens,
            few_shot=group.properties.few_shot is not None
            and group.properties.few_shot.count is not None
            and group.properties.few_shot.count > 0,
        )


# --- User Account Creation ---


class OrganizationCreatedProperties(BaseModel):
    event_type: Literal["org.created.account"] = "org.created.account"


# --- Task Creation ---


class CreatedTaskProperties(BaseModel):
    event_type: Literal["org.created.task"] = "org.created.task"


# --- Task Schema Edit ---
class EditedTaskSchemaEventProperties(BaseModel):
    updated_task: TaskProperties

    event_type: Literal["org.edited.task_schema"] = "org.edited.task_schema"


# --- Task Run ---

type RunTrigger = Literal["user", "benchmark", "evaluation", "internal", "review_benchmark"]


class RanTaskEventProperties(BaseModel):
    event_type: Literal["org.ran.task"] = "org.ran.task"

    trigger: RunTrigger | None

    group: VersionProperties = Field(description="The group of the task run")
    environment: str | None = Field(description="The environment used as part of the 'deploy to environment' feature")

    latency_seconds: float | None = Field(description="The latency of the task run in seconds", ge=0)

    tokens_count: float = Field(description="The number of tokens in the task run", ge=0)
    input_tokens_count: float | None = Field(description="The number of tokens in the input", ge=0)
    output_tokens_count: float | None = Field(description="The number of tokens in the output", ge=0)

    cost_usd: float | None = Field(description="The cost of the task run in USD", ge=0)

    error_code: str | None = Field(description="The error code of the task run", default=None)

    from_cache: bool | None = Field(default=None, description="Whether the task run was from cache")

    @classmethod
    def from_task_run(cls, task_run: SerializableTaskRun, trigger: RunTrigger | None):
        input_tokens, output_tokens = total_tokens_count(task_run.llm_completions)

        return cls(
            trigger=trigger,
            group=VersionProperties.from_domain(task_run.group),
            environment=task_run.used_environment,
            latency_seconds=task_run.duration_seconds,
            tokens_count=(input_tokens or 0) + (output_tokens or 0),
            input_tokens_count=input_tokens,
            output_tokens_count=output_tokens,
            cost_usd=task_run.cost_usd,
            error_code=task_run.error.code if task_run.error else None,
            from_cache=task_run.from_cache or None,
        )


# --- Task Run Import ---


class ImportedTaskRunEventProperties(BaseModel):
    event_type: Literal["org.imported.task_run"] = "org.imported.task_run"

    group: VersionProperties = Field(description="The group of the task run")

    latency_seconds: float | None = Field(description="The latency of the task run in seconds", ge=0)
    cost_usd: float | None = Field(description="The cost of the task run in USD", ge=0)


# --- Task Run Rating ---


class RatedTaskRunEventProperties(BaseModel):
    event_type: Literal["org.rated.task_run"] = "org.rated.task_run"

    group: VersionProperties = Field(description="The group of the task run")

    rating: float = Field(description="The rating of the task run", ge=0, le=1)


class AnnotatedTaskRunEventProperties(BaseModel):
    event_type: Literal["org.annotated.task_run"] = "org.annotated.task_run"

    group: VersionProperties = Field(description="The group of the task run")

    is_run_correct: bool = Field(description="Whether the task run is correct")


# --- Deploy ---


class DeployedTaskVersionProperties(BaseModel):
    event_type: Literal["org.deployed.version"] = "org.deployed.version"
    group: VersionProperties = Field(description="The group of the task run")

    environment: str = Field(description="The task version alias")


# --- Benchmark ---


class BenchmarkUpdatedProperties(BaseModel):
    event_type: Literal["org.ran.benchmark"] = "org.ran.benchmark"

    group_count: int = Field(description="The number of groups in the benchmark")
    input_count: int = Field(description="The number of inputs in the benchmark")


# --- Created inputs ---


class GeneratedInputProperties(BaseModel):
    event_type: Literal["org.generated.task_input"] = "org.generated.task_input"

    custom_instructions: bool = Field(description="Whether the inputs were generated with custom instructions")

    input_count: int = Field(description="The number of inputs generated")


# --- Actual events ---


EventProperties: TypeAlias = Annotated[
    AnnotatedTaskRunEventProperties
    | BenchmarkUpdatedProperties
    | CreatedTaskProperties
    | DeployedTaskVersionProperties
    | EditedTaskSchemaEventProperties
    | GeneratedInputProperties
    | ImportedTaskRunEventProperties
    | OrganizationCreatedProperties
    | RanTaskEventProperties
    | RatedTaskRunEventProperties,
    Field(discriminator="event_type"),
]


class AnalyticsEvent(BaseModel, ABC):
    time: datetime = Field(default_factory=datetime_factory)

    insert_id: str = Field(description="The insert ID", default_factory=id_factory)

    event_properties: EventProperties = Field(description="The event-specific properties")


class FullAnalyticsEvent(BaseModel):
    user_properties: UserProperties | None
    organization_properties: OrganizationProperties
    task_properties: TaskProperties | None

    event: AnalyticsEvent
