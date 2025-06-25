from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.services.tools_service import ToolsService
from core.domain.page import Page
from core.domain.tool import Tool

router = APIRouter(prefix="/v1/tools")


class HostedToolItem(BaseModel):
    """A tool hosted by WorkflowAI.
    To use a WorkflowAI hosted tool:
    - either refer to the tool name (e.g., '@search-google') in the first system message of
    the completion request
    - pass a tool with a corresponding name and no arguments in the `tools` argument of the completion request
    """

    name: str = Field(description="The tool handle/name (e.g., '@search-google')")
    description: str = Field(description="Description of what the tool does")

    @classmethod
    def from_tool(cls, tool: Tool):
        return cls(name=tool.name, description=tool.description or "")


@router.get("/hosted")
def list_hosted_tools() -> Page[HostedToolItem]:
    """
    Get a list of all available hosted tools.

    Returns a sorted list of WorkflowAI's built-in tools including web search,
    browser tools, and others. Each tool includes its name (handle) and description.

    Hosted tools require no setup or custom code - they work out of the box.

    Read the documentation about hosted tools via our:
    - MCP tool search_documentation(page=/agents/tools)
    - docs.workflowai.com/agents/tools
    """
    return Page(
        items=[HostedToolItem.from_tool(tool) for tool in ToolsService.hosted_tools()],
    )
