import json
import logging
from dataclasses import dataclass, field
from typing import Any

from datamodel_code_generator import DataModelType, PythonVersion
from datamodel_code_generator.model import get_data_model_types
from datamodel_code_generator.parser.jsonschema import JsonSchemaParser

from core.domain.integration.integration_domain import Integration, IntegrationKind
from core.domain.integration.integration_templates import get_templates_for_integration
from core.domain.message import Message
from core.domain.tool import Tool
from core.tools import ToolKind
from core.utils.templates import TemplateManager


@dataclass
class FieldInfo:
    type: str
    description: str | None = None


@dataclass
class CodeComponents:
    """Holds all the data needed to render code components for any integration"""

    # Integration metadata
    integration_kind: str = ""

    # Model and API configuration
    model: str = ""
    messages: str = ""
    base_url: str = "https://run.workflowai.com/v1"  # Default WorkflowAI URL

    # Structured output
    is_structured: bool = False
    class_name: str = ""
    schema_name: str = ""  # For TypeScript
    fields: dict[str, FieldInfo] = field(default_factory=dict)

    # DSPy-specific fields
    input_fields: dict[str, FieldInfo] = field(default_factory=dict)
    output_fields: dict[str, FieldInfo] = field(default_factory=dict)
    input_example: dict[str, Any] = field(default_factory=dict)
    signature_description: str = ""

    # Method and format (integration-specific)
    method: str = ""  # "chat.completions.create", "beta.chat.completions.parse"
    response_format: str = ""  # Class name, zodResponseFormat call, or JSON schema
    response_format_name: str = ""  # For TypeScript zodResponseFormat
    response_model: str = ""  # For Instructor

    # Input handling
    has_input_variables: bool = False
    extra_body: str = ""  # Python/TS input format
    input_data: str = ""  # curl input format

    # Tools support
    has_tools: bool = False
    tools_definitions: str = ""  # Tool definitions code
    tools_parameter: str = ""  # Tools parameter for API calls

    # Import requirements
    structured_imports: str = ""
    typing_imports: str = ""

    # Generated class definitions for nested schemas
    class_definitions: str = ""

    # Language-specific formatting
    language: str = "python"  # "python", "typescript", "bash"


class IntegrationTemplateService:
    def __init__(self, base_url: str = "https://run.workflowai.com/v1"):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.template_manager = TemplateManager()
        self.base_url = base_url

    def _get_integration_kind_from_integration(self, integration: Integration) -> str:
        """Map Integration object to template integration kind"""
        integration_map = {
            IntegrationKind.OPENAI_SDK_PYTHON: "openai-sdk-python",
            IntegrationKind.OPENAI_SDK_TS: "openai-sdk-ts",
            IntegrationKind.INSTRUCTOR_PYTHON: "instructor-python",
            IntegrationKind.DSPY_PYTHON: "dspy-python",
            IntegrationKind.LANGCHAIN_PYTHON: "langchain-python",
            IntegrationKind.LITELLM_PYTHON: "litellm-python",
            IntegrationKind.CURL: "curl",
        }
        return integration_map.get(integration.slug, "openai-sdk-python")

    def _generate_python_classes_from_schema(  # noqa: C901
        self,
        output_schema: dict[str, Any],
    ) -> tuple[str, str, dict[str, FieldInfo], tuple[list[str], list[str]]]:
        """Generate Python Pydantic classes from JSON schema using JsonSchemaParser"""
        try:
            # Prepare the schema for datamodel-code-generator
            schema_copy = output_schema.copy()
            class_name = schema_copy.get("title", "OutputData")

            # Ensure the schema has a title for proper class naming
            schema_copy["title"] = class_name

            # Configure the parser
            data_model_types = get_data_model_types(
                DataModelType.PydanticV2BaseModel,
                target_python_version=PythonVersion.PY_312,
            )

            parser = JsonSchemaParser(
                json.dumps(schema_copy),
                data_model_type=data_model_types.data_model,
                data_model_root_type=data_model_types.root_model,
                data_model_field_type=data_model_types.field_model,
                data_type_manager_type=data_model_types.data_type_manager,
                dump_resolve_reference_action=data_model_types.dump_resolve_reference_action,
                field_constraints=False,  # Disable to avoid extra='forbid' in model_config
            )

            generated_code = parser.parse()
            if not isinstance(generated_code, str):
                raise ValueError("Expected a string from parser")

            # Clean up the generated code
            generated_code = generated_code.replace("..., ", "")
            generated_code = generated_code.replace("...,\n", "")

            # Remove model_config lines that add extra='forbid'
            lines = generated_code.split("\n")
            filtered_lines: list[str] = []
            skip_model_config = False

            for line in lines:
                if line.strip().startswith("model_config = ConfigDict("):
                    skip_model_config = True
                    continue
                if skip_model_config and line.strip() == ")":
                    skip_model_config = False
                    continue
                if skip_model_config:
                    # Skip lines inside model_config block
                    continue
                filtered_lines.append(line)

            generated_code = "\n".join(filtered_lines)

            # Extract class definitions and imports
            lines = generated_code.split("\n")
            regular_imports: list[str] = []
            class_lines: list[str] = []
            in_class = False

            for line in lines:
                if line.startswith("from __future__"):
                    # Skip future imports - we don't need them for this use case
                    continue
                if line.startswith("from ") or line.startswith("import "):
                    regular_imports.append(line)
                elif line.startswith("class ") or in_class:
                    class_lines.append(line)
                    in_class = True
                    if not line.strip() and len(class_lines) > 1:
                        # End of class definition
                        in_class = False

            # Only include class lines in class_definitions, not imports
            class_definitions = "\n".join(class_lines).strip()

            # Update the extraction for template compatibility
            imports = regular_imports

            # Extract imports and clean them up
            pydantic_imports: list[str] = []
            typing_imports: list[str] = []

            for imp in imports:
                if "pydantic" in imp:
                    # Extract just the specific imports from pydantic
                    if "from pydantic import" in imp:
                        parts = imp.split("from pydantic import", 1)
                        if len(parts) == 2:
                            imports_part = parts[1].strip()
                            pydantic_imports.extend([i.strip() for i in imports_part.split(",")])
                elif "typing" in imp:
                    # Extract just the specific imports from typing
                    if "from typing import" in imp:
                        parts = imp.split("from typing import", 1)
                        if len(parts) == 2:
                            imports_part = parts[1].strip()
                            typing_imports.extend([i.strip() for i in imports_part.split(",")])

            # Remove duplicates while preserving order
            pydantic_imports = list(dict.fromkeys(pydantic_imports))
            typing_imports = list(dict.fromkeys(typing_imports))

            # Extract fields from the main class for template compatibility
            fields = self._extract_fields_from_generated_class(generated_code, class_name)

            return class_name, class_definitions, fields, (pydantic_imports, typing_imports)

        except Exception:
            self._logger.warning(
                "Failed to generate classes with JsonSchemaParser, falling back to simple parsing",
                exc_info=True,
            )
            # Fallback to the original simple method
            return self._parse_schema_for_structured_output_simple(output_schema, "python")

    def _extract_fields_from_generated_class(self, generated_code: str, class_name: str) -> dict[str, FieldInfo]:
        """Extract field information from generated Pydantic class for template compatibility"""
        fields: dict[str, FieldInfo] = {}
        lines = generated_code.split("\n")
        in_target_class = False

        for line in lines:
            if line.strip().startswith(f"class {class_name}("):
                in_target_class = True
                continue
            if in_target_class and line.strip().startswith("class "):
                # Started a new class, we're done with our target class
                break
            if in_target_class and ":" in line and not line.strip().startswith("class"):
                # This looks like a field definition
                parts = line.split(":", 1)
                if len(parts) == 2:
                    field_name = parts[0].strip()
                    field_type_part = parts[1].strip()

                    # Extract the type (before =, if any)
                    if "=" in field_type_part:
                        field_type = field_type_part.split("=")[0].strip()
                    else:
                        field_type = field_type_part

                    fields[field_name] = FieldInfo(type=field_type)

        return fields

    def _generate_typescript_types_from_schema(
        self,
        output_schema: dict[str, Any],
    ) -> tuple[str, str, dict[str, FieldInfo]]:
        """Generate TypeScript types/Zod schemas from JSON schema"""
        class_name = output_schema.get("title", "OutputData")

        # Generate Zod schema for runtime validation
        zod_schema = self._build_zod_schema(output_schema, class_name)

        # Extract fields for template compatibility
        fields: dict[str, FieldInfo] = {}
        properties = output_schema.get("properties", {})
        for field_name, field_def in properties.items():
            ts_type = self._get_typescript_type_from_schema_advanced(field_def)
            description = field_def.get("description")
            fields[field_name] = FieldInfo(type=ts_type, description=description)

        # Return the Zod schema as the class definitions since that's what we use for runtime validation
        return class_name, zod_schema, fields

    def _build_typescript_interface(self, schema: dict[str, Any], class_name: str) -> str:
        """Build TypeScript interface definition"""
        lines: list[str] = [f"interface {class_name} {{"]

        properties = schema.get("properties", {})
        required = schema.get("required", [])

        for field_name, field_def in properties.items():
            ts_type = self._get_typescript_type_from_schema_advanced(field_def)
            optional = "" if field_name in required else "?"
            description = field_def.get("description", "")

            if description:
                lines.append(f"  /** {description} */")
            lines.append(f"  {field_name}{optional}: {ts_type};")

        lines.append("}")
        return "\n".join(lines)

    def _build_zod_schema(self, schema: dict[str, Any], class_name: str) -> str:
        """Build Zod schema definition for TypeScript runtime validation"""
        lines: list[str] = [f"const {class_name}Schema = z.object({{"]

        properties = schema.get("properties", {})
        required = schema.get("required", [])

        for field_name, field_def in properties.items():
            zod_type = self._get_zod_type_from_schema(field_def)
            description = field_def.get("description", "")

            # Add optional() if not required
            if field_name not in required:
                zod_type += ".optional()"

            # Add description if available
            if description:
                zod_type += f'.describe("{description}")'

            # Handle multi-line nested objects properly
            if "\n" in zod_type:
                # For nested objects, indent properly
                indented_zod_type = zod_type.replace("\n", "\n  ")
                lines.append(f"  {field_name}: {indented_zod_type},")
            else:
                lines.append(f"  {field_name}: {zod_type},")

        lines.append("});")
        lines.append(f"type {class_name} = z.infer<typeof {class_name}Schema>;")
        return "\n".join(lines)

    def _get_typescript_type_from_schema_advanced(self, field_def: dict[str, Any]) -> str:
        """Convert JSON schema field definition to TypeScript type with nested object support"""
        field_type = field_def.get("type", "string")

        if field_type == "string":
            enum_values = field_def.get("enum")
            if enum_values:
                quoted_values = [f'"{val}"' for val in enum_values]
                return " | ".join(quoted_values)
            return "string"
        if field_type == "integer" or field_type == "number":
            return "number"
        if field_type == "boolean":
            return "boolean"
        if field_type == "array":
            items = field_def.get("items", {})
            item_type = self._get_typescript_type_from_schema_advanced(items)
            return f"{item_type}[]"
        if field_type == "object":
            # Handle nested objects
            properties = field_def.get("properties", {})
            if properties:
                nested_fields: list[str] = []
                required = field_def.get("required", [])
                for prop_name, prop_def in properties.items():
                    prop_type = self._get_typescript_type_from_schema_advanced(prop_def)
                    optional = "" if prop_name in required else "?"
                    nested_fields.append(f"{prop_name}{optional}: {prop_type}")
                return "{ " + "; ".join(nested_fields) + " }"
            return "Record<string, any>"
        return "any"

    # TODO: let the frontend generated Zod classes ?
    def _get_zod_type_from_schema(self, field_def: dict[str, Any]) -> str:  # noqa: C901
        """Convert JSON schema field definition to Zod type with nested object support"""
        field_type = field_def.get("type", "string")

        if field_type == "string":
            enum_values = field_def.get("enum")
            if enum_values:
                quoted_values = [f'"{val}"' for val in enum_values]
                return f"z.enum([{', '.join(quoted_values)}])"
            return "z.string()"
        if field_type == "integer":
            return "z.number().int()"
        if field_type == "number":
            return "z.number()"
        if field_type == "boolean":
            return "z.boolean()"
        if field_type == "array":
            items = field_def.get("items", {})
            item_type = self._get_zod_type_from_schema(items)
            return f"z.array({item_type})"
        if field_type == "object":
            # Handle nested objects with proper formatting
            properties = field_def.get("properties", {})
            if properties:
                nested_fields: list[str] = []
                required = field_def.get("required", [])
                for prop_name, prop_def in properties.items():
                    prop_type = self._get_zod_type_from_schema(prop_def)
                    description = prop_def.get("description", "")

                    if prop_name not in required:
                        prop_type += ".optional()"

                    if description:
                        prop_type += f'.describe("{description}")'

                    nested_fields.append(f"    {prop_name}: {prop_type}")

                return "z.object({\n" + ",\n".join(nested_fields) + "\n  })"
            return "z.record(z.any())"
        return "z.any()"

    def _parse_schema_for_structured_output_simple(
        self,
        output_schema: dict[str, Any],
        language: str = "python",
    ) -> tuple[str, str, dict[str, FieldInfo], tuple[list[str], list[str]]]:
        """Fallback simple schema parsing (original implementation)"""
        class_name = output_schema.get("title", "OutputData")
        properties = output_schema.get("properties", {})
        fields: dict[str, FieldInfo] = {}
        pydantic_imports: list[str] = []
        typing_imports: list[str] = []

        type_getter = (
            self._get_python_type_from_schema_simple
            if language == "python"
            else self._get_typescript_type_from_schema_simple
        )

        for field_name, field_def in properties.items():
            field_type = type_getter(field_def)
            description = field_def.get("description")
            fields[field_name] = FieldInfo(type=field_type, description=description)

            # Language-specific import detection
            if language == "python":
                if field_type.startswith("Literal"):
                    if "Literal" not in typing_imports:
                        typing_imports.append("Literal")
                elif "List[" in field_type:
                    if "List" not in typing_imports:
                        typing_imports.append("List")
                if description and "Field" not in pydantic_imports:
                    pydantic_imports.append("Field")

        # Generate simple class definition
        class_def = self._generate_simple_class_definition(class_name, fields, language)

        return class_name, class_def, fields, (pydantic_imports, typing_imports)

    def _generate_simple_class_definition(self, class_name: str, fields: dict[str, FieldInfo], language: str) -> str:
        """Generate a simple class definition from fields"""
        if language == "python":
            lines = [f"class {class_name}(BaseModel):"]
            for field_name, field_info in fields.items():
                if field_info.description:
                    lines.append(f'    {field_name}: {field_info.type} = Field(description="{field_info.description}")')
                else:
                    lines.append(f"    {field_name}: {field_info.type}")
            return "\n".join(lines)
        # TypeScript - return Zod schema
        lines = [f"const {class_name}Schema = z.object({{"]
        for field_name, field_info in fields.items():
            lines.append(f"  {field_name}: {field_info.type},")
        lines.append("});")
        lines.append(f"type {class_name} = z.infer<typeof {class_name}Schema>;")
        return "\n".join(lines)

    def _get_python_type_from_schema_simple(self, field_def: dict[str, Any]) -> str:
        """Convert JSON schema field definition to Python type annotation (simple fallback)"""
        field_type = field_def.get("type", "str")

        if field_type == "string":
            enum_values = field_def.get("enum")
            if enum_values:
                quoted_values = [f'"{val}"' for val in enum_values]
                return f"Literal[{', '.join(quoted_values)}]"
            return "str"
        if field_type == "integer":
            return "int"
        if field_type == "number":
            return "float"
        if field_type == "boolean":
            return "bool"
        if field_type == "array":
            items = field_def.get("items", {})
            item_type = self._get_python_type_from_schema_simple(items)
            return f"List[{item_type}]"
        if field_type == "object":
            return "dict"  # Fallback for simple case
        return "str"

    def _get_typescript_type_from_schema_simple(self, field_def: dict[str, Any]) -> str:
        """Convert JSON schema field definition to TypeScript/Zod type (simple fallback)"""
        field_type = field_def.get("type", "string")

        if field_type == "string":
            enum_values = field_def.get("enum")
            if enum_values:
                quoted_values = [f'"{val}"' for val in enum_values]
                return f"z.enum([{', '.join(quoted_values)}])"
            return "z.string()"
        if field_type == "integer":
            return "z.number().int()"
        if field_type == "number":
            return "z.number()"
        if field_type == "boolean":
            return "z.boolean()"
        if field_type == "array":
            items = field_def.get("items", {})
            item_type = self._get_typescript_type_from_schema_simple(items)
            return f"z.array({item_type})"
        if field_type == "object":
            return "z.object({})"  # Fallback for simple case
        return "z.string()"

    def _parse_schema_for_structured_output(
        self,
        output_schema: dict[str, Any],
        language: str = "python",
    ) -> tuple[str, dict[str, FieldInfo], tuple[list[str], list[str]]]:
        """Parse JSON schema to extract class name, fields, and imports needed - enhanced version"""
        if language == "python":
            class_name, _class_definitions, fields, imports = self._generate_python_classes_from_schema(output_schema)
            return class_name, fields, imports
        class_name, _class_definitions, fields = self._generate_typescript_types_from_schema(output_schema)
        # For TypeScript, return empty imports since they're handled differently
        return class_name, fields, ([], [])

    def _get_python_type_from_schema(self, field_def: dict[str, Any]) -> str:
        """Convert JSON schema field definition to Python type annotation"""
        field_type = field_def.get("type", "str")

        if field_type == "string":
            enum_values = field_def.get("enum")
            if enum_values:
                quoted_values = [f'"{val}"' for val in enum_values]
                return f"Literal[{', '.join(quoted_values)}]"
            return "str"
        if field_type == "integer":
            return "int"
        if field_type == "number":
            return "float"
        if field_type == "boolean":
            return "bool"
        if field_type == "array":
            items = field_def.get("items", {})
            item_type = self._get_python_type_from_schema(items)
            return f"List[{item_type}]"
        if field_type == "object":
            return "dict"
        return "str"

    def _get_typescript_type_from_schema(self, field_def: dict[str, Any]) -> str:
        """Convert JSON schema field definition to TypeScript/Zod type"""
        field_type = field_def.get("type", "string")

        if field_type == "string":
            enum_values = field_def.get("enum")
            if enum_values:
                quoted_values = [f'"{val}"' for val in enum_values]
                return f"z.enum([{', '.join(quoted_values)}])"
            return "z.string()"
        if field_type == "integer":
            return "z.number().int()"
        if field_type == "number":
            return "z.number()"
        if field_type == "boolean":
            return "z.boolean()"
        if field_type == "array":
            items = field_def.get("items", {})
            item_type = self._get_typescript_type_from_schema(items)
            return f"z.array({item_type})"
        if field_type == "object":
            return "z.object({})"
        return "z.string()"

    def _parse_schema_for_dspy_signature(  # noqa: C901
        self,
        input_schema: dict[str, Any] | None,
        output_schema: dict[str, Any] | None,
    ) -> tuple[dict[str, FieldInfo], dict[str, FieldInfo], list[str], dict[str, Any]]:
        """Parse schemas for DSPy signature creation"""
        input_fields: dict[str, FieldInfo] = {}
        output_fields: dict[str, FieldInfo] = {}
        imports: list[str] = []
        input_example: dict[str, Any] = {}

        # Process input schema
        if input_schema:
            properties = input_schema.get("properties", {})
            for field_name, field_def in properties.items():
                field_type = self._get_python_type_from_schema(field_def)
                description = field_def.get("description")
                input_fields[field_name] = FieldInfo(type=field_type, description=description)

                # Create example value
                if field_def.get("examples"):
                    input_example[field_name] = f'"{field_def["examples"][0]}"'
                elif field_type == "str":
                    input_example[field_name] = f'"example_{field_name}"'
                elif field_type == "int":
                    input_example[field_name] = 42
                elif field_type == "bool":
                    input_example[field_name] = True
                else:
                    input_example[field_name] = f'"example_{field_name}"'

                if field_type.startswith("Literal"):
                    if "Literal" not in imports:
                        imports.append("Literal")

        # Process output schema
        if output_schema:
            properties = output_schema.get("properties", {})
            for field_name, field_def in properties.items():
                field_type = self._get_python_type_from_schema(field_def)
                description = field_def.get("description")
                output_fields[field_name] = FieldInfo(type=field_type, description=description)

                if field_type.startswith("Literal"):
                    if "Literal" not in imports:
                        imports.append("Literal")

        return input_fields, output_fields, imports, input_example

    def _create_input_example(self, input_schema: dict[str, Any], format_type: str = "python") -> str:  # noqa: C901
        """Create an example input dictionary based on the input schema"""
        properties = input_schema.get("properties", {})
        example: dict[str, Any] = {}

        for field_name, field_def in properties.items():
            field_type = field_def.get("type", "string")
            examples = field_def.get("examples", [])

            if examples:
                example[field_name] = examples[0]
            elif field_type == "string":
                example[field_name] = f"example_{field_name}"
            elif field_type == "integer":
                example[field_name] = 42
            elif field_type == "number":
                example[field_name] = 3.14
            elif field_type == "boolean":
                example[field_name] = True
            elif field_type == "array":
                example[field_name] = ["example_item"]
            else:
                example[field_name] = f"example_{field_name}"

        if format_type == "python":
            # For Python, manually format to ensure proper Python literals (True vs true)
            lines: list[str] = []
            for key, value in example.items():
                key_str = str(key)
                if isinstance(value, bool):
                    formatted_value = "True" if value else "False"
                elif isinstance(value, str):
                    formatted_value = f'"{value}"'
                else:
                    formatted_value = str(value)
                lines.append(f'        "{key_str}": {formatted_value}')
            return "{\n" + ",\n".join(lines) + "\n        }"
        if format_type == "typescript":
            return json.dumps(example, indent=2)
        # curl
        return json.dumps(example)

    def _create_json_schema_for_curl(self, output_schema: dict[str, Any]) -> str:
        """Create JSON schema format for curl response_format"""
        schema_obj = {
            "type": "json_schema",
            "json_schema": {
                "name": output_schema.get("title", "OutputData"),
                "schema": output_schema,
            },
        }
        return json.dumps(schema_obj, indent=4)

    def _format_tools_for_integration(  # noqa: C901
        self,
        enabled_tools: list[ToolKind | Tool],
        integration_kind: str,
        is_using_structured_generation: bool = False,
    ) -> tuple[str, str]:
        """Format tools for the specific integration type"""
        if not enabled_tools:
            return "", ""

        if integration_kind == "openai-sdk-python":
            # OpenAI Python format
            tools_list: list[str] = []
            for tool in enabled_tools:
                if isinstance(tool, Tool):
                    tool_def: dict[str, Any] = {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or "",
                            "parameters": tool.input_schema,
                        },
                    }
                    # Always add additionalProperties: false for strict schema compliance
                    if "parameters" in tool_def["function"] and isinstance(
                        tool_def["function"]["parameters"],
                        dict,
                    ):
                        tool_def["function"]["parameters"]["additionalProperties"] = False

                        # For strict mode, all properties must be required
                        if is_using_structured_generation:
                            properties = tool_def["function"]["parameters"].get("properties", {})
                            if properties:
                                tool_def["function"]["parameters"]["required"] = list(properties.keys())

                    # Add strict mode when using structured output with beta.chat.completions.parse
                    if is_using_structured_generation:
                        tool_def["function"]["strict"] = True
                    # Convert to JSON and fix Python boolean syntax
                    tool_json = json.dumps(tool_def, indent=4)
                    tool_json = tool_json.replace('"strict": true', '"strict": True')
                    tool_json = tool_json.replace('"additionalProperties": false', '"additionalProperties": False')
                    tools_list.append(tool_json)
                else:  # ToolKind
                    # For ToolKind, we need to map to the actual tool definition
                    # For now, we'll create a placeholder - in a real implementation,
                    # you'd want to get the actual tool definition from the tool registry
                    tool_def = {
                        "type": "function",
                        "function": {
                            "name": tool.value.replace("@", ""),
                            "description": f"WorkflowAI hosted tool: {tool.value}",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    }
                    # Always add additionalProperties: false for strict schema compliance
                    if "parameters" in tool_def["function"] and isinstance(
                        tool_def["function"]["parameters"],
                        dict,
                    ):
                        tool_def["function"]["parameters"]["additionalProperties"] = False

                        # For strict mode, all properties must be required
                        if is_using_structured_generation:
                            properties = tool_def["function"]["parameters"].get("properties", {})
                            if properties:
                                tool_def["function"]["parameters"]["required"] = list(properties.keys())

                    # Add strict mode when using structured output with beta.chat.completions.parse
                    if is_using_structured_generation:
                        tool_def["function"]["strict"] = True
                    # Convert to JSON and fix Python boolean syntax
                    tool_json = json.dumps(tool_def, indent=4)
                    tool_json = tool_json.replace('"strict": true', '"strict": True')
                    tool_json = tool_json.replace('"additionalProperties": false', '"additionalProperties": False')
                    tools_list.append(tool_json)

            tools_definitions = "tools = [\n" + ",\n".join(f"    {tool_str}" for tool_str in tools_list) + "\n]"
            tools_parameter = "tools=tools"
            return tools_definitions, tools_parameter

        if integration_kind == "openai-sdk-ts":
            # TypeScript format
            ts_tools_list: list[str] = []
            for tool in enabled_tools:
                if isinstance(tool, Tool):
                    tool_def: dict[str, Any] = {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or "",
                            "parameters": tool.input_schema,
                        },
                    }
                    # Always add additionalProperties: false for strict schema compliance
                    if "parameters" in tool_def["function"] and isinstance(tool_def["function"]["parameters"], dict):
                        tool_def["function"]["parameters"]["additionalProperties"] = False
                    ts_tools_list.append(json.dumps(tool_def, indent=2))
                else:  # ToolKind
                    tool_def = {
                        "type": "function",
                        "function": {
                            "name": tool.value.replace("@", ""),
                            "description": f"WorkflowAI hosted tool: {tool.value}",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    }
                    # Always add additionalProperties: false for strict schema compliance
                    if "parameters" in tool_def["function"] and isinstance(tool_def["function"]["parameters"], dict):
                        tool_def["function"]["parameters"]["additionalProperties"] = False
                    ts_tools_list.append(json.dumps(tool_def, indent=2))

            tools_definitions = "const tools = [\n" + ",\n".join(f"  {tool_str}" for tool_str in ts_tools_list) + "\n];"
            tools_parameter = "tools: tools"
            return tools_definitions, tools_parameter

        if integration_kind == "instructor-python":
            # Instructor doesn't have separate tools parameter, tools are handled via response_model
            return "", ""

        if integration_kind == "curl":
            # curl format
            curl_tools_list: list[dict[str, Any]] = []
            for tool in enabled_tools:
                if isinstance(tool, Tool):
                    tool_def: dict[str, Any] = {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or "",
                            "parameters": tool.input_schema,
                        },
                    }
                    # Always add additionalProperties: false for strict schema compliance
                    if "parameters" in tool_def["function"] and isinstance(tool_def["function"]["parameters"], dict):
                        tool_def["function"]["parameters"]["additionalProperties"] = False
                    curl_tools_list.append(tool_def)
                else:  # ToolKind
                    tool_def = {
                        "type": "function",
                        "function": {
                            "name": tool.value.replace("@", ""),
                            "description": f"WorkflowAI hosted tool: {tool.value}",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    }
                    # Always add additionalProperties: false for strict schema compliance
                    if "parameters" in tool_def["function"] and isinstance(tool_def["function"]["parameters"], dict):
                        tool_def["function"]["parameters"]["additionalProperties"] = False
                    curl_tools_list.append(tool_def)

            tools_parameter = f'"tools": {json.dumps(curl_tools_list, indent=4)}'
            return "", tools_parameter

        if integration_kind in ["dspy-python", "langchain-python", "litellm-python"]:
            # These frameworks typically handle tools differently
            # For now, we'll format them similarly to OpenAI Python
            framework_tools_list: list[str] = []
            for tool in enabled_tools:
                if isinstance(tool, Tool):
                    tool_def = {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or "",
                            "parameters": tool.input_schema,
                        },
                    }
                    # Always add additionalProperties: false for strict schema compliance
                    if "parameters" in tool_def["function"] and isinstance(tool_def["function"]["parameters"], dict):
                        tool_def["function"]["parameters"]["additionalProperties"] = False
                    # Convert to JSON and fix Python boolean syntax
                    tool_json = json.dumps(tool_def, indent=4)
                    tool_json = tool_json.replace('"additionalProperties": false', '"additionalProperties": False')
                    framework_tools_list.append(tool_json)

                # elif hosted tools

            tools_definitions = (
                "tools = [\n" + ",\n".join(f"    {tool_str}" for tool_str in framework_tools_list) + "\n]"
            )
            tools_parameter = "tools=tools"
            return tools_definitions, tools_parameter

        return "", ""

    def _to_codeblock_messages(self, message: Message) -> str:
        deprecated_message = message.to_deprecated()
        payload: dict[str, Any] = {"role": deprecated_message.role.value, "content": deprecated_message.content}
        if deprecated_message.files:
            payload["files"] = [f.model_dump(exclude_none=True) for f in deprecated_message.files]
        if deprecated_message.tool_call_requests:
            payload["tool_call_requests"] = [
                t.model_dump(exclude_none=True) for t in deprecated_message.tool_call_requests
            ]
        if deprecated_message.tool_call_results:
            payload["tool_call_results"] = [
                t.model_dump(exclude_none=True) for t in deprecated_message.tool_call_results
            ]
        return json.dumps(payload, indent=2)

    def _build_code_components(  # noqa: C901
        self,
        integration: Integration,
        agent_id: str,
        agent_schema_id: int,
        model_used: str,
        version_messages: list[Message],
        version_deployment_environment: str | None = None,
        is_using_instruction_variables: bool = False,
        input_schema: dict[str, Any] | None = None,
        is_using_structured_generation: bool = False,
        output_schema: dict[str, Any] | None = None,
        enabled_tools: list[ToolKind | Tool] | None = None,
        input_variables: dict[str, Any] | None = None,
    ) -> CodeComponents:
        """Build all components needed for code generation"""
        integration_kind = self._get_integration_kind_from_integration(integration)

        components = CodeComponents(
            integration_kind=integration_kind,
            base_url=self.base_url,
        )

        # Set language
        if integration_kind in ["openai-sdk-ts"]:
            components.language = "typescript"
        elif integration_kind == "curl":
            components.language = "bash"
        else:
            components.language = "python"

        # Build model reference
        if version_deployment_environment:
            components.model = f"{agent_id}/#{agent_schema_id}/{version_deployment_environment}"
            components.messages = ""  # Empty for deployments
        else:
            components.model = f"{agent_id}/{model_used}"
            components.messages = (
                "["
                + ",".join(
                    [self._to_codeblock_messages(m) for m in version_messages],
                )
                + "]"
            )

        # Set method based on integration and structured output
        if integration_kind == "openai-sdk-python":
            components.method = (
                "beta.chat.completions.parse" if is_using_structured_generation else "chat.completions.create"
            )
        elif integration_kind == "openai-sdk-ts":
            components.method = (
                "beta.chat.completions.parse" if is_using_structured_generation else "chat.completions.create"
            )
        elif integration_kind == "instructor-python":
            components.method = "chat.completions.create"  # Instructor always uses create
        elif integration_kind in ["dspy-python", "langchain-python", "litellm-python"]:
            components.method = "generate"  # Generic method for these frameworks
        elif integration_kind == "curl":
            components.method = "POST"  # Not really used for curl

        # Handle tools
        if enabled_tools:
            components.has_tools = True
            tools_definitions, tools_parameter = self._format_tools_for_integration(
                enabled_tools,
                integration_kind,
                is_using_structured_generation,
            )
            components.tools_definitions = tools_definitions
            components.tools_parameter = tools_parameter

        # Handle structured output
        if is_using_structured_generation and output_schema:
            if integration_kind == "dspy-python":
                # DSPy handles structured output via signatures
                input_fields, output_fields, dspy_imports, input_example = self._parse_schema_for_dspy_signature(
                    input_schema,
                    output_schema,
                )
                components.input_fields = input_fields
                components.output_fields = output_fields
                components.input_example = input_example
                components.structured_imports = ", ".join(dspy_imports)
                components.signature_description = (
                    f"Process input and generate {output_schema.get('title', 'OutputData')} output"
                )
                components.class_name = output_schema.get("title", "OutputData")
                components.is_structured = True

                # Create JSON schema for response_format if needed
                response_format_obj = {
                    "type": "json_schema",
                    "json_schema": {"name": components.class_name, "schema": output_schema},
                }
                components.response_format = json.dumps(response_format_obj)
            else:
                # Use enhanced schema parsing for other integrations
                if components.language == "python":
                    class_name, class_definitions, fields, _ = self._generate_python_classes_from_schema(output_schema)

                    # Import handling is now done dynamically via _analyze_and_inject_imports
                    components.class_definitions = class_definitions
                else:
                    # TypeScript
                    class_name, class_definitions, fields = self._generate_typescript_types_from_schema(output_schema)
                    components.class_definitions = class_definitions

                components.class_name = class_name
                components.schema_name = class_name  # For TypeScript
                components.fields = fields
                components.is_structured = True

                # Set integration-specific response format
                if integration_kind == "openai-sdk-python":
                    components.response_format = class_name
                elif integration_kind == "openai-sdk-ts":
                    components.response_format = class_name + "Schema"
                    components.response_format_name = class_name.lower() + "_response"
                elif integration_kind == "instructor-python":
                    components.response_model = class_name
                elif integration_kind in ["langchain-python", "litellm-python"]:
                    components.response_format = class_name
                elif integration_kind == "curl":
                    components.response_format = self._create_json_schema_for_curl(output_schema)

        # Handle input variables
        if is_using_instruction_variables:
            components.has_input_variables = True

            if input_variables:
                # Use the input variables passed in the request, if present
                components.extra_body = json.dumps(input_variables, indent=2)
            else:
                if input_schema:
                    # If no input variables are passed, use the input schema to create an example input variable
                    components.extra_body = self._create_input_example(
                        input_schema,
                        "python" if integration_kind != "openai-sdk-ts" else "typescript",
                    )
                else:
                    components.extra_body = json.dumps({"example_field": "example_value"}, indent=2)

            components.input_data = components.extra_body

        return components

    async def _render_component(self, template: str, data: dict[str, Any]) -> str:
        """Render a single template component"""
        rendered, _ = await self.template_manager.render_template(template, data)
        return rendered

    async def generate_code(  # noqa: C901
        self,
        integration: Integration,
        agent_id: str,
        agent_schema_id: int,
        model_used: str,
        version_messages: list[Message],
        version_deployment_environment: str | None = None,
        is_using_instruction_variables: bool = False,
        input_schema: dict[str, Any] | None = None,
        is_using_structured_generation: bool = False,
        output_schema: dict[str, Any] | None = None,
        enabled_tools: list[ToolKind | Tool] | None = None,
        input_variables: dict[str, Any] | None = None,
    ) -> str:
        """Generate code for any supported integration using component templates"""

        try:
            integration_kind = self._get_integration_kind_from_integration(integration)
            templates = get_templates_for_integration(integration_kind)

            if not templates:
                raise ValueError(f"No templates found for integration kind: {integration_kind}")

            # Build all component data
            components = self._build_code_components(
                integration=integration,
                agent_id=agent_id,
                agent_schema_id=agent_schema_id,
                model_used=model_used,
                version_messages=version_messages,
                version_deployment_environment=version_deployment_environment,
                is_using_instruction_variables=is_using_instruction_variables,
                input_schema=input_schema,
                is_using_structured_generation=is_using_structured_generation,
                output_schema=output_schema,
                enabled_tools=enabled_tools,
                input_variables=input_variables,
            )

            # Convert components to template data
            template_data = {
                "model": components.model,
                "messages": components.messages,
                "method": components.method,
                "is_structured": components.is_structured,
                "class_name": components.class_name,
                "schema_name": components.schema_name,
                "fields": components.fields,
                "response_format": components.response_format,
                "response_format_name": components.response_format_name,
                "response_model": components.response_model,
                "structured_imports": components.structured_imports,
                "typing_imports": components.typing_imports,
                "class_definitions": components.class_definitions,
                "extra_body": components.extra_body,
                "input_data": components.input_data,
                "base_url": components.base_url,
                # Input variables support
                "has_input_variables": components.has_input_variables,
                # Tools support
                "has_tools": components.has_tools,
                "tools_definitions": components.tools_definitions,
                "tools_parameter": components.tools_parameter,
                # DSPy-specific data
                "input_fields": components.input_fields,
                "output_fields": components.output_fields,
                "input_example": components.input_example,
                "signature_description": components.signature_description,
            }

            # Handle curl differently (single template)
            if integration_kind == "curl":
                import json

                json_body_dict: dict[str, Any] = {"model": components.model}
                # Parse messages if present
                if components.messages:
                    if isinstance(components.messages, list):
                        json_body_dict["messages"] = [
                            m.model_dump() if isinstance(m, Message) else m for m in components.messages
                        ]
                    else:
                        try:
                            json_body_dict["messages"] = json.loads(components.messages)
                        except Exception:
                            json_body_dict["messages"] = components.messages
                else:
                    json_body_dict["messages"] = []
                if components.response_format:
                    try:
                        json_body_dict["response_format"] = json.loads(components.response_format)
                    except Exception:
                        json_body_dict["response_format"] = components.response_format
                if components.has_tools and components.tools_parameter:
                    # tools_parameter is like '"tools": ...'
                    try:
                        # Try to parse as JSON
                        key, value = components.tools_parameter.split(":", 1)
                        key = key.strip().strip('"')
                        value = value.strip()
                        json_body_dict[key] = json.loads(value)
                    except Exception:
                        pass
                if components.input_data:
                    try:
                        json_body_dict["input"] = json.loads(components.input_data)
                    except Exception:
                        json_body_dict["input"] = components.input_data
                template_data["json_body"] = json.dumps(json_body_dict, indent=2)
                request = await self._render_component(templates["request"], template_data)
                return f"```bash\n{request}\n```"

            # Handle other integrations (multi-component)
            code_parts: list[str] = []

            # Note: Future imports are no longer needed since we skip them during generation

            # Imports
            if "imports" in templates:
                imports = await self._render_component(templates["imports"], template_data)
                code_parts.append(imports)

            # For LangChain, we need the class definition before client setup
            # because the client setup references the class name
            if integration_kind == "langchain-python" and components.is_structured:
                if components.class_definitions:
                    # Use generated class definitions directly if available
                    code_parts.append(components.class_definitions)
                elif "structured_class" in templates:
                    class_definition = await self._render_component(templates["structured_class"], template_data)
                    code_parts.append(class_definition)

            # Client setup
            if "client_setup" in templates:
                client_setup = await self._render_component(templates["client_setup"], template_data)
                code_parts.append(client_setup)

            # Tools definitions
            if components.has_tools and "tools_definitions" in templates:
                tools_def = await self._render_component(templates["tools_definitions"], template_data)
                code_parts.append(tools_def)
            elif components.has_tools and components.tools_definitions:
                # Fallback: add tools definitions directly if no specific template
                code_parts.append(components.tools_definitions)

            # Structured output class/schema/signature (for non-LangChain integrations)
            if components.is_structured and integration_kind != "langchain-python":
                if "structured_class" in templates:
                    # Use template for rendering the class definitions
                    class_definition = await self._render_component(templates["structured_class"], template_data)
                    code_parts.append(class_definition)
                elif "structured_schema" in templates:
                    schema_definition = await self._render_component(templates["structured_schema"], template_data)
                    code_parts.append(schema_definition)
                elif "structured_signature" in templates:
                    signature_definition = await self._render_component(
                        templates["structured_signature"],
                        template_data,
                    )
                    code_parts.append(signature_definition)
                elif components.class_definitions:
                    # Fallback: use the generated class definitions directly if no specific template
                    code_parts.append(components.class_definitions)

            # Response call
            if "response_call" in templates:
                response_call = await self._render_component(templates["response_call"], template_data)
                code_parts.append(response_call)

            # Output handling
            if "output_handling" in templates:
                output_handling = await self._render_component(templates["output_handling"], template_data)
                code_parts.append(output_handling)

            # Combine all parts
            full_code = "\n".join(code_parts)

            # Analyze and inject required imports for Python integrations
            if components.language == "python":
                full_code = self._analyze_and_inject_imports(full_code, integration_kind)

            # Wrap in appropriate code block
            if components.language == "typescript":
                return f"```typescript\n{full_code}\n```"
            return f"```python\n{full_code}\n```"

        except Exception as e:
            self._logger.exception("Failed to generate code using templates", exc_info=e)
            raise

    def supports_integration(self, integration: Integration) -> bool:
        """Check if template generation is supported for this integration"""
        supported_integrations = {
            IntegrationKind.OPENAI_SDK_PYTHON,
            IntegrationKind.OPENAI_SDK_TS,
            IntegrationKind.INSTRUCTOR_PYTHON,
            IntegrationKind.DSPY_PYTHON,
            IntegrationKind.LANGCHAIN_PYTHON,
            IntegrationKind.LITELLM_PYTHON,
            IntegrationKind.CURL,
        }
        return integration.slug in supported_integrations

    def _analyze_and_inject_imports(self, code: str, integration_kind: str) -> str:  # noqa: C901
        """Analyze generated code and inject required imports at the top"""
        lines = code.split("\n")

        # Find where imports end (last import line or first non-import/non-empty line)
        import_end_index = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not (
                stripped.startswith("import ") or stripped.startswith("from ") or stripped.startswith("#")
            ):
                import_end_index = i
                break

        # Analyze code to determine needed imports
        needed_pydantic_imports: list[str] = []
        needed_typing_imports: list[str] = []
        needed_enum_imports: list[str] = []

        full_code = "\n".join(lines)

        # Check for Pydantic imports needed
        if "BaseModel" in full_code:
            needed_pydantic_imports.append("BaseModel")
        if "Field(" in full_code:
            needed_pydantic_imports.append("Field")
        if "ConfigDict" in full_code:
            needed_pydantic_imports.append("ConfigDict")
        if "confloat" in full_code:
            needed_pydantic_imports.append("confloat")
        if "conint" in full_code:
            needed_pydantic_imports.append("conint")
        if "constr" in full_code:
            needed_pydantic_imports.append("constr")
        if "validator" in full_code:
            needed_pydantic_imports.append("validator")
        if "root_validator" in full_code:
            needed_pydantic_imports.append("root_validator")
        if "AwareDatetime" in full_code:
            needed_pydantic_imports.append("AwareDatetime")
        if "NaiveDatetime" in full_code:
            needed_pydantic_imports.append("NaiveDatetime")
        if "PositiveInt" in full_code:
            needed_pydantic_imports.append("PositiveInt")
        if "PositiveFloat" in full_code:
            needed_pydantic_imports.append("PositiveFloat")
        if "NonNegativeInt" in full_code:
            needed_pydantic_imports.append("NonNegativeInt")
        if "NonNegativeFloat" in full_code:
            needed_pydantic_imports.append("NonNegativeFloat")

        # Check for typing imports needed
        if "List[" in full_code:
            needed_typing_imports.append("List")
        if "Optional[" in full_code:
            needed_typing_imports.append("Optional")
        if "Union[" in full_code:
            needed_typing_imports.append("Union")
        if "Literal[" in full_code:
            needed_typing_imports.append("Literal")
        if "Dict[" in full_code:
            needed_typing_imports.append("Dict")
        if "Any" in full_code and "dict[str, Any]" in full_code:
            needed_typing_imports.append("Any")

        # Check for enum imports needed
        if "Enum)" in full_code or ("class " in full_code and "(Enum)" in full_code):
            needed_enum_imports.append("Enum")

        # Build import lines
        new_import_lines: list[str] = []

        if needed_typing_imports:
            typing_imports = ", ".join(sorted(set(needed_typing_imports)))
            new_import_lines.append(f"from typing import {typing_imports}")

        if needed_enum_imports:
            enum_imports = ", ".join(sorted(set(needed_enum_imports)))
            new_import_lines.append(f"from enum import {enum_imports}")

        if needed_pydantic_imports:
            pydantic_imports = ", ".join(sorted(set(needed_pydantic_imports)))
            new_import_lines.append(f"from pydantic import {pydantic_imports}")

        # Insert the new imports
        if new_import_lines:
            lines[import_end_index:import_end_index] = new_import_lines + [""]

        return "\n".join(lines)
