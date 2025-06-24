import logging
import pickle
import uuid

from core.utils.redis_cache import shared_redis_client

from ._mcp_obersavilibity_session_state import SessionState

_logger = logging.getLogger(__name__)

# Session expiration time: 1 hour
SESSION_EXPIRY_SECONDS = 60 * 60  # 1 hour


class MCPRedisSessionStorage:
    """Redis-based session storage for MCP observability with 1-hour TTL"""

    def __init__(self):
        self._redis_client = shared_redis_client
        self._key_prefix = "mcp_session:"

    def _session_key(self, session_id: str) -> str:
        """Generate Redis key for session"""
        return f"{self._key_prefix}{session_id}"

    async def get_session(self, session_id: str) -> SessionState | None:
        """Retrieve session from Redis or return None if not found"""
        if not self._redis_client:
            _logger.warning("Redis client not available for session retrieval")
            return None

        try:
            session_data = await self._redis_client.get(self._session_key(session_id))
            if not session_data:
                return None

            # Deserialize session state
            session_dict = pickle.loads(session_data)  # pyright: ignore [reportUnknownArgumentType]
            return SessionState.from_dict(session_dict)

        except Exception as e:
            _logger.exception(
                "Failed to retrieve session from Redis",
                extra={"session_id": session_id, "error": str(e)},
            )
            return None

    async def create_session(self, user_agent: str, requested_session_id: str | None = None) -> SessionState:
        """Create a new session with optional requested session ID"""
        # If requested session ID is provided, try to use it, otherwise generate new
        session_id = requested_session_id or str(uuid.uuid4())

        # Create new session state
        session_state = SessionState(session_id, user_agent)

        # Store in Redis
        await self.store_session(session_state)

        _logger.info(
            "New MCP session created",
            extra={
                "mcp_event": "session_created",
                "session_id": session_id,
                "user_agent": user_agent,
                "requested_session_id": requested_session_id,
                "session_created_at": session_state.created_at,
            },
        )

        return session_state

    async def store_session(self, session_state: SessionState) -> bool:
        """Store session state in Redis with TTL"""
        if not self._redis_client:
            _logger.warning("Redis client not available for session storage")
            return False

        try:
            # Serialize session state to dict then pickle
            session_dict = session_state.to_dict()
            session_data = pickle.dumps(session_dict)

            # Store with TTL
            await self._redis_client.setex(  # pyright: ignore [reportUnknownMemberType]
                self._session_key(session_state.session_id),
                SESSION_EXPIRY_SECONDS,
                session_data,
            )
            return True

        except Exception as e:
            _logger.exception(
                "Failed to store session in Redis",
                extra={"session_id": session_state.session_id, "error": str(e)},
            )
            return False

    async def update_session(self, session_state: SessionState) -> bool:
        """Update existing session in Redis (extends TTL)"""
        return await self.store_session(session_state)

    async def delete_session(self, session_id: str) -> bool:
        """Delete session from Redis"""
        if not self._redis_client:
            _logger.warning("Redis client not available for session deletion")
            return False

        try:
            result = await self._redis_client.delete(self._session_key(session_id))  # pyright: ignore [reportUnknownMemberType]
            return int(result) > 0  # pyright: ignore [reportUnknownArgumentType]
        except Exception as e:
            _logger.exception(
                "Failed to delete session from Redis",
                extra={"session_id": session_id, "error": str(e)},
            )
            return False

    async def get_or_create_session(self, session_id: str | None, user_agent: str) -> SessionState:
        """Get existing session or create new one based on session_id"""
        if session_id:
            # Try to retrieve existing session
            existing_session = await self.get_session(session_id)
            if existing_session:
                # Update last activity and store back
                existing_session.update_last_activity()
                await self.update_session(existing_session)
                return existing_session
            _logger.info(
                "Session ID provided but not found in Redis, creating new session",
                extra={"requested_session_id": session_id, "user_agent": user_agent},
            )

        # Create new session (with or without requested session ID)
        return await self.create_session(user_agent, session_id)

    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions (optional since Redis TTL handles this automatically)
        Returns number of sessions cleaned up
        """
        # With Redis TTL, this is mostly for logging/monitoring purposes
        # Redis will automatically expire sessions after 1 hour
        if not self._redis_client:
            return 0

        try:
            # Get all session keys
            pattern = f"{self._key_prefix}*"
            keys = await self._redis_client.keys(pattern)  # pyright: ignore [reportUnknownMemberType]

            # Count active sessions for monitoring
            active_count = len(keys)
            _logger.info(
                "MCP session cleanup check",
                extra={
                    "mcp_event": "session_cleanup",
                    "active_sessions": active_count,
                    "cleanup_method": "redis_ttl_automatic",
                },
            )

            return 0  # Redis handles cleanup automatically

        except Exception as e:
            _logger.exception("Failed to check session count during cleanup", extra={"error": str(e)})
            return 0

    def is_available(self) -> bool:
        """Check if Redis client is available"""
        return self._redis_client is not None
