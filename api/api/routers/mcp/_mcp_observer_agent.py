import json
import os
from datetime import datetime
from typing import Any, Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, Field


class MCPToolCallObserverOutput(BaseModel):
    success: bool = Field(description="Whether the feedback was processed successfully")

    class ErrorAnalysis(BaseModel):
        explanation: str = Field(
            description="A detailed analysis of the error, if any. To only fill when success is False",
        )
        origin: Literal["mcp_client", "our_mcp_server"] = Field(
            description="The origin of the error, if any. 'mcp_client' are typically wrong arguments passed etc, and are less critical. 'our_mcp_server' are more serious errors, like the server not being able to process the request. To only fill when success is False",
        )
        criticity: Literal["low", "medium", "high", "unsure"] = Field(
            description="The criticity of the error, if any. To only fill when success is False",
        )

    error_analysis: ErrorAnalysis | None = Field(
        description="The error analysis, if any. To only fill when success is False",
        default=None,
    )


async def mcp_tool_call_observer_agent(
    tool_name: str,
    previous_tool_calls: list[dict[str, Any]],
    tool_arguments: dict[str, Any],
    tool_result: str | dict[str, Any],
    duration_seconds: float,
    mcp_session_id: str | None,
    user_agent: str | None = None,
    organization_name: str | None = None,
) -> MCPToolCallObserverOutput | None:
    system_message = """You are an MCP tool call observer agent. Overall, our goal is to be the guarantor of the quality of interaction between MCP clients (for example, Cursor, etc.) and WorkflowAI's MCP server.
    Assess if the 'new_tool_call'(and ONLY the 'new_tool_call', not the 'previous_tool_calls', that are just provided for context) was successful and if not, provide an error analysis.
    """

    user_message = """Current date and time: {{current_date_and_time}}
Previous tool calls: {{previous_tool_calls}}
New tool call: {{new_tool_call}}
MCP session ID: {{mcp_session_id}}"""

    client = AsyncOpenAI(
        api_key=os.environ["WORKFLOWAI_API_KEY"],
        base_url=f"{os.environ['WORKFLOWAI_API_URL']}/v1",
    )

    # Build metadata for tracking
    metadata = {
        "agent_id": "mcp-tool-call-observer-agent",
        "duration_seconds": str(duration_seconds),
    }
    if organization_name:
        metadata["tenant"] = organization_name
    if user_agent:
        metadata["mcp_client_user_agent"] = user_agent
    if mcp_session_id:
        metadata["mcp_session_id"] = mcp_session_id
    # TODO: add some mcp-session_id to be able to fetch the full MCP conversation too

    response = await client.beta.chat.completions.parse(
        model="gpt-4.1-latest",  # Large context window (1M) and native structured generation.
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ],
        extra_body={
            "input": {
                "previous_tool_calls": json.dumps(previous_tool_calls, indent=2),
                "new_tool_call": {
                    "tool_name": tool_name,
                    "tool_arguments": json.dumps(tool_arguments, indent=2),
                    "tool_result": tool_result,
                    "duration_seconds": str(duration_seconds),
                    "user_agent": user_agent,
                },
                "current_date_and_time": datetime.now().isoformat(),
                "mcp_session_id": mcp_session_id,
            },
        },
        response_format=MCPToolCallObserverOutput,
        metadata=metadata,
        temperature=0.0,
    )

    return response.choices[0].message.parsed
