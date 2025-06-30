from typing import Any, Protocol


class HasModelJsonSchema(Protocol):
    """Protocol for classes that have a model_json_schema method (like Pydantic BaseModel)"""

    def model_json_schema(self) -> dict[str, Any]: ...


def format_schema_as_yaml_description(model_class: HasModelJsonSchema) -> str:
    """Convert Pydantic model to YAML-like description format for MCP tool descriptions"""
    schema = model_class.model_json_schema()
    definitions = schema.get("$defs", {})

    def format_properties(properties: dict[str, Any], indent_level: int = 0) -> list[str]:
        """Format properties recursively"""
        lines: list[str] = []
        indent = "  " * indent_level

        for field_name, field_info in properties.items():
            description = field_info.get("description", "")

            # Handle array fields with nested objects
            if field_info.get("type") == "array" and "items" in field_info:
                items = field_info["items"]
                if "$ref" in items and definitions:
                    ref_name = items["$ref"].split("/")[-1]
                    if ref_name in definitions:
                        # This is an array of nested objects
                        if description:
                            lines.append(f"{indent}{field_name}: {description}")
                        else:
                            lines.append(f"{indent}{field_name}:")
                        nested_schema = definitions[ref_name]
                        if "properties" in nested_schema:
                            nested_lines = format_properties(nested_schema["properties"], indent_level + 1)
                            lines.extend(nested_lines)
                        continue

            # Regular field with description
            if description:
                lines.append(f"{indent}{field_name}: {description}")
            else:
                # No description - just show field name with colon
                lines.append(f"{indent}{field_name}:")

        return lines

    if "properties" not in schema:
        return ""

    lines = format_properties(schema["properties"])
    return "\n".join(lines)
