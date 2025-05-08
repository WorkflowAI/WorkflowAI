import json
from typing import Any

from core.domain.errors import JSONSchemaValidationError
from core.utils.dicts import InvalidKeyPathError, set_at_keypath_str
from core.utils.streams import JSONStreamError, JSONStreamParser


def parse_tolerant_json(json_str: str) -> dict[str, Any]:
    raw: dict[str, Any] = {}
    parser = JSONStreamParser(is_tolerant=True)
    try:
        if updates := parser.process_chunk(json_str):
            for update in updates:
                set_at_keypath_str(raw, *update)
    except (JSONStreamError, InvalidKeyPathError, KeyError, json.JSONDecodeError) as e:
        raise JSONSchemaValidationError("JSON was not reparable", json_str=json_str) from e

    # Sometimes the tolerant mode can ignore the entire JSON string
    # For example with `{meal_plan": "hello"}`
    # This is a failsafe to make sure we don't return an empty JSON object
    if json_str and not raw:
        raise JSONSchemaValidationError("Repaired JSON was empty", json_str=json_str)

    return raw


# TODO: deprecate and remove. It only handles dictionary
def extract_json_str(input_text: str) -> str:
    first_paren = input_text.find("{")
    last_paren = input_text.rfind("}")

    if first_paren == -1 or last_paren == -1:
        raise ValueError("Could not find JSON object in input text")

    return input_text[first_paren : last_paren + 1]


def safe_extract_dict_from_json(o: Any) -> dict[str, Any] | None:
    if isinstance(o, dict):
        return {str(k): v for k, v in o.items()}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    try:
        d = json.loads(o)
        if isinstance(d, dict):
            return {str(k): v for k, v in d.items()}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
        return None
    except (json.JSONDecodeError, TypeError):
        return None
