from typing import Any, AsyncIterator

from pydantic import BaseModel

from api.services.versions import VersionsService
from core.agents.tool_call_result_preview_agent import ToolCallResultPreviewAgentInput, tool_call_result_preview_agent
from core.domain.agent_run import AgentRun
from core.domain.tool import Tool
from core.runners.workflowai.internal_tool import InternalTool
from core.storage import ObjectNotFoundException
from core.tools import ToolKind


class ToolCallResultPreviewResponse(BaseModel):
    tool_call_result_preview_str: str | None = None
    tool_call_result_preview_json: dict[str, Any] | None = None


class ToolCallService:
    async def stream_tool_call_result_preview(
        self,
        run: AgentRun,
        version: VersionsService.EnrichedVersion,
    ) -> AsyncIterator[ToolCallResultPreviewResponse]:
        if not run.tool_call_requests:
            raise ObjectNotFoundException(
                "Agent run has no tool calls, can't generate tool call result preview",
                extras={"run_id": run.id},
            )

        # TODO: support mulitple tool calls in the future
        tool_call_request = run.tool_call_requests[0]

        if not version.group.properties.enabled_tools:
            raise ObjectNotFoundException(
                "Agent version has no enabled tools, can't generate tool call result preview",
                extras={"version_id": version.group.id},
            )

        tool_definition = next(
            (tool for tool in version.group.properties.enabled_tools if tool.name == tool_call_request.tool_name),
            None,
        )

        if not tool_definition:
            raise ObjectNotFoundException(
                "Tool definition not found",
                extras={"tool_name": tool_call_request.tool_name},
            )

        if type(tool_definition) is Tool:
            tool_definition_payload = tool_definition.model_dump_json()
        elif type(tool_definition) is ToolKind:
            tool_definition_payload = InternalTool.from_tool_kind(tool_definition).definition.model_dump_json()
        else:
            raise ValueError(f"Unexpected tool definition type: {type(tool_definition)}")

        async for chunk in tool_call_result_preview_agent.stream(
            ToolCallResultPreviewAgentInput(
                tool_name=tool_call_request.tool_name,
                tool_description=tool_definition_payload,
                tool_input=tool_call_request.tool_input_dict,
            ),
        ):
            yield ToolCallResultPreviewResponse(
                tool_call_result_preview_str=chunk.output.example_tool_output_string,
                tool_call_result_preview_json=chunk.output.example_tool_output_json,
            )
