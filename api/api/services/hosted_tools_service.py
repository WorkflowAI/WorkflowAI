from api.schemas.hosted_tools_schema import HostedToolResponse, HostedToolsListResponse
from core.runners.workflowai.workflowai_runner import WorkflowAIRunner


class HostedToolsService:
    """Service for managing hosted tools information."""

    def __init__(self):
        # Use the existing internal_tools mapping as the source of truth
        self._internal_tools = WorkflowAIRunner.internal_tools

    async def list_hosted_tools(self) -> HostedToolsListResponse:
        """
        Get all available hosted tools sorted by name.

        Returns:
            HostedToolsListResponse: List of hosted tools with metadata
        """
        tools: list[HostedToolResponse] = []

        for tool_kind, internal_tool in self._internal_tools.items():
            tool_response = HostedToolResponse(
                name=tool_kind.value,  # e.g., "@search-google"
                description=internal_tool.definition.description or "No description available",
            )
            tools.append(tool_response)

        # Sort tools by name for consistent ordering
        tools.sort(key=lambda t: t.name)

        return tools
