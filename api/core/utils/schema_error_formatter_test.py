"""Tests for schema error formatter."""

from jsonschema import ValidationError, validate

from core.utils.schema_error_formatter import (
    format_validation_error,
    format_validation_errors,
    get_validation_error_details,
)


class TestFormatValidationError:
    def test_missing_required_field_single(self):
        """Test formatting for a single missing required field."""
        schema = {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}
        data = {}

        try:
            validate(data, schema)
        except ValidationError as e:
            formatted = format_validation_error(e)
            assert formatted == "Missing required field 'name' at root level"

    def test_missing_required_fields_multiple(self):
        """Test formatting for multiple missing required fields."""
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "required": ["name", "age"],
        }
        data = {}

        try:
            validate(data, schema)
        except ValidationError as e:
            formatted = format_validation_error(e)
            assert "Missing required fields:" in formatted
            assert "'name'" in formatted
            assert "'age'" in formatted

    def test_type_mismatch_string_to_integer(self):
        """Test formatting for type mismatch."""
        schema = {"type": "object", "properties": {"age": {"type": "integer"}}}
        data = {"age": "twenty-five"}

        try:
            validate(data, schema)
        except ValidationError as e:
            formatted = format_validation_error(e)
            assert formatted == "Invalid type at 'age': expected integer, got string"

    def test_type_mismatch_nested(self):
        """Test formatting for nested type mismatch."""
        schema = {
            "type": "object",
            "properties": {
                "person": {
                    "type": "object",
                    "properties": {"age": {"type": "integer"}},
                },
            },
        }
        data = {"person": {"age": "invalid"}}

        try:
            validate(data, schema)
        except ValidationError as e:
            formatted = format_validation_error(e)
            assert formatted == "Invalid type at 'person.age': expected integer, got string"

    def test_enum_validation(self):
        """Test formatting for enum validation failure."""
        schema = {"type": "object", "properties": {"status": {"enum": ["ACTIVE", "INACTIVE", "PENDING"]}}}
        data = {"status": "INVALID"}

        try:
            validate(data, schema)
        except ValidationError as e:
            formatted = format_validation_error(e)
            assert "Invalid value at 'status': 'INVALID' is not one of" in formatted
            assert "['ACTIVE', 'INACTIVE', 'PENDING']" in formatted

    def test_enum_validation_many_values(self):
        """Test formatting for enum with many allowed values."""
        allowed = [f"VALUE_{i}" for i in range(10)]
        schema = {"type": "object", "properties": {"field": {"enum": allowed}}}
        data = {"field": "INVALID"}

        try:
            validate(data, schema)
        except ValidationError as e:
            formatted = format_validation_error(e)
            assert "(and 5 more)" in formatted

    def test_string_length_validation(self):
        """Test formatting for string length constraints."""
        schema = {"type": "object", "properties": {"name": {"type": "string", "minLength": 3, "maxLength": 10}}}

        # Too short
        try:
            validate({"name": "ab"}, schema)
        except ValidationError as e:
            formatted = format_validation_error(e)
            assert formatted == "String too short at 'name': minimum length is 3, got 2"

        # Too long
        try:
            validate({"name": "this is too long"}, schema)
        except ValidationError as e:
            formatted = format_validation_error(e)
            assert formatted == "String too long at 'name': maximum length is 10, got 16"

    def test_number_range_validation(self):
        """Test formatting for number range constraints."""
        schema = {"type": "object", "properties": {"score": {"type": "number", "minimum": 0, "maximum": 100}}}

        # Too small
        try:
            validate({"score": -5}, schema)
        except ValidationError as e:
            formatted = format_validation_error(e)
            assert formatted == "Value too small at 'score': minimum is 0, got -5"

        # Too large
        try:
            validate({"score": 150}, schema)
        except ValidationError as e:
            formatted = format_validation_error(e)
            assert formatted == "Value too large at 'score': maximum is 100, got 150"

    def test_array_validation(self):
        """Test formatting for array constraints."""
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 3,
                    "uniqueItems": True,
                },
            },
        }

        # Too short
        try:
            validate({"items": []}, schema)
        except ValidationError as e:
            formatted = format_validation_error(e)
            assert formatted == "Array too short at 'items': minimum 1 items, got 0"

        # Too long
        try:
            validate({"items": [1, 2, 3, 4]}, schema)
        except ValidationError as e:
            formatted = format_validation_error(e)
            assert formatted == "Array too long at 'items': maximum 3 items, got 4"

        # Duplicate items
        try:
            validate({"items": [1, 2, 1]}, schema)
        except ValidationError as e:
            formatted = format_validation_error(e)
            assert formatted == "Array contains duplicate items at 'items'"

    def test_pattern_validation(self):
        """Test formatting for pattern validation."""
        schema = {"type": "object", "properties": {"email": {"type": "string", "pattern": r"^[\w\.-]+@[\w\.-]+\.\w+$"}}}
        data = {"email": "invalid-email"}

        try:
            validate(data, schema)
        except ValidationError as e:
            formatted = format_validation_error(e)
            assert "String does not match pattern at 'email'" in formatted

    def test_additional_properties(self):
        """Test formatting for additional properties error."""
        schema = {"type": "object", "properties": {"name": {"type": "string"}}, "additionalProperties": False}
        data = {"name": "John", "unexpected": "value"}

        try:
            validate(data, schema)
        except ValidationError as e:
            formatted = format_validation_error(e)
            assert "Unexpected field 'unexpected' at root level" in formatted

    def test_format_validation(self):
        """Test formatting for format validation."""
        schema = {"type": "object", "properties": {"date": {"type": "string", "format": "date"}}}
        data = {"date": "not-a-date"}

        try:
            validate(data, schema)
        except ValidationError as e:
            formatted = format_validation_error(e)
            assert "Invalid format at 'date': expected date format" in formatted

    def test_array_index_path(self):
        """Test formatting with array indices in path."""
        schema = {
            "type": "object",
            "properties": {
                "users": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                },
            },
        }
        data = {"users": [{"name": "Alice"}, {}]}

        try:
            validate(data, schema)
        except ValidationError as e:
            formatted = format_validation_error(e)
            assert formatted == "Missing required field 'name' at 'users[1]'"


class TestFormatValidationErrors:
    def test_single_error(self):
        """Test formatting a single error."""
        schema = {"type": "object", "required": ["field"]}
        data = {}

        errors = []
        try:
            validate(data, schema)
        except ValidationError as e:
            errors.append(e)

        formatted = format_validation_errors(errors)
        assert formatted == "Missing required field 'field' at root level"

    def test_multiple_errors(self):
        """Test formatting multiple errors."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name", "age"],
        }
        data = {"age": "invalid"}

        errors = []
        # Collect all validation errors
        validator = validate.__wrapped__.__self__.VALIDATORS.get(
            schema.get("$schema", "http://json-schema.org/draft-07/schema#")
        )
        v = validator(schema)
        for error in v.iter_errors(data):
            errors.append(error)

        formatted = format_validation_errors(errors)
        assert "Multiple validation errors:" in formatted
        assert "- " in formatted

    def test_max_errors_limit(self):
        """Test that error list is truncated at max_errors."""
        # Create a schema that will generate many errors
        schema = {
            "type": "object",
            "properties": {f"field_{i}": {"type": "string"} for i in range(10)},
            "required": [f"field_{i}" for i in range(10)],
        }
        data = {}

        errors = []
        validator = validate.__wrapped__.__self__.VALIDATORS.get(
            schema.get("$schema", "http://json-schema.org/draft-07/schema#")
        )
        v = validator(schema)
        for error in v.iter_errors(data):
            errors.append(error)

        formatted = format_validation_errors(errors, max_errors=3)
        assert "... and" in formatted
        assert "more validation errors" in formatted


class TestGetValidationErrorDetails:
    def test_extract_error_details(self):
        """Test extracting detailed error information."""
        schema = {"type": "object", "properties": {"age": {"type": "integer"}}}
        data = {"age": "invalid"}

        try:
            validate(data, schema)
        except ValidationError as e:
            details = get_validation_error_details(e)

            assert details["path"] == ["age"]
            assert details["validator"] == "type"
            assert details["validator_value"] == "integer"
            assert details["instance"] == "invalid"
            assert "message" in details
            assert "schema_path" in details
