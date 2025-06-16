from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.domain.changelogs import VersionChangelog
from core.domain.message import Message
from core.domain.models import Model, Provider
from core.domain.task_deployment import TaskDeployment
from core.domain.users import UserIdentifier
from core.domain.version_environment import VersionEnvironment


class VersionDeploymentMetadata(BaseModel):
    deployed_at: datetime
    deployed_by: UserIdentifier | None
    environment: VersionEnvironment

    @classmethod
    def from_deployment(cls, deployment: TaskDeployment):
        return cls(
            deployed_at=deployment.deployed_at,
            deployed_by=deployment.deployed_by,
            environment=deployment.environment,
        )


class VersionMajor(BaseModel):
    similarity_hash: str
    major: int
    schema_id: int

    class Properties(BaseModel):
        temperature: float | None = None
        instructions: str | None = None
        messages: list[Message] | None = None
        task_variant_id: str | None = None
        top_p: float | None = None
        frequency_penalty: float | None = None
        presence_penalty: float | None = None

    properties: Properties

    class Minor(BaseModel):
        id: str = Field(description="The id of the full version")
        # Deprecated, will be removed when we have migrated all routes
        iteration: int
        minor: int

        class Properties(BaseModel):
            model: Model | str

            provider: Provider | None = None

            temperature: float | None = None

            model_config = ConfigDict(extra="allow")

            @field_validator("model")
            def validate_model(cls, v: str) -> Model | str:
                try:
                    return Model(v)
                except ValueError:
                    return v

        properties: Properties

        last_active_at: datetime | None = None

        cost_estimate_usd: float | None = None

        deployments: list[VersionDeploymentMetadata] | None = None

        is_favorite: bool | None = None

        favorited_by: UserIdentifier | None = None

        notes: str | None = None

        run_count: int | None = None

        created_by: UserIdentifier | None = None

    minors: list[Minor]

    created_by: UserIdentifier | None = None

    created_at: datetime

    changelog: VersionChangelog | None = None
