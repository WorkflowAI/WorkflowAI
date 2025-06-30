import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi.responses import StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware, _StreamingResponse  # type: ignore[reportPrivateImportUsage]
from starlette.requests import Request
from starlette.responses import Response

from api.routers.mcp._mcp_dependencies import get_tenant_from_context
from api.routers.mcp._mcp_observability_session_state import ObserverAgentData, SessionState, ToolCallData
from core.domain.tenant_data import TenantData
from core.utils.background import add_background_task
from core.utils.json_utils import extract_json_str

from ._mcp_observer_agent import mcp_tool_call_observer_agent

logger = logging.getLogger(__name__)


class MCPObservabilityMiddleware(BaseHTTPMiddleware):
    """Enhanced middleware to log MCP tool calls and track session observability"""

    def _extract_session_id(self, request: Request) -> str | None:
        """Extract session ID from request headers"""
        # Check for MCP session ID header
        session_id = request.headers.get("mcp-session-id")
        if session_id:
            return session_id

        # Check for X-Session-ID header (custom header)
        session_id = request.headers.get("x-session-id")
        if session_id:
            return session_id

        # Return None if no session ID found
        return None

    def _inject_session_id_to_headers(self, request: Request, session_id: str) -> None:
        request.scope["headers"].append((b"mcp-session-id", session_id.encode()))

    async def _get_or_create_session(self, session_id: str | None, tenant: TenantData) -> tuple[SessionState, bool]:
        """Get existing session or create a new one using Redis"""
        session_state, is_new_session = await SessionState.get_or_create(session_id, tenant)
        return session_state, is_new_session

    def _is_mcp_tool_call(self, request_data: dict[str, Any] | None) -> bool:
        """Check if this is an MCP tool call request"""
        if not request_data:
            return False
        return request_data.get("method") == "tools/call"

    def _extract_tool_call_info(self, request_data: dict[str, Any]) -> tuple[str, dict[str, Any], str]:
        """Extract tool call information from request data"""
        params = request_data.get("params", {})
        tool_name = params.get("name", "unknown")
        tool_arguments = params.get("arguments", {})
        request_id = request_data.get("id", "unknown")
        return tool_name, tool_arguments, request_id

    def _create_observing_streaming_response(
        self,
        original_response: _StreamingResponse,
        on_complete_callback: Callable[[bytes], None],
    ) -> StreamingResponse:
        """Create a streaming response that yields chunks as they come and processes them after completion"""

        async def observing_body_iterator():
            body_parts: list[bytes] = []
            async for chunk in original_response.body_iterator:
                if isinstance(chunk, bytes):
                    chunk_bytes = chunk
                else:
                    chunk_bytes = str(chunk).encode("utf-8")

                # Collect chunk for later processing
                body_parts.append(chunk_bytes)

                # Yield chunk immediately for streaming
                yield chunk_bytes

            if body_parts:
                complete_body = b"".join(body_parts)
                try:
                    on_complete_callback(complete_body)
                except Exception as e:
                    logger.warning(
                        "Error in streaming response completion callback",
                        extra={"error": str(e)},
                    )

        return StreamingResponse(
            observing_body_iterator(),
            status_code=original_response.status_code,
            headers=original_response.headers,
            media_type=original_response.media_type,
        )

    def _parse_tool_call_response(self, response_body: bytes, request_id: str) -> str:
        try:
            response_str = response_body.decode("utf-8")
            response_json_str = extract_json_str(response_str)

            response_data = json.loads(response_json_str)
            return response_data["result"]["content"][0]["text"]

        except (json.JSONDecodeError, UnicodeDecodeError, KeyError, IndexError, ValueError) as e:
            logger.error(
                "Failed to parse MCP response JSON",
                extra={
                    "error": str(e),
                    "response_body_length": len(response_body),
                    "request_id": request_id,
                },
            )
            return str(e)

    async def run_observer_agent(self, observer_data: ObserverAgentData) -> None:
        await mcp_tool_call_observer_agent(
            tool_name=observer_data.tool_name,
            previous_tool_calls=observer_data.previous_tool_calls,
            tool_arguments=observer_data.tool_arguments,
            tool_result=observer_data.tool_result,
            duration_seconds=observer_data.duration_seconds,
            user_agent=observer_data.user_agent,
            mcp_session_id=observer_data.mcp_session_id,
            organization_name=observer_data.organization_name,
        )

    async def _setup_session_and_validate_request(
        self,
        request: Request,
        session_id_from_header: str | None,
    ) -> tuple[TenantData, SessionState, dict[str, Any] | None] | None:
        """Setup session and validate request. Returns None if should use fallback."""
        try:
            tenant_info = await get_tenant_from_context(request)
        except Exception as e:
            logger.warning("No tenant info found, using fallback response", extra={"error": str(e)})
            return None

        session_state, _ = await self._get_or_create_session(session_id_from_header, tenant_info)

        # Read and parse request body
        try:
            body = await request.body()
            request_data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(
                "Failed to parse request body as JSON, using fallback response",
                extra={"error": str(e)},
            )
            return None

        return tenant_info, session_state, request_data

    async def _validate_mcp_tool_call(
        self,
        request_data: dict[str, Any] | None,
        session_state: SessionState,
    ) -> tuple[str, dict[str, Any], Any] | None:
        """Validate MCP tool call and extract info. Returns None if not an MCP tool call."""
        if not self._is_mcp_tool_call(request_data):
            logger.debug(
                "Non-MCP tool call request, passing through",
                extra={
                    "method": request_data.get("method") if request_data else None,
                    "session_id": session_state.session_id,
                },
            )
            return None

        if request_data is None:  # type narrowing for the type checker
            logger.error("Request data is None, using fallback response")
            return None

        # Extract tool call information
        return self._extract_tool_call_info(request_data)

    def _create_tool_call_completion_handler(
        self,
        session_state: SessionState,
        tenant_info: TenantData,
        tool_name: str,
        tool_arguments: dict[str, Any],
        request_id: Any,
        start_time: float,
        tool_call_start_time: datetime,
        user_agent: str,
    ) -> Callable[[bytes], None]:
        """Create the callback handler for when tool call streaming completes."""

        def on_streaming_complete(response_body: bytes) -> None:
            """Process the complete response body after streaming is done"""

            # Process tool call response
            duration = time.time() - start_time
            completed_at = datetime.now(timezone.utc)
            tool_result = self._parse_tool_call_response(response_body, request_id)

            # Create tool call data
            tool_call_data = ToolCallData(
                tool_name=tool_name,
                tool_arguments=tool_arguments,
                request_id=str(request_id),
                duration=duration,
                result=tool_result,
                started_at=tool_call_start_time,
                completed_at=completed_at,
                user_agent=user_agent,
            )

            # Update session state with completed tool call (async call in sync context)
            async def update_session():
                await session_state.register_tool_call(tool_call_data)

            # Run observer agent in background
            if response_body:
                observer_data = ObserverAgentData(
                    tool_name=tool_name,
                    previous_tool_calls=session_state.tool_calls,
                    tool_arguments=tool_arguments,
                    tool_result=tool_result,
                    duration_seconds=duration,
                    user_agent=user_agent,
                    mcp_session_id=session_state.session_id,
                    request_id=str(request_id),
                    organization_name=tenant_info.slug,
                )

                # Create background task for observer agent
                async def run_observer_background():
                    # Update session first, then run observer
                    await update_session()
                    await self.run_observer_agent(observer_data)

                add_background_task(run_observer_background())
            else:
                # Just update session if no response body
                add_background_task(update_session())
                logger.warning(
                    "No response body received, skipping observer agent",
                    extra={
                        "session_id": session_state.session_id,
                        "request_id": request_id,
                    },
                )

        return on_streaming_complete

    def _log_request(self, request: Request) -> None:
        """Log the request"""
        # Log the headers to investigate mcp-session-id problems
        # But remove the authorization header
        headers = dict(request.headers)
        headers.pop("authorization", None)

        logger.info(
            "MCPMiddleware has received a call request",
            extra={"headers": headers},
        )

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        """Main dispatch method with comprehensive error handling"""

        self._log_request(request)

        session_id_from_header = self._extract_session_id(request)

        # TODO: refactor, we are validating the token and fetching the tenant twice, here and in the actual tool functions
        setup_result = await self._setup_session_and_validate_request(request, session_id_from_header)
        if not setup_result:
            # No valid tenant or request data
            return await call_next(request)

        tenant_info, session_state, request_data = setup_result
        if session_id_from_header is None:
            self._inject_session_id_to_headers(request, session_state.session_id)

        # Validate MCP tool call and extract info
        tool_call_info = await self._validate_mcp_tool_call(request_data, session_state)
        if not tool_call_info:
            return await call_next(request)

        tool_name, tool_arguments, request_id = tool_call_info

        # Track timing
        start_time = time.time()
        user_agent = request.headers.get("user-agent", "unknown")
        tool_call_start_time = datetime.now(timezone.utc)

        # Process request through middleware chain
        original_response = await call_next(request)

        # Create completion handler for streaming response
        on_streaming_complete = self._create_tool_call_completion_handler(
            session_state=session_state,
            tenant_info=tenant_info,
            tool_name=tool_name,
            tool_arguments=tool_arguments,
            request_id=request_id,
            start_time=start_time,
            tool_call_start_time=tool_call_start_time,
            user_agent=user_agent,
        )

        # Create observing streaming response (only supports _StreamingResponse)
        if isinstance(original_response, _StreamingResponse):
            response = self._create_observing_streaming_response(original_response, on_streaming_complete)
        else:
            logger.error(
                "Non-streaming response type, cannot observe - using original response",
                extra={
                    "response_type": type(original_response).__name__,
                    "session_id": session_state.session_id,
                    "request_id": request_id,
                },
            )
            response = original_response

        return response
