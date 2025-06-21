from fastapi import APIRouter

from api.schemas.hosted_tools_schema import HostedToolsListResponse
from api.services.hosted_tools_service import HostedToolsService

router = APIRouter(prefix="/v1/tools")


@router.get("/hosted", response_model=HostedToolsListResponse)
async def list_hosted_tools() -> HostedToolsListResponse:
    """
    Get a list of all available hosted tools.

    Returns a sorted list of WorkflowAI's built-in tools including web search,
    browser tools, and others. Each tool includes its name (handle) and description.

    Hosted tools require no setup or custom code - they work out of the box.

    Read the documentation about hosted tools via our:
    - MCP tool search_documentation(page=/agents/tools)
    - docs.workflowai.com/agents/tools
    """
    service = HostedToolsService()
    return await service.list_hosted_tools()
