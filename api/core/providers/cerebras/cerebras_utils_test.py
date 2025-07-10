from core.providers.cerebras.cerebras_utils import prepare_cerebras_json_schema


def test_prepare_cerebras_json_schema_basic_object():
    """Test that basic object schemas are transformed with required property enforcement."""
    raw = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "email": {"type": "string"},
        },
        "required": ["name"],  # Only name is originally required
    }

    sanitized = prepare_cerebras_json_schema(raw)

    # Should preserve the original structure
    assert sanitized["type"] == "object"

    # All properties should now be required
    assert set(sanitized["required"]) == {"name", "age", "email"}

    # additionalProperties should be set to false
    assert sanitized["additionalProperties"] is False

    # Originally required property should remain as-is
    assert sanitized["properties"]["name"]["type"] == "string"
    assert "anyOf" not in sanitized["properties"]["name"]

    # Optional properties should become nullable with anyOf
    age_prop = sanitized["properties"]["age"]
    assert "type" not in age_prop
    assert "anyOf" in age_prop
    assert len(age_prop["anyOf"]) == 2
    assert {"type": "integer"} in age_prop["anyOf"]
    assert {"type": "null"} in age_prop["anyOf"]

    email_prop = sanitized["properties"]["email"]
    assert "type" not in email_prop
    assert "anyOf" in email_prop
    assert len(email_prop["anyOf"]) == 2
    assert {"type": "string"} in email_prop["anyOf"]
    assert {"type": "null"} in email_prop["anyOf"]


def test_prepare_cerebras_json_schema_all_properties_required():
    """Test schema where all properties are already required."""
    raw = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
        },
        "required": ["name", "age"],  # All properties already required
    }

    sanitized = prepare_cerebras_json_schema(raw)

    # All properties should remain required
    assert set(sanitized["required"]) == {"name", "age"}

    # Properties should remain as-is (not made nullable)
    assert sanitized["properties"]["name"]["type"] == "string"
    assert sanitized["properties"]["age"]["type"] == "integer"
    assert "anyOf" not in sanitized["properties"]["name"]
    assert "anyOf" not in sanitized["properties"]["age"]

    # additionalProperties should be set to false
    assert sanitized["additionalProperties"] is False


def test_prepare_cerebras_json_schema_no_required_field():
    """Test schema with no required field (all properties optional)."""
    raw = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
        },
        # No required field
    }

    sanitized = prepare_cerebras_json_schema(raw)

    # All properties should now be required
    assert set(sanitized["required"]) == {"name", "age"}

    # All properties should become nullable since they were optional
    name_prop = sanitized["properties"]["name"]
    assert "anyOf" in name_prop
    assert {"type": "string"} in name_prop["anyOf"]
    assert {"type": "null"} in name_prop["anyOf"]

    age_prop = sanitized["properties"]["age"]
    assert "anyOf" in age_prop
    assert {"type": "integer"} in age_prop["anyOf"]
    assert {"type": "null"} in age_prop["anyOf"]


def test_prepare_cerebras_json_schema_array_types():
    """Test that array types like ['string', 'null'] are converted to anyOf format."""
    raw = {
        "type": "object",
        "properties": {
            "name": {"type": ["string", "null"]},
            "age": {"type": ["integer", "null"]},
            "active": {"type": ["boolean", "null"]},
            "single_type": {"type": "string"},  # Will become nullable since not required
        },
        "required": ["name"],
    }

    sanitized = prepare_cerebras_json_schema(raw)

    # All properties should now be required
    assert set(sanitized["required"]) == {"name", "age", "active", "single_type"}

    # Array types should be converted to anyOf
    name_prop = sanitized["properties"]["name"]
    assert "type" not in name_prop
    assert "anyOf" in name_prop
    assert len(name_prop["anyOf"]) == 2
    assert {"type": "string"} in name_prop["anyOf"]
    assert {"type": "null"} in name_prop["anyOf"]

    age_prop = sanitized["properties"]["age"]
    assert "type" not in age_prop
    assert "anyOf" in age_prop
    assert len(age_prop["anyOf"]) == 2
    assert {"type": "integer"} in age_prop["anyOf"]
    assert {"type": "null"} in age_prop["anyOf"]

    active_prop = sanitized["properties"]["active"]
    assert "type" not in active_prop
    assert "anyOf" in active_prop
    assert len(active_prop["anyOf"]) == 2
    assert {"type": "boolean"} in active_prop["anyOf"]
    assert {"type": "null"} in active_prop["anyOf"]

    # Single type should become nullable (was optional)
    single_type_prop = sanitized["properties"]["single_type"]
    assert "anyOf" in single_type_prop
    assert {"type": "string"} in single_type_prop["anyOf"]
    assert {"type": "null"} in single_type_prop["anyOf"]


def test_prepare_cerebras_json_schema_single_element_array_type():
    """Test that single-element array types are preserved but properties are made required."""
    raw = {
        "type": "object",
        "properties": {
            "name": {"type": ["string"]},  # Single element array, optional property
        },
    }

    sanitized = prepare_cerebras_json_schema(raw)

    # Property should be required now
    assert sanitized["required"] == ["name"]

    # Single element arrays should not be converted to anyOf, but property becomes nullable
    name_prop = sanitized["properties"]["name"]
    assert "anyOf" in name_prop
    assert len(name_prop["anyOf"]) == 2
    # The original single-element array should be converted back to string + null
    assert {"type": "string"} in name_prop["anyOf"]
    assert {"type": "null"} in name_prop["anyOf"]


def test_prepare_cerebras_json_schema_preserves_format():
    """Test that format and other keys are preserved, not moved to description."""
    raw = {
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "format": "date-time",
                "examples": ["2023-01-01T00:00:00Z"],
                "default": "2023-01-01T00:00:00Z",
            },
        },
        "required": ["date"],
    }

    sanitized = prepare_cerebras_json_schema(raw)

    # Should preserve format, examples, and default
    date_prop = sanitized["properties"]["date"]
    assert date_prop["format"] == "date-time"
    assert date_prop["examples"] == ["2023-01-01T00:00:00Z"]
    assert date_prop["default"] == "2023-01-01T00:00:00Z"

    # Should not move these to description
    assert "description" not in date_prop or "format:" not in date_prop.get("description", "")


def test_prepare_cerebras_json_schema_preserves_title():
    """Test that title and other metadata keys are preserved."""
    raw = {
        "type": "object",
        "title": "User Profile",
        "properties": {
            "name": {
                "type": "string",
                "title": "Full Name",
                "pattern": "^[A-Za-z ]+$",
            },
        },
        "required": ["name"],
    }

    sanitized = prepare_cerebras_json_schema(raw)

    # Should preserve title and pattern
    assert sanitized["title"] == "User Profile"
    assert sanitized["properties"]["name"]["title"] == "Full Name"
    assert sanitized["properties"]["name"]["pattern"] == "^[A-Za-z ]+$"


def test_prepare_cerebras_json_schema_nested_objects():
    """Test that nested objects are processed correctly with property requirements."""
    raw = {
        "type": "object",
        "properties": {
            "user": {
                "type": "object",
                "properties": {
                    "profile": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "age": {"type": "integer"},
                        },
                        "required": ["name"],  # Only name required in nested object
                    },
                },
                "required": ["profile"],  # Profile required in user object
            },
        },
        "required": ["user"],  # User required at top level
    }

    sanitized = prepare_cerebras_json_schema(raw)

    # Top level should work correctly
    assert set(sanitized["required"]) == {"user"}
    assert sanitized["additionalProperties"] is False

    # User level should make profile required (it already was)
    user_obj = sanitized["properties"]["user"]
    assert set(user_obj["required"]) == {"profile"}
    assert user_obj["additionalProperties"] is False

    # Profile level should make both name and age required
    profile_obj = user_obj["properties"]["profile"]
    assert set(profile_obj["required"]) == {"name", "age"}
    assert profile_obj["additionalProperties"] is False

    # Name should remain as-is (was required)
    assert profile_obj["properties"]["name"]["type"] == "string"
    assert "anyOf" not in profile_obj["properties"]["name"]

    # Age should become nullable (was optional)
    age_prop = profile_obj["properties"]["age"]
    assert "anyOf" in age_prop
    assert {"type": "integer"} in age_prop["anyOf"]
    assert {"type": "null"} in age_prop["anyOf"]


def test_prepare_cerebras_json_schema_arrays():
    """Test that arrays are handled correctly with property requirements."""
    raw = {
        "type": "object",
        "properties": {
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 10,
            },
            "nested_array": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                    },
                    "required": ["id"],
                },
            },
        },
        "required": ["tags"],
    }

    sanitized = prepare_cerebras_json_schema(raw)

    # All top-level properties should be required
    assert set(sanitized["required"]) == {"tags", "nested_array"}

    # Should preserve array constraints
    tags_prop = sanitized["properties"]["tags"]
    assert tags_prop["type"] == "array"
    assert tags_prop["items"]["type"] == "string"
    assert tags_prop["minItems"] == 1
    assert tags_prop["maxItems"] == 10

    # Should handle nested object arrays - all properties in nested object become required
    nested_array = sanitized["properties"]["nested_array"]
    assert nested_array["items"]["properties"]["id"]["type"] == "integer"
    assert set(nested_array["items"]["required"]) == {"id", "name"}  # Both required now
    assert nested_array["items"]["additionalProperties"] is False

    # Name should be nullable since it was optional in the original schema
    name_prop = nested_array["items"]["properties"]["name"]
    assert "anyOf" in name_prop
    assert {"type": "string"} in name_prop["anyOf"]
    assert {"type": "null"} in name_prop["anyOf"]


def test_prepare_cerebras_json_schema_anyof():
    """Test that anyOf schemas are preserved."""
    raw = {
        "type": "object",
        "properties": {
            "value": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "integer"},
                    {
                        "type": "object",
                        "properties": {
                            "nested": {"type": "boolean"},
                        },
                        "required": ["nested"],
                    },
                ],
            },
        },
        "required": ["value"],
    }

    sanitized = prepare_cerebras_json_schema(raw)

    # Should preserve anyOf structure
    value_prop = sanitized["properties"]["value"]
    assert "anyOf" in value_prop
    assert len(value_prop["anyOf"]) == 3
    assert value_prop["anyOf"][0]["type"] == "string"
    assert value_prop["anyOf"][1]["type"] == "integer"
    assert value_prop["anyOf"][2]["properties"]["nested"]["type"] == "boolean"


def test_prepare_cerebras_json_schema_with_defs():
    """Test that $defs are handled correctly."""
    raw = {
        "type": "object",
        "properties": {
            "user": {"$ref": "#/$defs/User"},
            "users": {
                "type": "array",
                "items": {"$ref": "#/$defs/User"},
            },
        },
        "required": ["user"],
        "$defs": {
            "User": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "email": {
                        "type": "string",
                        "format": "email",
                    },
                },
                "required": ["name", "email"],
            },
        },
    }

    sanitized = prepare_cerebras_json_schema(raw)

    # Should preserve $defs and $ref
    assert "$defs" in sanitized
    assert "User" in sanitized["$defs"]
    assert sanitized["$defs"]["User"]["properties"]["email"]["format"] == "email"
    assert sanitized["properties"]["user"]["$ref"] == "#/$defs/User"


def test_prepare_cerebras_json_schema_immutable():
    """Test that the original schema is not modified."""
    original = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
        },
        "required": ["name"],
    }

    original_copy = original.copy()
    prepare_cerebras_json_schema(original)

    # Original should be unchanged
    assert original == original_copy


def test_prepare_cerebras_json_schema_empty_schema():
    """Test handling of empty or minimal schemas."""
    raw = {"type": "object"}

    sanitized = prepare_cerebras_json_schema(raw)

    # Should preserve minimal structure
    assert sanitized["type"] == "object"


def test_prepare_cerebras_json_schema_numeric_constraints():
    """Test that numeric constraints are preserved."""
    raw = {
        "type": "object",
        "properties": {
            "price": {
                "type": "number",
                "minimum": 0,
                "maximum": 1000,
                "multipleOf": 0.01,
            },
            "quantity": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
            },
        },
        "required": ["price", "quantity"],
    }

    sanitized = prepare_cerebras_json_schema(raw)

    # Should preserve numeric constraints
    price_prop = sanitized["properties"]["price"]
    assert price_prop["minimum"] == 0
    assert price_prop["maximum"] == 1000
    assert price_prop["multipleOf"] == 0.01

    quantity_prop = sanitized["properties"]["quantity"]
    assert quantity_prop["minimum"] == 1
    assert quantity_prop["maximum"] == 100


def test_prepare_cerebras_json_schema_nested_array_types():
    """Test that array types are converted to anyOf in nested structures."""
    raw = {
        "type": "object",
        "properties": {
            "user": {
                "type": "object",
                "properties": {
                    "name": {"type": ["string", "null"]},
                    "profile": {
                        "type": "object",
                        "properties": {
                            "age": {"type": ["integer", "null"]},
                            "tags": {
                                "type": "array",
                                "items": {"type": ["string", "number"]},  # Array type in items
                            },
                        },
                    },
                },
            },
            "metadata": {
                "anyOf": [
                    {
                        "type": "object",
                        "properties": {
                            "value": {"type": ["boolean", "null"]},  # Array type in anyOf subschema
                        },
                    },
                    {"type": "null"},
                ],
            },
        },
        "$defs": {
            "CustomType": {
                "type": "object",
                "properties": {
                    "field": {"type": ["string", "integer", "null"]},  # Array type in $defs
                },
            },
        },
    }

    sanitized = prepare_cerebras_json_schema(raw)

    # Check nested object array type conversion
    user_name = sanitized["properties"]["user"]["properties"]["name"]
    assert "anyOf" in user_name
    assert {"type": "string"} in user_name["anyOf"]
    assert {"type": "null"} in user_name["anyOf"]

    # Check deeply nested array type conversion
    profile_age = sanitized["properties"]["user"]["properties"]["profile"]["properties"]["age"]
    assert "anyOf" in profile_age
    assert {"type": "integer"} in profile_age["anyOf"]
    assert {"type": "null"} in profile_age["anyOf"]

    # Check array items array type conversion
    tags_items = sanitized["properties"]["user"]["properties"]["profile"]["properties"]["tags"]["items"]
    assert "anyOf" in tags_items
    assert {"type": "string"} in tags_items["anyOf"]
    assert {"type": "number"} in tags_items["anyOf"]

    # Check array type in anyOf subschema
    metadata_value = sanitized["properties"]["metadata"]["anyOf"][0]["properties"]["value"]
    assert "anyOf" in metadata_value
    assert {"type": "boolean"} in metadata_value["anyOf"]
    assert {"type": "null"} in metadata_value["anyOf"]

    # Check array type in $defs
    custom_type_field = sanitized["$defs"]["CustomType"]["properties"]["field"]
    assert "anyOf" in custom_type_field
    assert {"type": "string"} in custom_type_field["anyOf"]
    assert {"type": "integer"} in custom_type_field["anyOf"]
    assert {"type": "null"} in custom_type_field["anyOf"]


def test_prepare_cerebras_json_schema_mixed_array_and_anyof():
    """Test schema that already has anyOf mixed with array types."""
    raw = {
        "type": "object",
        "properties": {
            "field1": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "integer"},
                ],
            },
            "field2": {"type": ["boolean", "null"]},  # Should be converted
            "field3": {
                "anyOf": [
                    {"type": ["string", "null"]},  # Array type inside existing anyOf
                    {"type": "integer"},
                ],
            },
        },
        # No required field, so all properties become optional->nullable
    }

    sanitized = prepare_cerebras_json_schema(raw)

    # All properties should be required now
    assert set(sanitized["required"]) == {"field1", "field2", "field3"}

    # Existing anyOf should be preserved but made nullable (was optional)
    field1 = sanitized["properties"]["field1"]
    assert "anyOf" in field1
    assert len(field1["anyOf"]) == 3  # Original 2 + null for being optional
    assert {"type": "string"} in field1["anyOf"]
    assert {"type": "integer"} in field1["anyOf"]
    assert {"type": "null"} in field1["anyOf"]  # Added because field was optional

    # Array type should be converted to anyOf (already nullable)
    field2 = sanitized["properties"]["field2"]
    assert "anyOf" in field2
    assert len(field2["anyOf"]) == 2  # boolean and null (null not duplicated)
    assert {"type": "boolean"} in field2["anyOf"]
    assert {"type": "null"} in field2["anyOf"]

    # Array type inside anyOf should be converted
    field3 = sanitized["properties"]["field3"]
    assert "anyOf" in field3
    assert len(field3["anyOf"]) == 3  # Converted array + integer + null for optional

    # First anyOf item should now have anyOf instead of type array
    converted_items = [item for item in field3["anyOf"] if "anyOf" in item]
    assert len(converted_items) == 1
    first_item = converted_items[0]
    assert {"type": "string"} in first_item["anyOf"]
    assert {"type": "null"} in first_item["anyOf"]

    # Second anyOf item should remain unchanged
    assert {"type": "integer"} in field3["anyOf"]
    # Third item should be the added null for optional property
    assert {"type": "null"} in field3["anyOf"]


def test_prepare_cerebras_json_schema_array_types_with_property_requirements():
    """Test that array types are converted AND property requirements are enforced together."""
    raw = {
        "type": "object",
        "properties": {
            "required_array_type": {"type": ["string", "null"]},  # Required + array type
            "optional_array_type": {"type": ["integer", "null"]},  # Optional + array type
            "required_single_type": {"type": "boolean"},  # Required + single type
            "optional_single_type": {"type": "string"},  # Optional + single type
        },
        "required": ["required_array_type", "required_single_type"],
    }

    sanitized = prepare_cerebras_json_schema(raw)

    # All properties should be required
    assert set(sanitized["required"]) == {
        "required_array_type",
        "optional_array_type",
        "required_single_type",
        "optional_single_type",
    }
    assert sanitized["additionalProperties"] is False

    # Required array type: should be converted to anyOf (no additional null)
    required_array = sanitized["properties"]["required_array_type"]
    assert "anyOf" in required_array
    assert len(required_array["anyOf"]) == 2
    assert {"type": "string"} in required_array["anyOf"]
    assert {"type": "null"} in required_array["anyOf"]

    # Optional array type: should be converted to anyOf AND made nullable
    # Since it already had null in the array, it shouldn't add another null
    optional_array = sanitized["properties"]["optional_array_type"]
    assert "anyOf" in optional_array
    # Should have integer, null, and an additional null from making it nullable
    # But since null is already there, it should not duplicate
    assert len(optional_array["anyOf"]) == 2
    assert {"type": "integer"} in optional_array["anyOf"]
    assert {"type": "null"} in optional_array["anyOf"]

    # Required single type: should remain as-is
    required_single = sanitized["properties"]["required_single_type"]
    assert required_single["type"] == "boolean"
    assert "anyOf" not in required_single

    # Optional single type: should be made nullable with anyOf
    optional_single = sanitized["properties"]["optional_single_type"]
    assert "anyOf" in optional_single
    assert len(optional_single["anyOf"]) == 2
    assert {"type": "string"} in optional_single["anyOf"]
    assert {"type": "null"} in optional_single["anyOf"]


def test_prepare_cerebras_json_schema_property_with_existing_anyof():
    """Test handling of properties that already have anyOf."""
    raw = {
        "type": "object",
        "properties": {
            "required_anyof": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "integer"},
                ],
            },
            "optional_anyof": {
                "anyOf": [
                    {"type": "boolean"},
                    {"type": "string"},
                ],
            },
            "optional_anyof_with_null": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
            },
        },
        "required": ["required_anyof"],
    }

    sanitized = prepare_cerebras_json_schema(raw)

    # All properties should be required
    assert set(sanitized["required"]) == {
        "required_anyof",
        "optional_anyof",
        "optional_anyof_with_null",
    }

    # Required anyOf should remain unchanged
    required_anyof = sanitized["properties"]["required_anyof"]
    assert len(required_anyof["anyOf"]) == 2
    assert {"type": "string"} in required_anyof["anyOf"]
    assert {"type": "integer"} in required_anyof["anyOf"]
    assert {"type": "null"} not in required_anyof["anyOf"]

    # Optional anyOf should have null added
    optional_anyof = sanitized["properties"]["optional_anyof"]
    assert len(optional_anyof["anyOf"]) == 3
    assert {"type": "boolean"} in optional_anyof["anyOf"]
    assert {"type": "string"} in optional_anyof["anyOf"]
    assert {"type": "null"} in optional_anyof["anyOf"]

    # Optional anyOf with existing null should not add duplicate null
    optional_anyof_null = sanitized["properties"]["optional_anyof_with_null"]
    assert len(optional_anyof_null["anyOf"]) == 2
    assert {"type": "string"} in optional_anyof_null["anyOf"]
    assert {"type": "null"} in optional_anyof_null["anyOf"]


def test_prepare_cerebras_json_schema_optional_property_with_array_type():
    """Test that optional properties with array types are converted to anyOf format when made nullable."""
    raw = {
        "type": "object",
        "properties": {
            "required_field": {"type": "string"},
            "optional_with_array_type": {"type": ["object", "null"]},  # This should be converted to anyOf
            "optional_with_multiple_array_types": {"type": ["string", "integer", "boolean"]},  # This too
        },
        "required": ["required_field"],
    }

    sanitized = prepare_cerebras_json_schema(raw)

    # All properties should be required
    assert set(sanitized["required"]) == {
        "required_field",
        "optional_with_array_type",
        "optional_with_multiple_array_types",
    }

    # Required field should remain as-is
    assert sanitized["properties"]["required_field"]["type"] == "string"

    # Optional with array type should be converted to anyOf (already has null, so no duplicate)
    optional_array = sanitized["properties"]["optional_with_array_type"]
    assert "type" not in optional_array
    assert "anyOf" in optional_array
    assert len(optional_array["anyOf"]) == 2
    assert {"type": "object"} in optional_array["anyOf"]
    assert {"type": "null"} in optional_array["anyOf"]

    # Optional with multiple array types should be converted to anyOf and null should be added
    optional_multiple = sanitized["properties"]["optional_with_multiple_array_types"]
    assert "type" not in optional_multiple
    assert "anyOf" in optional_multiple
    assert len(optional_multiple["anyOf"]) == 4  # string, integer, boolean, null
    assert {"type": "string"} in optional_multiple["anyOf"]
    assert {"type": "integer"} in optional_multiple["anyOf"]
    assert {"type": "boolean"} in optional_multiple["anyOf"]
    assert {"type": "null"} in optional_multiple["anyOf"]
