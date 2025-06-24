import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi.responses import StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware, _StreamingResponse  # type: ignore[reportPrivateImportUsage]
from starlette.requests import Request
from starlette.responses import Response

from api.routers.mcp._mcp_obersavilibity_session_state import ObserverAgentData, SessionState, ToolCallData
from api.services import storage
from api.services.analytics import analytics_service
from api.services.event_handler import system_event_router
from api.services.security_service import SecurityService
from core.domain.analytics_events.analytics_events import OrganizationProperties, UserProperties
from core.utils.background import add_background_task
from core.utils.json_utils import extract_json_str

from ._mcp_observer_agent import mcp_tool_call_observer_agent

logger = logging.getLogger(__name__)

# Track tool call start times per request
_tool_call_start_times: dict[str, datetime] = {}


class TenantInfo:
    """Container for tenant authentication information"""

    def __init__(self, tenant: Any, org_properties: OrganizationProperties, user_properties: UserProperties | None):
        self.tenant = tenant
        self.org_properties = org_properties
        self.user_properties = user_properties

    @property
    def organization_name(self) -> str | None:
        return self.tenant.slug if self.tenant else None

    @property
    def user_email(self) -> str | None:
        # TODO: Extract user email from tenant if available
        return None


class MCPObservabilityMiddleware(BaseHTTPMiddleware):
    """Enhanced middleware to log MCP tool calls and track session observability"""

    async def _extract_tenant_info(self, request: Request) -> TenantInfo | None:
        """Extract tenant information from request using auth header"""
        try:
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                logger.debug("No valid Authorization header found in request")
                return None

            _system_storage = storage.system_storage(storage.shared_encryption())
            security_service = SecurityService(
                _system_storage.organizations,
                system_event_router(),
                analytics_service(user_properties=None, organization_properties=None, task_properties=None),
            )

            tenant = await security_service.tenant_from_credentials(auth_header.split(" ")[1])
            if not tenant:
                logger.debug("Invalid bearer token provided")
                return None

            org_properties = OrganizationProperties.build(tenant)
            # TODO: user analytics - extract user properties if available
            user_properties: UserProperties | None = None

            return TenantInfo(tenant, org_properties, user_properties)

        except Exception as e:
            logger.warning(
                "Failed to extract tenant info from request",
                extra={"error": str(e)},
            )
            return None

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

    async def _get_or_create_session(self, session_id: str | None, user_agent: str) -> SessionState:
        """Get existing session or create a new one using Redis"""
        session_state, is_new = await SessionState.get_or_create(session_id, user_agent)
        return session_state

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
            try:
                async for chunk in original_response.body_iterator:
                    if isinstance(chunk, bytes):
                        chunk_bytes = chunk
                    else:
                        chunk_bytes = str(chunk).encode("utf-8")

                    # Collect chunk for later processing
                    body_parts.append(chunk_bytes)

                    # Yield chunk immediately for streaming
                    yield chunk_bytes

            except Exception as e:
                logger.error(
                    "Error during streaming response iteration",
                    extra={"error": str(e)},
                )
                raise
            finally:
                # Process complete response after streaming is done
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

        except (json.JSONDecodeError, UnicodeDecodeError, KeyError, IndexError) as e:
            logger.error(
                "Failed to parse MCP response JSON",
                extra={
                    "error": str(e),
                    "response_body_length": len(response_body),
                    "request_id": request_id,
                },
            )
            return str(e)

    def _log_tool_call_completion(
        self,
        tool_call_data: ToolCallData,
        session_id: str,
        response: Response,
        user_agent: str,
        session_state: SessionState,
        error_info: dict[str, Any] | None,
    ):
        """Log tool call completion with session context"""
        log_extra = {
            "mcp_event": "tool_call_complete",
            "session_id": session_id,
            "duration_seconds": tool_call_data.duration,
            "status_code": response.status_code,
            "user_agent": user_agent,
            "tool_name": tool_call_data.tool_name,
            "request_id": tool_call_data.request_id,
            "has_result": tool_call_data.result is not None,
            "has_error": error_info is not None,
        }

        # Include the actual tool result for debugging (truncated if too long)
        if tool_call_data.result is not None:
            try:
                result_str = json.dumps(tool_call_data.result)
                if len(result_str) > 1000:  # Truncate very long results
                    log_extra["tool_result_preview"] = result_str[:1000] + "... (truncated)"
                else:
                    log_extra["tool_result"] = tool_call_data.result
            except (TypeError, ValueError):
                log_extra["tool_result"] = str(tool_call_data.result)[:500]

        # Include error details if present (but limit size)
        if error_info:
            log_extra["error_code"] = error_info.get("code", "unknown")
            log_extra["error_message"] = str(error_info.get("message", ""))[:200]

        logger.info("MCP tool call completed", extra=log_extra)

    def _log_tool_call_completion_with_tenant(
        self,
        tool_call_data: ToolCallData,
        session_id: str,
        response: Response,
        user_agent: str,
        session_state: SessionState,
        tenant_info: TenantInfo | None,
        error_info: dict[str, Any] | None,
    ):
        """Log tool call completion with session context and tenant information"""
        log_extra = {
            "mcp_event": "tool_call_complete",
            "session_id": session_id,
            "duration_seconds": tool_call_data.duration,
            "status_code": response.status_code,
            "user_agent": user_agent,
            "tool_name": tool_call_data.tool_name,
            "request_id": tool_call_data.request_id,
            "has_result": tool_call_data.result is not None,
            "has_error": error_info is not None,
        }

        # Add tenant information if available
        if tenant_info:
            log_extra["organization_name"] = tenant_info.organization_name
            log_extra["user_email"] = tenant_info.user_email
            log_extra["is_authenticated"] = True
        else:
            log_extra["is_authenticated"] = False

        # Include the actual tool result for debugging (truncated if too long)
        if tool_call_data.result is not None:
            try:
                result_str = json.dumps(tool_call_data.result)
                if len(result_str) > 1000:  # Truncate very long results
                    log_extra["tool_result_preview"] = result_str[:1000] + "... (truncated)"
                else:
                    log_extra["tool_result"] = tool_call_data.result
            except (TypeError, ValueError):
                log_extra["tool_result"] = str(tool_call_data.result)[:500]

        # Include error details if present (but limit size)
        if error_info:
            log_extra["error_code"] = error_info.get("code", "unknown")
            log_extra["error_message"] = str(error_info.get("message", ""))[:200]

        logger.info("MCP tool call completed with tenant context", extra=log_extra)

    async def _run_observer_agent_background(self, observer_data: ObserverAgentData):
        """Run observer agent in background for analysis"""
        try:

            async def run_observer_agent() -> None:
                try:
                    await mcp_tool_call_observer_agent(
                        tool_name=observer_data.tool_name,
                        previous_tool_calls=observer_data.previous_tool_calls,
                        tool_arguments=observer_data.tool_arguments,
                        tool_result=observer_data.tool_result,
                        duration_seconds=observer_data.duration_seconds,
                        user_agent=observer_data.user_agent,
                        mcp_session_id=observer_data.mcp_session_id,
                        organization_name=observer_data.organization_name,
                        user_email=observer_data.user_email,
                    )
                except Exception as e:
                    logger.exception(
                        "Observer agent execution failed",
                        exc_info=e,
                    )

            # Run in the background
            add_background_task(run_observer_agent())
        except Exception as e:
            logger.exception(
                "Failed to start observer agent background task",
                exc_info=e,
            )

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:  # noqa: C901
        start_time = time.time()
        user_agent = request.headers.get("user-agent", "unknown")
        session_id_from_header = self._extract_session_id(request)
        session_state = await self._get_or_create_session(session_id_from_header, user_agent)

        # Extract tenant information for authentication and metadata
        tenant_info = await self._extract_tenant_info(request)

        # Log authentication status for debugging
        if tenant_info:
            logger.debug(
                "Authenticated MCP request with tenant info",
                extra={
                    "session_id": session_state.session_id,
                    "organization_name": tenant_info.organization_name,
                    "has_user_email": tenant_info.user_email is not None,
                },
            )
        else:
            logger.debug(
                "Unauthenticated MCP request - no tenant info available",
                extra={"session_id": session_state.session_id},
            )

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
                    "session_id": session_state.session_id,
                },
            )

        # Check if this is an MCP tool call - if not, just pass through
        if not self._is_mcp_tool_call(request_data):
            logger.debug(
                "Non-MCP tool call request, passing through",
                extra={
                    "method": request_data.get("method") if request_data else None,
                    "session_id": session_state.session_id,
                },
            )
            response = await call_next(request)
            response.headers["mcp-session-id"] = session_state.session_id
            response.headers["x-session-id"] = session_state.session_id
            return response

        # At this point, request_data is guaranteed to be a dict with method="tools/call"
        if request_data is None:  # type narrowing for the type checker
            logger.error("Request data is None", extra={"request": request.headers})
            raise ValueError("Request data is None")

        # Extract tool call information
        tool_name, tool_arguments, request_id = self._extract_tool_call_info(request_data)

        # Track start time for this tool call
        tool_call_start_time = datetime.now(timezone.utc)
        _tool_call_start_times[request_id] = tool_call_start_time

        # Execute the request
        original_response = await call_next(request)

        # Create callback to process response after streaming completes
        # Note: tenant_info is captured in the closure for use in the callback
        def on_streaming_complete(response_body: bytes) -> None:
            """Process the complete response body after streaming is done"""
            try:
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
                    started_at=_tool_call_start_times.get(request_id, tool_call_start_time),
                    completed_at=completed_at,
                    user_agent=user_agent,
                )

                # Update session state with completed tool call (async call in sync context)
                async def update_session():
                    await session_state.register_tool_call(tool_call_data)

                # Clean up start time tracking
                _tool_call_start_times.pop(request_id, None)

                # Run observer agent in background
                if response_body:
                    observer_data = ObserverAgentData(
                        tool_name=tool_name,
                        previous_tool_calls=session_state.tool_calls[:-1] if len(session_state.tool_calls) > 1 else [],
                        tool_arguments=tool_arguments,
                        tool_result=tool_result,
                        duration_seconds=duration,
                        user_agent=user_agent,
                        mcp_session_id=session_state.session_id,
                        request_id=str(request_id),
                        # Extract organization and user info from authenticated tenant
                        organization_name=tenant_info.organization_name if tenant_info else None,
                        user_email=tenant_info.user_email if tenant_info else None,
                    )

                    # Create background task for observer agent
                    async def run_observer_background():
                        # Update session first, then run observer
                        await update_session()
                        await self._run_observer_agent_background(observer_data)

                    add_background_task(run_observer_background())
                else:
                    # Just update session if no response body
                    add_background_task(update_session())
                    logger.error(
                        "No response body received, skipping observer agent",
                        extra={
                            "session_id": session_state.session_id,
                            "request_id": request_id,
                        },
                    )

                # Log completion with tenant context
                self._log_tool_call_completion_with_tenant(
                    tool_call_data,
                    session_state.session_id,
                    original_response,
                    user_agent,
                    session_state,
                    tenant_info,
                    None,  # error_info - we could parse this from response if needed
                )

            except Exception as e:
                logger.error(
                    "Error processing streaming response completion",
                    extra={
                        "error": str(e),
                        "session_id": session_state.session_id,
                        "request_id": request_id,
                    },
                )

        # Create observing streaming response (only supports _StreamingResponse)
        try:
            if isinstance(original_response, _StreamingResponse):
                response = self._create_observing_streaming_response(original_response, on_streaming_complete)
            else:
                logger.error(
                    "Non-streaming response type, cannot observe",
                    extra={
                        "response_type": type(original_response).__name__,
                        "session_id": session_state.session_id,
                        "request_id": request_id,
                    },
                )
                response = original_response
        except Exception as e:
            logger.exception("Error creating observing response", exc_info=e)
            response = original_response

        # Add session ID to response headers
        response.headers["mcp-session-id"] = session_state.session_id
        response.headers["x-session-id"] = session_state.session_id
        return response
