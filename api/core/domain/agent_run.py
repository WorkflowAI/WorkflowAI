from datetime import datetime, timezone
from typing import Any, Literal, Optional, Protocol, cast

from pydantic import BaseModel, Field, model_validator

from core.domain.consts import (
    METADATA_KEY_DEPLOYMENT_ENVIRONMENT,
    METADATA_KEY_DEPLOYMENT_ENVIRONMENT_DEPRECATED,
)
from core.domain.error_response import ErrorResponse
from core.domain.fields.internal_reasoning_steps import InternalReasoningStep
from core.domain.llm_completion import LLMCompletion
from core.domain.review import Review
from core.domain.task_group import TaskGroup
from core.domain.tool_call import ToolCall, ToolCallRequestWithID
from core.domain.types import TaskInputDict, TaskOutputDict
from core.domain.utils import compute_eval_hash

AIReview = Literal["in_progress", "positive", "negative", "unsure"]

UserReview = Literal["positive", "negative"]


class AgentRunBase(BaseModel):
    id: str = Field(
        ...,
        description="the id of the task run. If not provided a uuid will be generated",
    )

    # TODO: fill
    task_uid: int = Field(default=0, description="the uid of the task")

    task_id: str = Field(..., description="the id of the associated task, read only", examples=[""])
    task_schema_id: int = Field(..., description="the schema idx of the associated task, read only")
    task_input_hash: str = Field(..., description="a hash describing the input")
    task_input_preview: str = Field(
        default="",
        description="A preview of the input data. This is used to display the input data in the UI.",
    )
    task_output_hash: str = Field(..., description="a hash describing the output")
    task_output_preview: str = Field(
        default="",
        description="A preview of the output data. This is used to display the output data in the UI.",
    )
    group: TaskGroup

    status: Literal["success", "failure"] = "success"

    error: ErrorResponse.Error | None = None

    duration_seconds: Optional[float] = None
    overhead_seconds: Optional[float] = None
    cost_usd: Optional[float] = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="The time the task run was created",
    )

    user_review: UserReview | None = None

    ai_review: AIReview | None = None

    author_tenant: str | None = None
    author_uid: int | None = None

    eval_hash: str = ""

    def _assign_eval_hash(self):
        if not self.eval_hash and (self.task_schema_id and self.task_input_hash and self.task_output_hash):
            self.eval_hash = compute_eval_hash(self.task_schema_id, self.task_input_hash, self.task_output_hash)

    @model_validator(mode="after")
    def post_validate(self):
        self._assign_eval_hash()
        return self

    def assign_review(self, review: Review):
        match review.reviewer.reviewer_type:
            case "user":
                self.user_review = cast(UserReview, review.outcome)
            case "ai":
                self.ai_review = review.outcome


class AgentRun(AgentRunBase):
    """A task run represents an instance of a task being executed"""

    task_input: TaskInputDict
    task_output: TaskOutputDict

    # ------------------------------------------
    # Optional properties

    metadata: dict[str, Any] | None = Field(
        default=None,
        description="A user set metadata key / value. Keys are not searchable.",
    )

    llm_completions: Optional[list[LLMCompletion]] = Field(
        default=None,
        description="A list of raw completions used to generate the task output",
    )

    from_cache: bool | None = None

    private_fields: set[str] | None = None

    is_active: bool | None = Field(
        default=None,
        description="Whether the task run is triggered using sdk/api",
    )

    reasoning_steps: list[InternalReasoningStep] | None = None

    tool_calls: list[ToolCall] | None = Field(
        default=None,
        description="A list of tool calls used to generate the task output",
    )

    tool_call_requests: list[ToolCallRequestWithID] | None = None

    version_changed: bool | None = None

    is_external: bool | None = None

    @property
    def used_environment(self) -> str | None:
        if not self.metadata:
            return None

        if METADATA_KEY_DEPLOYMENT_ENVIRONMENT in self.metadata:
            return str(self.metadata[METADATA_KEY_DEPLOYMENT_ENVIRONMENT])

        if METADATA_KEY_DEPLOYMENT_ENVIRONMENT_DEPRECATED in self.metadata:
            return str(self.metadata[METADATA_KEY_DEPLOYMENT_ENVIRONMENT_DEPRECATED]).removeprefix("environment=")
        return None

    @model_validator(mode="after")
    def post_validate(self):
        self._assign_eval_hash()
        return self

    def is_failure(self) -> bool:
        return self.status == "failure"

    @property
    def input_token_count(self) -> int | None:
        if self.llm_completions:
            return int(sum(completion.usage.prompt_token_count or 0 for completion in self.llm_completions))
        return None

    @property
    def output_token_count(self) -> int | None:
        if self.llm_completions:
            return int(sum(completion.usage.completion_token_count or 0 for completion in self.llm_completions))
        return None

    @property
    def credits_used(self) -> float:
        """Return the total amount of credits used for the task run"""
        if not self.llm_completions:
            return 0

        return sum(completion.credits_used for completion in self.llm_completions)


class TaskRunIO(Protocol):
    @property
    def task_input(self) -> dict[str, Any]: ...

    @property
    def task_output(self) -> dict[str, Any]: ...
