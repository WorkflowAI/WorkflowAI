from copy import deepcopy
from typing import Any

from jsonschema import SchemaError, validate
from jsonschema import ValidationError as SchemaValidationError
from jsonschema.validators import validator_for  # pyright: ignore[reportUnknownVariableType]
from pydantic import BaseModel, Field

from core.domain.errors import JSONSchemaValidationError
from core.utils.hash import compute_obj_hash
from core.utils.schema_sanitation import streamline_schema
from core.utils.schemas import (
    JsonSchema,
    make_optional,
    remove_extra_keys,
    remove_optional_nulls_and_empty_strings,
    strip_metadata,
)


class SerializableTaskIO(BaseModel):
    version: str = Field(..., description="the version of the schema definition. Titles and descriptions are ignored.")
    json_schema: dict[str, Any] = Field(..., description="A json schema")

    _optional_json_schema: dict[str, Any] | None = None

    def enforce(
        self,
        obj: Any,
        partial: bool = False,
        strip_extras: bool = False,
        strip_opt_none_and_empty_strings: bool = False,
    ) -> None:
        """Enforce validates that an object matches the schema. Object is updated in place."""

        if partial:
            if self._optional_json_schema is None:
                self._optional_json_schema = make_optional(self.json_schema)
            schema = self._optional_json_schema
        else:
            schema = self.json_schema

        navigators: list[JsonSchema.Navigator] = []
        if strip_opt_none_and_empty_strings:
            navigators.append(remove_optional_nulls_and_empty_strings)
        if strip_extras:
            navigators.append(remove_extra_keys)

        if navigators:
            JsonSchema(schema).navigate(obj, navigators=navigators)

        try:
            validate(obj, schema)
        except SchemaValidationError as e:
            kp = ".".join([str(p) for p in e.path])
            raise JSONSchemaValidationError(f"at [{kp}], {e.message}")

    def sanitize(self, obj: Any) -> Any:
        """Duplicate and enforce an object to match the schema"""
        obj = deepcopy(obj)
        # partial to make sure we don't throw if we have missing fields
        self.enforce(obj, partial=True, strip_extras=True, strip_opt_none_and_empty_strings=True)
        return obj

    def resolve_ref(self, ref: str, defs: dict[str, Any]) -> dict[str, Any]:
        if not ref.startswith("#/"):
            raise ValueError(f"Unsupported ref format: {ref}")
        parts = ref.lstrip("#/").split("/")
        schema = self.json_schema
        for part in parts:
            if part in schema:
                schema = schema[part]
            elif part in defs and part in defs:
                schema = defs[part]
            else:
                raise ValueError(f"Invalid ref path: {ref}")
        return schema

    @classmethod
    def from_json_schema(cls, json_schema: dict[str, Any], streamline: bool = False):
        try:
            validator_for(json_schema).check_schema(json_schema)  # pyright: ignore [reportUnknownMemberType]
        except (SchemaValidationError, SchemaError) as e:
            raise JSONSchemaValidationError(f"Invalid schema: {e}")
        if streamline:
            json_schema = streamline_schema(json_schema)
        return cls(version=compute_obj_hash(strip_metadata(json_schema)), json_schema=json_schema)

    @classmethod
    def from_model(cls, model_cls: type[BaseModel], streamline: bool = True):
        return cls.from_json_schema(model_cls.model_json_schema(), streamline=streamline)


RawStringSchema = SerializableTaskIO.from_json_schema({"type": "string"})
RawJSONSchema = SerializableTaskIO.from_json_schema({})
