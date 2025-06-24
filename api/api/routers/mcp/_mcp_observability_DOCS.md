# MCP Observability Middleware Documentation

## Overview

The MCP (Model Control Protocol) Observability Middleware is a comprehensive system designed to monitor, track, and analyze tool calls made through the WorkflowAI MCP server. It provides session management, performance monitoring, and automated analysis of tool usage patterns.

## Architecture

The observability system consists of three main components:

1. **MCPObservabilityMiddleware** - HTTP middleware that intercepts and monitors requests
2. **SessionState** - Redis-backed session management for tracking tool call history
3. **Observer Agent** - Background AI agent that analyzes tool usage patterns

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   MCP Client    │    │   Observability  │    │   Session       │
│   (Claude, etc) │◄──►│   Middleware     │◄──►│   State         │
└─────────────────┘    └──────────────────┘    │   (Redis)       │
                                │               └─────────────────┘
                                ▼
                       ┌──────────────────┐
                       │   Observer       │
                       │   Agent          │
                       │   (Background)   │
                       └──────────────────┘
```

## Components

### 1. MCPObservabilityMiddleware

The core middleware class that intercepts all HTTP requests to the MCP server.

#### Key Responsibilities:
- **Authentication & Tenant Extraction**: Validates Bearer tokens and extracts tenant information
- **Session Management**: Creates or retrieves session state from Redis
- **Tool Call Detection**: Identifies MCP tool calls vs. other requests
- **Response Monitoring**: Wraps streaming responses to capture complete results
- **Background Processing**: Triggers observer agent analysis

#### Key Methods:

```python
async def _extract_tenant_info(request: Request) -> TenantData | None
```
Extracts tenant information from the Authorization header using the SecurityService.

```python
def _extract_session_id(request: Request) -> str | None
```
Looks for session ID in headers: `mcp-session-id` or `x-session-id`.

```python
async def _get_or_create_session(session_id: str | None, tenant: TenantData) -> SessionState
```
Retrieves existing session from Redis or creates a new one with UUID.

```python
def _is_mcp_tool_call(request_data: dict) -> bool
```
Identifies requests with `method: "tools/call"` as MCP tool calls.

```python
def _create_observing_streaming_response(...) -> StreamingResponse
```
Wraps streaming responses to collect complete body while streaming chunks to client.

### 2. SessionState

Redis-backed session management system with 1-hour expiration.

#### Data Structure:
```python
{
    "session_id": "uuid4-string",
    "created_at": "2024-01-01T12:00:00Z",
    "last_activity": "2024-01-01T12:05:00Z",
    "tool_calls": [
        {
            "tool_name": "list_models",
            "tool_arguments": {...},
            "request_id": "req-123",
            "started_at": "2024-01-01T12:00:00Z",
            "completed_at": "2024-01-01T12:00:02Z",
            "duration": 2.1,
            "result": "...",
            "user_agent": "Claude/1.0"
        }
    ]
}
```

#### Key Features:
- **Persistence**: Stored in Redis with automatic expiration
- **Tool Call History**: Maintains chronological list of all tool calls in session
- **Activity Tracking**: Updates last activity timestamp on each interaction
- **Fallback Handling**: Graceful degradation when Redis unavailable

### 3. Data Models

#### ToolCallData
Represents a completed tool call with comprehensive metadata:
```python
class ToolCallData(BaseModel):
    tool_name: str                    # e.g., "list_models", "search_runs"
    tool_arguments: dict[str, Any]    # Tool input parameters
    request_id: str                   # Unique request identifier
    duration: float                   # Execution time in seconds
    result: str | None                # Tool output/response
    started_at: datetime              # When tool call began
    completed_at: datetime            # When tool call finished
    user_agent: str                   # Client identifier
```

#### ObserverAgentData
Data structure passed to the background observer agent:
```python
class ObserverAgentData(BaseModel):
    tool_name: str                           # Current tool being analyzed
    previous_tool_calls: list[dict]          # Session history context
    tool_arguments: dict[str, Any]           # Current tool inputs
    tool_result: str                         # Current tool output
    duration_seconds: float                  # Performance metrics
    user_agent: str                          # Client information
    mcp_session_id: str                      # Session tracking
    request_id: str                          # Request correlation
    organization_name: str | None            # Tenant context
    user_email: str | None                   # User context
```

## Request Flow

### 1. Request Interception
```
Client Request → Middleware → Tenant Validation → Session Management
```

1. Middleware intercepts all HTTP requests
2. Extracts Bearer token and validates with SecurityService
3. Retrieves or creates session state in Redis
4. Determines if request is an MCP tool call

### 2. Tool Call Processing
```
Tool Call Detection → Timing Start → Request Execution → Response Wrapping
```

1. Identifies `method: "tools/call"` requests
2. Extracts tool name, arguments, and request ID
3. Records start time and executes original request
4. Wraps streaming response for result capture

### 3. Response Processing
```
Streaming Response → Result Capture → Session Update → Observer Agent → Logging
```

1. Streams response chunks to client in real-time
2. Collects complete response body when streaming finishes
3. Creates ToolCallData with performance metrics
4. Updates Redis session state with new tool call
5. Triggers background observer agent analysis
6. Logs completion with structured data

### 4. Background Analysis
```
Observer Agent → Pattern Analysis → Performance Insights → Recommendations
```

The observer agent runs asynchronously to analyze:
- Tool usage patterns and sequences
- Performance characteristics and bottlenecks
- Error patterns and failure modes
- Optimization opportunities

## Session Management

### Session Creation
- New sessions get UUID4 identifiers
- Stored in Redis with 1-hour TTL
- Headers added to response: `mcp-session-id`, `x-session-id`

### Session Persistence
- Redis key format: `mcp_session:{tenant}:{session_id}`
- Automatic expiration prevents memory leaks
- Graceful fallback when Redis unavailable

### Session Continuity
- Clients can pass session ID in headers
- Existing sessions extend TTL on activity
- Tool call history maintained across requests

## Error Handling

The middleware implements comprehensive error handling:

### Fallback Strategy
```python
async def _fallback_response(self, request: Request, call_next) -> Response:
    """Fallback when middleware fails - pass through normally"""
```

### Error Scenarios:
1. **Redis Unavailable**: Creates in-memory fallback session
2. **JSON Parse Errors**: Logs error and passes request through
3. **Tenant Authentication Fails**: Returns 401 or falls back
4. **Observer Agent Failures**: Logged but don't block main request
5. **Session Update Errors**: Logged as warnings, request continues

### Graceful Degradation
- Core MCP functionality never blocked by observability failures
- Observability features degrade gracefully when dependencies unavailable
- Detailed error logging for debugging and monitoring

## Configuration

### Session Expiration
```python
SESSION_EXPIRATION_SECONDS = 60 * 60  # 1 hour
```

### Redis Integration
- Uses `shared_redis_client` from core utilities
- Automatic serialization/deserialization of session data
- Connection pooling and error handling built-in

## Integration

### FastMCP Integration
```python
def mcp_http_app():
    custom_middleware = [
        Middleware(MCPObservabilityMiddleware),
    ]
    return _mcp.http_app(path="/", middleware=custom_middleware)
```


