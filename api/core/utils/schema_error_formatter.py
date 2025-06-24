"""Utility for formatting JSON schema validation errors into user-friendly messages."""

from typing import Any

from jsonschema import ValidationError as SchemaValidationError


def format_validation_error(error: SchemaValidationError) -> str:
    """Format a jsonschema ValidationError into a user-friendly message.

    Args:
        error: The jsonschema ValidationError

    Returns:
        A formatted error message with details about what went wrong
    """
    # Build the path to the failing element
    path = _format_path(list(error.path))

    # Get the validator that failed
    validator = str(error.validator) if error.validator else ""

    if validator == "required":
        # Handle missing required fields
        missing_fields = error.validator_value
        if isinstance(missing_fields, list) and len(missing_fields) == 1:
            return f"Missing required field '{missing_fields[0]}'{path}"
        if isinstance(missing_fields, list):
            return f"Missing required fields: {', '.join(repr(f) for f in missing_fields)}{path}"
        return f"Missing required field{path}"

    if validator == "type":
        # Handle type mismatches
        expected_type = error.validator_value
        actual_value = error.instance
        actual_type = type(actual_value).__name__

        # Special handling for None/null
        if actual_value is None:
            actual_type = "null"
        elif isinstance(actual_value, bool):
            actual_type = "boolean"
        elif isinstance(actual_value, (int, float)):
            if isinstance(actual_value, bool):
                actual_type = "boolean"
            elif isinstance(actual_value, int):
                actual_type = "integer"
            else:
                actual_type = "number"
        elif isinstance(actual_value, str):
            actual_type = "string"
        elif isinstance(actual_value, list):
            actual_type = "array"
        elif isinstance(actual_value, dict):
            actual_type = "object"

        return f"Invalid type{path}: expected {expected_type}, got {actual_type}"

    if validator == "enum":
        # Handle enum validation
        allowed_values = error.validator_value
        actual_value = error.instance

        # Truncate long lists of allowed values
        if isinstance(allowed_values, list) and len(allowed_values) > 5:
            allowed_str = f"{allowed_values[:5]} (and {len(allowed_values) - 5} more)"
        else:
            allowed_str = str(allowed_values)

        return f"Invalid value{path}: '{actual_value}' is not one of {allowed_str}"

    if validator == "minLength":
        return f"String too short{path}: minimum length is {error.validator_value}, got {len(str(error.instance))}"

    if validator == "maxLength":
        return f"String too long{path}: maximum length is {error.validator_value}, got {len(str(error.instance))}"

    if validator == "minimum":
        return f"Value too small{path}: minimum is {error.validator_value}, got {error.instance}"

    if validator == "maximum":
        return f"Value too large{path}: maximum is {error.validator_value}, got {error.instance}"

    if validator == "pattern":
        return f"String does not match pattern{path}: expected pattern '{error.validator_value}'"

    if validator == "additionalProperties":
        # Extract the additional property from the error message
        if "Additional properties are not allowed" in error.message:
            # Parse the property name from the message
            import re

            match = re.search(r"'([^']+)' was unexpected", error.message)
            if match:
                prop_name = match.group(1)
                return f"Unexpected field '{prop_name}'{path}"
        return f"Additional properties not allowed{path}"

    if validator == "minItems":
        instance_len = len(error.instance) if hasattr(error.instance, "__len__") else 0
        return f"Array too short{path}: minimum {error.validator_value} items, got {instance_len}"

    if validator == "maxItems":
        instance_len = len(error.instance) if hasattr(error.instance, "__len__") else 0
        return f"Array too long{path}: maximum {error.validator_value} items, got {instance_len}"

    if validator == "uniqueItems":
        return f"Array contains duplicate items{path}"

    if validator == "format":
        expected_format = error.validator_value
        return f"Invalid format{path}: expected {expected_format} format"

    if validator == "oneOf" or validator == "anyOf":
        # These are complex and the default message is often better
        return f"Value does not match any of the expected schemas{path}"

    # Fallback to the original message for unknown validators
    return f"{error.message}{path}"


def _format_path(path: list[str | int]) -> str:
    """Format a jsonschema path into a readable string.

    Args:
        path: List of path components

    Returns:
        Formatted path string, e.g., " at 'users[0].name'"
    """
    if not path:
        return " at root level"

    result = []
    for component in path:
        if isinstance(component, int):
            result.append(f"[{component}]")
        else:
            if result:
                result.append(f".{component}")
            else:
                result.append(str(component))

    return f" at '{''.join(result)}'"


def format_validation_errors(errors: list[SchemaValidationError], max_errors: int = 5) -> str:
    """Format multiple validation errors into a single message.

    Args:
        errors: List of jsonschema ValidationError objects
        max_errors: Maximum number of errors to include in the message

    Returns:
        A formatted error message listing all validation issues
    """
    if not errors:
        return "Validation failed"

    # Format individual errors
    formatted_errors = []
    for error in errors[:max_errors]:
        formatted = format_validation_error(error)
        if formatted not in formatted_errors:  # Avoid duplicates
            formatted_errors.append(formatted)

    # Add indication if there are more errors
    if len(errors) > max_errors:
        formatted_errors.append(f"... and {len(errors) - max_errors} more validation errors")

    # Combine into a single message
    if len(formatted_errors) == 1:
        return formatted_errors[0]

    return "Multiple validation errors:\n- " + "\n- ".join(formatted_errors)


def get_validation_error_details(e: SchemaValidationError) -> dict[str, Any]:
    """Extract detailed information from a validation error for logging.

    Args:
        e: The jsonschema ValidationError

    Returns:
        Dictionary with error details
    """
    return {
        "path": list(e.path),
        "validator": str(e.validator) if e.validator else None,
        "validator_value": e.validator_value,
        "instance": e.instance,
        "message": e.message,
        "schema_path": list(e.schema_path),
    }
