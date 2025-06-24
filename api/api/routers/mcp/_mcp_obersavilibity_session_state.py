import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


# Session state tracking
class SessionState:
    def __init__(self, session_id: str, user_agent: str):
        self.session_id = session_id
        self.user_agent = user_agent
        self.created_at = time.time()
        self.last_activity = time.time()
        self.tool_calls: list[dict[str, Any]] = []
        self.conversation_context: list[dict[str, Any]] = []
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_duration = 0.0

    def update_last_activity(self):
        """Update the last activity timestamp"""
        self.last_activity = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Serialize session state to dictionary for Redis storage"""
        return {
            "session_id": self.session_id,
            "user_agent": self.user_agent,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "tool_calls": self.tool_calls,
            "conversation_context": self.conversation_context,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "total_duration": self.total_duration,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionState":
        """Deserialize session state from dictionary retrieved from Redis"""
        session = cls(data["session_id"], data["user_agent"])
        session.created_at = data["created_at"]
        session.last_activity = data["last_activity"]
        session.tool_calls = data.get("tool_calls", [])
        session.conversation_context = data.get("conversation_context", [])
        session.total_requests = data.get("total_requests", 0)
        session.successful_requests = data.get("successful_requests", 0)
        session.failed_requests = data.get("failed_requests", 0)
        session.total_duration = data.get("total_duration", 0.0)
        return session

    def add_tool_call(self, tool_name: str, tool_arguments: dict[str, Any], request_id: str):
        """Add a tool call to the session history"""
        self.tool_calls.append(
            {
                "tool_name": tool_name,
                "tool_arguments": tool_arguments,
                "request_id": request_id,
                "timestamp": time.time(),
                "status": "started",
            },
        )
        self.total_requests += 1
        self.last_activity = time.time()

    def complete_tool_call(
        self,
        request_id: str,
        duration: float,
        success: bool,
        result: Any = None,
        error_info: dict[str, Any] | None = None,
    ):
        """Mark a tool call as completed and store the result and error information

        Args:
            request_id: The ID of the request to mark as completed
            duration: How long the tool call took in seconds
            success: Whether the tool call was successful
            result: The result of the tool call (will always be stored, even if None)
            error_info: Error information if the call failed
        """
        for call in reversed(self.tool_calls):  # Search from most recent
            if call["request_id"] == request_id:
                call["status"] = "completed" if success else "failed"
                call["duration"] = duration
                call["completed_at"] = time.time()

                # Always store the result (even if None, as that could be a valid result)
                call["result"] = result

                if not success:
                    # For failed calls, always store error information
                    if error_info:
                        call["error"] = error_info
                    else:
                        # Provide default error info if none was provided
                        call["error"] = {
                            "type": "unknown_error",
                            "message": "Tool call failed without specific error details",
                            "timestamp": time.time(),
                        }
                break

        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

        self.total_duration += duration
        self.last_activity = time.time()

    def add_conversation_turn(self, request_id: str, tool_name: str, tool_arguments: dict[str, Any], result: Any):
        """Add a conversation turn for context tracking"""
        self.conversation_context.append(
            {
                "request_id": request_id,
                "tool_name": tool_name,
                "tool_arguments": tool_arguments,
                "result": result,
                "timestamp": time.time(),
            },
        )

        # Keep only last 10 conversation turns to prevent memory bloat
        if len(self.conversation_context) > 10:
            self.conversation_context = self.conversation_context[-10:]

    def get_failed_tool_calls(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent failed tool calls for debugging"""
        failed_calls = [call for call in self.tool_calls if call.get("status") == "failed"]
        return failed_calls[-limit:] if limit else failed_calls

    def get_error_summary(self) -> dict[str, Any]:
        """Get a summary of errors that occurred in this session"""
        failed_calls = self.get_failed_tool_calls()

        # Group errors by type
        error_types: dict[str, int] = {}
        error_messages: list[str] = []

        for call in failed_calls:
            error = call.get("error", {})
            error_type = error.get("type", "unknown_error")
            error_types[error_type] = error_types.get(error_type, 0) + 1

            error_message = error.get("message", "No error message")
            if error_message not in error_messages:
                error_messages.append(error_message)

        return {
            "total_failures": len(failed_calls),
            "error_types": error_types,
            "unique_error_messages": error_messages[:5],  # Limit to 5 most recent unique messages
            "recent_failed_tools": [call["tool_name"] for call in failed_calls[-5:]],
        }

    def get_session_summary(self) -> dict[str, Any]:
        """Get a summary of the session state including error information"""
        error_summary = self.get_error_summary()

        return {
            "session_id": self.session_id,
            "user_agent": self.user_agent,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "session_duration": self.last_activity - self.created_at,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": self.successful_requests / max(self.total_requests, 1),
            "total_duration": self.total_duration,
            "avg_request_duration": self.total_duration / max(self.total_requests, 1),
            "conversation_turns": len(self.conversation_context),
            "recent_tools": [call["tool_name"] for call in self.tool_calls[-5:]],  # Last 5 tools
            "error_summary": error_summary,
        }
