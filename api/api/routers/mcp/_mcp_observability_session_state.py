import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel

from core.domain.tenant_data import TenantData
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


class SessionState:
    """Redis-backed session state for MCP sessions"""

    def __init__(
        self,
        session_id: str,
        tenant: TenantData,
        created_at: datetime = datetime.now(timezone.utc),
        last_activity: datetime = datetime.now(timezone.utc),
        tool_calls: list[dict[str, Any]] | None = None,
    ):
        self.session_id = session_id
        self.tenant: TenantData = tenant
        self.created_at = created_at
        self.last_activity = last_activity
        self.tool_calls: list[dict[str, Any]] = tool_calls if tool_calls is not None else []

    @classmethod
    def _get_redis_key(cls, tenant: TenantData, session_id: str) -> str:
        """Get the Redis key for this session"""
        return f"mcp_session:{tenant.tenant}:{session_id}"

    async def save(self) -> None:
        """Save session state to Redis"""
        if not shared_redis_client:
            logger.warning("Redis client not available, cannot save session state")
            return

        try:
            session_data = {
                "session_id": self.session_id,
                "created_at": self.created_at.isoformat(),
                "last_activity": self.last_activity.isoformat(),
                "tool_calls": self.tool_calls,
            }

            await shared_redis_client.setex(
                self._get_redis_key(self.tenant, self.session_id),
                SESSION_EXPIRATION_SECONDS,
                json.dumps(session_data),
            )

            logger.debug(
                "Session saved to Redis",
                extra={
                    "session_id": self.session_id,
                    "tool_calls_count": len(self.tool_calls),
                },
            )
        except Exception as e:
            logger.error(
                "Failed to save session to Redis",
                extra={
                    "session_id": self.session_id,
                    "error": str(e),
                },
            )

    @classmethod
    async def load(cls, session_id: str, tenant: TenantData) -> Optional["SessionState"]:
        """Load session state from Redis"""
        if not shared_redis_client:
            logger.warning("Redis client not available, cannot load session state")
            return None

        try:
            redis_key = cls._get_redis_key(tenant, session_id)
            session_data_str = await shared_redis_client.get(redis_key)

            if not session_data_str:
                logger.debug(
                    "Session not found in Redis",
                    extra={"session_id": session_id},
                )
                return None

            session_data = json.loads(session_data_str.decode())

            # Reconstruct session state
            session_data["created_at"] = datetime.fromisoformat(session_data["created_at"])
            session_data["last_activity"] = datetime.fromisoformat(session_data["last_activity"])
            session = SessionState(
                session_id=session_data["session_id"],
                tenant=tenant,
                created_at=session_data["created_at"],
                last_activity=session_data["last_activity"],
                tool_calls=session_data["tool_calls"],
            )

            logger.debug(
                "Session loaded from Redis",
                extra={
                    "session_id": session_id,
                    "tool_calls_count": len(session.tool_calls),
                    "created_at": session.created_at,
                },
            )

            return session

        except Exception as e:
            logger.error(
                "Failed to load session from Redis",
                extra={
                    "session_id": session_id,
                    "error": str(e),
                },
            )
            return None

    @classmethod
    async def get_or_create(cls, session_id: str | None, tenant: TenantData) -> tuple["SessionState", bool]:
        """
        Get existing session or create a new one.

        Returns:
            tuple: (SessionState, is_new_session)
        """
        # If no session ID provided or session doesn't exist, create new one
        if session_id:
            if found_session := await cls.load(session_id, tenant):
                # Update last activity and extend expiration
                found_session.last_activity = datetime.now(timezone.utc)
                await found_session.save()
                return found_session, False

            new_session = cls(session_id, tenant)
            await new_session.save()
            return new_session, True

        # Create new session
        new_session_id = str(uuid.uuid4())
        new_session = cls(new_session_id, tenant)
        await new_session.save()

        logger.info(
            "New MCP session created",
            extra={
                "mcp_event": "session_created",
                "session_id": new_session_id,
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
