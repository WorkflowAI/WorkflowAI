# pyright: reportPrivateUsage=false

from typing import cast

import pytest
from pytest import raises

from core.domain.errors import JSONSchemaValidationError
from core.domain.task_io import SerializableTaskIO

from .task_variant import SerializableTaskVariant


class TestComputeHashes:
    def test_simple(self):
        task = SerializableTaskVariant(
            id="",
            task_schema_id=1,
            name="",
            input_schema=SerializableTaskIO.from_json_schema(
                {"type": "object", "properties": {"a": {"type": "string"}}},
            ),
            output_schema=SerializableTaskIO.from_json_schema(
                {"type": "object", "properties": {"b": {"type": "string"}}},
            ),
        )

        input_hash = task.compute_input_hash({"a": "a"})
        assert input_hash == "582af9ef5cdc53d6628f45cb842f874a"
        output_hash = task.compute_output_hash({"b": "b"})
        assert output_hash == "53dd738814f8440b36a9ac19e49e9b8d"

        # Check with extra keys
        input_hash1 = task.compute_input_hash({"a": "a", "b": "b"})
        output_hash1 = task.compute_output_hash({"b": "b", "a": "a"})
        assert input_hash1 == input_hash
        assert output_hash1 == output_hash


class TestValidateOutput:
    def _build_task_variant(self) -> SerializableTaskVariant:
        """Helper to create a minimal task variant with simple schemas"""
        input_schema = SerializableTaskIO.from_json_schema(
            {
                "type": "object",
                "properties": {"a": {"type": "string"}},
                "required": ["a"],
            },
        )
        output_schema = SerializableTaskIO.from_json_schema(
            {
                "type": "object",
                "properties": {"b": {"type": "string"}},
                "required": ["b"],
            },
        )
        # id will be computed automatically based on schemas
        return SerializableTaskVariant(
            id="",  # will be populated by the model validator
            task_id="test_task",
            name="Test Task",
            input_schema=input_schema,
            output_schema=output_schema,
        )

    def test_validate_output_includes_error_details(self):
        variant = self._build_task_variant()

        # Missing required field 'b' so validation must fail
        with raises(JSONSchemaValidationError) as exc_info:
            variant.validate_output({})

        # exc_info is a pytest.ExceptionInfo but importing the type directly is optional
        # We use a cast for static type checkers.
        error_val = cast("pytest.ExceptionInfo[JSONSchemaValidationError]", exc_info)
        msg = str(error_val.value)
        # The error message should still start with the generic prefix
        assert msg.startswith("Task output does not match schema"), msg
        # And it should include details from the underlying jsonschema error
        assert "required property" in msg or "is not of type" in msg, msg
