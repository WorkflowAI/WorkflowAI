import pytest

from core.domain.errors import JSONSchemaValidationError
from core.utils.detailed_schema_validation import DetailedSchemaValidator, validate_with_detailed_errors


class TestDetailedSchemaValidator:
    def test_valid_data_passes(self):
        """Test that valid data passes validation without error."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer", "minimum": 0},
            },
            "required": ["name"],
        }
        data = {"name": "John", "age": 30}

        validator = DetailedSchemaValidator(schema)
        # Should not raise any exception
        validator.validate_with_detailed_errors(data)

    def test_missing_required_field_single(self):
        """Test error message for single missing required field."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name"],
        }
        data = {"age": 30}

        validator = DetailedSchemaValidator(schema)
        with pytest.raises(JSONSchemaValidationError) as exc_info:
            validator.validate_with_detailed_errors(data)

        error_msg = str(exc_info.value)
        assert "Missing required field 'name'" in error_msg
        assert "at root" in error_msg

    def test_missing_required_fields_multiple(self):
        """Test error message for multiple missing required fields."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name", "email"],
        }
        data = {"age": 30}

        validator = DetailedSchemaValidator(schema)
        with pytest.raises(JSONSchemaValidationError) as exc_info:
            validator.validate_with_detailed_errors(data)

        error_msg = str(exc_info.value)
        assert "Missing required fields: 'name', 'email'" in error_msg

    def test_wrong_type_error(self):
        """Test error message for wrong data type."""
        schema = {
            "type": "object",
            "properties": {
                "age": {"type": "integer"},
            },
        }
        data = {"age": "thirty"}

        validator = DetailedSchemaValidator(schema)
        with pytest.raises(JSONSchemaValidationError) as exc_info:
            validator.validate_with_detailed_errors(data)

        error_msg = str(exc_info.value)
        assert "Expected integer but got str" in error_msg
        assert "'thirty'" in error_msg
        assert "at age" in error_msg

    def test_enum_validation_error(self):
        """Test error message for invalid enum value."""
        schema = {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["active", "inactive", "pending"]},
            },
        }
        data = {"status": "unknown"}

        validator = DetailedSchemaValidator(schema)
        with pytest.raises(JSONSchemaValidationError) as exc_info:
            validator.validate_with_detailed_errors(data)

        error_msg = str(exc_info.value)
        assert "Value 'unknown' is not allowed" in error_msg
        assert "Allowed values: 'active', 'inactive', 'pending'" in error_msg
        assert "at status" in error_msg

    def test_string_length_validation(self):
        """Test error messages for string length constraints."""
        schema = {
            "type": "object",
            "properties": {
                "short": {"type": "string", "minLength": 5},
                "long": {"type": "string", "maxLength": 10},
            },
        }

        # Test too short
        validator = DetailedSchemaValidator(schema)
        with pytest.raises(JSONSchemaValidationError) as exc_info:
            validator.validate_with_detailed_errors({"short": "hi"})

        error_msg = str(exc_info.value)
        assert "String too short" in error_msg
        assert "Expected at least 5 characters, got 2" in error_msg

        # Test too long
        with pytest.raises(JSONSchemaValidationError) as exc_info:
            validator.validate_with_detailed_errors({"long": "this is way too long"})

        error_msg = str(exc_info.value)
        assert "String too long" in error_msg
        assert "Expected at most 10 characters" in error_msg

    def test_numeric_range_validation(self):
        """Test error messages for numeric range constraints."""
        schema = {
            "type": "object",
            "properties": {
                "score": {"type": "number", "minimum": 0, "maximum": 100},
            },
        }

        validator = DetailedSchemaValidator(schema)

        # Test too small
        with pytest.raises(JSONSchemaValidationError) as exc_info:
            validator.validate_with_detailed_errors({"score": -5})

        error_msg = str(exc_info.value)
        assert "Value -5 is too small" in error_msg
        assert "Minimum allowed: 0" in error_msg

        # Test too large
        with pytest.raises(JSONSchemaValidationError) as exc_info:
            validator.validate_with_detailed_errors({"score": 150})

        error_msg = str(exc_info.value)
        assert "Value 150 is too large" in error_msg
        assert "Maximum allowed: 100" in error_msg

    def test_array_length_validation(self):
        """Test error messages for array length constraints."""
        schema = {
            "type": "object",
            "properties": {
                "tags": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 5},
            },
        }

        validator = DetailedSchemaValidator(schema)

        # Test too few items
        with pytest.raises(JSONSchemaValidationError) as exc_info:
            validator.validate_with_detailed_errors({"tags": ["one"]})

        error_msg = str(exc_info.value)
        assert "Array too short" in error_msg
        assert "Expected at least 2 items, got 1" in error_msg

        # Test too many items
        with pytest.raises(JSONSchemaValidationError) as exc_info:
            validator.validate_with_detailed_errors({"tags": ["1", "2", "3", "4", "5", "6"]})

        error_msg = str(exc_info.value)
        assert "Array too long" in error_msg
        assert "Expected at most 5 items, got 6" in error_msg

    def test_additional_properties_error(self):
        """Test error message for additional properties not allowed."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "additionalProperties": False,
        }
        data = {"name": "John", "age": 30, "email": "john@example.com", "phone": "123-456-7890"}

        validator = DetailedSchemaValidator(schema)
        with pytest.raises(JSONSchemaValidationError) as exc_info:
            validator.validate_with_detailed_errors(data)

        error_msg = str(exc_info.value)
        assert "Unexpected properties" in error_msg
        assert "'email'" in error_msg
        assert "'phone'" in error_msg

    def test_nested_object_validation(self):
        """Test error messages for nested object validation."""
        schema = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {
                        "profile": {
                            "type": "object",
                            "properties": {
                                "age": {"type": "integer"},
                            },
                            "required": ["age"],
                        },
                    },
                    "required": ["profile"],
                },
            },
        }
        data = {"user": {"profile": {"age": "twenty"}}}

        validator = DetailedSchemaValidator(schema)
        with pytest.raises(JSONSchemaValidationError) as exc_info:
            validator.validate_with_detailed_errors(data)

        error_msg = str(exc_info.value)
        assert "Expected integer but got str" in error_msg
        assert "at user.profile.age" in error_msg

    def test_array_item_validation(self):
        """Test error messages for array item validation."""
        schema = {
            "type": "object",
            "properties": {
                "scores": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0, "maximum": 100},
                },
            },
        }
        data = {"scores": [85, 92, 150, 78]}

        validator = DetailedSchemaValidator(schema)
        with pytest.raises(JSONSchemaValidationError) as exc_info:
            validator.validate_with_detailed_errors(data)

        error_msg = str(exc_info.value)
        assert "Value 150 is too large" in error_msg
        assert "at scores[2]" in error_msg

    def test_multiple_errors_summary(self):
        """Test that multiple errors are properly summarized."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer", "minimum": 0},
                "email": {"type": "string", "format": "email"},
            },
            "required": ["name", "age"],
        }
        data = {"age": -5, "email": "invalid-email"}

        validator = DetailedSchemaValidator(schema)
        with pytest.raises(JSONSchemaValidationError) as exc_info:
            validator.validate_with_detailed_errors(data)

        error_msg = str(exc_info.value)
        assert "Found" in error_msg and "validation error(s)" in error_msg
        assert "Missing required field 'name'" in error_msg
        assert "Value -5 is too small" in error_msg

    def test_format_validation(self):
        """Test error message for format validation."""
        schema = {
            "type": "object",
            "properties": {
                "email": {"type": "string", "format": "email"},
            },
        }
        data = {"email": "not-an-email"}

        validator = DetailedSchemaValidator(schema)
        with pytest.raises(JSONSchemaValidationError) as exc_info:
            validator.validate_with_detailed_errors(data)

        error_msg = str(exc_info.value)
        assert "Invalid email format" in error_msg
        assert "Got: 'not-an-email'" in error_msg

    def test_convenience_function(self):
        """Test the convenience function works correctly."""
        schema = {"type": "string"}
        data = 123

        with pytest.raises(JSONSchemaValidationError) as exc_info:
            validate_with_detailed_errors(data, schema)

        error_msg = str(exc_info.value)
        assert "Expected string but got int" in error_msg

    def test_value_display_formatting(self):
        """Test that values are formatted appropriately for display."""
        schema = {"type": "string"}

        validator = DetailedSchemaValidator(schema)

        # Test long string truncation
        long_string = "a" * 150
        with pytest.raises(JSONSchemaValidationError) as exc_info:
            validator.validate_with_detailed_errors(long_string)

        error_msg = str(exc_info.value)
        # Should be truncated with ellipsis
        assert "..." in error_msg
        assert len([part for part in error_msg.split("'") if "aaa" in part][0]) < 150

    def test_complex_object_display(self):
        """Test display formatting for complex objects."""
        schema = {"type": "string"}

        validator = DetailedSchemaValidator(schema)

        # Test object display
        complex_obj = {"key1": "value1", "key2": "value2", "key3": "value3", "key4": "value4"}
        with pytest.raises(JSONSchemaValidationError) as exc_info:
            validator.validate_with_detailed_errors(complex_obj)

        error_msg = str(exc_info.value)
        assert "object with" in error_msg
        assert "keys:" in error_msg

    def test_empty_values(self):
        """Test handling of empty values."""
        schema = {"type": "string"}

        validator = DetailedSchemaValidator(schema)

        # Test null value
        with pytest.raises(JSONSchemaValidationError) as exc_info:
            validator.validate_with_detailed_errors(None)

        error_msg = str(exc_info.value)
        assert "null" in error_msg

        # Test empty list
        with pytest.raises(JSONSchemaValidationError) as exc_info:
            validator.validate_with_detailed_errors([])

        error_msg = str(exc_info.value)
        assert "[]" in error_msg or "array with 0 items" in error_msg
