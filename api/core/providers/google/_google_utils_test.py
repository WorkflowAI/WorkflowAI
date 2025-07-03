from typing import Any

import pytest

from core.providers.google._google_utils import get_google_json_schema_name, prepare_google_json_schema


class TestPrepareGoogleJsonSchema:
    def test_simple_schema(self):
        raw: dict[str, Any] = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The name of the person"},
                "age": {"type": "integer", "description": "The age of the person"},
            },
        }
        sanitized = prepare_google_json_schema(raw)
        assert sanitized == {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The name of the person"},
                "age": {"type": "integer", "description": "The age of the person"},
            },
        }

    def test_schema_with_unsupported_properties(self):
        raw: dict[str, Any] = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The name of the person"},
            },
            "additionalProperties": False,
            "title": "Person Schema",
            "default": {"name": "John"},
        }
        sanitized = prepare_google_json_schema(raw)
        # Should remove additionalProperties, title, and default
        assert sanitized == {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The name of the person"},
            },
        }

    def test_schema_with_refs(self):
        raw: dict[str, Any] = {
            "type": "object",
            "properties": {
                "person": {"$ref": "#/$defs/Person"},
                "company": {"$ref": "#/$defs/Company"},
            },
            "$defs": {
                "Person": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": "integer"},
                    },
                },
                "Company": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                    },
                },
            },
        }
        sanitized = prepare_google_json_schema(raw)
        # Should resolve $refs and remove $defs
        expected = {
            "type": "object",
            "properties": {
                "person": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": "integer"},
                    },
                },
                "company": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                    },
                },
            },
        }
        assert sanitized == expected

    def test_empty_object_properties(self):
        raw: dict[str, Any] = {
            "type": "object",
            "properties": {},
        }
        sanitized = prepare_google_json_schema(raw)
        # Should add placeholder property for empty objects
        assert sanitized == {
            "type": "object",
            "properties": {"_placeholder": {"type": "string"}},
        }

    def test_nested_refs(self):
        raw: dict[str, Any] = {
            "type": "object",
            "properties": {
                "data": {"$ref": "#/$defs/NestedData"},
            },
            "$defs": {
                "NestedData": {
                    "type": "object",
                    "properties": {
                        "inner": {"$ref": "#/$defs/InnerData"},
                    },
                },
                "InnerData": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                    },
                },
            },
        }
        sanitized = prepare_google_json_schema(raw)
        expected = {
            "type": "object",
            "properties": {
                "data": {
                    "type": "object",
                    "properties": {
                        "inner": {
                            "type": "object",
                            "properties": {
                                "value": {"type": "string"},
                            },
                        },
                    },
                },
            },
        }
        assert sanitized == expected

    def test_missing_ref(self):
        raw: dict[str, Any] = {
            "type": "object",
            "properties": {
                "person": {"$ref": "#/$defs/Person"},
                "missing": {"$ref": "#/$defs/MissingType"},
            },
            "$defs": {
                "Person": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                    },
                },
            },
        }
        sanitized = prepare_google_json_schema(raw)
        # Should resolve existing refs and handle missing refs gracefully
        expected = {
            "type": "object",
            "properties": {
                "person": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                    },
                },
                "missing": {},  # Missing ref becomes empty object
            },
        }
        assert sanitized == expected


class TestGoogleJsonSchemaName:
    def test_schema_name_length(self) -> None:
        # Test with a very long task name
        long_task_name = "This_Is_A_Very_Long_Task_Name_That_Should_Be_Truncated_To_Fit_The_Limit"
        schema: dict[str, Any] = {"type": "object", "properties": {"test": {"type": "string"}}}

        result = get_google_json_schema_name(long_task_name, schema)

        assert result == "this_is_a_very_long_task_na_074c782a899adc060960f939b821b193"
        assert len(result) == 60

    @pytest.mark.parametrize(
        ("task_name", "schema", "expected"),
        [
            pytest.param("test", {"type": "object"}, "test_01fc056eed58c88fe1c507fcd84dd4b7", id="test"),
            pytest.param(
                "[GOOGLE] User Info Extraction",
                {"type": "object"},
                "google_user_info_extraction_01fc056eed58c88fe1c507fcd84dd4b7",
                id="google_user_info_extraction",
            ),
            pytest.param(
                None,
                {"type": "object"},
                "01fc056eed58c88fe1c507fcd84dd4b7",
                id="no_task_name",
            ),
        ],
    )
    def test_schema_name(self, task_name: str | None, schema: dict[str, Any], expected: str):
        result = get_google_json_schema_name(task_name, schema)
        assert result == expected
