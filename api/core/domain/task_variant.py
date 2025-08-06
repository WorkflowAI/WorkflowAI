from datetime import datetime, timezone
from typing import Any, Protocol, Self

from pydantic import BaseModel, Field, model_validator

from core.domain.errors import JSONSchemaValidationError
from core.domain.fields.chat_message import ChatMessage
from core.domain.task_typology import TaskTypology
from core.domain.types import AgentInput, AgentOutput
from core.storage import TaskTuple
from core.utils.hash import compute_obj_hash
from core.utils.schemas import JsonSchema

from .task_io import SerializableTaskIO


class SerializableTaskVariant(BaseModel):
    id: str = Field(
        ...,
        description="the task version id, computed based on the other parameters. Read only.",
    )
    task_id: str = Field(default="", description="the task id, stable accross all versions")
    # TODO[uids]: this is not filled on every path for now, we should eventually store it with the task variant
    task_uid: int = 0
    task_schema_id: int = Field(
        0,
        description="""The task schema idx. The schema index only changes when the types
        of the input / ouput objects change so all task versions with the same schema idx
        have compatible input / output objects. Read only""",
    )
    tenant: str | None = Field(default=None, description="A unique tenant id that the task variant belongs to")
    # TODO: remove, should be at task info level
    name: str = Field(description="the task display name")
    # TODO: remove, should be at task info level
    description: str | None = Field(default=None, description="a concise task description")
    input_schema: SerializableTaskIO
    output_schema: SerializableTaskIO
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # TODO: remove, should be at task info level
    is_public: bool | None = None

    creation_chat_messages: list[ChatMessage] | None = None
    used_integration_kind: str | None = None

    def enforce(self, task_input: dict[str, Any], task_output: dict[str, Any], strip_extras: bool = False) -> None:
        try:
            self.input_schema.enforce(task_input, strip_extras=strip_extras, sanitize_empties=True)
        except JSONSchemaValidationError as e:
            raise JSONSchemaValidationError(f"Task input does not match schema: {e}")

        try:
            self.output_schema.enforce(task_output, strip_extras=strip_extras, sanitize_empties=True)
        except JSONSchemaValidationError as e:
            raise JSONSchemaValidationError(f"Task output does not match schema: {e}")

    def model_hash(self) -> str:
        # the model hash depends on the full json schema for both input and outputs
        return compute_obj_hash(
            {"input_schema": self.input_schema.json_schema, "output_schema": self.output_schema.json_schema},
        )

    @model_validator(mode="after")
    def post_validate(self) -> Self:
        if self.id == "":
            self.id = self.model_hash()
        return self

    def validate_input(self, input: Any, partial: bool = False) -> dict[str, Any]:
        try:
            self.input_schema.enforce(
                input,
                strip_extras=True,
                partial=partial,
                sanitize_empties=True,
            )
            return input
        except JSONSchemaValidationError as e:
            raise JSONSchemaValidationError(f"Task input does not match schema: {e}")

    def validate_output(self, output: Any, partial: bool = False, strip_extras: bool = False) -> dict[str, Any]:
        try:
            self.output_schema.enforce(
                output,
                strip_extras=strip_extras,
                partial=partial,
                sanitize_empties=True,
            )
            return output
        except JSONSchemaValidationError as e:
            # Pass through the detailed error message from the enhanced validator
            raise JSONSchemaValidationError(f"Task output does not match schema: {e}") from e

    def output_json_schema(self) -> JsonSchema:
        return JsonSchema(schema=self.output_schema.json_schema)

    def compute_input_hash(self, input: AgentInput) -> str:
        try:
            # We allow input schemas to be invalid
            # Really no point in doubling the validation that should occur client side
            # The one down side is that we won't strip out optional values
            # when computing the hash but that's ok
            sanitized = self.input_schema.sanitize(input)
        except JSONSchemaValidationError:
            sanitized = input
        return compute_obj_hash(sanitized)

    def compute_output_hash(self, output: AgentOutput) -> str:
        return compute_obj_hash(self.output_schema.sanitize(output))

    def typology(self) -> TaskTypology:
        return TaskTypology.from_schema(self.input_schema.json_schema, self.output_schema.json_schema)

    @property
    def id_tuple(self) -> TaskTuple:
        return (self.task_id, self.task_uid)


class VariantIO(Protocol):
    @property
    def input_schema(self) -> SerializableTaskIO: ...

    @property
    def output_schema(self) -> SerializableTaskIO: ...
