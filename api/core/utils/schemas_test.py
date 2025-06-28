from copy import deepcopy
from typing import Any

import pytest
from jsonschema import ValidationError, validate
from pydantic import BaseModel

from tests.utils import fixtures_json

from .schemas import (
    JsonSchema,
    clean_json_string,
    is_schema_only_containing_one_property,
    make_optional,
    remove_extra_keys,
    sanitize_empty_values,
    schema_from_data,
    schema_needs_explanation,
    strip_json_schema_metadata_keys,
    strip_metadata,
)


class TestSubSchema:
    def test_sub_schema_bool(self, schema_1: JsonSchema):
        sub = schema_1.sub_schema(keypath="is_email_thread_about_an_event")
        assert sub
        assert sub.type == "boolean"

    def test_sub_schema_nullable_child(self, schema_1: JsonSchema):
        sub = schema_1.sub_schema(keypath="is_event_confirmed")
        assert sub
        assert sub.type == "boolean"
        assert sub.is_nullable

    def test_sub_schema_ref(self, schema_1: JsonSchema):
        sub = schema_1.sub_schema(keypath="event_category")
        assert sub
        assert sub.type == "string"
        assert "enum" in sub
        assert sub["enum"] == ["UNSPECIFIED", "IN_PERSON_MEETING", "REMOTE_MEETING", "FLIGHT", "TO_DO", "BIRTHDAY"]

    def test_sub_schema_one_of(self, schema_2: JsonSchema):
        sub = schema_2.sub_schema(keypath="sub1.key2")
        assert sub
        assert sub.type == "integer"
        assert sub["description"] == "Value in cents"

    def test_sub_schema_one_of_root(self, schema_2: JsonSchema):
        # Check that we dive into an allOf if there is a single possibility
        sub = schema_2.sub_schema(keypath="sub1")
        assert sub
        assert sub.type == "object"

    def test_sub_schema_array(self, schema_2: JsonSchema):
        sub = schema_2.sub_schema(keypath="sub2.0.key3")
        assert sub
        assert sub.type == "string"
        assert sub.is_nullable

    def test_follow_ref_with_object(self, schema_2: JsonSchema):
        """Test that we can dive into a ref object"""
        sub = schema_2.sub_schema(keypath="sub1.key2")
        assert sub
        assert sub.type == "integer"
        assert sub.get("description") == "Value in cents"


class TestChildSchema:
    def test_child_schema_missing_types(self, schema_3: JsonSchema):
        assert schema_3.type == "object"
        assert schema_3.child_schema("sorted_cities").type == "array"

    def test_follow_refs(self, schema_3: JsonSchema):
        schema = JsonSchema(
            {
                "type": "object",
                "properties": {"image": {"$ref": "#/$defs/File", "format": "image"}},
                "$defs": {"File": {"properties": {"url": {"type": "string"}}}},
            },
        )
        sub = schema.child_schema("image")
        assert sub
        assert sub.get("format") == "image"
        assert sub.get("followed_ref_name") == "File"


class ModelWithTitle(BaseModel):
    title: str
    description: str
    examples: int
    other: int

    class Nested(BaseModel):
        title: str = "Title"

    nested: list[Nested]


@pytest.mark.parametrize(
    "input_dict, expected_dict",
    [
        (
            {"title": "Title", "description": "Description", "examples": "Examples", "other": "Other"},
            {"other": "Other"},
        ),
        (
            {
                "title": "Title",
                "description": "Description",
                "examples": "Examples",
                "nested": {"title": "Nested Title", "other": "Other"},
            },
            {"nested": {"other": "Other"}},
        ),
        (
            {
                "title": "Title",
                "description": "Description",
                "examples": "Examples",
                "list": [{"title": "List Title", "other": "Other"}],
            },
            {"list": [{"other": "Other"}]},
        ),
        # title or description as a property
        (
            ModelWithTitle.model_json_schema(),
            {
                "$defs": {
                    "Nested": {
                        "properties": {"title": {"type": "string"}},
                        "type": "object",
                    },
                },
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "examples": {"type": "integer"},
                    "other": {"type": "integer"},
                    "nested": {
                        "items": {"$ref": "#/$defs/Nested"},
                        "type": "array",
                    },
                },
                "required": ["title", "description", "examples", "other", "nested"],
                "type": "object",
            },
        ),
    ],
)
def test_strip_metadata(input_dict: dict[str, Any], expected_dict: dict[str, Any]):
    assert strip_metadata(input_dict) == expected_dict


class TestMakeOptional:
    def check(self, schema: Any, full_payload: dict[str, Any], *partials: dict[str, Any]):
        optional_schema = make_optional(schema)

        # Making sure a full payload works with both the full and optional schema
        validate(full_payload, schema)
        validate(full_payload, optional_schema)

        # Partials should fail for the full schema but succeed for the optional schema
        for p in partials:
            with pytest.raises(ValidationError):
                validate(p, schema)
            validate(p, optional_schema)

        return optional_schema

    def test_simple(self):
        schema = {
            "properties": {
                "title": {"type": "string"},
            },
            "required": ["title"],
            "type": "object",
        }

        self.check(schema, {"title": "Title"}, {})

    def test_nested(self):
        schema = {
            "properties": {
                "title": {"type": "string"},
                "nested": {
                    "properties": {
                        "required": {"type": "boolean"},
                    },
                    "required": ["required"],
                    "type": "object",
                },
            },
            "required": ["title"],
            "type": "object",
        }

        full_payload = {
            "title": "Title",
            "nested": {"required": True},
        }

        self.check(
            schema,
            full_payload,
            {
                "title": "Title",
                "nested": {},
            },
            {"nested": {"required": True}},
        )

    def test_array_min_length(self):
        schema = {
            "properties": {
                "items": {"type": "array", "items": {"type": "string"}, "minItems": 2},
            },
        }

        optional_schema = self.check(schema, {"items": ["1", "2"]}, {"items": []}, {"items": ["1"]})

        with pytest.raises(ValidationError):
            validate({"items": [1, 2, 3]}, optional_schema)

    def test_enum(self):
        schema = {
            "properties": {
                "item": {"enum": ["ablaba", "bblabal"]},
            },
        }
        self.check(schema, {"item": "ablaba"}, {"item": "ab"})


@pytest.fixture(scope="function")
def base_schema2_obj():
    return {
        "name1": "Widget",
        "description": "A useful tool for X",
        "opt_description": "Optional detailed description",
        "opt_description2": None,
        "price": 12.99,
        "in_stock": True,
        "sub1": {"key1": "Value1", "key2": 100},
        "sub2": [{"key3": "Value3"}, {"key3": None}],
        "string_array": ["string1", "string2"],
    }


class TestNavigate:
    def test_count_simple(self):
        schema = JsonSchema(
            {
                "properties": {
                    "title": {"type": "string"},
                    "nested": {
                        "properties": {
                            "required": {"type": "boolean"},
                        },
                        "required": ["required"],
                        "type": "object",
                    },
                },
                "required": ["title"],
                "type": "object",
            },
        )

        count = 0

        def navigate(*args: Any, **kwargs: Any):
            nonlocal count
            count += 1

        schema.navigate(
            {
                "title": "Title",
                "nested": {"required": True},
            },
            [navigate],
        )

        assert count == 4

    def test_modify_value(self, schema_2: JsonSchema, base_schema2_obj: dict[str, Any]):
        # test that we can modify a value based on a parent

        def navigate(schema: JsonSchema, obj: Any):
            title = schema.get("title")
            if title == "Sub1":
                obj["key2"] = 200
            elif title == "Sub2" and schema.type == "object":
                del obj["key3"]
            # we should never find key3 because it was deleted above
            assert title != "Key3"

        schema_2.navigate(base_schema2_obj, [navigate])

        assert base_schema2_obj == {
            "name1": "Widget",
            "description": "A useful tool for X",
            "opt_description": "Optional detailed description",
            "opt_description2": None,
            "price": 12.99,
            "in_stock": True,
            "sub1": {"key1": "Value1", "key2": 200},
            "sub2": [{}, {}],
            "string_array": ["string1", "string2"],
        }


class TestSanitizeEmptyValues:
    def test_remove_optional_nulls(self, schema_2: JsonSchema, base_schema2_obj: dict[str, Any]):
        clone = deepcopy(base_schema2_obj)
        assert "opt_description2" in clone

        schema_2.navigate(base_schema2_obj, [sanitize_empty_values])
        assert "opt_description2" not in base_schema2_obj
        del clone["opt_description2"]

        assert base_schema2_obj == clone

    def test_remove_optional_nulls_in_nested(self, schema_2: JsonSchema, base_schema2_obj: dict[str, Any]):
        # Test for objects in refs
        schema_2["$defs"]["Sub1"]["required"].remove("key2")
        base_schema2_obj["sub1"]["key2"] = None

        assert "key2" in base_schema2_obj["sub1"]
        schema_2.navigate(base_schema2_obj, [sanitize_empty_values])

        assert "key2" not in base_schema2_obj["sub1"]

    @pytest.mark.parametrize(
        ("name", "value"),
        [
            pytest.param({"type": ["string", "null"]}, None, id="type_string_null"),
            pytest.param({"type": "null"}, None, id="type_null"),
            pytest.param({"anyOf": [{"type": "string"}, {"type": "null"}]}, None, id="anyOf_string_null"),
            pytest.param(
                {"oneOf": [{"type": "string"}, {"type": "null"}, {"type": "integer"}]},
                None,
                id="oneOf_string_null_integer",
            ),
        ],
    )
    def test_add_missing_nones(self, name: dict[str, Any], value: Any):
        """Check that we add missing None values"""

        schema = JsonSchema(
            {
                "type": "object",
                "properties": {"name": name},
                "required": ["name"],
            },
        )
        obj = {}
        schema.navigate(obj, [sanitize_empty_values])

        assert obj == {"name": value}

    @pytest.mark.parametrize(
        "name",
        [
            {"type": "string"},
            {"type": "number"},
            {"type": "integer"},
            {"type": "boolean"},
            {"type": "array"},
            {"type": "object"},
        ],
    )
    def test_not_add_missing_key(self, name: dict[str, Any]):
        """Validates that we do not set the missing key for most types"""

        schema = JsonSchema(
            {
                "type": "object",
                "properties": {"name": name},
                "required": ["name"],
            },
        )
        obj = {}
        schema.navigate(obj, [sanitize_empty_values])

        assert obj == {}


class TestRemoveExtraKeys:
    def test_none_root(self, schema_2: JsonSchema):
        # Test that we don't crash if we send None
        schema_2.navigate(None, [remove_extra_keys])

    def test_none_obj(self, schema_2: JsonSchema, base_schema2_obj: dict[str, Any]):
        base_schema2_obj["sub1"] = None
        clone = deepcopy(base_schema2_obj)
        schema_2.navigate(base_schema2_obj, [remove_extra_keys])

        assert base_schema2_obj == clone

    def test_extras_root(self, schema_2: JsonSchema, base_schema2_obj: dict[str, Any]):
        clone = deepcopy(base_schema2_obj)
        base_schema2_obj["whatever"] = None
        schema_2.navigate(base_schema2_obj, [remove_extra_keys])

        # Test that whatever is removed
        assert base_schema2_obj == clone

    def test_extras_child(self, schema_2: JsonSchema, base_schema2_obj: dict[str, Any]):
        clone = deepcopy(base_schema2_obj)
        base_schema2_obj["sub1"]["blabla"] = "hello"
        schema_2.navigate(base_schema2_obj, [remove_extra_keys])

        # Test that whatever is removed
        assert base_schema2_obj == clone

    @pytest.mark.parametrize(
        "raw_schema",
        [
            # Properties is defined but empty
            {"type": "object", "properties": {}},
            # Properties is not defined
            {"type": "object"},
            # additionalProperties is True
            {"type": "object", "properties": {"bla": {"type": "string"}}, "additionalProperties": True},
        ],
    )
    def test_freeform_object(self, raw_schema: dict[str, Any]):
        schema = JsonSchema(raw_schema)
        obj = {"blabla": "hello"}
        schema.navigate(obj, [remove_extra_keys])

        # Test that the object is left in place
        assert obj == {"blabla": "hello"}

    # Check that if the passed object does not respect the schema, we do not crash
    @pytest.mark.parametrize(
        "replacement",
        [
            ["a", "b"],
            1,
            "hello",
        ],
    )
    def test_invalid_obj(self, schema_2: JsonSchema, base_schema2_obj: dict[str, Any], replacement: Any):
        # Replace an object in the schema with an invalid type
        base_schema2_obj["sub1"] = replacement
        clone = deepcopy(base_schema2_obj)

        schema_2.navigate(base_schema2_obj, [remove_extra_keys])
        # Object should remain the same
        assert base_schema2_obj == clone


class TestRemoveEmptyStrings:
    @pytest.fixture
    def basic_schema(self):
        return JsonSchema(
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "optional_field": {"type": "string"},
                    "date": {"type": "string", "format": "date"},
                    "number": {"type": "number"},
                    "nested": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string"},
                            "empty": {"type": "string"},
                            "null_value": {"type": "string"},
                        },
                    },
                    "array": {"type": "array", "items": {"type": "string"}},
                },
            },
        )

    def test_basic(self, basic_schema: JsonSchema):
        obj = {
            "name": "Test",
            "description": "",
            "optional_field": None,
            "date": "",
            "number": 42,
            "nested": {"key": "value", "empty": "", "null_value": None},
            "array": ["", "not empty", None],
        }

        expected = {
            "name": "Test",
            "description": "",
            "number": 42,
            "nested": {"key": "value", "empty": ""},
            "array": ["", "not empty", None],
        }

        basic_schema.navigate(obj, [sanitize_empty_values])
        assert obj == expected

    @pytest.fixture
    def array_schema(self):
        return JsonSchema(
            {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"name": {"type": "string"}, "description": {"type": "string"}},
                        },
                    },
                },
            },
        )

    def test_array_of_objects(self, array_schema: JsonSchema):
        obj = {
            "items": [
                {"name": "Item 1", "description": ""},
                {"name": "", "description": None},
                {"name": "Item 3", "description": "Valid"},
            ],
        }

        expected = {
            "items": [{"name": "Item 1", "description": ""}, {"name": ""}, {"name": "Item 3", "description": "Valid"}],
        }

        array_schema.navigate(obj, [sanitize_empty_values])
        assert obj == expected

    @pytest.fixture
    def non_string_schema(self):
        return JsonSchema(
            {
                "type": "object",
                "properties": {
                    "number": {"type": "number"},
                    "boolean": {"type": "boolean"},
                    "list": {"type": "array"},
                    "dict": {"type": "object"},
                },
            },
        )


@pytest.mark.parametrize(
    "input_string, expected_output",
    [
        ("Normal string", "Normal string"),
        ("String with\nline break", "String with\nline break"),  # Keep line breaks
        ("String with\rcarriage return", "String with\rcarriage return"),  # Keep carriage return
        ("String with \x00null char", "String with null char"),  # All the other control chars are removed
        ("String with \x01SOH char", "String with SOH char"),
        ("String with \x1funit separator", "String with unit separator"),
        ("String with \ttab", "String with tab"),
        ("String with \x0bvertical tab", "String with vertical tab"),
        ("String with \x0cform feed", "String with form feed"),
        ("Mixed\x00\x01\x02\x03\x04string", "Mixedstring"),
        ("\x00\x01\x02\x03\x04\x05", ""),
        ("", ""),
    ],
)
def test_clean_json_string(input_string: str, expected_output: str):
    assert clean_json_string(input_string) == expected_output


def test_clean_json_string_preserves_unicode():
    input_string = "Unicode: \u2022 \u2023 \u2024"
    assert clean_json_string(input_string) == input_string


def test_clean_json_string_with_all_control_chars():
    input_string = "".join(chr(i) for i in range(32))
    expected_output = "\n\r"
    assert clean_json_string(input_string) == expected_output


def test_clean_json_string_long_string():
    long_string = "A" * 1000000 + "\x00" * 1000 + "B" * 1000000
    result = clean_json_string(long_string)
    assert len(result) == 2000000
    assert "\x00" not in result


class TestStripKeys:
    # Tests for the strip_json_schema_metadata_keys function
    def test_strip_json_schema_metadata_keys_basic(self):
        input_dict = {"a": 1, "b": 2, "c": 3}
        exc_keys = {"a", "c"}
        expected = {"b": 2}
        assert strip_json_schema_metadata_keys(input_dict, exc_keys) == expected

    def test_strip_json_schema_metadata_keys_nested(self):
        input_dict = {
            "level1": {
                "a": 1,
                "ignore": 2,
                "level2": {"b": 3, "c": 4},
            },
            "ignore": 5,
        }
        exc_keys = {"ignore"}
        expected = {
            "level1": {
                "a": 1,
                "level2": {"b": 3, "c": 4},
            },
        }
        assert strip_json_schema_metadata_keys(input_dict, exc_keys) == expected

    def test_strip_json_schema_metadata_keys_with_lists(self):
        input_dict = [
            {"a": 1, "b": 2},
            {"a": 3, "c": 4},
        ]
        exc_keys = {"a"}
        expected = [
            {"b": 2},
            {"c": 4},
        ]
        assert strip_json_schema_metadata_keys(input_dict, exc_keys) == expected

    def test_strip_json_schema_metadata_keys_no_keys_removed(self):
        input_dict = {"x": 1, "y": 2}
        exc_keys = {"a", "b"}
        expected = {"x": 1, "y": 2}
        assert strip_json_schema_metadata_keys(input_dict, exc_keys) == expected

    def test_strip_json_schema_metadata_keys_empty_exc_keys(self):
        input_dict = {"a": 1, "b": 2}
        exc_keys: set[str] = set()
        expected = {"a": 1, "b": 2}
        assert strip_json_schema_metadata_keys(input_dict, exc_keys) == expected

    def test_strip_json_schema_metadata_keys_empty_input(self):
        input_dict = {}
        exc_keys = {"a"}
        expected = {}
        assert strip_json_schema_metadata_keys(input_dict, exc_keys) == expected

    def test_strip_json_schema_metadata_keys_deeply_nested(self):
        input_dict = {
            "a": {
                "b": {
                    "c": 3,
                    "d": 4,
                },
                "e": 5,
            },
            "f": 6,
        }
        exc_keys = {"c", "f"}
        expected = {
            "a": {
                "b": {
                    "d": 4,
                },
                "e": 5,
            },
        }
        assert strip_json_schema_metadata_keys(input_dict, exc_keys) == expected

    def test_strip_json_schema_metadata_keys_all_keys_removed(self):
        input_dict = {"a": 1, "b": 2}
        exc_keys = {"a", "b"}
        expected = {}
        assert strip_json_schema_metadata_keys(input_dict, exc_keys) == expected

    def test_strip_json_schema_metadata_keys_none_exc_keys(self):
        input_dict = {"a": 1, "b": 2}
        exc_keys = None
        expected = {"a": 1, "b": 2}
        assert strip_json_schema_metadata_keys(input_dict, exc_keys or set()) == expected

    def test_strip_json_schema_metadata_keys_non_dict_input(self):
        input_data = ["a", "b", "c"]
        exc_keys = {"a"}
        expected = ["a", "b", "c"]
        assert strip_json_schema_metadata_keys(input_data, exc_keys) == expected

    def test_strip_json_schema_metadata_keys_mixed_types(self):
        input_dict = {
            "a": 1,
            "b": "string",
            "c": None,
            "d": [1, 2, {"e": 3, "f": 4}],
            "g": {"h": 5, "i": [6, 7, {"j": 8}]},
        }
        exc_keys = {"c", "e", "j"}
        expected: dict[str, Any] = {
            "a": 1,
            "b": "string",
            "d": [1, 2, {"f": 4}],
            "g": {"h": 5, "i": [6, 7, {}]},
        }
        assert strip_json_schema_metadata_keys(input_dict, exc_keys) == expected

    def test_strip_json_schema_metadata_keys_ignore_parent_properties(self):
        input_dict = {
            "properties": {
                "a": 1,
                "b": 2,
            },
            "c": 3,
        }
        exc_keys = {"a", "c"}
        expected = {
            "properties": {
                "a": 1,
                "b": 2,
            },
        }
        assert strip_json_schema_metadata_keys(input_dict, exc_keys) == expected

    def test_strip_json_schema_metadata_keys_ignore_parent_extra_properties(self):
        input_dict = {
            "extra_properties": {
                "d": 4,
                "e": 5,
            },
            "f": 6,
        }
        exc_keys = {"d", "f"}
        expected = {
            "extra_properties": {
                "d": 4,
                "e": 5,
            },
        }
        assert strip_json_schema_metadata_keys(input_dict, exc_keys) == expected

    def test_strip_json_schema_metadata_keys_ignore_parent_defs(self):
        input_dict = {
            "$defs": {
                "g": 7,
                "h": 8,
            },
            "i": 9,
        }
        exc_keys = {"g", "i"}
        expected = {
            "$defs": {
                "g": 7,
                "h": 8,
            },
        }
        assert strip_json_schema_metadata_keys(input_dict, exc_keys) == expected

    def test_strip_json_schema_metadata_keys_ignore_parent_nested(self):
        input_dict = {
            "properties": {
                "a": 1,
                "nested": {
                    "properties": {
                        "b": 2,
                        "c": 3,
                    },
                    "d": 4,
                },
            },
            "e": 5,
        }
        exc_keys = {"a", "b", "d", "e"}
        expected = {
            "properties": {
                "a": 1,
                "nested": {
                    "properties": {
                        "b": 2,
                        "c": 3,
                    },
                },
            },
        }
        assert strip_json_schema_metadata_keys(input_dict, exc_keys) == expected

    def test_strip_json_schema_metadata_keys_with_filter(self):
        input_dict = {
            "keep": 1,
            "remove": 2,
            "nested": {
                "should_be_kept_because_of_filter": 3,
                "value_to_filter_on": "some_value",
            },
        }
        exc_keys = {"remove", "should_be_kept_because_of_filter"}

        def filter_condition(d: dict[str, Any]) -> bool:
            return "value_to_filter_on" not in d

        expected = {
            "keep": 1,
            "nested": {
                "should_be_kept_because_of_filter": 3,
                "value_to_filter_on": "some_value",
            },
        }

        result = strip_json_schema_metadata_keys(input_dict, exc_keys, filter=filter_condition)
        assert result == expected


class TestIsSchemaOnlyContainingFiles:
    def test_not_object_schema(self):
        result = is_schema_only_containing_one_property({"type": "string"})
        assert result.value is False
        assert result.field_description is None

    def test_empty_properties(self):
        result = is_schema_only_containing_one_property({"type": "object", "properties": {}})
        assert result.value is False
        assert result.field_description is None

    def test_multiple_properties(self):
        result = is_schema_only_containing_one_property(
            {
                "type": "object",
                "properties": {
                    "file1": {"$ref": "#/$defs/File"},
                    "file2": {"$ref": "#/$defs/File"},
                },
            },
        )
        assert result.value is False
        assert result.field_description is None

    def test_single_file_property(self):
        result = is_schema_only_containing_one_property(
            {
                "type": "object",
                "properties": {
                    "file": {"$ref": "#/$defs/File", "description": "A test file"},
                },
            },
        )
        assert result.value is True
        assert result.field_description == "Input is a single file with the following description: A test file"

    def test_single_image_property(self):
        result = is_schema_only_containing_one_property(
            {
                "type": "object",
                "properties": {
                    "image": {"$ref": "#/$defs/Image", "description": "A test image"},
                },
            },
        )
        assert result.value is True
        assert result.field_description == "Input is a single image with the following description: A test image"

    def test_array_of_files(self):
        result = is_schema_only_containing_one_property(
            {
                "type": "object",
                "properties": {
                    "files": {
                        "type": "array",
                        "description": "Array description",
                        "items": {"$ref": "#/$defs/File", "description": "Item description"},
                    },
                },
            },
        )
        assert result.value is True
        assert (
            result.field_description
            == "Input is an array of files with the following description: Array description (each item description is: Item description)"
        )

    def test_array_of_files_no_descriptions(self):
        result = is_schema_only_containing_one_property(
            {
                "type": "object",
                "properties": {
                    "files": {
                        "type": "array",
                        "items": {"$ref": "#/$defs/File"},
                    },
                },
            },
        )
        assert result.value is True
        assert result.field_description == "Input is an array of files"

    def test_array_of_files_only_array_description(self):
        result = is_schema_only_containing_one_property(
            {
                "type": "object",
                "properties": {
                    "files": {
                        "type": "array",
                        "description": "Array description",
                        "items": {"$ref": "#/$defs/File"},
                    },
                },
            },
        )
        assert result.value is True
        assert (
            result.field_description == "Input is an array of files with the following description: Array description"
        )

    def test_array_of_files_only_item_description(self):
        result = is_schema_only_containing_one_property(
            {
                "type": "object",
                "properties": {
                    "files": {
                        "type": "array",
                        "items": {"$ref": "#/$defs/File", "description": "Item description"},
                    },
                },
            },
        )
        assert result.value is True
        assert result.field_description == "Input is an array of files with the following description: Item description"

    def test_array_of_non_files(self):
        result = is_schema_only_containing_one_property(
            {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        )
        assert result.value is False
        assert result.field_description is None

    def test_custom_types_to_detect(self):
        result = is_schema_only_containing_one_property(
            {
                "type": "object",
                "properties": {
                    "document": {"$ref": "#/$defs/Document", "description": "A test document"},
                },
            },
        )
        assert result.value is False
        assert result.field_description is None

        result = is_schema_only_containing_one_property(
            {
                "type": "object",
                "properties": {
                    "document": {"$ref": "#/$defs/Document", "description": "A test document"},
                },
            },
            types_to_detect=["Document"],
        )
        assert result.value is True
        assert result.field_description == "Input is a single document with the following description: A test document"

    def test_non_ref_object(self):
        result = is_schema_only_containing_one_property(
            {
                "type": "object",
                "properties": {
                    "file": {"type": "object", "title": "File"},
                },
            },
        )
        assert result.value is False
        assert result.field_description is None


class TestFieldIterator:
    def test_extract_event_output(self):
        schema = JsonSchema(fixtures_json("jsonschemas", "extract_event_output.json"))

        fields = {".".join(k): v for k, v, _ in schema.fields_iterator([])}

        assert fields == {
            "title": "string",
            "end_time": "object",
            "description": "string",
            "start_time": "object",
            "start_time.date": "string",
            "start_time.time": "string",
            "start_time.timezone": "string",
            "end_time.date": "string",
            "end_time.time": "string",
            "end_time.timezone": "string",
            "location": "string",
        }

    def test_nested_object(self):
        schema = JsonSchema(
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                    "email": {"type": "string"},
                    "properties": {"type": "object", "properties": {"test": {"type": "string"}}},
                    "validated_input": {"type": "boolean"},
                },
                "required": ["name", "age"],
            },
        )

        fields = {".".join(k): v for k, v, _ in schema.fields_iterator([])}
        assert fields == {
            "name": "string",
            "age": "integer",
            "email": "string",
            "properties": "object",
            "properties.test": "string",
            "validated_input": "boolean",
        }

    def test_file(self):
        schema = JsonSchema(
            {
                "type": "object",
                "properties": {
                    "audio_file": {
                        "description": "The audio file to be transcribed",
                        "type": "object",
                        "$ref": "#/$defs/File",
                        "format": "audio",
                    },
                    "image_file": {
                        "description": "The image file to be processed",
                        "type": "object",
                        "$ref": "#/$defs/File",
                        "format": "image",
                    },
                },
                "$defs": {
                    "File": {
                        "properties": {
                            "name": {"description": "An optional name for the file", "title": "Name", "type": "string"},
                            "content_type": {
                                "description": "The content type of the file",
                                "examples": ["image/png", "image/jpeg", "audio/wav", "application/pdf"],
                                "title": "Content Type",
                                "type": "string",
                            },
                            "data": {
                                "description": "The base64 encoded data of the file",
                                "title": "Data",
                                "type": "string",
                            },
                        },
                        "required": ["name", "content_type", "data"],
                        "title": "File",
                        "type": "object",
                    },
                },
            },
        )
        fields = {".".join(k): v for k, v, _ in schema.fields_iterator([])}
        assert fields == {
            "audio_file": "object",
            "audio_file.name": "string",
            "audio_file.content_type": "string",
            "audio_file.data": "string",
            "image_file": "object",
            "image_file.name": "string",
            "image_file.content_type": "string",
            "image_file.data": "string",
        }

        # Without diving into the File schema
        fields = {
            ".".join(k): v for k, v, _ in schema.fields_iterator([], dive=lambda r: r.followed_ref_name != "File")
        }
        assert fields == {
            "audio_file": "object",
            "image_file": "object",
        }

    def test_nullable(self):
        schema = JsonSchema(
            {
                "properties": {
                    "inital_task_instructions": {
                        "anyOf": [
                            {
                                "type": "string",
                            },
                            {
                                "type": "null",
                            },
                        ],
                        "default": None,
                        "description": "The initial instructions to reformat",
                        "title": "Inital Task Instructions",
                    },
                },
                "title": "TaskInstructionsReformatingTaskInput",
                "type": "object",
            },
        )
        fields = {".".join(k): v for k, v, _ in schema.fields_iterator([])}
        assert fields == {
            "inital_task_instructions": "string",
        }


class TestChildIterator:
    def test_child_iterator_object(self):
        schema = JsonSchema(
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                    "email": {"type": "string"},
                },
            },
        )

        children = dict(schema.child_iterator())
        assert len(children) == 3
        assert all(isinstance(child, JsonSchema) for child in children.values())
        assert set(children.keys()) == {"name", "age", "email"}
        assert children["name"].type == "string"
        assert children["age"].type == "integer"
        assert children["email"].type == "string"

    def test_child_iterator_array_single_type(self):
        schema = JsonSchema(
            {
                "type": "array",
                "items": {"type": "string"},
            },
        )

        children = dict(schema.child_iterator())
        assert len(children) == 1
        assert 0 in children
        assert children[0].type == "string"

    def test_child_iterator_array_tuple_type(self):
        schema = JsonSchema(
            {
                "type": "array",
                "items": [
                    {"type": "string"},
                    {"type": "integer"},
                    {"type": "boolean"},
                ],
            },
        )

        children = dict(schema.child_iterator())
        assert len(children) == 3
        assert children[0].type == "string"
        assert children[1].type == "integer"
        assert children[2].type == "boolean"

    def test_child_iterator_empty_object(self):
        schema = JsonSchema(
            {
                "type": "object",
                "properties": {},
            },
        )

        children = dict(schema.child_iterator())
        assert len(children) == 0

    def test_child_iterator_empty_array(self):
        schema = JsonSchema(
            {
                "type": "array",
            },
        )

        children = dict(schema.child_iterator())
        assert len(children) == 0

    def test_child_iterator_primitive_type(self):
        schema = JsonSchema(
            {
                "type": "string",
            },
        )

        children = dict(schema.child_iterator())
        assert len(children) == 0

    def test_child_iterator_with_refs(self):
        schema = JsonSchema(
            {
                "type": "object",
                "properties": {
                    "file": {
                        "$ref": "#/$defs/File",
                    },
                },
                "$defs": {
                    "File": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "content": {"type": "string"},
                        },
                    },
                },
            },
        )

        children = dict(schema.child_iterator())
        assert len(children) == 1
        assert "file" in children
        file_schema = children["file"]
        assert file_schema.type == "object"

        # Test that refs are followed
        file_children = dict(file_schema.child_iterator())
        assert len(file_children) == 2
        assert set(file_children.keys()) == {"name", "content"}
        assert all(child.type == "string" for child in file_children.values())


class TestSchemaNeedsExplaination:
    @pytest.mark.parametrize(
        "schema, expected",
        [
            # Same tests but wrapped in object properties
            # Single enum wrapped in object
            (
                {
                    "type": "object",
                    "properties": {
                        "choice": {"enum": ["value1", "value2", "value3"], "description": "Select a value"},
                    },
                },
                True,
            ),
            # Enum without description wrapped in object
            (
                {"type": "object", "properties": {"numbers": {"enum": [1, 2, 3]}}},
                True,
            ),
            # Array of enums wrapped in object
            (
                {
                    "type": "object",
                    "properties": {
                        "colors": {
                            "type": "array",
                            "items": {"enum": ["red", "green", "blue"]},
                            "description": "Select colors",
                        },
                    },
                },
                True,
            ),
            # Array of enums with description in items wrapped in object
            (
                {
                    "type": "object",
                    "properties": {
                        "colors": {
                            "type": "array",
                            "items": {"enum": ["red", "green", "blue"], "description": "Color choices"},
                        },
                    },
                },
                True,
            ),
            # OneOf with enum wrapped in object
            (
                {
                    "type": "object",
                    "properties": {
                        "priority": {
                            "oneOf": [{"enum": ["low", "medium", "high"]}],
                            "description": "Priority level",
                        },
                    },
                },
                True,
            ),
            # AnyOf with enum wrapped in object
            (
                {
                    "type": "object",
                    "properties": {
                        "status": {"anyOf": [{"enum": ["draft", "published", "archived"]}]},
                    },
                },
                True,
            ),
            # AllOf with enum wrapped in object
            (
                {
                    "type": "object",
                    "properties": {
                        "answer": {
                            "allOf": [{"enum": ["yes", "no", "maybe"], "description": "Answer choices"}],
                            "description": "Your answer",
                        },
                    },
                },
                True,
            ),
            # Boolean schema wrapped in object
            (
                {
                    "type": "object",
                    "properties": {
                        "agree": {"type": "boolean", "description": "True or false question"},
                    },
                },
                True,
            ),
            # Boolean schema without description wrapped in object
            (
                {"type": "object", "properties": {"flag": {"type": "boolean"}}},
                True,
            ),
            # String schema wrapped in object
            (
                {"type": "object", "properties": {"name": {"type": "string"}}},
                False,
            ),
            # Nested object should NOT return True
            (
                {
                    "type": "object",
                    "properties": {
                        "user": {"type": "object", "properties": {"name": {"type": "string"}}},
                    },
                },
                False,
            ),
            # Array but not of enums wrapped in object should NOT return True
            (
                {
                    "type": "object",
                    "properties": {
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                },
                False,
            ),
            # OneOf but not with enum wrapped in object should NOT return True
            (
                {
                    "type": "object",
                    "properties": {
                        "value": {"oneOf": [{"type": "string"}, {"type": "number"}]},
                    },
                },
                False,
            ),
            # Enum with other properties should NOT return True
            (
                {
                    "type": "object",
                    "properties": {
                        "enum_field": {"enum": ["value1", "value2", "value3"], "description": "Select a value"},
                        "other_field": {"type": "string"},
                    },
                },
                False,
            ),
            # Enum array with other properties should NOT return True
            (
                {
                    "type": "object",
                    "properties": {
                        "enum_array": {
                            "type": "array",
                            "items": {"enum": ["value1", "value2", "value3"], "description": "Select a value"},
                        },
                        "other_field": {"type": "string"},
                    },
                },
                False,
            ),
            # Bool with other properties should NOT return True
            (
                {
                    "type": "object",
                    "properties": {
                        "bool_field": {"type": "boolean"},
                        "other_field": {"type": "string"},
                    },
                },
                False,
            ),
            # Object with enum inside should NOT return True
            (
                {
                    "type": "object",
                    "properties": {
                        "parent": {"type": "object", "properties": {"child": {"enum": ["value1", "value2", "value3"]}}},
                    },
                },
                False,
            ),
            # Array of objects with enum inside should NOT return True
            (
                {
                    "type": "object",
                    "properties": {
                        "parent_array": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "parent_object": {
                                        "type": "object",
                                        "properties": {"child": {"enum": ["value1", "value2", "value3"]}},
                                    },
                                },
                            },
                        },
                    },
                },
                False,
            ),
            # Explaination is already present
            (
                {"type": "object", "properties": {"explanation": {"type": "boolean"}}},
                False,
            ),
        ],
    )
    def test_schema_needs_explanation(self, schema: dict[str, Any], expected: bool):
        result = schema_needs_explanation(schema)
        assert result == expected


class TestRemoveFromParent:
    def test_remove_from_parent_object(self):
        schema = JsonSchema(
            {
                "type": "object",
                "properties": {"name": {"type": "string"}},
            },
        )

        child = schema.child_schema("name")
        child.remove_from_parent()
        assert schema.schema == {"type": "object", "properties": {}}

    def test_remove_from_parent_array(self):
        schema = JsonSchema(
            {
                "type": "object",
                "properties": {"name": {"type": "array", "items": {"type": "string"}}},
            },
        )

        child = schema.child_schema("name").child_schema(0)
        # child.remove_from_parent(recursive=False)
        # assert schema.schema == {"type": "object", "properties": {"name": {"type": "array"}}}
        child.remove_from_parent(recursive=True)
        assert schema.schema == {"type": "object", "properties": {}}

    def test_remove_from_parent_nested_object(self):
        schema = JsonSchema(
            {
                "type": "object",
                "properties": {
                    "user": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "age": {"type": "integer"},
                        },
                    },
                },
            },
        )

        child = schema.child_schema("user").child_schema("name")
        child.remove_from_parent(recursive=False)
        assert schema.schema == {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {
                        "age": {"type": "integer"},
                    },
                },
            },
        }

    def test_remove_from_parent_nested_array(self):
        schema = JsonSchema(
            {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "value": {"type": "number"},
                            },
                        },
                    },
                },
            },
        )

        child = schema.child_schema("items").child_schema(0).child_schema("id")
        child.remove_from_parent(recursive=False)
        assert schema.schema == {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "number"},
                        },
                    },
                },
            },
        }

    def test_remove_from_parent_with_required(self):
        schema = JsonSchema(
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )

        child = schema.child_schema("name")
        child.remove_from_parent(recursive=False)
        assert schema.schema == {
            "type": "object",
            "properties": {
                "age": {"type": "integer"},
            },
            "required": ["age"],
        }

    def test_remove_from_parent_with_refs(self):
        schema = JsonSchema(
            {
                "type": "object",
                "properties": {
                    "file": {
                        "$ref": "#/$defs/File",
                    },
                },
                "$defs": {
                    "File": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "content": {"type": "string"},
                        },
                    },
                },
            },
        )

        child = schema.child_schema("file").child_schema("name")
        child.remove_from_parent(recursive=False)
        assert schema.schema == {
            "type": "object",
            "properties": {
                "file": {
                    "$ref": "#/$defs/File",
                },
            },
            "$defs": {
                "File": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                    },
                },
            },
        }

    def test_remove_from_parent_with_one_of(self):
        schema = JsonSchema(
            {
                "type": "object",
                "properties": {
                    "choice": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "number"},
                        ],
                    },
                },
            },
        )

        child = schema.child_schema("choice")
        child.remove_from_parent(recursive=False)
        assert schema.schema == {
            "type": "object",
            "properties": {},
        }

    def test_remove_from_parent_with_array_of_objects(self):
        schema = JsonSchema(
            {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": [
                            {"type": "string"},
                            {"type": "number"},
                        ],
                    },
                },
            },
        )

        child = schema.child_schema("items").child_schema(0)
        child.remove_from_parent(recursive=False)
        assert schema.schema == {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": [
                        {"type": "number"},
                    ],
                },
            },
        }

    def test_remove_from_parent_with_additional_properties(self):
        schema = JsonSchema(
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                },
                "additionalProperties": True,
            },
        )

        child = schema.child_schema("name")
        child.remove_from_parent(recursive=False)
        assert schema.schema == {
            "type": "object",
            "properties": {},
            "additionalProperties": True,
        }

    def test_remove_from_parent_with_empty_properties(self):
        schema = JsonSchema(
            {
                "type": "object",
                "properties": {},
            },
        )

        # This should not raise an error
        schema.remove_from_parent(recursive=False)
        assert schema.schema == {
            "type": "object",
            "properties": {},
        }


class TestSchemaFromData:
    def test_schema_from_data_all_types(self):
        schema = schema_from_data(
            {
                "a_number": 1.0,
                "a_boolean": True,
                "a_array": [1, 2, 3],
                "a_object": {"a": 1, "b": "hello"},
                "a_null": None,
            },
        )
        assert schema == {
            "type": "object",
            "properties": {
                "a_number": {"type": "number"},
                "a_boolean": {"type": "boolean"},
                "a_array": {"type": "array", "items": {"type": "integer"}},
                "a_object": {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "string"}}},
                "a_null": {},
            },
        }
