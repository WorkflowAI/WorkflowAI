THIS SHOULD BE A LINTER ERRORimport json
import logging
import uuid
import time
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel

from core.utils.redis_cache import shared_redis_client

logger = logging.getLogger(__name__)

# Session expiration time in seconds (1 hour)
SESSION_EXPIRATION_SECONDS = 60 * 60


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


class SessionState:
    """Redis-backed session state for MCP sessions"""
    
    def __init__(self, session_id: str, user_agent: str):
        self.session_id = session_id
        self.user_agent = user_agent
        self.created_at = datetime.now(timezone.utc)
        self.last_activity = datetime.now(timezone.utc)
        self.tool_calls: list[dict[str, Any]] = []

    def _get_redis_key(self) -> str:
        """Get the Redis key for this session"""
        return f"mcp_session:{self.session_id}"

    async def save(self) -> None:
        """Save session state to Redis"""
        if not shared_redis_client:
            logger.warning("Redis client not available, cannot save session state")
            return
            
        try:
            session_data = {
                "session_id": self.session_id,
                "user_agent": self.user_agent,
                "created_at": self.created_at.isoformat(),
                "last_activity": self.last_activity.isoformat(),
                "tool_calls": self.tool_calls,
            }
            
            await shared_redis_client.setex(
                self._get_redis_key(),
                SESSION_EXPIRATION_SECONDS,
                json.dumps(session_data)
            )
            
            logger.debug(
                "Session saved to Redis",
                extra={
                    "session_id": self.session_id,
                    "tool_calls_count": len(self.tool_calls),
                }
            )
        except Exception as e:
            logger.error(
                "Failed to save session to Redis",
                extra={
                    "session_id": self.session_id,
                    "error": str(e),
                }
            )

    @classmethod
    async def load(cls, session_id: str) -> Optional["SessionState"]:
        """Load session state from Redis"""
        if not shared_redis_client:
            logger.warning("Redis client not available, cannot load session state")
            return None
            
        try:
            redis_key = f"mcp_session:{session_id}"
            session_data_str = await shared_redis_client.get(redis_key)
            
            if not session_data_str:
                logger.debug(
                    "Session not found in Redis",
                    extra={"session_id": session_id}
                )
                return None
                
            session_data = json.loads(session_data_str.decode())
            
            # Reconstruct session state
            session = cls.__new__(cls)
            session.session_id = session_data["session_id"]
            session.user_agent = session_data["user_agent"]
            session.created_at = datetime.fromisoformat(session_data["created_at"])
            session.last_activity = datetime.fromisoformat(session_data["last_activity"])
            session.tool_calls = session_data["tool_calls"]
            
            logger.debug(
                "Session loaded from Redis",
                extra={
                    "session_id": session_id,
                    "tool_calls_count": len(session.tool_calls),
                    "created_at": session.created_at,
                }
            )
            
            return session
            
        except Exception as e:
            logger.error(
                "Failed to load session from Redis",
                extra={
                    "session_id": session_id,
                    "error": str(e),
                }
            )
            return None

    @classmethod
    async def get_or_create(cls, session_id: str | None, user_agent: str) -> tuple["SessionState", bool]:
        """
        Get existing session or create a new one.
        
        Returns:
            tuple: (SessionState, is_new_session)
        """
        # If no session ID provided or session doesn't exist, create new one
        if session_id:
            existing_session = await cls.load(session_id)
            if existing_session:
                # Update last activity and extend expiration
                existing_session.last_activity = datetime.now(timezone.utc)
                await existing_session.save()
                return existing_session, False
        
        # Create new session
        new_session_id = str(uuid.uuid4())
        new_session = cls(new_session_id, user_agent)
        await new_session.save()
        
        logger.info(
            "New MCP session created",
            extra={
                "mcp_event": "session_created",
                "session_id": new_session_id,
                "user_agent": user_agent,
                "session_created_at": new_session.created_at,
                "replaced_session_id": session_id,
            },
        )
        
        return new_session, True

    async def register_tool_call(self, tool_call_data: ToolCallData) -> None:
        """Add a completed tool call to the session history and save to Redis"""
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
        self.last_activity = datetime.now(timezone.utc)
        
        # Save updated session state to Redis
        await self.save()

    async def delete(self) -> None:
        """Delete session from Redis"""
        if not shared_redis_client:
            logger.warning("Redis client not available, cannot delete session")
            return
            
        try:
            await shared_redis_client.delete(self._get_redis_key())
            logger.debug(
                "Session deleted from Redis",
                extra={"session_id": self.session_id}
            )
        except Exception as e:
            logger.error(
                "Failed to delete session from Redis",
                extra={
                    "session_id": self.session_id,
                    "error": str(e),
                }
            )
