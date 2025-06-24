import json
import logging
import time
import uuid
from typing import Any, Callable

from fastapi.responses import StreamingResponse
from starlette.exceptions import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware, _StreamingResponse  # type: ignore[reportPrivateImportUsage]
from starlette.requests import Request
from starlette.responses import Response

from api.routers.mcp._mcp_observability_session_state import SessionState
from api.services import storage
from api.services.analytics import analytics_service
from api.services.event_handler import system_event_router
from api.services.security_service import SecurityService
from core.domain.analytics_events.analytics_events import OrganizationProperties
from core.utils.background import add_background_task
from core.utils.json_utils import extract_json_str

from ._mcp_observer_agent import mcp_tool_call_observer_agent

logger = logging.getLogger(__name__)


# Global session storage
_session_store: dict[str, SessionState] = {}


class AuthInfo:
    """Container for authentication information extracted from request"""

    def __init__(
        self,
        tenant_slug: str,
        user_email: str | None,
        organization_name: str | None,
        user_id: str | None,
        tenant_uid: str,
    ):
        self.tenant_slug = tenant_slug
        self.user_email = user_email
        self.organization_name = organization_name
        self.user_id = user_id
        self.tenant_uid = tenant_uid


async def extract_auth_info_from_request(request: Request) -> AuthInfo | None:
    """
    Extract authentication information from request headers.
    Reuses the auth logic from mcp_server.py get_mcp_service() function.

    Returns None if authentication fails or is missing.
    """
    try:
        _system_storage = storage.system_storage(storage.shared_encryption())
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            logger.debug("Missing or invalid Authorization header format")
            return None

        security_service = SecurityService(
            _system_storage.organizations,
            system_event_router(),
            analytics_service(user_properties=None, organization_properties=None, task_properties=None),
        )

        tenant = await security_service.tenant_from_credentials(auth_header.split(" ")[1])
        if not tenant:
            logger.debug("Invalid bearer token - tenant not found")
            return None

        # Extract organization and user information
        org_properties = OrganizationProperties.build(tenant)

        return AuthInfo(
            tenant_slug=tenant.slug,
            user_email=None,  # TODO: Extract from tenant if available
            organization_name=org_properties.name if hasattr(org_properties, "name") else tenant.slug,
            user_id=None,  # TODO: Extract from tenant if available
            tenant_uid=tenant.uid,
        )

    except HTTPException:
        # Let the HTTPException bubble up if it's a real auth error
        raise
    except Exception as e:
        logger.warning(
            "Failed to extract auth info from request",
            extra={
                "error": str(e),
                "has_auth_header": bool(request.headers.get("Authorization")),
            },
        )
        return None


class MCPObservabilityMiddleware(BaseHTTPMiddleware):
    """Enhanced middleware to log MCP tool calls and track session observability"""

    def _extract_session_id(self, request: Request) -> str:
        """Extract or create session ID for the request"""
        # Check for MCP session ID header
        session_id = request.headers.get("mcp-session-id")
        if session_id:
            return session_id

        # Check for X-Session-ID header (custom header)
        session_id = request.headers.get("x-session-id")
        if session_id:
            return session_id

        # Generate a new session ID
        return str(uuid.uuid4())

    def _get_or_create_session(self, session_id: str, user_agent: str, auth_info: AuthInfo | None) -> SessionState:
        """Get existing session or create a new one"""
        if session_id not in _session_store:
            _session_store[session_id] = SessionState(session_id, user_agent)

            # Log new session creation with auth context
            log_extra = {
                "mcp_event": "session_created",
                "session_id": session_id,
                "user_agent": user_agent,
                "session_created_at": _session_store[session_id].created_at,
            }

            if auth_info:
                log_extra.update(
                    {
                        "tenant_slug": auth_info.tenant_slug,
                        "organization_name": auth_info.organization_name,
                        "user_email": auth_info.user_email,
                    },
                )

            logger.info("New MCP session created", extra=log_extra)

        return _session_store[session_id]

    def _cleanup_old_sessions(self):
        """Clean up sessions older than 24 hours"""
        current_time = time.time()
        cutoff_time = current_time - (24 * 60 * 60)  # 24 hours ago

        sessions_to_remove: list[str] = []
        for session_id, session_state in _session_store.items():
            if session_state.last_activity < cutoff_time:
                sessions_to_remove.append(session_id)

        for session_id in sessions_to_remove:
            session_summary = _session_store[session_id].get_session_summary()
            logger.info(
                "MCP session expired and cleaned up",
                extra={
                    "mcp_event": "session_expired",
                    "session_summary": session_summary,
                },
            )
            del _session_store[session_id]

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

    def _log_tool_call_start(
        self,
        session_id: str,
        tool_name: str,
        tool_arguments: dict[str, Any],
        request_id: str,
        request_data: dict[str, Any],
        user_agent: str,
        session_state: SessionState,
        auth_info: AuthInfo | None,
    ):
        """Log the start of a tool call"""
        log_extra = {
            "mcp_event": "tool_call_start",
            "session_id": session_id,
            "tool_name": tool_name,
            "tool_arguments": tool_arguments,
            "request_id": request_id,
            "jsonrpc": request_data.get("jsonrpc"),
            "user_agent": user_agent,
            "session_total_requests": session_state.total_requests,
            "session_duration": time.time() - session_state.created_at,
        }

        if auth_info:
            log_extra.update(
                {
                    "tenant_slug": auth_info.tenant_slug,
                    "organization_name": auth_info.organization_name,
                    "user_email": auth_info.user_email,
                },
            )

        logger.info("MCP tool call started", extra=log_extra)

    async def _capture_streaming_response_body(self, response: Response) -> bytes:
        """Capture response body from streaming response"""
        if not isinstance(response, _StreamingResponse):
            raise ValueError(f"Unsupported response type: {type(response)}. Only _StreamingResponse is supported.")

        # For streaming responses, consume the iterator
        body_parts: list[bytes] = []
        async for chunk in response.body_iterator:
            if isinstance(chunk, bytes):
                body_parts.append(chunk)
            else:
                body_parts.append(str(chunk).encode("utf-8"))
        return b"".join(body_parts)

    def _create_new_streaming_response(
        self,
        response_body: bytes,
        original_response: _StreamingResponse,
    ) -> StreamingResponse:
        """Create a new streaming response with the captured body"""

        async def new_body_iterator():
            yield response_body

        return StreamingResponse(
            new_body_iterator(),
            status_code=original_response.status_code,
            headers=original_response.headers,
            media_type=original_response.media_type,
        )

    def _parse_tool_call_response(self, response_body: bytes, request_id: str) -> tuple[Any, dict[str, Any] | None]:
        """Parse tool call response and extract result and error info"""
        try:
            response_text = response_body.decode("utf-8")
            logger.info(
                "MCP response body captured for tool call",
                extra={
                    "response_text": response_text,
                    "request_id": request_id,
                },
            )

            response_data = json.loads(response_text)
            tool_result = response_data.get("result")
            error_info = response_data.get("error")

            logger.info(
                "MCP response data extracted",
                extra={
                    "has_result": tool_result is not None,
                    "has_error": error_info is not None,
                    "request_id": request_id,
                    "response_keys": list(response_data.keys()) if response_data else [],
                },
            )
            return tool_result, error_info

        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(
                "Failed to parse MCP response JSON",
                extra={
                    "error": str(e),
                    "response_body_length": len(response_body),
                    "request_id": request_id,
                },
            )
            return None, None

    def _update_session_state(
        self,
        session_state: SessionState,
        request_id: str,
        duration: float,
        success: bool,
        error_info: dict[str, Any] | None,
        tool_name: str,
        tool_arguments: dict[str, Any],
        tool_result: Any,
    ):
        """Update session state with tool call completion"""
        session_state.complete_tool_call(
            request_id=request_id,
            duration=duration,
            success=success,
            result=tool_result,
            error_info=error_info,
        )

        session_state.add_conversation_turn(
            request_id=request_id,
            tool_name=tool_name,
            tool_arguments=tool_arguments,
            result=tool_result,
        )

    async def _run_observer_agent_background(
        self,
        tool_name: str,
        previous_tool_calls: list[dict[str, Any]],
        tool_arguments: dict[str, Any],
        response_text: str,
        duration: float,
        user_agent: str,
        session_id: str,
        request_id: str,
        auth_info: AuthInfo | None,
    ):
        """Run observer agent in background for analysis"""
        try:
            # Extract JSON from response text
            try:
                raw_json = extract_json_str(response_text)
                processed_response = json.loads(raw_json)["result"]["content"][0]["text"]
            except Exception as e:
                logger.warning(
                    "Failed to extract JSON from response text",
                    extra={"error": str(e), "response_text": response_text},
                )
                processed_response = response_text

            # Create wrapper coroutine for background task
            async def run_observer_agent() -> None:
                try:
                    await mcp_tool_call_observer_agent(
                        tool_name=tool_name,
                        previous_tool_calls=previous_tool_calls[1:]
                        if len(previous_tool_calls) > 1
                        else [],  # Ignore the latest tool call
                        tool_arguments=tool_arguments,
                        tool_result=processed_response,
                        duration_seconds=duration,
                        user_agent=user_agent,
                        mcp_session_id=session_id,
                        organization_name=auth_info.organization_name if auth_info else None,
                        user_email=auth_info.user_email if auth_info else None,
                    )
                except Exception as e:
                    logger.warning(
                        "Observer agent execution failed",
                        extra={
                            "error": str(e),
                            "session_id": session_id,
                            "request_id": request_id,
                        },
                    )

            # Add the wrapper as a background task
            add_background_task(run_observer_agent())
        except Exception as observer_error:
            logger.warning(
                "Failed to start observer agent background task",
                extra={
                    "error": str(observer_error),
                    "session_id": session_id,
                    "request_id": request_id,
                },
            )

    def _log_tool_call_completion(
        self,
        session_id: str,
        duration: float,
        response: Response,
        user_agent: str,
        session_state: SessionState,
        tool_name: str,
        request_id: str,
        tool_result: Any,
        error_info: dict[str, Any] | None,
        auth_info: AuthInfo | None,
    ):
        """Log tool call completion with session context"""
        log_extra = {
            "mcp_event": "tool_call_complete",
            "session_id": session_id,
            "duration_seconds": duration,
            "status_code": response.status_code,
            "user_agent": user_agent,
            "session_summary": session_state.get_session_summary(),
            "tool_name": tool_name,
            "request_id": request_id,
            "has_result": tool_result is not None,
            "has_error": error_info is not None,
        }

        if auth_info:
            log_extra.update(
                {
                    "tenant_slug": auth_info.tenant_slug,
                    "organization_name": auth_info.organization_name,
                    "user_email": auth_info.user_email,
                },
            )

        # Include the actual tool result for debugging (truncated if too long)
        if tool_result is not None:
            try:
                result_str = json.dumps(tool_result)
                if len(result_str) > 1000:  # Truncate very long results
                    log_extra["tool_result_preview"] = result_str[:1000] + "... (truncated)"
                else:
                    log_extra["tool_result"] = tool_result
            except (TypeError, ValueError):
                log_extra["tool_result"] = str(tool_result)[:500]

        # Include error details if present (but limit size)
        if error_info:
            log_extra["error_code"] = error_info.get("code", "unknown")
            log_extra["error_message"] = str(error_info.get("message", ""))[:200]

        logger.info("MCP tool call completed", extra=log_extra)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        start_time = time.time()
        user_agent = request.headers.get("user-agent", "unknown")
        session_id: str = self._extract_session_id(request)

        # Extract authentication information using the reused auth logic
        auth_info = None
        try:
            auth_info = await extract_auth_info_from_request(request)
        except HTTPException:
            # If auth fails with HTTPException, let it bubble up for auth-required endpoints
            # For middleware, we'll continue but log the auth failure
            logger.debug("Authentication failed in middleware", extra={"session_id": session_id})
        except Exception as e:
            logger.warning(
                "Unexpected error during auth extraction",
                extra={"error": str(e), "session_id": session_id},
            )

        session_state = self._get_or_create_session(session_id, user_agent, auth_info)

        # Periodically cleanup old sessions
        if len(_session_store) > 100:
            self._cleanup_old_sessions()

        # Read request body
        body = await request.body()
        request_data = None

        # Parse request body
        try:
            if body:
                request_data = json.loads(body)
        except json.JSONDecodeError:
            logger.error(
                "Failed to parse MCP request body",
                extra={
                    "body": body.decode(),
                    "user_agent": user_agent,
                    "session_id": session_id,
                },
            )

        # Check if this is an MCP tool call - if not, just pass through
        if not self._is_mcp_tool_call(request_data):
            logger.debug(
                "Non-MCP tool call request, passing through",
                extra={
                    "method": request_data.get("method") if request_data else None,
                    "session_id": session_id,
                },
            )
            response = await call_next(request)
            response.headers["mcp-session-id"] = session_id
            response.headers["x-session-id"] = session_id
            return response

        # At this point, request_data is guaranteed to be a dict with method="tools/call"
        if request_data is None:  # type narrowing for the type checker
            logger.error("Request data is None", extra={"request": request.headers})
            raise ValueError("Request data is None")

        # Extract tool call information
        tool_name, tool_arguments, request_id = self._extract_tool_call_info(request_data)

        # Add tool call to session state and log start
        session_state.add_tool_call(tool_name, tool_arguments, request_id)
        self._log_tool_call_start(
            session_id,
            tool_name,
            tool_arguments,
            request_id,
            request_data,
            user_agent,
            session_state,
            auth_info,
        )

        # Execute the request
        original_response = await call_next(request)

        # Capture response body (only supports _StreamingResponse)
        try:
            response_body = await self._capture_streaming_response_body(original_response)
            response = self._create_new_streaming_response(response_body, original_response)
        except ValueError as e:
            logger.exception("Response type error", exc_info=e)
            raise
        except Exception as e:
            logger.exception("Error capturing response body", exc_info=e)
            response = original_response
            response_body = b""

        # Process tool call response
        duration = time.time() - start_time
        tool_result, error_info = self._parse_tool_call_response(response_body, request_id)
        success = response.status_code < 400 and error_info is None

        # Update session state
        self._update_session_state(
            session_state,
            request_id,
            duration,
            success,
            error_info,
            tool_name,
            tool_arguments,
            tool_result,
        )

        # Run observer agent in background with auth metadata
        if response_body:
            await self._run_observer_agent_background(
                tool_name,
                session_state.tool_calls,
                tool_arguments,
                response_body.decode("utf-8"),
                duration,
                user_agent,
                session_id,
                request_id,
                auth_info,
            )

        # Log completion with auth context
        self._log_tool_call_completion(
            session_id,
            duration,
            response,
            user_agent,
            session_state,
            tool_name,
            request_id,
            tool_result,
            error_info,
            auth_info,
        )

        # Add session ID to response headers
        response.headers["mcp-session-id"] = session_id
        response.headers["x-session-id"] = session_id
        return response
