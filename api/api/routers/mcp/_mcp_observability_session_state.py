import time
from typing import Any


class SessionState:
    """State tracking for MCP sessions"""

    def __init__(self, session_id: str, user_agent: str):
        self.session_id = session_id
        self.user_agent = user_agent
        self.created_at = time.time()
        self.last_activity = time.time()
        self.total_requests = 0
        self.tool_calls: list[dict[str, Any]] = []
        self._pending_tool_calls: dict[str, dict[str, Any]] = {}
        self._completed_tool_calls: list[dict[str, Any]] = []
        self._conversation_turns: list[dict[str, Any]] = []

    def add_tool_call(self, tool_name: str, tool_arguments: dict[str, Any], request_id: str) -> None:
        """Add a new tool call to the session"""
        self.last_activity = time.time()
        self.total_requests += 1

        tool_call = {
            "request_id": request_id,
            "tool_name": tool_name,
            "tool_arguments": tool_arguments,
            "started_at": time.time(),
        }

        self.tool_calls.append(tool_call)
        self._pending_tool_calls[request_id] = tool_call

    def complete_tool_call(
        self,
        request_id: str,
        duration: float,
        success: bool,
        result: Any,
        error_info: dict[str, Any] | None,
    ) -> None:
        """Mark a tool call as completed"""
        self.last_activity = time.time()

        if request_id in self._pending_tool_calls:
            tool_call = self._pending_tool_calls.pop(request_id)
            tool_call.update(
                {
                    "completed_at": time.time(),
                    "duration": duration,
                    "success": success,
                    "result": result,
                    "error_info": error_info,
                }
            )
            self._completed_tool_calls.append(tool_call)

    def add_conversation_turn(
        self,
        request_id: str,
        tool_name: str,
        tool_arguments: dict[str, Any],
        result: Any,
    ) -> None:
        """Add a conversation turn to the session"""
        self.last_activity = time.time()

        turn = {
            "request_id": request_id,
            "tool_name": tool_name,
            "tool_arguments": tool_arguments,
            "result": result,
            "timestamp": time.time(),
        }

        self._conversation_turns.append(turn)

    def get_session_summary(self) -> dict[str, Any]:
        """Get a summary of the session"""
        return {
            "session_id": self.session_id,
            "user_agent": self.user_agent,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "duration": self.last_activity - self.created_at,
            "total_requests": self.total_requests,
            "total_tool_calls": len(self.tool_calls),
            "completed_tool_calls": len(self._completed_tool_calls),
            "pending_tool_calls": len(self._pending_tool_calls),
            "conversation_turns": len(self._conversation_turns),
            "success_rate": (
                len([tc for tc in self._completed_tool_calls if tc.get("success", False)])
                / len(self._completed_tool_calls)
                if self._completed_tool_calls
                else 0
            ),
        }
