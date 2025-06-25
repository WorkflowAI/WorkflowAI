import logging
from datetime import datetime
from typing import Any, Self

from pydantic import Field
from typing_extensions import override

from core.domain.major_minor import MajorMinor
from core.domain.task_group import TaskGroup, TaskGroupQuery
from core.domain.task_group_properties import TaskGroupProperties
from core.storage.mongo.models.user_identifier import UserIdentifierSchema

from .base_document import BaseDocumentWithID

logger = logging.getLogger(__name__)


class TaskGroupDocument(BaseDocumentWithID):
    hash: str = ""

    task_id: str = ""

    task_schema_id: int = 0

    iteration: int

    run_count: int = Field(default=0, description="The number of runs for this group")

    alias: str | None = Field(default=None, description="A user provided or generated id for the task group")

    properties: dict[str, Any] | None = None

    tags: list[str] | None = None

    aliases: list[str] | None = None

    is_external: bool | None = None

    benchmark_for_datasets: list[str] | None = None

    is_favorite: bool | None = Field(default=None)

    notes: str | None = Field(default=None, description="Additional notes or comments about the task group")

    similarity_hash: str = Field(default="")

    created_by: UserIdentifierSchema | None = None

    favorited_by: UserIdentifierSchema | None = None

    deployed_by: UserIdentifierSchema | None = None

    last_active_at: datetime | None = None

    major: int | None = None

    minor: int | None = None

    @classmethod
    def from_resource(
        cls,
        tenant: str,
        task_id: str,
        task_schema_id: int,
        resource: TaskGroup,
    ) -> Self:
        hash = resource.properties.model_hash()
        if resource.id and resource.id != hash:
            logger.warning("TaskGroupDocument.from_resource: id is deprecated, use hash instead")
        return cls(
            hash=hash,
            task_id=task_id,
            task_schema_id=task_schema_id,
            tenant=tenant,
            iteration=resource.iteration,
            run_count=resource.run_count,
            alias=resource.id,
            properties=resource.properties.model_dump(exclude_none=True),
            tags=resource.tags,
            aliases=list(resource.aliases) if resource.aliases else None,
            is_external=resource.is_external,
            benchmark_for_datasets=list(resource.benchmark_for_datasets) if resource.benchmark_for_datasets else None,
            is_favorite=resource.is_favorite if resource.is_favorite else None,
            notes=resource.notes,
            similarity_hash=resource.similarity_hash,
            created_by=UserIdentifierSchema.from_domain(resource.created_by) if resource.created_by else None,
            favorited_by=UserIdentifierSchema.from_domain(resource.favorited_by) if resource.favorited_by else None,
            deployed_by=UserIdentifierSchema.from_domain(resource.deployed_by) if resource.deployed_by else None,
            last_active_at=resource.last_active_at,
            major=resource.semver.major if resource.semver else None,
            minor=resource.semver.minor if resource.semver else None,
        )

    def to_resource(self) -> TaskGroup:
        return TaskGroup(
            id=self.alias or self.hash,
            semver=MajorMinor(major=self.major, minor=self.minor)
            if self.major is not None and self.minor is not None
            else None,
            schema_id=self.task_schema_id,
            iteration=self.iteration,
            run_count=self.run_count,
            properties=TaskGroupProperties.model_validate(self.properties)
            if self.properties
            else TaskGroupProperties(),
            tags=self.tags or [],
            aliases=set(self.aliases) if self.aliases else None,
            is_external=self.is_external,
            benchmark_for_datasets=set(self.benchmark_for_datasets) if self.benchmark_for_datasets else None,
            is_favorite=self.is_favorite if self.is_favorite is not None else None,
            notes=self.notes,
            similarity_hash=self.similarity_hash,
            created_by=self.created_by.to_domain() if self.created_by else None,
            favorited_by=self.favorited_by.to_domain() if self.favorited_by else None,
            deployed_by=self.deployed_by.to_domain() if self.deployed_by else None,
            last_active_at=self.last_active_at,
            created_at=self.id.generation_time if self.id else None,
        )

    # Override to change the default value of exclude_none
    @override
    def model_dump(self, exclude_none: bool = True, **kwargs: Any) -> dict[str, Any]:
        return super().model_dump(exclude_none=exclude_none, **kwargs)

    @classmethod
    def build_filter(cls, task_group_query: TaskGroupQuery) -> dict[str, Any]:
        base: dict[str, Any] = {
            "task_id": task_group_query.task_id,
        }
        if task_group_query.task_schema_id:
            base["task_schema_id"] = task_group_query.task_schema_id

        if task_group_query.benchmark_for_dataset_id:
            base["benchmark_for_datasets"] = task_group_query.benchmark_for_dataset_id

        if task_group_query.is_deployed is not None:
            base["aliases.0"] = {"$exists": task_group_query.is_deployed}

        if task_group_query.iterations:
            base["iteration"] = {"$in": list(task_group_query.iterations)}

        if task_group_query.is_saved is not None:
            base["major"] = {"$exists": task_group_query.is_saved}

        if task_group_query.semvers:
            if len(task_group_query.semvers) == 1:
                if k := task_group_query.semvers.pop():
                    base["major"] = k.major
                    base["minor"] = k.minor
            else:
                base["major"] = {"$exists": True}
                base["$or"] = [{"major": semver.major, "minor": semver.minor} for semver in task_group_query.semvers]

        if task_group_query.ids:
            base["hash"] = {"$in": list(task_group_query.ids)}

        return base

    @classmethod
    def build_sort(cls, query: TaskGroupQuery) -> list[tuple[str, int]]:
        if not query.sort_by:
            return []

        match query.sort_by:
            case "iteration":
                return [("iteration", -1)]  # Ascending order for iteration
            case "oldest":
                # TODO[iteration]: This should really be `_id: 1` but we currently do not have
                # a compound index index sorted by _id
                return [("iteration", 1)]  # Ascending order for oldest

        logger.warning(
            "Unsupported sort_by field",
            extra={"sort_by": query.sort_by, "default_to": "iteration"},
        )
        return [("iteration", 1)]  # Default to ascending order for iteration
