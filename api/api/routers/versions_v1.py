from datetime import datetime, timedelta
from typing import Annotated, Any, Self

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, model_validator

from api.dependencies.path_params import TaskID, TaskSchemaID
from api.dependencies.security import RequiredUserDep
from api.dependencies.services import GroupServiceDep, InternalTasksServiceDep, ModelsServiceDep, VersionsServiceDep
from api.dependencies.storage import StorageDep
from api.dependencies.task_info import TaskTupleDep
from api.schemas.user_identifier import UserIdentifier
from api.schemas.version_properties import FullVersionProperties, ShortVersionProperties
from api.tags import RouteTags
from core.domain.changelogs import VersionChangelog
from core.domain.major_minor import MajorMinor
from core.domain.models import Model
from core.domain.page import Page
from core.domain.task_group import TaskGroup, TaskGroupIdentifier
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_group_update import TaskGroupUpdate
from core.domain.task_variant import SerializableTaskVariant
from core.domain.version_environment import VersionEnvironment
from core.domain.version_major import VersionDeploymentMetadata as DVersionDeploymentMetadata
from core.domain.version_major import VersionMajor
from core.utils.fields import datetime_factory
from core.utils.streams import format_model_for_sse

router = APIRouter(prefix="/v1/{tenant}/agents/{task_id}", tags=[RouteTags.VERSIONS])


def version_identifier_dep(
    version_id: Annotated[str, Path(description="The id of the version, either a semver or a hash")],
) -> TaskGroupIdentifier:
    if val := MajorMinor.from_string(version_id):
        return val
    return version_id


VersionIdentifierDep = Annotated[
    TaskGroupIdentifier,
    Depends(version_identifier_dep),
]


class CreateVersionRequest(BaseModel):
    properties: TaskGroupProperties

    save: bool | None = Field(
        default=None,
        description="Whether to save the version after creating it. If false, the version will "
        "not be returned in the list of versions until it is saved. If save is not provided, the version "
        "is automatically saved if it is the first version for the schema.",
    )


class CreateVersionResponse(BaseModel):
    id: str
    # TODO[versionsv1]: Remove this once the usage of iteration is removed
    iteration: int = Field(deprecated=True)
    semver: tuple[int, int] | None
    properties: TaskGroupProperties

    @classmethod
    def from_domain(cls, version: TaskGroup):
        return cls(
            id=version.id,
            iteration=version.iteration,
            semver=version.semver,
            properties=version.properties,
        )


@router.post(
    "/schemas/{task_schema_id}/versions",
    description="Create a new version for a agent."
    "The version can be used to run the agent but will not be returned in the list of versions until it is saved.",
    response_model_exclude_none=True,
)
async def create_version(
    task_id: TaskID,
    task_schema_id: TaskSchemaID,
    request: CreateVersionRequest,
    user: RequiredUserDep,
    versions_service: VersionsServiceDep,
    groups_service: GroupServiceDep,
) -> CreateVersionResponse:
    grp = await groups_service.create_task_group(
        task_id=task_id,
        task_schema_id=task_schema_id,
        properties=request.properties,
        user=user.identifier(),
        disable_autosave=request.save is False,
    )
    if request.save:
        grp = await versions_service.save_version(task_id, grp.id)

    return CreateVersionResponse.from_domain(grp)


class ImproveVersionRequest(BaseModel):
    # The run id that received an evaluation
    # We will use the input / output / version properties of the associated run to improve on the version properties
    run_id: str | None = None
    variant_id: str | None = None
    instructions: str | None = None

    user_evaluation: str = Field(description="A comment on why the task run was not optimal")

    stream: bool = False

    @model_validator(mode="after")
    def sanitize(self) -> Self:
        # We should have either a run_id or a variant_id AND instructions
        if not (any([any([self.run_id, self.variant_id]), self.instructions])):
            raise ValueError("Either 'run_id' or 'variant_id' and 'instructions' must be provided")
        return self


class ImproveVersionResponse(BaseModel):
    improved_properties: TaskGroupProperties
    changelog: list[str] | None


@router.post(
    "/versions/improve",
    description="Improve the version properties by using a user evaluation of a given run. The run's version properties"
    ", input and outputs are used as context to generate new version properties.",
    responses={
        200: {
            "content": {
                "application/json": {"schema": ImproveVersionResponse.model_json_schema()},
            },
            "text/event-stream": {"schema": ImproveVersionResponse.model_json_schema()},
        },
    },
)
async def improve_prompt(
    internal_tasks: InternalTasksServiceDep,
    request: ImproveVersionRequest,
    task_id: TaskTupleDep,
):
    if not request.stream:
        improved_properties, changelog = await internal_tasks.improve_prompt.run(
            task_id,
            run_id=request.run_id,
            variant_id=request.variant_id,
            instructions=request.instructions,
            user_evaluation=request.user_evaluation,
        )
        return JSONResponse(
            content=ImproveVersionResponse(
                improved_properties=improved_properties,
                changelog=changelog,
            ).model_dump(mode="json", exclude_none=True),
        )

    async def _stream():
        async for chunk in internal_tasks.improve_prompt.stream(
            task_id,
            run_id=request.run_id,
            variant_id=request.variant_id,
            instructions=request.instructions,
            user_evaluation=request.user_evaluation,
        ):
            yield format_model_for_sse(ImproveVersionResponse(improved_properties=chunk[0], changelog=chunk[1]))

    return StreamingResponse(_stream(), media_type="text/event-stream")


class MajorVersionProperties(BaseModel):
    temperature: float
    instructions: str
    task_variant_id: str | None = Field(description="The id of the full schema, including versions and examples")

    @classmethod
    def from_domain(cls, properties: VersionMajor.Properties):
        return cls(
            temperature=properties.temperature or 0.0,
            instructions=properties.instructions or "",
            task_variant_id=properties.task_variant_id,
        )


class VersionDeploymentMetadata(BaseModel):
    environment: VersionEnvironment
    deployed_at: datetime
    deployed_by: UserIdentifier | None
    provider_config_id: str | None

    @classmethod
    def from_domain(cls, deployment: DVersionDeploymentMetadata):
        return cls(
            environment=deployment.environment,
            deployed_at=deployment.deployed_at,
            deployed_by=UserIdentifier.from_domain(deployment.deployed_by),
            provider_config_id=deployment.provider_config_id,
        )


class MinorVersionBase(BaseModel):
    id: str = Field(description="The id of the full version")
    iteration: int = Field(deprecated=True)
    model: Model | str

    deployments: list[VersionDeploymentMetadata] | None

    cost_estimate_usd: float | None

    last_active_at: datetime | None = Field(
        description="The last time the task version minor was active",
    )

    is_favorite: bool | None

    favorited_by: UserIdentifier | None

    created_by: UserIdentifier | None

    notes: str | None

    run_count: int | None


class MajorVersion(BaseModel):
    major: int
    schema_id: int

    class MinorVersion(MinorVersionBase):
        minor: int

        properties: ShortVersionProperties

        @classmethod
        def from_domain(cls, minor: VersionMajor.Minor):
            return cls(
                id=minor.id,
                iteration=minor.iteration,
                minor=minor.minor,
                properties=ShortVersionProperties(
                    model=minor.properties.model,
                    provider=minor.properties.provider,
                    temperature=minor.properties.temperature,
                ),
                model=minor.properties.model,
                deployments=[VersionDeploymentMetadata.from_domain(d) for d in minor.deployments]
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

    minors: list[MinorVersion]

    created_by: UserIdentifier | None = Field(
        default=None,
        description="The user who created the version",
    )

    created_at: datetime

    properties: MajorVersionProperties

    class PreviousVersion(BaseModel):
        major: int

        changelog: list[str]

        @classmethod
        def from_domain(cls, previous_version: VersionChangelog):
            return cls(
                major=previous_version.major_from,
                changelog=previous_version.changelog,
            )

    previous_version: PreviousVersion | None

    @classmethod
    def from_domain(cls, version: VersionMajor):
        return cls(
            major=version.major,
            schema_id=version.schema_id,
            created_by=UserIdentifier.from_domain(version.created_by),
            created_at=version.created_at,
            minors=[MajorVersion.MinorVersion.from_domain(m) for m in version.minors],
            properties=MajorVersionProperties.from_domain(version.properties),
            previous_version=MajorVersion.PreviousVersion.from_domain(version.changelog) if version.changelog else None,
        )


@router.get(
    "/versions",
    description="List versions for a agent. Versions are grouped by major version",
    response_model_exclude_none=True,
)
async def list_versions(
    task_id: TaskTupleDep,
    versions_service: VersionsServiceDep,
    models_service: ModelsServiceDep,
    schema_id: Annotated[int | None, Query(description="The schema id to filter versions by")] = None,
) -> Page[MajorVersion]:
    versions = await versions_service.list_version_majors(task_id, schema_id, models_service)
    return Page(items=[MajorVersion.from_domain(v) for v in versions], count=len(versions))


class VersionStat(BaseModel):
    version_id: str
    run_count: int


@router.get(
    "/versions/stats",
    description="Get stats about versions for a agent",
    response_model_exclude_none=True,
)
async def get_version_stats(
    task_id: TaskTupleDep,
    storage: StorageDep,
    from_date: Annotated[
        datetime | None,
        Query(description="The date to filter versions by. Defaults to 24 hours ago"),
    ] = None,
) -> Page[VersionStat]:
    from_date = from_date or datetime.now() - timedelta(hours=24)
    stats = [
        VersionStat(
            version_id=stat.version_id,
            run_count=stat.run_count,
        )
        async for stat in storage.task_runs.run_count_by_version_id(task_id[1], from_date)
    ]
    return Page(items=stats)


class VersionV1(MinorVersionBase):
    schema_id: int
    semver: tuple[int, int] | None
    created_at: datetime

    properties: FullVersionProperties

    input_schema: dict[str, Any] = Field(
        description="The full input schema used for this version. Includes descriptions and examples",
    )
    output_schema: dict[str, Any] = Field(
        description="The full output schema used for this version. Includes descriptions and examples",
    )

    @classmethod
    def from_domain(
        cls,
        version: TaskGroup,
        deployments: list[DVersionDeploymentMetadata] | None,
        cost_estimate_usd: float | None,
        variant: SerializableTaskVariant | None,
    ):
        return cls(
            id=version.id,
            schema_id=version.schema_id,
            semver=version.semver,
            created_at=version.created_at or datetime_factory(),
            iteration=version.iteration,
            properties=FullVersionProperties.from_domain(version.properties),
            model=Model(version.properties.model),
            deployments=[VersionDeploymentMetadata.from_domain(d) for d in deployments] if deployments else None,
            cost_estimate_usd=cost_estimate_usd,
            last_active_at=version.last_active_at,
            is_favorite=version.is_favorite,
            notes=version.notes,
            run_count=version.run_count,
            favorited_by=UserIdentifier.from_domain(version.favorited_by),
            created_by=UserIdentifier.from_domain(version.created_by),
            input_schema=variant.input_schema.json_schema if variant else {},
            output_schema=variant.output_schema.json_schema if variant else {},
        )


@router.get(
    "/versions/{version_id}",
    description="Get a version by hash or semver",
    response_model_exclude_none=True,
)
async def get_version(
    task_id: TaskTupleDep,
    version_id: VersionIdentifierDep,
    versions_service: VersionsServiceDep,
    models_service: ModelsServiceDep,
) -> VersionV1:
    v = await versions_service.get_version(task_id, version_id, models_service)
    return VersionV1.from_domain(*v)


@router.post(
    "/versions/{version_id}/save",
    description="Save a version for the agent. Saving will attribute a friendly ID to the version, e-g 10.1"
    "Saving a version that has already been saved is a no-op.",
)
async def save_version(
    task_id: TaskID,
    # Not using a version identifier here, only checking for hashes
    version_id: Annotated[str, Path(description="The id of the version to save, as returned when listing runs")],
    versions_service: VersionsServiceDep,
) -> CreateVersionResponse:
    grp = await versions_service.save_version(task_id, version_id)
    return CreateVersionResponse.from_domain(grp)


@router.post("/versions/{version_id}/favorite", description="Favorite a version")
async def favorite_version(
    task_id: TaskID,
    version_id: VersionIdentifierDep,
    storage: StorageDep,
    user: RequiredUserDep,
) -> None:
    await storage.task_groups.update_task_group_by_id(
        task_id,
        version_id,
        TaskGroupUpdate(is_favorite=True),
        user.identifier(),
    )


@router.delete("/versions/{version_id}/favorite", description="Unfavorite a version")
async def unfavorite_version(
    task_id: TaskID,
    version_id: Annotated[str, Path(description="The id of the version to unfavorite, as returned when listing runs")],
    storage: StorageDep,
    user: RequiredUserDep,
) -> None:
    await storage.task_groups.update_task_group_by_id(
        task_id,
        version_id,
        TaskGroupUpdate(is_favorite=False),
        user.identifier(),
    )


class UpdateVersionNotesRequest(BaseModel):
    notes: str


@router.patch("/versions/{version_id}/notes", description="Update the notes for a version")
async def update_version_notes(
    task_id: TaskID,
    version_id: VersionIdentifierDep,
    storage: StorageDep,
    user: RequiredUserDep,
    request: UpdateVersionNotesRequest,
) -> None:
    await storage.task_groups.update_task_group_by_id(
        task_id,
        version_id,
        TaskGroupUpdate(notes=request.notes),
        user.identifier(),
    )
