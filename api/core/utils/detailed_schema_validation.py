# pyright: reportPrivateUsage=false
import logging
from typing import Any

from jsonschema.validators import validator_for  # pyright: ignore[reportUnknownVariableType]

from core.domain.errors import JSONSchemaValidationError

logger = logging.getLogger(__name__)


class DetailedSchemaValidator:
    """
    Enhanced schema validator that provides detailed, human-readable error messages
    when JSON data doesn't match a schema.
    """

    def __init__(self, schema: dict[str, Any]):
        self.schema = schema
        self.validator = validator_for(schema)(schema)  # pyright: ignore[reportUnknownMemberType]

    def validate_with_detailed_errors(self, data: Any) -> None:
        """
        Validate data against schema and raise JSONSchemaValidationError with detailed message.

        Args:
            data: The data to validate

        Raises:
            JSONSchemaValidationError: With detailed error message if validation fails
        """
        errors = list(self.validator.iter_errors(data))  # pyright: ignore[reportUnknownMemberType]
        if not errors:
            return

        # Generate detailed error message
        detailed_message = self._generate_detailed_error_message(errors, data)  # pyright: ignore[reportUnknownArgumentType]
        raise JSONSchemaValidationError(detailed_message)

    def _generate_detailed_error_message(self, errors: list[Any], data: Any) -> str:  # pyright: ignore[reportUnknownParameterType]
        """
        Generate a comprehensive error message from validation errors.

        Args:
            errors: List of validation errors from jsonschema
            data: The original data that failed validation

        Returns:
            A detailed, human-readable error message
        """
        if len(errors) == 1:
            return self._format_single_error(errors[0], data)

        # Multiple errors - provide a summary
        error_summaries = []
        for error in errors[:5]:  # Limit to first 5 errors to avoid overwhelming output
            summary = self._format_single_error(error, data, brief=True)
            error_summaries.append(f"  • {summary}")

        message = f"Found {len(errors)} validation error(s):\n" + "\n".join(error_summaries)  # pyright: ignore[reportUnknownArgumentType]

        if len(errors) > 5:
            message += f"\n  ... and {len(errors) - 5} more error(s)"

        return message

    def _format_single_error(self, error: Any, data: Any, brief: bool = False) -> str:  # pyright: ignore[reportUnknownParameterType]
        """
        Format a single validation error into a human-readable message.

        Args:
            error: The validation error
            data: The original data
            brief: Whether to generate a brief summary or detailed explanation

        Returns:
            Formatted error message
        """
        path = self._format_path(list(error.path))  # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType]
        location = f"at {path}" if path else "at root"

        # Get the actual value that caused the error
        actual_value = self._get_value_at_path(data, list(error.path))  # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType]
        actual_value_str = self._format_value_for_display(actual_value)

        # Generate error message based on error type
        if error.validator == "required":  # pyright: ignore[reportUnknownMemberType]
            missing_fields = error.validator_value  # pyright: ignore[reportUnknownMemberType]
            if isinstance(missing_fields, list) and len(missing_fields) == 1:
                field_name = missing_fields[0]
                return f"Missing required field '{field_name}' {location}"
            fields_str = ", ".join(f"'{field}'" for field in missing_fields)
            return f"Missing required fields: {fields_str} {location}"

        if error.validator == "type":  # pyright: ignore[reportUnknownMemberType]
            expected_type = error.validator_value  # pyright: ignore[reportUnknownMemberType]
            if isinstance(expected_type, list):
                expected_str = " or ".join(expected_type)
            else:
                expected_str = expected_type
            return (
                f"Expected {expected_str} but got {type(actual_value).__name__.lower()} ({actual_value_str}) {location}"
            )

        if error.validator == "enum":  # pyright: ignore[reportUnknownMemberType]
            allowed_values = error.validator_value  # pyright: ignore[reportUnknownMemberType]
            allowed_str = ", ".join(f"'{v}'" for v in allowed_values[:5])
            if len(allowed_values) > 5:
                allowed_str += f" (and {len(allowed_values) - 5} more)"
            return f"Value {actual_value_str} is not allowed {location}. Allowed values: {allowed_str}"

        if error.validator == "minLength":  # pyright: ignore[reportUnknownMemberType]
            min_length = error.validator_value  # pyright: ignore[reportUnknownMemberType]
            actual_length = len(actual_value) if hasattr(actual_value, "__len__") else 0
            return f"String too short {location}. Expected at least {min_length} characters, got {actual_length}"

        if error.validator == "maxLength":  # pyright: ignore[reportUnknownMemberType]
            max_length = error.validator_value  # pyright: ignore[reportUnknownMemberType]
            actual_length = len(actual_value) if hasattr(actual_value, "__len__") else 0
            return f"String too long {location}. Expected at most {max_length} characters, got {actual_length}"

        if error.validator == "minimum":  # pyright: ignore[reportUnknownMemberType]
            min_value = error.validator_value  # pyright: ignore[reportUnknownMemberType]
            return f"Value {actual_value_str} is too small {location}. Minimum allowed: {min_value}"

        if error.validator == "maximum":  # pyright: ignore[reportUnknownMemberType]
            max_value = error.validator_value  # pyright: ignore[reportUnknownMemberType]
            return f"Value {actual_value_str} is too large {location}. Maximum allowed: {max_value}"

        if error.validator == "minItems":  # pyright: ignore[reportUnknownMemberType]
            min_items = error.validator_value  # pyright: ignore[reportUnknownMemberType]
            actual_length = len(actual_value) if hasattr(actual_value, "__len__") else 0
            return f"Array too short {location}. Expected at least {min_items} items, got {actual_length}"

        if error.validator == "maxItems":  # pyright: ignore[reportUnknownMemberType]
            max_items = error.validator_value  # pyright: ignore[reportUnknownMemberType]
            actual_length = len(actual_value) if hasattr(actual_value, "__len__") else 0
            return f"Array too long {location}. Expected at most {max_items} items, got {actual_length}"

        if error.validator == "pattern":  # pyright: ignore[reportUnknownMemberType]
            pattern = error.validator_value  # pyright: ignore[reportUnknownMemberType]
            return f"String {actual_value_str} does not match required pattern {location}. Expected pattern: {pattern}"

        if error.validator == "format":  # pyright: ignore[reportUnknownMemberType]
            expected_format = error.validator_value  # pyright: ignore[reportUnknownMemberType]
            return f"Invalid {expected_format} format {location}. Got: {actual_value_str}"

        if error.validator == "additionalProperties":  # pyright: ignore[reportUnknownMemberType]
            if error.validator_value is False:  # pyright: ignore[reportUnknownMemberType]
                # Find the extra property
                if hasattr(actual_value, "keys") and error.schema.get("properties"):  # pyright: ignore[reportUnknownMemberType]
                    allowed_props = set(error.schema["properties"].keys())  # pyright: ignore[reportUnknownMemberType]
                    actual_props = set(actual_value.keys())
                    extra_props = actual_props - allowed_props
                    if extra_props:
                        extra_str = ", ".join(f"'{prop}'" for prop in sorted(extra_props)[:3])
                        if len(extra_props) > 3:
                            extra_str += f" (and {len(extra_props) - 3} more)"
                        return f"Unexpected properties {location}: {extra_str}"
                return f"Additional properties not allowed {location}"

        elif error.validator in ("oneOf", "anyOf", "allOf"):  # pyright: ignore[reportUnknownMemberType]
            return f"Value {actual_value_str} does not match any of the expected schemas {location}"

        # Fallback for other error types
        return f"{error.message} {location}. Got: {actual_value_str}"  # pyright: ignore[reportUnknownMemberType]

    def _format_path(self, path: list[Any]) -> str:
        """Format a JSONPath into a readable string."""
        if not path:
            return ""

        formatted_parts = []
        for part in path:
            if isinstance(part, int):
                formatted_parts.append(f"[{part}]")
            else:
                if formatted_parts:
                    formatted_parts.append(f".{part}")
                else:
                    formatted_parts.append(str(part))

        return "".join(formatted_parts)

    def _get_value_at_path(self, data: Any, path: list[Any]) -> Any:
        """Get the value at a specific path in the data structure."""
        current = data
        try:
            for part in path:
                if isinstance(current, dict):
                    current = current[part]
                elif isinstance(current, list) and isinstance(part, int):
                    current = current[part]
                else:
                    return None
            return current
        except (KeyError, IndexError, TypeError):
            return None

    def _format_value_for_display(self, value: Any, max_length: int = 100) -> str:
        """Format a value for display in error messages."""
        if value is None:
            return "null"
        if isinstance(value, str):
            if len(value) <= max_length:
                return f"'{value}'"
            return f"'{value[: max_length - 3]}...'"
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, dict):
            if not value:
                return "{}"
            key_count = len(value)
            sample_keys = list(value.keys())[:3]
            if key_count <= 3:
                return f"object with keys: {', '.join(repr(k) for k in sample_keys)}"
            return f"object with {key_count} keys: {', '.join(repr(k) for k in sample_keys)}, ..."
        if isinstance(value, list):
            if not value:
                return "[]"
            return f"array with {len(value)} items"
        return f"{type(value).__name__} value"


def validate_with_detailed_errors(data: Any, schema: dict[str, Any]) -> None:
    """
    Convenience function to validate data against a schema with detailed error messages.

    Args:
        data: The data to validate
        schema: The JSON schema to validate against

    Raises:
        JSONSchemaValidationError: With detailed error message if validation fails
    """
    validator = DetailedSchemaValidator(schema)
    validator.validate_with_detailed_errors(data)
