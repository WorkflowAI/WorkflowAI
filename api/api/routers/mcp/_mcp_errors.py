import json
from collections.abc import Callable, Coroutine
from typing import Any

from core.utils.generics import BM


class MCPError(Exception):
    def __init__(self, message: str, data: Any | None = None):
        super().__init__(message)
        self.message = message
        self.data = data

    def __str__(self):
        base = self.message
        if self.data:
            base += f"\n\nExtra data: \n{json.dumps(self.data, indent=2)}"
        return base


async def mcp_wrap(
    coro: Coroutine[Any, Any, BM],
    message: Callable[[BM], str | None] | None = None,
):
    """Wraps a coroutine to return a MCPToolReturn and handle MCPError"""
    # TODO: fix circular import
    from api.routers.mcp._mcp_models import MCPToolReturn

    try:
        value = await coro
    except MCPError as e:
        return MCPToolReturn[BM](
            success=False,
            error=str(e),
        )
    return MCPToolReturn(
        success=True,
        data=value,
        message=message(value) if message else None,
    )
