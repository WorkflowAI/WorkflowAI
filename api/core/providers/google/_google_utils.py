from copy import deepcopy
from typing import Any

from core.utils.hash import compute_obj_hash
from core.utils.strings import slugify


def get_google_json_schema_name(task_name: str | None, schema: dict[str, Any]) -> str:
    """Return a unique schema name truncated to 60 characters using the task name and schema hash."""
    # We want to limit the length of the schema name to 60 characters for consistency with OpenAI
    # We keep a buffer of 4 character.
    MAX_SCHEMA_NAME_CHARACTERS_LENGTH = 60

    # We don't know for sure what are the inner workings of the feature at Google,
    # but passing a schema_name which is unique to the schema appeared safer, hence the hash.
    hash_str = compute_obj_hash(schema)
    snake_case_name = slugify(task_name).replace("-", "_") if task_name else ""
    # Reserve 32 chars for hash and 1 for underscore
    max_name_length = MAX_SCHEMA_NAME_CHARACTERS_LENGTH - len(hash_str) - 1
    if len(snake_case_name) > max_name_length:
        snake_case_name = snake_case_name[:max_name_length]
    return f"{snake_case_name}_{hash_str}" if snake_case_name else hash_str


def prepare_google_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize and prepare a JSON schema for Google/Gemini structured output.
    
    Based on browser-use implementation and Google's schema requirements.
    Google has different schema requirements than OpenAI:
    - Doesn't support $ref - need to resolve references inline
    - Doesn't support some properties like 'additionalProperties', 'title', 'default'
    - Doesn't allow empty OBJECT types - need to add placeholder properties
    """
    schema = deepcopy(schema)
    
    # First resolve $ref references since Google doesn't support them
    schema = _resolve_refs(schema)
    
    # Then clean the schema by removing unsupported properties
    schema = _clean_schema(schema)
    
    return schema


def _resolve_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Resolve $ref references in the schema since Google doesn't support them.
    This recursively replaces $ref with the actual definition.
    """
    if not isinstance(schema, dict):
        return schema
        
    # Extract definitions if they exist
    defs = schema.get("$defs", {})
    
    def resolve_refs_recursive(obj: Any) -> Any:
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref = obj["$ref"]
                # Extract the reference name (e.g., "#/$defs/MyType" -> "MyType")
                ref_name = ref.split("/")[-1]
                if ref_name in defs:
                    # Replace the $ref with the actual definition
                    resolved = deepcopy(defs[ref_name])
                    return resolve_refs_recursive(resolved)
                else:
                    # If reference not found, remove the $ref
                    return {k: resolve_refs_recursive(v) for k, v in obj.items() if k != "$ref"}
            else:
                return {k: resolve_refs_recursive(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [resolve_refs_recursive(item) for item in obj]
        else:
            return obj
    
    resolved_schema = resolve_refs_recursive(schema)
    
    # Remove $defs since we've resolved all references
    if "$defs" in resolved_schema:
        del resolved_schema["$defs"]
    
    return resolved_schema


def _clean_schema(obj: Any) -> Any:
    """
    Clean the schema by removing properties that Google doesn't support.
    """
    if isinstance(obj, dict):
        cleaned = {}
        for key, value in obj.items():
            # Remove properties that Google rejects
            if key not in ['additionalProperties', 'title', 'default']:
                cleaned[key] = _clean_schema(value)
        
        # Handle empty OBJECT types - Google doesn't allow empty objects
        if (cleaned.get('type', '').upper() == 'OBJECT' 
            and 'properties' in cleaned 
            and isinstance(cleaned['properties'], dict)
            and len(cleaned['properties']) == 0):
            cleaned['properties'] = {'_placeholder': {'type': 'string'}}
        
        return cleaned
    elif isinstance(obj, list):
        return [_clean_schema(item) for item in obj]
    else:
        return obj