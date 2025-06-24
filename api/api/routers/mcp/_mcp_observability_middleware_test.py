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
from fastapi.responses import StreamingResponse
from starlette.middleware.base import _StreamingResponse  # type: ignore[reportPrivateUsage]
from starlette.requests import Request
from starlette.responses import Response

from api.routers.mcp._mcp_observability_middleware import MCPObservabilityMiddleware
from api.routers.mcp._mcp_observability_session_state import SessionState, ToolCallData
from core.domain.tenant_data import TenantData


@pytest.fixture
def middleware():
    return MCPObservabilityMiddleware(app=Mock())


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
def mock_request():
    request = Mock(spec=Request)
    request.headers = {
        "Authorization": "Bearer test-token",
        "user-agent": "test-agent",
        "mcp-session-id": "test-session-id",
    }
    request.body = AsyncMock(
        return_value=b'{"method": "tools/call", "params": {"name": "test_tool", "arguments": {"arg1": "value1"}}, "id": "req-123"}',
    )
    return request


@pytest.fixture
def mock_mcp_request_data():
    return {
        "method": "tools/call",
        "params": {
            "name": "test_tool",
            "arguments": {"arg1": "value1"},
        },
        "id": "req-123",
    }


@pytest.fixture
def mock_non_mcp_request_data():
    return {
        "method": "tools/list",
        "params": {},
        "id": "req-456",
    }


class TestMCPObservabilityMiddleware:
    @pytest.mark.asyncio
    async def test_extract_tenant_info_success(self, middleware, mock_request):
        with (
            patch("api.routers.mcp._mcp_observability_middleware.storage"),
            patch("api.routers.mcp._mcp_observability_middleware.SecurityService") as mock_security_service,
            patch("api.routers.mcp._mcp_observability_middleware.system_event_router"),
            patch("api.routers.mcp._mcp_observability_middleware.analytics_service"),
        ):
            mock_tenant = TenantData(
                tenant="test-tenant",
                slug="test-slug",
                name="Test Organization",
                org_id="test-org-id",
                owner_id="test-owner-id",
            )

            mock_security_instance = Mock()
            mock_security_instance.tenant_from_credentials = AsyncMock(return_value=mock_tenant)
            mock_security_service.return_value = mock_security_instance

            result = await middleware._extract_tenant_info(mock_request)

            assert result == mock_tenant
            mock_security_instance.tenant_from_credentials.assert_called_once_with("test-token")

    @pytest.mark.asyncio
    async def test_extract_tenant_info_no_auth_header(self, middleware):
        request = Mock(spec=Request)
        request.headers = {}

        result = await middleware._extract_tenant_info(request)

        assert result is None

    @pytest.mark.asyncio
    async def test_extract_tenant_info_invalid_token(self, middleware, mock_request):
        with (
            patch("api.routers.mcp._mcp_observability_middleware.storage"),
            patch("api.routers.mcp._mcp_observability_middleware.SecurityService") as mock_security_service,
            patch("api.routers.mcp._mcp_observability_middleware.system_event_router"),
            patch("api.routers.mcp._mcp_observability_middleware.analytics_service"),
        ):
            mock_security_instance = Mock()
            mock_security_instance.tenant_from_credentials = AsyncMock(return_value=None)
            mock_security_service.return_value = mock_security_instance

            result = await middleware._extract_tenant_info(mock_request)

            assert result is None

    @pytest.mark.parametrize(
        "session_header,expected",
        [
            ({"mcp-session-id": "session-123"}, "session-123"),
            ({"x-session-id": "session-456"}, "session-456"),
            (
                {"mcp-session-id": "session-123", "x-session-id": "session-456"},
                "session-123",
            ),  # mcp-session-id takes precedence
            ({}, None),
        ],
    )
    def test_extract_session_id(self, middleware, session_header, expected):
        request = Mock(spec=Request)
        request.headers = session_header

        result = middleware._extract_session_id(request)

        assert result == expected

    @pytest.mark.asyncio
    async def test_get_or_create_session_success(self, middleware, mock_tenant):
        with patch.object(SessionState, "get_or_create") as mock_get_or_create:
            mock_session = Mock()
            mock_get_or_create.return_value = (mock_session, False)

            result = await middleware._get_or_create_session("test-session", mock_tenant)

            assert result == mock_session
            mock_get_or_create.assert_called_once_with("test-session", mock_tenant)

    @pytest.mark.asyncio
    async def test_get_or_create_session_fallback(self, middleware, mock_tenant):
        with patch.object(SessionState, "get_or_create", side_effect=Exception("Redis error")):
            result = await middleware._get_or_create_session("test-session", mock_tenant)

            assert isinstance(result, SessionState)
            assert result.session_id == "test-session"

    @pytest.mark.parametrize(
        "request_data,expected",
        [
            ({"method": "tools/call"}, True),
            ({"method": "tools/list"}, False),
            ({"method": "other"}, False),
            ({}, False),
            (None, False),
        ],
    )
    def test_is_mcp_tool_call(self, middleware, request_data, expected):
        result = middleware._is_mcp_tool_call(request_data)
        assert result == expected

    def test_extract_tool_call_info(self, middleware, mock_mcp_request_data):
        tool_name, tool_arguments, request_id = middleware._extract_tool_call_info(mock_mcp_request_data)

        assert tool_name == "test_tool"
        assert tool_arguments == {"arg1": "value1"}
        assert request_id == "req-123"

    def test_extract_tool_call_info_missing_data(self, middleware):
        request_data = {"method": "tools/call"}  # Missing params

        tool_name, tool_arguments, request_id = middleware._extract_tool_call_info(request_data)

        assert tool_name == "unknown"
        assert tool_arguments == {}
        assert request_id == "unknown"

    @pytest.mark.asyncio
    async def test_create_observing_streaming_response(self, middleware):
        # Create a mock streaming response
        async def mock_body_iterator():
            yield b"chunk1"
            yield b"chunk2"
            yield b"chunk3"

        mock_original_response = Mock(spec=_StreamingResponse)
        mock_original_response.body_iterator = mock_body_iterator()
        mock_original_response.status_code = 200
        mock_original_response.headers = {"content-type": "application/json"}
        mock_original_response.media_type = "application/json"

        callback_data = []

        def test_callback(body: bytes):
            callback_data.append(body)

        response = middleware._create_observing_streaming_response(mock_original_response, test_callback)

        # Consume the response
        chunks = [chunk async for chunk in response.body_iterator]

        assert chunks == [b"chunk1", b"chunk2", b"chunk3"]
        assert callback_data == [b"chunk1chunk2chunk3"]

    def test_parse_tool_call_response_success(self, middleware):
        response_body = b'{"result": {"content": [{"text": "Tool result"}]}}'

        result = middleware._parse_tool_call_response(response_body, "req-123")

        assert result == "Tool result"

    def test_parse_tool_call_response_invalid_json(self, middleware):
        response_body = b"invalid json"

        result = middleware._parse_tool_call_response(response_body, "req-123")

        assert "Could not find JSON object" in result  # Extract JSON error message

    def test_parse_tool_call_response_missing_fields(self, middleware):
        response_body = b'{"result": {}}'  # Missing content field

        result = middleware._parse_tool_call_response(response_body, "req-123")

        assert "KeyError" in result or "'content'" in result

    def test_log_tool_call_completion(self, middleware):
        tool_call_data = ToolCallData(
            tool_name="test_tool",
            tool_arguments={"arg1": "value1"},
            request_id="req-123",
            duration=1.5,
            result="Tool result",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            user_agent="test-agent",
        )

        session_state = Mock()
        response = Mock()
        response.status_code = 200

        with patch("api.routers.mcp._mcp_observability_middleware.logger") as mock_logger:
            middleware._log_tool_call_completion(
                tool_call_data,
                "session-123",
                response,
                "test-agent",
                session_state,
                None,
            )

            mock_logger.info.assert_called_once()
            args, kwargs = mock_logger.info.call_args
            assert "MCP tool call completed" in args[0]
            assert kwargs["extra"]["tool_name"] == "test_tool"
            assert kwargs["extra"]["duration_seconds"] == 1.5

    @pytest.mark.asyncio
    async def test_run_observer_agent_background(self, middleware):
        from api.routers.mcp._mcp_observability_session_state import ObserverAgentData

        observer_data = ObserverAgentData(
            tool_name="test_tool",
            previous_tool_calls=[],
            tool_arguments={"arg1": "value1"},
            tool_result="Tool result",
            duration_seconds=1.5,
            user_agent="test-agent",
            mcp_session_id="session-123",
            request_id="req-123",
        )

        with (
            patch("api.routers.mcp._mcp_observability_middleware.mcp_tool_call_observer_agent"),
            patch("api.routers.mcp._mcp_observability_middleware.add_background_task") as mock_add_task,
        ):
            await middleware._run_observer_agent_background(observer_data)

            mock_add_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_response(self, middleware, mock_request):
        mock_call_next = AsyncMock(return_value=Response())

        response = await middleware._fallback_response(mock_request, mock_call_next)

        assert isinstance(response, Response)
        mock_call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_dispatch_non_mcp_request(self, middleware, mock_request, mock_tenant):
        mock_request.body = AsyncMock(return_value=b'{"method": "tools/list"}')
        mock_call_next = AsyncMock(return_value=Response())

        with (
            patch.object(middleware, "_extract_tenant_info", return_value=mock_tenant),
            patch.object(middleware, "_get_or_create_session") as mock_get_session,
        ):
            mock_session = Mock()
            mock_session.session_id = "session-123"
            mock_get_session.return_value = mock_session

            response = await middleware.dispatch(mock_request, mock_call_next)

            assert isinstance(response, Response)
            assert response.headers["mcp-session-id"] == "session-123"
            mock_call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_dispatch_mcp_tool_call_streaming(self, middleware, mock_request, mock_tenant, mock_mcp_request_data):
        # Setup mocks
        mock_request.body = AsyncMock(return_value=json.dumps(mock_mcp_request_data).encode())

        async def mock_body_iterator():
            yield b'{"result": {"content": [{"text": "Tool result"}]}}'

        mock_streaming_response = Mock(spec=_StreamingResponse)
        mock_streaming_response.body_iterator = mock_body_iterator()
        mock_streaming_response.status_code = 200
        mock_streaming_response.headers = {"content-type": "application/json"}
        mock_streaming_response.media_type = "application/json"

        mock_call_next = AsyncMock(return_value=mock_streaming_response)

        with (
            patch.object(middleware, "_extract_tenant_info", return_value=mock_tenant),
            patch.object(middleware, "_get_or_create_session") as mock_get_session,
            patch("api.routers.mcp._mcp_observability_middleware.add_background_task") as mock_add_task,
        ):
            mock_session = Mock()
            mock_session.session_id = "session-123"
            mock_session.tool_calls = []
            mock_session.register_tool_call = AsyncMock()
            mock_get_session.return_value = mock_session

            response = await middleware.dispatch(mock_request, mock_call_next)

            assert isinstance(response, StreamingResponse)
            assert response.headers["mcp-session-id"] == "session-123"

            # Consume the response to trigger callbacks
            chunks = [chunk async for chunk in response.body_iterator]

            assert chunks == [b'{"result": {"content": [{"text": "Tool result"}]}}']
            mock_add_task.assert_called()

    @pytest.mark.asyncio
    async def test_dispatch_no_tenant_info(self, middleware, mock_request):
        mock_call_next = AsyncMock(return_value=Response())

        with patch.object(middleware, "_extract_tenant_info", return_value=None):
            response = await middleware.dispatch(mock_request, mock_call_next)

            assert isinstance(response, Response)
            mock_call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_dispatch_invalid_request_body(self, middleware, mock_request, mock_tenant):
        mock_request.body = AsyncMock(return_value=b"invalid json")
        mock_call_next = AsyncMock(return_value=Response())

        with patch.object(middleware, "_extract_tenant_info", return_value=mock_tenant):
            response = await middleware.dispatch(mock_request, mock_call_next)

            assert isinstance(response, Response)
            mock_call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_dispatch_error_in_call_next(self, middleware, mock_request, mock_tenant, mock_mcp_request_data):
        mock_request.body = AsyncMock(return_value=json.dumps(mock_mcp_request_data).encode())
        mock_call_next = AsyncMock(side_effect=Exception("Request processing failed"))

        with (
            patch.object(middleware, "_extract_tenant_info", return_value=mock_tenant),
            patch.object(middleware, "_get_or_create_session") as mock_get_session,
        ):
            mock_session = Mock()
            mock_session.session_id = "session-123"
            mock_get_session.return_value = mock_session

            with pytest.raises(Exception, match="Request processing failed"):
                await middleware.dispatch(mock_request, mock_call_next)

    @pytest.mark.asyncio
    async def test_dispatch_non_streaming_response(self, middleware, mock_request, mock_tenant, mock_mcp_request_data):
        mock_request.body = AsyncMock(return_value=json.dumps(mock_mcp_request_data).encode())
        mock_call_next = AsyncMock(return_value=Response(content="regular response"))

        with (
            patch.object(middleware, "_extract_tenant_info", return_value=mock_tenant),
            patch.object(middleware, "_get_or_create_session") as mock_get_session,
        ):
            mock_session = Mock()
            mock_session.session_id = "session-123"
            mock_get_session.return_value = mock_session

            response = await middleware.dispatch(mock_request, mock_call_next)

            assert isinstance(response, Response)
            assert response.headers["mcp-session-id"] == "session-123"
