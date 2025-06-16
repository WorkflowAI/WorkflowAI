# MCP Tool Error Analysis and Fix

## The Error

The error occurred when calling the `ask_ai_engineer` MCP tool:

```
Error calling tool 'ask_ai_engineer': 1 validation error for call[ask_ai_engineer]
request
  Input should be a valid dictionary or instance of AskAIEngineerRequest [type=model_type, input_value='{\n  "agent_id": "new",\...gent on WorkflowAI."\n}', input_type=str]
```

## Root Cause

The `ask_ai_engineer` MCP tool was defined with a Pydantic model parameter:

```python
async def ask_ai_engineer(request: AskAIEngineerRequest) -> MCPToolReturn:
```

However, the MCP framework was passing a JSON string instead of a parsed dictionary or Pydantic model instance. This caused a Pydantic validation error because:

- **Expected**: A dictionary or `AskAIEngineerRequest` instance
- **Received**: A JSON string (`input_type=str`)
- **Input value**: `'{\n  "agent_id": "new",\n  "message": "How do I create an AI agent?..."\n}'`

## The Problem Pattern

Looking at other MCP tools in the same file, they all follow a consistent pattern of using simple typed parameters with `Annotated` descriptions:

```python
async def list_agents(
    from_date: Annotated[str, "ISO date string to filter stats from..."],
) -> MCPToolReturn:

async def fetch_run_details(
    agent_id: Annotated[str | None, "The id of the user's agent..."] = None,
    run_id: Annotated[str | None, "The id of the run..."] = None,
    run_url: Annotated[str | None, "The url of the run..."] = None,
) -> MCPToolReturn:
```

The `ask_ai_engineer` tool was the only one expecting a complex Pydantic model, which was inconsistent with the MCP framework's parameter handling.

## The Solution

Changed the `ask_ai_engineer` function to use simple typed parameters with `Annotated` descriptions, matching the pattern used by other MCP tools:

```python
async def ask_ai_engineer(
    agent_id: Annotated[str, "The id of the user's agent..."],
    message: Annotated[str, "Your message to the AI engineer..."],
    agent_schema_id: Annotated[int | None, "The schema ID..."] = None,
    user_programming_language: Annotated[str | None, "The programming language..."] = None,
    user_code_extract: Annotated[str | None, "The code you are working on..."] = None,
) -> MCPToolReturn:
```

## Changes Made

1. **Modified function signature**: Changed from expecting a `AskAIEngineerRequest` model to individual typed parameters
2. **Updated parameter passing**: Changed the function body to pass individual parameters instead of accessing them from a request object
3. **Removed unused class**: Deleted the `AskAIEngineerRequest` Pydantic model class since it's no longer needed

## Files Modified

- `api/api/routers/mcp/mcp_server.py`: Updated the `ask_ai_engineer` function signature and removed the `AskAIEngineerRequest` class

## Result

The MCP tool should now work correctly with JSON input, as the framework can properly map JSON fields to individual function parameters rather than trying to parse a JSON string into a Pydantic model.