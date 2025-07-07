import copy
import logging
from typing import Any, cast

from core.utils.schema_sanitation import streamline_schema
from core.utils.schemas import JsonSchema, strip_json_schema_metadata_keys

logger = logging.getLogger(__name__)


def resolve_schema_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively resolves all $ref references in a JSON Schema by replacing them
    with the actual referenced schema definitions.
    """
    # Deep copy the schema to avoid modifying the original
    defs = schema.get("$defs", {})

    def resolve_ref(ref: str) -> dict[str, Any]:
        """Get the schema definition for a reference."""
        if not ref.startswith("#/$defs/"):
            raise ValueError(f"Unsupported reference format: {ref}")
        def_name = ref.split("/")[-1]
        if def_name not in defs:
            raise ValueError(f"Definition not found: {def_name}")
        return copy.deepcopy(defs[def_name])

    def resolve_node(node: Any) -> Any:
        """Recursively resolve all references in a schema node."""
        if not isinstance(node, (dict, list)):
            return node

        if isinstance(node, list):
            return [resolve_node(item) for item in node]  # pyright: ignore[reportUnknownVariableType]

        if "$ref" in node:
            # Get the referenced definition
            ref_def = resolve_ref(node["$ref"])  # pyright: ignore[reportUnknownArgumentType]
            # Remove $ref from the node
            resolved = {k: v for k, v in node.items() if k != "$ref"}  # pyright: ignore[reportUnknownVariableType]
            # Resolve any refs in the definition first
            ref_def = resolve_node(ref_def)
            # Merge the resolved definition with any additional properties
            resolved.update(ref_def)  # pyright: ignore[reportUnknownMemberType]
            return resolved  # pyright: ignore[reportUnknownVariableType]

        return {k: resolve_node(v) for k, v in node.items()}  # pyright: ignore[reportUnknownVariableType]

    # Resolve all references in the schema
    resolved = resolve_node(schema)

    # Remove the $defs section as it's no longer needed
    if "$defs" in resolved:
        del resolved["$defs"]

    return resolved


def _capitalize_type_value(type_value: Any) -> Any:
    """Helper function to capitalize a type value (string or list of strings)."""
    if isinstance(type_value, str):
        return type_value.upper()
    if isinstance(type_value, list):
        capitalized_types: list[Any] = []
        for item in cast(list[Any], type_value):
            if isinstance(item, str):
                capitalized_types.append(item.upper())
            else:
                capitalized_types.append(item)
        return capitalized_types
    return type_value


def capitalize_schema_types(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Capitalize the types ("type") in a JSON Schema
    """

    # Browse the full schema passed as input and capitalize the types
    for k, v in schema.items():
        if isinstance(v, dict):
            capitalize_schema_types(cast(dict[str, Any], v))
        elif isinstance(v, list):
            for item in v:  # pyright: ignore[reportUnknownVariableType]
                if isinstance(item, dict):
                    capitalize_schema_types(cast(dict[str, Any], item))

        # Handle type capitalization
        if k == "type":
            schema[k] = _capitalize_type_value(v)

    return schema


def _handle_string_format_restriction(schema: dict[str, Any], allowed_formats: set[str]) -> dict[str, Any]:
    """Handle string format restrictions for a single schema node."""
    schema_type = schema.get("type")
    is_string_type = (
        schema_type == "string"
        or schema_type == "STRING"
        or (isinstance(schema_type, list) and ("string" in schema_type or "STRING" in schema_type))
    )

    if not is_string_type:
        return schema

    # Check if this string field has a format
    if "format" in schema:
        format_value = schema["format"]
        if format_value not in allowed_formats:
            # Remove the unsupported format
            schema = {k: v for k, v in schema.items() if k != "format"}
            logger.warning("Removed unsupported string format", extra={"format": format_value})

    # Handle enum case - if enum is present and allowed, keep it
    if "enum" in schema and "enum" not in allowed_formats:
        # Convert enum to a regular string field if enum format is not allowed
        schema = {k: v for k, v in schema.items() if k != "enum"}
        logger.warning("Removed enum constraint as enum format is not allowed")

    return schema


def _apply_format_restrictions_recursively(schema: dict[str, Any], allowed_formats: set[str]) -> dict[str, Any]:
    """Apply format restrictions recursively to nested structures."""
    # Recursively handle object properties
    if "properties" in schema:
        new_props = {}
        for prop_name, prop_schema in schema["properties"].items():
            new_props[prop_name] = restrict_string_formats(prop_schema, allowed_formats)
        schema = {**schema, "properties": new_props}

    # Recursively handle array items
    if "items" in schema:
        items = schema["items"]
        if isinstance(items, list):
            schema = {**schema, "items": [restrict_string_formats(item, allowed_formats) for item in items]}  # pyright: ignore[reportUnknownArgumentType,reportUnknownVariableType]
        else:
            schema = {**schema, "items": restrict_string_formats(items, allowed_formats)}

    # Handle oneOf/anyOf/allOf
    for key in ["oneOf", "anyOf", "allOf"]:
        if key in schema:
            schema[key] = [restrict_string_formats(sub_schema, allowed_formats) for sub_schema in schema[key]]  # pyright: ignore[reportUnknownArgumentType]

    return schema


def restrict_string_formats(schema: dict[str, Any], allowed_formats: set[str] | None = None) -> dict[str, Any]:
    """
    Recursively restrict string formats in a JSON Schema to only the allowed formats.

    Args:
        schema: The schema to process
        allowed_formats: Set of allowed string formats (e.g., {"enum", "date-time"})
                        If None, no restrictions are applied

    Returns:
        The schema with restricted string formats
    """
    if allowed_formats is None:
        return schema

    # Handle current level
    schema = _handle_string_format_restriction(schema, allowed_formats)

    # Apply restrictions recursively
    return _apply_format_restrictions_recursively(schema, allowed_formats)


def splat_nulls_recursive(schema: dict[str, Any]) -> dict[str, Any]:
    """Recursively splats nulls throughout an entire schema"""
    # Save fields we want to preserve
    preserved_fields = {
        k: v for k, v in schema.items() if k not in ["oneOf", "anyOf", "allOf", "properties", "items", "type"]
    }

    # Handle direct type arrays (e.g., ["object", "null"])
    schema_type = schema.get("type")
    if isinstance(schema_type, list) and "null" in schema_type:
        # Convert ["object", "null"] to {"type": "object", "nullable": true}
        typed_schema_type = cast(list[Any], schema_type)
        non_null_types = [t for t in typed_schema_type if t != "null"]
        if len(non_null_types) == 1:
            schema = {**schema, "type": non_null_types[0], "nullable": True}
        elif len(non_null_types) > 1:
            # Multiple non-null types - keep as array but remove null and add nullable
            schema = {**schema, "type": non_null_types, "nullable": True}
        else:
            # Only null type - keep as is
            pass

    # Handle oneOf/anyOf/allOf at current level
    schema, nullable = JsonSchema.splat_nulls(schema)  # pyright: ignore[reportAssignmentType, reportArgumentType]
    if nullable:
        schema = {**schema, "nullable": True}

    # Restore preserved fields
    schema.update(preserved_fields)

    # Recursively handle object properties
    if "properties" in schema:
        new_props = {}
        for prop_name, prop_schema in schema["properties"].items():
            new_props[prop_name] = splat_nulls_recursive(prop_schema)
        schema = {**schema, "properties": new_props}

    # Recursively handle array items
    if "items" in schema:
        items = schema["items"]
        if isinstance(items, list):
            schema = {**schema, "items": [splat_nulls_recursive(item) for item in items]}  # pyright: ignore[reportUnknownArgumentType,reportUnknownVariableType]
        else:
            schema = {**schema, "items": splat_nulls_recursive(items)}

    return schema


def prepare_google_response_schema(
    schema: dict[str, Any],
    allowed_string_formats: set[str] | None = None,
) -> dict[str, Any]:
    """Prepare the schema according to Google's standard as defined in:
    https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/control-generated-output

    Args:
        schema: The JSON schema to prepare
        allowed_string_formats: Optional set of allowed string formats (e.g., {"enum", "date-time"})
                               If provided, only these string formats will be kept in the schema.
                               Common formats include:
                               - "enum": For string enumeration constraints
                               - "date-time": For ISO 8601 datetime strings
                               - "email": For email address strings
                               - "uri": For URI strings
                               - "uuid": For UUID strings
                               - "ipv4": For IPv4 address strings
                               - "ipv6": For IPv6 address strings

    Returns:
        dict: The prepared schema compatible with Google's requirements

    Example:
        >>> schema = {
        ...     "type": "object",
        ...     "properties": {
        ...         "status": {"type": "string", "enum": ["active", "inactive"]},
        ...         "email": {"type": "string", "format": "email"},
        ...         "created_at": {"type": "string", "format": "date-time"}
        ...     }
        ... }
        >>> # Allow only enum and date-time formats
        >>> prepare_google_response_schema(schema, {"enum", "date-time"})
        {
            "type": "OBJECT",
            "properties": {
                "status": {"type": "STRING", "enum": ["active", "inactive"]},
                "email": {"type": "STRING"},  # format removed
                "created_at": {"type": "STRING", "format": "date-time"}  # format kept
            }
        }
    """

    schema = copy.deepcopy(schema)

    # Replace all $refs by the actual definitions, as Google does not support $refs
    schema = resolve_schema_refs(schema)

    # Clean all anyOf, oneOf, allOf at current level, as Google does not support them
    schema = splat_nulls_recursive(schema)

    # Restrict string formats if specified
    if allowed_string_formats is not None:
        schema = restrict_string_formats(schema, allowed_string_formats)

    # Google use capitalized types, ex: 'STRING' instead of 'string'
    schema = capitalize_schema_types(schema)

    schema = streamline_schema(schema)

    # Remove examples, fuzzy, additionalProperties, as they are not supported by Google
    return strip_json_schema_metadata_keys(schema, exc_keys={"examples", "fuzzy", "additionalProperties", "title"})
