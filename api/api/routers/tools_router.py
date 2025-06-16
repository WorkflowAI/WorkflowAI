from fastapi import APIRouter, HTTPException

from api.dependencies.services import ToolsServiceDep
from api.schemas.tools_schema import ToolParamsRequest, ToolResponse
from core.storage import ObjectNotFoundException

router = APIRouter(prefix="/agents/{agent_id}/tools")


@router.get("")
async def list_tools(tools_service: ToolsServiceDep) -> list[ToolResponse]:
    tools = await tools_service.list_tools()
    return [ToolResponse.from_domain(tool) for tool in tools]


@router.get("/{id}")
async def get_tool(id: str, tools_service: ToolsServiceDep) -> ToolResponse:
    try:
        tool = await tools_service.get_tool_by_id(id)
        return ToolResponse.from_domain(tool)
    except ObjectNotFoundException:
        raise HTTPException(status_code=404, detail=f"Tool with ID '{id}' not found")


@router.post("")
async def create_tool(tool: ToolParamsRequest, tools_service: ToolsServiceDep) -> ToolResponse:
    try:
        created_tool = await tools_service.create_tool(tool.name, tool.description, tool.input_schema)
        return ToolResponse.from_domain(created_tool)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{id}")
async def update_tool(
    id: str,
    tool: ToolParamsRequest,
    tools_service: ToolsServiceDep,
) -> ToolResponse:
    try:
        updated_tool = await tools_service.update_tool(id, tool.name, tool.description, tool.input_schema)
        return ToolResponse.from_domain(updated_tool)
    except ObjectNotFoundException:
        raise HTTPException(status_code=404, detail=f"Tool with ID '{id}' not found")


@router.delete("/{id}", status_code=204)
async def delete_tool(id: str, tools_service: ToolsServiceDep):
    try:
        await tools_service.delete_tool(id)
    except ObjectNotFoundException:
        raise HTTPException(status_code=404, detail=f"Tool with ID '{id}' not found")
