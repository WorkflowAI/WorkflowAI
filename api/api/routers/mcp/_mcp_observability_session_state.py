from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ToolCallData(BaseModel):
    """Data about a completed tool call"""
    
    tool_name: str = Field(description="Name of the tool that was called")
    tool_arguments: dict[str, Any] = Field(description="Arguments passed to the tool")
    request_id: str = Field(description="Unique ID for this tool call request")
    duration: float = Field(description="Duration of the tool call in seconds")
    result: Any = Field(description="Result returned by the tool")
    started_at: datetime = Field(description="When the tool call started")
    completed_at: datetime = Field(description="When the tool call completed")
    user_agent: str = Field(description="User agent string from the request")


class SessionState:
    """Tracks the state of an MCP session including tool calls"""
    
    def __init__(self, session_id: str, user_agent: str):
        self.session_id = session_id
        self.user_agent = user_agent
        self.created_at = datetime.now(timezone.utc)
        self.last_activity_at = self.created_at
        self.tool_calls: list[ToolCallData] = []
        
    def register_tool_call(self, tool_call_data: ToolCallData) -> None:
        """Register a completed tool call in the session"""
        self.tool_calls.append(tool_call_data)
        self.last_activity_at = datetime.now(timezone.utc)
        
    @property
    def total_tool_calls(self) -> int:
        """Total number of tool calls in this session"""
        return len(self.tool_calls)
        
    @property
    def total_duration(self) -> float:
        """Total duration of all tool calls in this session"""
        return sum(call.duration for call in self.tool_calls)
        
    @property
    def unique_tools_used(self) -> set[str]:
        """Set of unique tool names used in this session"""
        return {call.tool_name for call in self.tool_calls}


class ObserverAgentData(BaseModel):
    """Data passed to the observer agent for analysis"""
    
    tool_name: str = Field(description="Name of the tool that was called")
    previous_tool_calls: list[ToolCallData] = Field(description="Previous tool calls in the session")
    tool_arguments: dict[str, Any] = Field(description="Arguments passed to the tool")
    tool_result: Any = Field(description="Result returned by the tool")  
    duration_seconds: float = Field(description="Duration of the tool call in seconds")
    user_agent: str = Field(description="User agent string from the request")
    mcp_session_id: str = Field(description="MCP session identifier")
    request_id: str = Field(description="Unique ID for this tool call request")
    organization_name: str | None = Field(description="Organization name from authentication", default=None)
    user_email: str | None = Field(description="User email from authentication", default=None)