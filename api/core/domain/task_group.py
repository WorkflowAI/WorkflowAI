from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.domain.major_minor import MajorMinor
from core.domain.users import UserIdentifier
from core.utils.schemas import add_required_fields

from .task_group_properties import TaskGroupProperties

TaskGroupIdentifier = str | MajorMinor


class TaskGroup(BaseModel):
    id: str = Field(
        default="",
        description="The group id either client provided or generated, stable for given set of properties",
    )
    semver: MajorMinor | None = Field(
        default=None,
        description="The semantic version of the task group",
    )
    schema_id: int = Field(
        default=0,
        description="The schema id of the task group, incremented for each new schema",
    )
    iteration: int = Field(default=0, description="The iteration of the group, incremented for each new group")
    run_count: int = Field(default=0, description="The number of runs in the group")
    properties: TaskGroupProperties = Field(
        default_factory=TaskGroupProperties,
        description="The properties used for executing the run.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="A list of tags associated with the group. When empty, tags are computed from the properties.",
    )

    aliases: set[str] | None = Field(
        default=None,
        description="A list of aliases to use in place of iteration or id. "
        "An alias can be used to uniquely identify a group for a given task. ",
    )

    is_external: bool | None = Field(
        default=None,
        description="Whether the group is external, i-e not creating by internal runners",
    )

    is_favorite: bool | None = Field(
        default=None,
        description="Indicates if the task group is marked as favorite",
    )

    notes: str | None = Field(
        default=None,
        description="Additional notes or comments about the task group",
    )

    similarity_hash: str = Field(
        default="",
        description="A hash computed based on task group properties, used for similarity comparisons",
    )

    benchmark_for_datasets: set[str] | None = None

    favorited_by: UserIdentifier | None = Field(
        default=None,
        description="The user who favorited the task group",
    )

    created_by: UserIdentifier | None = Field(
        default=None,
        description="The user who created the task group",
    )

    deployed_by: UserIdentifier | None = Field(
        default=None,
        description="The user who deployed the task group",
    )

    last_active_at: datetime | None = Field(
        default=None,
        description="The last time the task group was active",
    )

    created_at: datetime | None = Field(
        default=None,
        description="The time the task group was created",
    )

    @model_validator(mode="after")
    def fill_empty_tags(self) -> Self:
        if not self.tags:
            self.tags = self.properties.compute_tags()
        if not self.similarity_hash:
            self.similarity_hash = self.properties.similarity_hash
        return self

    @property
    def displayed_id(self) -> str:
        """The semver ID if it exists, otherwise the id"""
        if self.semver:
            return f"{self.semver.major}.{self.semver.minor}"
        return self.id

    model_config = ConfigDict(
        json_schema_extra=add_required_fields("id", "iteration", "tags", "properties", "similarity_hash"),
    )


class TaskGroupQuery(BaseModel):
    task_id: str
    task_schema_id: int | None = None
    benchmark_for_dataset_id: str | None = None
    sort_by: Literal["iteration", "oldest"] = Field(default="iteration", description="The field to sort by")
    is_deployed: bool | None = Field(
        default=None,
        description="Whether to filter groups with deployment aliases",
    )
    iterations: set[int] | None = None
    is_saved: bool | None | None = None
    semvers: set[MajorMinor] | None = None
    limit: int | None = None
    ids: set[str] | None = None


class TaskGroupWithCost(TaskGroup):
    cost_estimate_usd: float | None = None


TaskGroupFields = Literal[
    "id",
    "iteration",
    "properties",
    "properties.model",
    "properties.temperature",
    "properties.provider",
    "semver",
]
