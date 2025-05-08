from typing import Any, Optional

from pydantic import BaseModel

from core.domain.models import Model
from core.domain.tool import Tool


class ProviderOptions(BaseModel):
    model: Model
    output_schema: dict[str, Any] | None = None
    task_name: str | None = None
    temperature: float = 0
    max_tokens: Optional[int] = None
    structured_generation: bool = False
    timeout: Optional[float] = 180
    enabled_tools: list[Tool] | None = None
    tenant: str | None = None
    stream_deltas: bool = False
