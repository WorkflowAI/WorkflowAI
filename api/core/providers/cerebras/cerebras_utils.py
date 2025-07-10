from copy import deepcopy
from typing import Any, cast


def prepare_cerebras_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Prepare a JSON schema for Cerebras structured outputs.

    Unlike OpenAI, Cerebras appears to support standard JSON Schema format
    without requiring specific transformations like nullable arrays or
    moving keys into descriptions.

    However, Cerebras may not support array types like ["string", "null"]
    and requires them to be converted to anyOf format.

    Args:
        schema: The input JSON schema dictionary

    Returns:
        The prepared schema suitable for Cerebras structured outputs
    """
    # Make a deep copy to avoid modifying the original schema
    schema = deepcopy(schema)

    # Process the schema recursively to handle any Cerebras-specific requirements
    _process_cerebras_schema(schema)

    return schema


def _process_cerebras_schema(schema: dict[str, Any]) -> None:  # noqa: C901
    """Recursively process a schema for Cerebras compatibility.

    Converts array types like ["string", "null"] to anyOf format,
    as Cerebras may not support the array syntax for multiple types.
    Also ensures all properties are required (making optional ones nullable).
    """
    # Convert array types to anyOf format
    _convert_array_types_to_anyof(schema)

    # Handle properties - make all required and optional ones nullable
    if "properties" in schema:
        _process_properties(schema)

    # Handle nested objects
    if "properties" in schema:
        properties = schema["properties"]
        if isinstance(properties, dict):
            for prop_schema in cast(dict[str, Any], properties).values():
                if isinstance(prop_schema, dict):
                    _process_cerebras_schema(cast(dict[str, Any], prop_schema))

    # Handle arrays
    if "items" in schema:
        items = schema["items"]
        if isinstance(items, dict):
            _process_cerebras_schema(cast(dict[str, Any], items))
        elif isinstance(items, list):
            for item in cast(list[Any], items):
                if isinstance(item, dict):
                    _process_cerebras_schema(cast(dict[str, Any], item))

    # Handle anyOf/allOf/oneOf
    for key in ["anyOf", "allOf", "oneOf"]:
        if key in schema:
            schemas = schema[key]
            if isinstance(schemas, list):
                for subschema in cast(list[Any], schemas):
                    if isinstance(subschema, dict):
                        _process_cerebras_schema(cast(dict[str, Any], subschema))

    # Handle $defs (definitions)
    if "$defs" in schema:
        defs = schema["$defs"]
        if isinstance(defs, dict):
            for def_schema in cast(dict[str, Any], defs).values():
                if isinstance(def_schema, dict):
                    _process_cerebras_schema(cast(dict[str, Any], def_schema))


def _process_properties(schema: dict[str, Any]) -> None:
    """Process properties to make all required and optional ones nullable."""
    if "properties" not in schema:
        return

    properties = schema["properties"]
    if not isinstance(properties, dict):
        return

    original_required = set(schema.get("required", []))
    properties_dict = cast(dict[str, Any], properties)

    # Make non-required properties nullable
    for prop_name, prop_schema in properties_dict.items():
        if isinstance(prop_schema, dict) and prop_name not in original_required:
            _make_property_nullable(cast(dict[str, Any], prop_schema))

    # Make all properties required
    schema["required"] = list(properties_dict.keys())
    schema["additionalProperties"] = False


def _make_property_nullable(prop_schema: dict[str, Any]) -> None:
    """Make a property nullable by converting its type to anyOf with null."""
    if "type" in prop_schema:
        current_type = prop_schema["type"]
        if isinstance(current_type, str):
            # Convert single type to anyOf with null
            prop_schema["anyOf"] = [
                {"type": current_type},
                {"type": "null"},
            ]
            del prop_schema["type"]
        elif isinstance(current_type, list):
            # Convert array type to anyOf format and ensure null is included
            type_list = cast(list[Any], current_type)
            any_of_schemas = [{"type": single_type} for single_type in type_list]

            # Ensure null is included
            has_null = any(schema_item.get("type") == "null" for schema_item in any_of_schemas)
            if not has_null:
                any_of_schemas.append({"type": "null"})

            # Replace type with anyOf
            del prop_schema["type"]
            prop_schema["anyOf"] = any_of_schemas
    elif "anyOf" in prop_schema:
        # If it already has anyOf, ensure null type is included
        any_of_list = prop_schema["anyOf"]
        if isinstance(any_of_list, list):
            any_of_schemas = cast(list[dict[str, Any]], any_of_list)
            has_null = any(schema_item.get("type") == "null" for schema_item in any_of_schemas)
            if not has_null:
                any_of_schemas.append({"type": "null"})


def _convert_array_types_to_anyof(schema: dict[str, Any]) -> None:
    """Convert array types like ['string', 'null'] to anyOf format.

    Transforms:
        {"type": ["string", "null"]}
    Into:
        {"anyOf": [{"type": "string"}, {"type": "null"}]}
    """
    if "type" in schema:
        type_value = schema["type"]
        if isinstance(type_value, list) and len(cast(list[Any], type_value)) > 1:
            # Convert array type to anyOf
            any_of_schemas = [{"type": single_type} for single_type in cast(list[Any], type_value)]

            # Replace the type field with anyOf
            del schema["type"]
            schema["anyOf"] = any_of_schemas
