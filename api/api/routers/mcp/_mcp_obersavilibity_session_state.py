import logging
import time
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ToolCallData(BaseModel):
    """Data structure for a completed tool call"""

    tool_name: str
    tool_arguments: dict[str, Any]
    request_id: str
    duration: float
    result: str | None = None
    started_at: datetime
    completed_at: datetime
    user_agent: str


class ObserverAgentData(BaseModel):
    """Data structure for observer agent execution"""

    tool_name: str
    previous_tool_calls: list[dict[str, Any]]
    tool_arguments: dict[str, Any]
    tool_result: str
    duration_seconds: float
    user_agent: str
    mcp_session_id: str
    request_id: str
    organization_name: str | None = None
    user_email: str | None = None


# Session state tracking
class SessionState:
    def __init__(self, session_id: str, user_agent: str):
        now = datetime.now(timezone.utc)
        self.session_id = session_id
        self.created_at = now
        self.last_activity = now
        self.tool_calls: list[dict[str, Any]] = []

    def register_tool_call(self, tool_call_data: ToolCallData):
        """Add a completed tool call to the session history"""
        self.tool_calls.append(
            {
                "tool_name": tool_call_data.tool_name,
                "tool_arguments": tool_call_data.tool_arguments,
                "request_id": tool_call_data.request_id,
                "started_at": tool_call_data.started_at.isoformat(),
                "completed_at": tool_call_data.completed_at.isoformat(),
                "duration": tool_call_data.duration,
                "result": tool_call_data.result,
                "user_agent": tool_call_data.user_agent,
            },
        )
        self.last_activity = time.time()
