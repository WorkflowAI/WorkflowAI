from datetime import datetime, timedelta
from typing import Any, Concatenate, Coroutine, Generic, Literal, NamedTuple, Protocol, Self, TypeVar

from pydantic import BaseModel, field_validator, model_validator
from taskiq import AsyncTaskiqDecoratedTask

from core.agents.chat_task_schema_generation.chat_task_schema_generation_task import AgentSchemaJson
from core.agents.meta_agent import MetaAgentChatMessage
from core.domain.agent_run import AgentRun
from core.domain.analytics_events.analytics_events import (
    FullAnalyticsEvent,
    OrganizationProperties,
    RunTrigger,
    TaskProperties,
    UserProperties,
)
from core.domain.fields.chat_message import ChatMessage
from core.domain.review import Review
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_variant import SerializableTaskVariant
from core.domain.users import UserIdentifier


class Event(BaseModel):
    name: str = ""

    tenant: str = ""  # Default to "" since it will be set before being sent
    tenant_uid: int = 0

    user_properties: UserProperties | None = None
    organization_properties: OrganizationProperties | None = None
    task_properties: TaskProperties | None = None

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, name: Any) -> str:
        if not name:
            return cls.__name__.removesuffix("Event")
        return name

    @property
    def user_identifier(self) -> UserIdentifier | None:
        if self.user_properties:
            return UserIdentifier(user_id=self.user_properties.user_id, user_email=self.user_properties.user_email)
        return None


# TODO: all events should only include resource ids


class StoreTaskRunEvent(Event):
    run: AgentRun
    task: SerializableTaskVariant
    trigger: RunTrigger | None


class RunCreatedEvent(Event):
    run: AgentRun


class TaskEvent(Event):
    task_id: str
    task_schema_id: int


class TaskGroupCreated(Event):
    task_id: str
    task_schema_id: int
    id: str
    disable_autosave: bool | None = None


class TaskGroupSaved(Event):
    task_id: str
    task_schema_id: int
    hash: str
    major: int
    minor: int
    properties: TaskGroupProperties


class TaskSchemaCreatedEvent(TaskEvent):
    skip_generation: bool = False


class TaskChatStartedEvent(Event):
    existing_task_name: str | None = None
    user_message: str


class TaskSchemaGeneratedEvent(Event):
    version_identifier: str
    chat_messages: list[ChatMessage]
    previous_task_schema: AgentSchemaJson | None = None
    assistant_answer: str
    updated_task_schema: AgentSchemaJson


class ProxyAgentCreatedEvent(Event):
    agent_slug: str
    task_id: str
    task_schema_id: int


class TriggerTaskRunEvent(TaskEvent):
    group_iteration: int
    # Either task_input_hash or task_input must be provided
    task_input_hash: str | None
    task_input: dict[str, Any] | None

    # The run id to use
    run_id: str | None = None

    trigger: RunTrigger

    retry_count: int = 0

    @model_validator(mode="after")
    def at_least_one_input(self) -> Self:
        if self.task_input_hash is None and self.task_input is None:
            raise ValueError("Either task_input_hash or task_input must be provided")
        return self


class TriggerRunEvaluationEvent(TaskEvent):
    task_input_hash: str
    task_output_hash: str
    input_evaluation_id: str | None
    evaluator_id: str | None
    run_id: str
    iteration: int
    version_id: str
    run_failed: bool


class RecomputeReviewBenchmarkEvent(TaskEvent):
    # If specified, only recomputes the review benchmark for the given iterations
    iterations: set[int] | None = None
    # Sent when a run was just completed
    run_id: str | None = None
    input_hashes: tuple[str, str] | None = None
    # Whether the run came from the cache
    cached_run_id: str | None = None


# TODO: remove once we no longer use the event (post 2025-06-03 release)
class SendAnalyticsEvent(Event):
    event: FullAnalyticsEvent


class UserReviewAddedEvent(TaskEvent):
    task_input_hash: str
    task_output_hash: str
    review_id: str
    # Whether this is the first review for the given input hash
    # A first review will trigger benchmark runs
    is_first_review: bool = False
    run_id: str | None = None

    # a review id that this review is in response to
    in_response_to: str | None = None
    comment: str | None = None

    @classmethod
    def from_review(
        cls,
        review: Review,
        is_first_review: bool = False,
        run_id: str | None = None,
    ) -> Self:
        return cls(
            task_id=review.task_id,
            task_schema_id=review.task_schema_id,
            task_input_hash=review.task_input_hash,
            task_output_hash=review.task_output_hash,
            review_id=review.id,
            comment=review.comment or None,
            in_response_to=review.responding_to_review_id or None,
            run_id=run_id,
            is_first_review=is_first_review,
        )


class AIReviewerBuildStartedEvent(TaskEvent):
    evaluator_id: str


class AIReviewerUpdatedEvent(TaskEvent):
    # The evaluator id that completed the build
    evaluator_id: str | None
    input_evaluation_id: str | None = None
    task_input_hash: str | None = None
    evaluator_did_change: bool


class AIReviewStartedEvent(TaskEvent):
    review_id: str
    task_input_hash: str
    task_output_hash: str
    run_id: str | None
    version_id: str | None


class AIReviewCompletedEvent(TaskEvent):
    review_id: str | None
    reviewer_type: Literal["ai", "user"]
    task_input_hash: str
    task_output_hash: str


class AgentInstructionsGeneratedEvent(TaskEvent):
    agent_instructions: str


class MetaAgentChatMessagesSent(Event):
    messages: list[MetaAgentChatMessage]


class FeaturesByDomainGenerationStarted(Event):
    company_domain: str


class FeedbackCreatedEvent(Event):
    feedback_id: str
    task_uid: int
    user_id: str | None
    run_id: str
    outcome: Literal["positive", "negative"]
    comment: str | None


class TenantCreatedEvent(Event):
    pass


class TenantMigratedEvent(Event):
    migrated_to: Literal["organization", "user"]
    from_user_id: str | None = None
    from_anon_id: str | None = None


class EventRouter(Protocol):
    def __call__(self, event: Event, retry_after: datetime | None = None) -> None: ...


T = TypeVar("T", bound=Event)


class WithDelay(NamedTuple, Generic[T]):
    job: AsyncTaskiqDecoratedTask[Concatenate[T, ...], Coroutine[Any, Any, None]]
    delay: timedelta
