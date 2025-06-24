from typing import Any

from fastmcp.tools.tool import default_serializer
from pydantic import BaseModel


def tool_serializer(value: Any) -> str:
    if isinstance(value, BaseModel):
        return value.model_dump_json(indent=2, exclude_none=True)
    return default_serializer(value)
