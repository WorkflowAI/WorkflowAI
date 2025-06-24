# pyright: reportPrivateUsage=false
from unittest.mock import AsyncMock

import pytest

from ._mcp_obersavilibity_session_state import SessionState
from ._mcp_redis_session_storage import MCPRedisSessionStorage


class TestMCPRedisSessionStorage:
    @pytest.fixture
    def redis_storage(self):
        """Create a session storage instance with mocked Redis client"""
        storage = MCPRedisSessionStorage()
        storage._redis_client = AsyncMock()
        return storage

    @pytest.fixture
    def sample_session_state(self):
        """Create a sample session state for testing"""
        session = SessionState("test-session-id", "test-user-agent")
        session.add_tool_call("test_tool", {"arg1": "value1"}, "req-123")
        session.complete_tool_call("req-123", 1.5, True, {"result": "success"})
        return session

    async def test_get_session_returns_none_when_not_found(self, redis_storage):
        """Test that get_session returns None when session is not found"""
        redis_storage._redis_client.get.return_value = None

        result = await redis_storage.get_session("nonexistent-session")

        assert result is None
        redis_storage._redis_client.get.assert_called_once_with("mcp_session:nonexistent-session")

    async def test_get_session_deserializes_existing_session(self, redis_storage, sample_session_state):
        """Test that get_session properly deserializes an existing session"""
        import pickle

        serialized_data = pickle.dumps(sample_session_state.to_dict())
        redis_storage._redis_client.get.return_value = serialized_data

        result = await redis_storage.get_session("test-session-id")

        assert result is not None
        assert result.session_id == "test-session-id"
        assert result.user_agent == "test-user-agent"
        assert result.total_requests == 1
        assert len(result.tool_calls) == 1

    async def test_create_session_with_new_id(self, redis_storage):
        """Test creating a new session without specifying session ID"""
        redis_storage._redis_client.setex = AsyncMock()

        result = await redis_storage.create_session("test-agent")

        assert result.user_agent == "test-agent"
        assert result.session_id is not None
        assert len(result.session_id) > 0  # Should have generated a UUID
        redis_storage._redis_client.setex.assert_called_once()

    async def test_create_session_with_requested_id(self, redis_storage):
        """Test creating a session with a requested session ID"""
        redis_storage._redis_client.setex = AsyncMock()
        requested_id = "requested-session-id"

        result = await redis_storage.create_session("test-agent", requested_id)

        assert result.session_id == requested_id
        assert result.user_agent == "test-agent"
        redis_storage._redis_client.setex.assert_called_once()

    async def test_store_session_serializes_and_stores(self, redis_storage, sample_session_state):
        """Test that store_session properly serializes and stores session data"""
        redis_storage._redis_client.setex = AsyncMock()

        result = await redis_storage.store_session(sample_session_state)

        assert result is True
        redis_storage._redis_client.setex.assert_called_once()

        # Verify the call arguments
        call_args = redis_storage._redis_client.setex.call_args
        assert call_args[0][0] == "mcp_session:test-session-id"  # key
        assert call_args[0][1] == 3600  # TTL (1 hour)
        # The third argument should be pickled data

    async def test_get_or_create_session_returns_existing(self, redis_storage, sample_session_state):
        """Test that get_or_create_session returns existing session when found"""
        import pickle

        serialized_data = pickle.dumps(sample_session_state.to_dict())
        redis_storage._redis_client.get.return_value = serialized_data
        redis_storage._redis_client.setex = AsyncMock()

        result = await redis_storage.get_or_create_session("test-session-id", "test-agent")

        assert result.session_id == "test-session-id"
        assert result.user_agent == "test-user-agent"  # From existing session
        redis_storage._redis_client.setex.assert_called_once()  # Should update the session

    async def test_get_or_create_session_creates_new_when_not_found(self, redis_storage):
        """Test that get_or_create_session creates new session when not found"""
        redis_storage._redis_client.get.return_value = None
        redis_storage._redis_client.setex = AsyncMock()

        result = await redis_storage.get_or_create_session("nonexistent-id", "test-agent")

        assert result.session_id == "nonexistent-id"  # Should use requested ID
        assert result.user_agent == "test-agent"
        redis_storage._redis_client.setex.assert_called_once()

    async def test_get_or_create_session_creates_new_without_id(self, redis_storage):
        """Test that get_or_create_session creates new session when no ID provided"""
        redis_storage._redis_client.setex = AsyncMock()

        result = await redis_storage.get_or_create_session(None, "test-agent")

        assert result.session_id is not None
        assert len(result.session_id) > 0  # Should generate UUID
        assert result.user_agent == "test-agent"
        redis_storage._redis_client.setex.assert_called_once()

    async def test_delete_session(self, redis_storage):
        """Test session deletion"""
        redis_storage._redis_client.delete.return_value = 1  # Indicates successful deletion

        result = await redis_storage.delete_session("test-session-id")

        assert result is True
        redis_storage._redis_client.delete.assert_called_once_with("mcp_session:test-session-id")

    async def test_cleanup_expired_sessions_logs_count(self, redis_storage):
        """Test that cleanup method logs active session count"""
        redis_storage._redis_client.keys.return_value = ["mcp_session:1", "mcp_session:2"]

        result = await redis_storage.cleanup_expired_sessions()

        assert result == 0  # Should return 0 since Redis handles cleanup automatically
        redis_storage._redis_client.keys.assert_called_once_with("mcp_session:*")

    async def test_is_available_when_redis_client_exists(self, redis_storage):
        """Test is_available returns True when Redis client exists"""
        assert redis_storage.is_available() is True

    def test_is_available_when_redis_client_none(self):
        """Test is_available returns False when Redis client is None"""
        storage = MCPRedisSessionStorage()
        storage._redis_client = None
        assert storage.is_available() is False

    async def test_graceful_degradation_when_redis_unavailable(self):
        """Test that methods handle Redis being unavailable gracefully"""
        storage = MCPRedisSessionStorage()
        storage._redis_client = None

        # Should return None when Redis is unavailable
        assert await storage.get_session("test-id") is None

        # Should return False when trying to store without Redis
        session = SessionState("test-id", "test-agent")
        assert await storage.store_session(session) is False

        # Should return False when trying to delete without Redis
        assert await storage.delete_session("test-id") is False

        # Should return 0 for cleanup when Redis unavailable
        assert await storage.cleanup_expired_sessions() == 0
