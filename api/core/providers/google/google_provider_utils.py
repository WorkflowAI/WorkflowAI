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


def sanitize_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Prepare the schema according to Google's standard as defined in:
    https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/control-generated-output"""

    schema = copy.deepcopy(schema)

    # Replace all $refs by the actual definitions, as Google does not support $refs
    schema = resolve_schema_refs(schema)

    # Clean all anyOf, oneOf, allOf at current level, as Google does not support them
    schema = splat_nulls_recursive(schema)

    # Google use capitalized types, ex: 'STRING' instead of 'string'
    schema = capitalize_schema_types(schema)

    schema = streamline_schema(schema)

    # Remove examples, fuzzy, additionalProperties, as they are not supported by Google
    return strip_json_schema_metadata_keys(schema, exc_keys={"examples", "fuzzy", "additionalProperties", "title"})
