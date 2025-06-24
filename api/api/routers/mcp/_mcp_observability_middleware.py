import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi.responses import StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware, _StreamingResponse  # type: ignore[reportPrivateImportUsage]
from starlette.requests import Request
from starlette.responses import Response

from api.routers.mcp._mcp_observability_session_state import ObserverAgentData, SessionState, ToolCallData
from api.services import storage
from api.services.analytics import analytics_service
from api.services.event_handler import system_event_router
from api.services.security_service import SecurityService
from core.domain.tenant_data import TenantData
from core.utils.background import add_background_task
from core.utils.json_utils import extract_json_str

from ._mcp_observer_agent import mcp_tool_call_observer_agent

logger = logging.getLogger(__name__)

# Track tool call start times per request
_tool_call_start_times: dict[str, datetime] = {}


class MCPObservabilityMiddleware(BaseHTTPMiddleware):
    """Enhanced middleware to log MCP tool calls and track session observability"""

    async def _extract_tenant_info(self, request: Request) -> TenantData | None:
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

            return tenant

        except Exception as e:
            logger.warning(
                "Failed to extract tenant info from request",
                extra={"error": str(e)},
            )
            return None

    def _extract_session_id(self, request: Request) -> str | None:
        """Extract session ID from request headers"""
        try:
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
        except Exception as e:
            logger.warning(
                "Error extracting session ID from request headers",
                extra={"error": str(e)},
            )
            return None

    async def _get_or_create_session(self, session_id: str | None, tenant: TenantData) -> SessionState:
        """Get existing session or create a new one using Redis"""
        try:
            session_state, _ = await SessionState.get_or_create(session_id, tenant)
            return session_state
        except Exception as e:
            logger.warning(
                "Error getting or creating session state, creating fallback session",
                extra={"error": str(e), "session_id": session_id},
            )
            # Create a fallback session that won't be persisted
            return SessionState(
                session_id=session_id or "fallback",
            )

    def _is_mcp_tool_call(self, request_data: dict[str, Any] | None) -> bool:
        """Check if this is an MCP tool call request"""
        try:
            if not request_data:
                return False
            return request_data.get("method") == "tools/call"
        except Exception as e:
            logger.warning(
                "Error checking if request is MCP tool call",
                extra={"error": str(e)},
            )
            return False

    def _extract_tool_call_info(self, request_data: dict[str, Any]) -> tuple[str, dict[str, Any], str]:
        """Extract tool call information from request data"""
        try:
            params = request_data.get("params", {})
            tool_name = params.get("name", "unknown")
            tool_arguments = params.get("arguments", {})
            request_id = request_data.get("id", "unknown")
            return tool_name, tool_arguments, request_id
        except Exception as e:
            logger.warning(
                "Error extracting tool call information",
                extra={"error": str(e)},
            )
            return "unknown", {}, "unknown"

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
        try:
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
        except Exception as e:
            logger.warning(
                "Error logging tool call completion",
                extra={"error": str(e)},
            )

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

    async def _fallback_response(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        """Fallback response when middleware fails - just pass through the request normally"""
        try:
            return await call_next(request)
        except Exception as e:
            logger.error(
                "Error in fallback response",
                extra={"error": str(e)},
            )
            raise  # Re-raise since this is the final fallback

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:  # noqa: C901
        """Main dispatch method with comprehensive error handling"""
        try:
            tenant_info = await self._extract_tenant_info(request)
            if not tenant_info:
                logger.warning("No tenant info found, using fallback response")
                return await self._fallback_response(request, call_next)

            start_time = time.time()
            user_agent = request.headers.get("user-agent", "unknown")
            session_id_from_header = self._extract_session_id(request)
            session_state = await self._get_or_create_session(session_id_from_header, tenant_info)

            # Read request body
            body = await request.body()
            request_data = None

            # Parse request body
            try:
                if body:
                    request_data = json.loads(body)
            except json.JSONDecodeError:
                logger.error(
                    "Failed to parse MCP request body, proceeding with normal request",
                    extra={
                        "body": body.decode() if body else "",
                        "user_agent": user_agent,
                        "session_id": session_state.session_id,
                    },
                )
                # If we can't parse the request body, just pass through
                return await self._fallback_response(request, call_next)

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
                try:
                    response.headers["mcp-session-id"] = session_state.session_id
                    response.headers["x-session-id"] = session_state.session_id
                except Exception as e:
                    logger.warning(
                        "Error setting session headers on response",
                        extra={"error": str(e)},
                    )
                return response

            # At this point, request_data is guaranteed to be a dict with method="tools/call"
            if request_data is None:  # type narrowing for the type checker
                logger.error("Request data is None, using fallback response")
                return await self._fallback_response(request, call_next)

            # Extract tool call information
            tool_name, tool_arguments, request_id = self._extract_tool_call_info(request_data)

            # Track start time for this tool call
            tool_call_start_time = datetime.now(timezone.utc)
            try:
                _tool_call_start_times[request_id] = tool_call_start_time
            except Exception as e:
                logger.warning(
                    "Error tracking tool call start time",
                    extra={"error": str(e), "request_id": request_id},
                )

            # Execute the request
            try:
                original_response = await call_next(request)
            except Exception as e:
                # Clean up start time tracking on error
                _tool_call_start_times.pop(request_id, None)
                logger.error(
                    "Error executing original request",
                    extra={"error": str(e), "request_id": request_id},
                )
                raise  # Re-raise since this is the actual request processing

            # Create callback to process response after streaming completes
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
                        try:
                            await session_state.register_tool_call(tool_call_data, tenant_info)
                        except Exception as e:
                            logger.warning(
                                "Error updating session state",
                                extra={"error": str(e), "session_id": session_state.session_id},
                            )

                    # Clean up start time tracking
                    _tool_call_start_times.pop(request_id, None)

                    # Run observer agent in background
                    if response_body:
                        try:
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
                                await self._run_observer_agent_background(observer_data)

                            add_background_task(run_observer_background())
                        except Exception as e:
                            logger.warning(
                                "Error setting up observer agent background task",
                                extra={"error": str(e), "session_id": session_state.session_id},
                            )
                            # Still try to update session even if observer fails
                            add_background_task(update_session())
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

                    # Log completion
                    self._log_tool_call_completion(
                        tool_call_data,
                        session_state.session_id,
                        original_response,
                        user_agent,
                        session_state,
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
                    logger.warning(
                        "Non-streaming response type, cannot observe - using original response",
                        extra={
                            "response_type": type(original_response).__name__,
                            "session_id": session_state.session_id,
                            "request_id": request_id,
                        },
                    )
                    response = original_response
            except Exception as e:
                logger.error(
                    "Error creating observing response, using original response",
                    extra={"error": str(e), "session_id": session_state.session_id},
                )
                response = original_response

            # Add session ID to response headers
            try:
                response.headers["mcp-session-id"] = session_state.session_id
                response.headers["x-session-id"] = session_state.session_id
            except Exception as e:
                logger.warning(
                    "Error setting session headers on final response",
                    extra={"error": str(e)},
                )

            return response

        except Exception as e:
            # If anything goes wrong in the middleware, log the error and fall back to normal request processing
            logger.error(
                "Unexpected error in MCP observability middleware, falling back to normal request processing",
                extra={"error": str(e)},
            )
            return await self._fallback_response(request, call_next)
