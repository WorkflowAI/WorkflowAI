import logging
import os
from datetime import datetime
from typing import Any

import openai
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ToolCallData(BaseModel):
    """Input data for the MCP Server Observer Agent"""

    tool_name: str = Field(description="Name of the MCP tool that was called")
    parameters: dict[str, Any] = Field(description="Parameters passed to the tool")
    result: dict[str, Any] | None = Field(description="Result returned by the tool, None if failed")
    execution_time_ms: float = Field(description="Time taken to execute the tool in milliseconds")
    success: bool = Field(description="Whether the tool execution was successful")
    error_message: str | None = Field(description="Error message if the tool failed, None if successful")
    timestamp: str = Field(description="ISO timestamp when the tool was called")
    tenant_slug: str | None = Field(description="Tenant/organization identifier")
    user_context: dict[str, Any] | None = Field(description="Additional user context if available")


class ToolCallAssessment(BaseModel):
    """Assessment and recommendations for a tool call"""

    overall_health: str = Field(
        description="Overall health assessment of the tool call",
        examples=["HEALTHY", "DEGRADED", "CRITICAL"],
    )

    success_status: bool = Field(
        description="Binary assessment of whether the execution went well",
    )

    performance_score: int = Field(
        description="Performance score from 1-10, considering execution time and efficiency",
        examples=[8],
    )

    error_analysis: str | None = Field(
        description="Analysis of any errors that occurred, None if no errors",
        examples=["Authentication failure due to invalid bearer token", "Rate limit exceeded for external API"],
    )

    recommendations: list[str] = Field(
        description="Specific recommendations for improvement",
        examples=[
            ["Implement exponential backoff for rate-limited calls", "Add input validation for required parameters"],
        ],
    )

    potential_issues: list[str] = Field(
        description="Potential issues or concerns identified",
        examples=[
            [
                "Slow response time may indicate performance degradation",
                "High parameter complexity could lead to user errors",
            ],
        ],
    )

    optimization_suggestions: list[str] = Field(
        description="Suggestions for optimization and better performance",
        examples=[
            ["Cache frequently requested data", "Implement request batching for bulk operations"],
        ],
    )

    summary: str = Field(
        description="Brief summary of the tool call analysis",
        examples=[
            "Tool executed successfully with good performance. Minor optimization opportunities identified for caching.",
        ],
    )


def analyze_mcp_tool_call(tool_call_data: ToolCallData, session_id: str | None = None) -> ToolCallAssessment | None:
    """
    Analyze an MCP tool call and provide assessment and recommendations

    Args:
        tool_call_data: Data about the tool call execution
        session_id: Optional session identifier for tracking related calls

    Returns:
        ToolCallAssessment: Analysis results or None if error
    """

    # Set up WorkflowAI API key
    client = openai.OpenAI(
        api_key=os.environ["WORKFLOWAI_API_KEY"],
        base_url=f"{os.environ['WORKFLOWAI_API_URL']}/v1",
    )

    # Define the agent messages
    messages = [  # type: ignore
        {
            "role": "system",
            "content": """You are an MCP (Model Context Protocol) server observer and analysis specialist. Your task is to analyze tool call executions and provide comprehensive assessments and recommendations.

For each tool call, you must:
1. Assess overall health (HEALTHY, DEGRADED, CRITICAL) based on success, performance, and error patterns
2. Evaluate performance considering execution time and complexity
3. Analyze any errors or failures in detail
4. Provide specific, actionable recommendations for improvement
5. Identify potential issues that might cause future problems
6. Suggest optimizations for better performance and reliability

Consider these factors in your analysis:
- Execution time relative to typical performance for similar operations
- Success/failure patterns and error types
- Parameter complexity and potential for user errors
- Resource utilization and efficiency
- Security and reliability concerns

Provide practical, implementable recommendations that can improve the MCP server experience.""",
        },
        {
            "role": "user",
            "content": """Please analyze this MCP tool call execution:

Tool Name: {{tool_name}}
Parameters: {{parameters}}
Result: {{result}}
Execution Time: {{execution_time_ms}}ms
Success: {{success}}
Error: {{error_message}}
Timestamp: {{timestamp}}
Tenant: {{tenant_slug}}
{% if session_id %}Session ID: {{session_id}}{% endif %}

Provide a comprehensive analysis including health assessment, performance evaluation, error analysis (if applicable), and specific recommendations for improvement.""",
        },
    ]

    try:
        completion = client.beta.chat.completions.parse(
            model="claude-3-5-sonnet-20241022",  # Good model for analysis tasks
            messages=messages,  # type: ignore
            response_format=ToolCallAssessment,
            extra_body={
                "input": {
                    "tool_name": tool_call_data.tool_name,
                    "parameters": str(tool_call_data.parameters),
                    "result": str(tool_call_data.result) if tool_call_data.result else "None",
                    "execution_time_ms": tool_call_data.execution_time_ms,
                    "success": tool_call_data.success,
                    "error_message": tool_call_data.error_message or "None",
                    "timestamp": tool_call_data.timestamp,
                    "tenant_slug": tool_call_data.tenant_slug or "unknown",
                    "session_id": session_id or "none",
                },
            },
            metadata={
                "agent_id": "mcp-server-observer",
                "tool_name": tool_call_data.tool_name,
                "session_id": session_id or "standalone",
                "analysis_timestamp": datetime.now().isoformat(),
                "tenant_slug": tool_call_data.tenant_slug or "",
            },
        )

        return completion.choices[0].message.parsed

    except Exception as e:
        logger.exception(
            "Error analyzing MCP tool call",
            extra={
                "tool_name": tool_call_data.tool_name,
                "session_id": session_id,
                "tenant_slug": tool_call_data.tenant_slug,
            },
            exc_info=e,
        )
        return None
