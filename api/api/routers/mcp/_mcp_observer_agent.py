import json
import os
from datetime import datetime
from typing import Any, Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, Field


class MCPToolCallObserverOutput(BaseModel):
    success: bool = Field(description="Whether the feedback was processed successfully")
    error_criticity: Literal["low", "medium", "high"] | None = Field(
        description="The criticity of the error, if any",
        default=None,
    )
    error_analysis: str | None = Field(
        description="A detailed analysis of the error, if any",
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
    user_email: str | None = None,
) -> MCPToolCallObserverOutput | None:
    system_message = """You are an MCP tool call observer agent. Overall, our goal is to be the warrant of the quality of interaction between MTP clients (for example, Cursor, etc.) and our MTP server.
    Assess if the tool call was successful and if not, and if not, provide a summary of the error and the error criticity.
    """

    user_message = """Here is the tool call:
    Current date and time: {{current_date_and_time}}
    Previous tool calls: {{previous_tool_calls}}
    New tool call: {{new_tool_call}}
    MCP session ID: {{mcp_session_id}}
    """

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
        metadata["organization_name"] = organization_name
    if user_email:
        metadata["user_email"] = user_email
    if user_agent:
        metadata["mcp_client_user_agent"] = user_agent
    # TODO: add some mcp-session_id to be able to fetch the full MCP conversation too

    response = await client.beta.chat.completions.parse(
        model="gemini-2.0-flash-latest",
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
