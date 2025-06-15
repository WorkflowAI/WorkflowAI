from datetime import datetime, time
from typing import Any, Literal

from pydantic import BaseModel

from api.schemas.user_identifier import UserIdentifier
from api.schemas.version_properties import ShortVersionProperties
from core.domain.message import Message
from core.domain.models.model_data import FinalModelData
from core.domain.task_group import TaskGroup
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_variant import SerializableTaskVariant
from core.domain.version_environment import VersionEnvironment
from core.domain.version_major import VersionDeploymentMetadata, VersionMajor
from core.utils.fields import datetime_zero


class MCPToolReturn(BaseModel):
    """Standardized return format for MCP tools"""

    success: bool
    data: Any | None = None
    error: str | None = None
    messages: list[str] | None = None


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
        display_name: str
        icon_url: str
        supports: dict[str, Any]

        @classmethod
        def from_model_data(cls, id: str, model: FinalModelData):
            # Whitelist of support fields to include in the API response
            included_support_fields = {
                "supports_input_image",
                "supports_input_pdf",
                "supports_input_audio",
                "supports_output_image",
                "supports_output_text",
                "supports_audio_only",
                "supports_tool_calling",
                "supports_parallel_tool_calls",
            }

            return cls(
                id=id,
                created=int(datetime.combine(model.release_date, time(0, 0)).timestamp()),
                display_name=model.display_name,
                icon_url=model.icon_url,
                supports={
                    k.removeprefix("supports_"): v
                    for k, v in model.model_dump(
                        mode="json",
                        include=included_support_fields,
                    ).items()
                },
            )

    data: list[ModelItem]
