# pyright: reportPrivateUsage=false
# pyright: reportUnknownParameterType=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingParameterType=false
# pyright: reportUnknownArgumentType=false
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from api.routers.mcp._mcp_observability_session_state import (
    SESSION_EXPIRATION_SECONDS,
    ObserverAgentData,
    SessionState,
    ToolCallData,
)
from core.domain.tenant_data import TenantData


@pytest.fixture
def mock_tenant():
    return TenantData(
        tenant="test-tenant",
        slug="test-slug",
        name="Test Organization",
        org_id="test-org-id",
        owner_id="test-owner-id",
    )


@pytest.fixture
def sample_tool_call_data():
    return ToolCallData(
        tool_name="test_tool",
        tool_arguments={"arg1": "value1", "arg2": 42},
        request_id="req-123",
        duration=1.5,
        result="Tool execution successful",
        started_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2024, 1, 1, 12, 0, 1, tzinfo=timezone.utc),
        user_agent="test-agent/1.0",
    )


@pytest.fixture
def sample_observer_data():
    return ObserverAgentData(
        tool_name="test_tool",
        previous_tool_calls=[
            {
                "tool_name": "previous_tool",
                "tool_arguments": {"prev_arg": "prev_value"},
                "duration": 0.8,
                "result": "Previous result",
            },
        ],
        tool_arguments={"arg1": "value1"},
        tool_result="Tool result",
        duration_seconds=1.5,
        user_agent="test-agent/1.0",
        mcp_session_id="session-123",
        request_id="req-123",
        organization_name="Test Org",
        user_email="test@example.com",
    )


class TestToolCallData:
    def test_tool_call_data_creation(self, sample_tool_call_data):
        assert sample_tool_call_data.tool_name == "test_tool"
        assert sample_tool_call_data.tool_arguments == {"arg1": "value1", "arg2": 42}
        assert sample_tool_call_data.request_id == "req-123"
        assert sample_tool_call_data.duration == 1.5
        assert sample_tool_call_data.result == "Tool execution successful"
        assert sample_tool_call_data.user_agent == "test-agent/1.0"

    def test_tool_call_data_serialization(self, sample_tool_call_data):
        # Test that the model can be serialized to dict
        data_dict = sample_tool_call_data.model_dump()
        assert data_dict["tool_name"] == "test_tool"
        assert data_dict["duration"] == 1.5

    def test_tool_call_data_optional_result(self):
        tool_call = ToolCallData(
            tool_name="test_tool",
            tool_arguments={},
            request_id="req-456",
            duration=0.5,
            result=None,  # Test optional result
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            user_agent="test-agent",
        )
        assert tool_call.result is None


class TestObserverAgentData:
    def test_observer_agent_data_creation(self, sample_observer_data):
        assert sample_observer_data.tool_name == "test_tool"
        assert len(sample_observer_data.previous_tool_calls) == 1
        assert sample_observer_data.mcp_session_id == "session-123"
        assert sample_observer_data.organization_name == "Test Org"
        assert sample_observer_data.user_email == "test@example.com"

    def test_observer_agent_data_optional_fields(self):
        observer_data = ObserverAgentData(
            tool_name="test_tool",
            previous_tool_calls=[],
            tool_arguments={},
            tool_result="result",
            duration_seconds=1.0,
            user_agent="agent",
            mcp_session_id="session-id",
            request_id="req-id",
            # Optional fields not provided
        )
        assert observer_data.organization_name is None
        assert observer_data.user_email is None


class TestSessionState:
    def test_session_state_creation(self):
        session = SessionState("test-session-id")

        assert session.session_id == "test-session-id"
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.last_activity, datetime)
        assert session.tool_calls == []

    def test_get_redis_key(self, mock_tenant):
        redis_key = SessionState._get_redis_key(mock_tenant, "session-123")

        assert redis_key == "mcp_session:test-tenant:session-123"

    @pytest.mark.asyncio
    async def test_save_success(self, mock_tenant):
        session = SessionState("test-session")
        session.tool_calls = [{"tool_name": "test", "duration": 1.0}]

        with patch("api.routers.mcp._mcp_observability_session_state.shared_redis_client") as mock_redis:
            mock_redis.setex = AsyncMock()

            await session.save(mock_tenant)

            mock_redis.setex.assert_called_once()
            args = mock_redis.setex.call_args[0]

            # Check Redis key
            assert args[0] == "mcp_session:test-tenant:test-session"
            # Check expiration time
            assert args[1] == SESSION_EXPIRATION_SECONDS
            # Check data is JSON
            session_data = json.loads(args[2])
            assert session_data["session_id"] == "test-session"
            assert len(session_data["tool_calls"]) == 1

    @pytest.mark.asyncio
    async def test_save_no_redis_client(self, mock_tenant):
        session = SessionState("test-session")

        with patch("api.routers.mcp._mcp_observability_session_state.shared_redis_client", None):
            # Should not raise an exception
            await session.save(mock_tenant)

    @pytest.mark.asyncio
    async def test_save_redis_error(self, mock_tenant):
        session = SessionState("test-session")

        with (
            patch("api.routers.mcp._mcp_observability_session_state.shared_redis_client") as mock_redis,
            patch("api.routers.mcp._mcp_observability_session_state.logger") as mock_logger,
        ):
            mock_redis.setex = AsyncMock(side_effect=Exception("Redis connection failed"))

            # Should not raise an exception, but should log error
            await session.save(mock_tenant)

            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_success(self, mock_tenant):
        session_data = {
            "session_id": "test-session",
            "created_at": "2024-01-01T12:00:00+00:00",
            "last_activity": "2024-01-01T12:05:00+00:00",
            "tool_calls": [
                {
                    "tool_name": "test_tool",
                    "duration": 1.5,
                    "result": "success",
                },
            ],
        }

        with patch("api.routers.mcp._mcp_observability_session_state.shared_redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=json.dumps(session_data).encode())

            session = await SessionState.load("test-session", mock_tenant)

            assert session is not None
            assert session.session_id == "test-session"
            assert len(session.tool_calls) == 1
            assert session.tool_calls[0]["tool_name"] == "test_tool"

            mock_redis.get.assert_called_once_with("mcp_session:test-tenant:test-session")

    @pytest.mark.asyncio
    async def test_load_not_found(self, mock_tenant):
        with patch("api.routers.mcp._mcp_observability_session_state.shared_redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)

            session = await SessionState.load("nonexistent-session", mock_tenant)

            assert session is None

    @pytest.mark.asyncio
    async def test_load_no_redis_client(self, mock_tenant):
        with patch("api.routers.mcp._mcp_observability_session_state.shared_redis_client", None):
            session = await SessionState.load("test-session", mock_tenant)

            assert session is None

    @pytest.mark.asyncio
    async def test_load_redis_error(self, mock_tenant):
        with (
            patch("api.routers.mcp._mcp_observability_session_state.shared_redis_client") as mock_redis,
            patch("api.routers.mcp._mcp_observability_session_state.logger") as mock_logger,
        ):
            mock_redis.get = AsyncMock(side_effect=Exception("Redis error"))

            session = await SessionState.load("test-session", mock_tenant)

            assert session is None
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_invalid_json(self, mock_tenant):
        with (
            patch("api.routers.mcp._mcp_observability_session_state.shared_redis_client") as mock_redis,
            patch("api.routers.mcp._mcp_observability_session_state.logger") as mock_logger,
        ):
            mock_redis.get = AsyncMock(return_value=b"invalid json")

            session = await SessionState.load("test-session", mock_tenant)

            assert session is None
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_create_existing_session(self, mock_tenant):
        existing_session = SessionState("existing-session")

        with (
            patch.object(SessionState, "load", return_value=existing_session) as mock_load,
            patch.object(existing_session, "save") as mock_save,
        ):
            result_session, is_new = await SessionState.get_or_create("existing-session", mock_tenant)

            assert result_session == existing_session
            assert is_new is False
            mock_load.assert_called_once_with("existing-session", mock_tenant)
            mock_save.assert_called_once_with(mock_tenant)  # Should update last_activity

    @pytest.mark.asyncio
    async def test_get_or_create_new_session_with_id(self, mock_tenant):
        with (
            patch.object(SessionState, "load", return_value=None),
            patch("uuid.uuid4", return_value=Mock(__str__=Mock(return_value="new-uuid-session"))),
            patch.object(SessionState, "save") as mock_save,
        ):
            result_session, is_new = await SessionState.get_or_create("nonexistent-session", mock_tenant)

            assert result_session.session_id == "new-uuid-session"
            assert is_new is True
            mock_save.assert_called_once_with(mock_tenant)

    @pytest.mark.asyncio
    async def test_get_or_create_new_session_no_id(self, mock_tenant):
        with (
            patch("uuid.uuid4", return_value=Mock(__str__=Mock(return_value="new-uuid-session"))),
            patch.object(SessionState, "save") as mock_save,
        ):
            result_session, is_new = await SessionState.get_or_create(None, mock_tenant)

            assert result_session.session_id == "new-uuid-session"
            assert is_new is True
            mock_save.assert_called_once_with(mock_tenant)

    @pytest.mark.asyncio
    async def test_register_tool_call(self, mock_tenant, sample_tool_call_data):
        session = SessionState("test-session")

        with patch.object(session, "save") as mock_save:
            await session.register_tool_call(sample_tool_call_data, mock_tenant)

            assert len(session.tool_calls) == 1

            registered_call = session.tool_calls[0]
            assert registered_call["tool_name"] == "test_tool"
            assert registered_call["tool_arguments"] == {"arg1": "value1", "arg2": 42}
            assert registered_call["request_id"] == "req-123"
            assert registered_call["duration"] == 1.5
            assert registered_call["result"] == "Tool execution successful"
            assert registered_call["user_agent"] == "test-agent/1.0"

            # Check that timestamps are ISO formatted
            assert "started_at" in registered_call
            assert "completed_at" in registered_call

            # Verify save was called to persist the updated session
            mock_save.assert_called_once_with(mock_tenant)

    @pytest.mark.asyncio
    async def test_register_multiple_tool_calls(self, mock_tenant, sample_tool_call_data):
        session = SessionState("test-session")

        # Create another tool call
        second_tool_call = ToolCallData(
            tool_name="second_tool",
            tool_arguments={"arg": "value"},
            request_id="req-456",
            duration=0.8,
            result="Second result",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            user_agent="test-agent",
        )

        with patch.object(session, "save"):
            await session.register_tool_call(sample_tool_call_data, mock_tenant)
            await session.register_tool_call(second_tool_call, mock_tenant)

            assert len(session.tool_calls) == 2
            assert session.tool_calls[0]["tool_name"] == "test_tool"
            assert session.tool_calls[1]["tool_name"] == "second_tool"

    @pytest.mark.asyncio
    async def test_register_tool_call_updates_last_activity(self, mock_tenant, sample_tool_call_data):
        session = SessionState("test-session")
        original_last_activity = session.last_activity

        # Wait a bit to ensure time difference
        import asyncio

        await asyncio.sleep(0.01)

        with patch.object(session, "save"):
            await session.register_tool_call(sample_tool_call_data, mock_tenant)

            assert session.last_activity > original_last_activity

    def test_session_data_serialization_roundtrip(self, mock_tenant):
        """Test that session data can be serialized and deserialized correctly"""
        original_session = SessionState("test-session")
        original_session.tool_calls = [
            {
                "tool_name": "test_tool",
                "tool_arguments": {"arg1": "value1", "nested": {"key": "value"}},
                "request_id": "req-123",
                "duration": 1.5,
                "result": "Test result with unicode: 🚀",
                "started_at": "2024-01-01T12:00:00+00:00",
                "completed_at": "2024-01-01T12:00:01+00:00",
                "user_agent": "test-agent/1.0",
            },
        ]

        # Simulate serialization/deserialization as done in save/load
        session_data = {
            "session_id": original_session.session_id,
            "created_at": original_session.created_at.isoformat(),
            "last_activity": original_session.last_activity.isoformat(),
            "tool_calls": original_session.tool_calls,
        }

        json_str = json.dumps(session_data)
        deserialized_data = json.loads(json_str)

        # Reconstruct session (mimicking load method)
        reconstructed_session = SessionState.__new__(SessionState)
        reconstructed_session.session_id = deserialized_data["session_id"]
        reconstructed_session.created_at = datetime.fromisoformat(deserialized_data["created_at"])
        reconstructed_session.last_activity = datetime.fromisoformat(deserialized_data["last_activity"])
        reconstructed_session.tool_calls = deserialized_data["tool_calls"]

        # Verify reconstruction
        assert reconstructed_session.session_id == original_session.session_id
        assert len(reconstructed_session.tool_calls) == 1
        assert reconstructed_session.tool_calls[0]["tool_name"] == "test_tool"
        assert reconstructed_session.tool_calls[0]["result"] == "Test result with unicode: 🚀"
