from typing import Any

from core.domain.tool import CustomTool, Tool
from core.runners.workflowai.workflowai_runner import WorkflowAIRunner
from core.storage.backend_storage import BackendStorage


class ToolsService:
    def __init__(self, storage: BackendStorage):
        self.storage = storage

    async def list_tools(self) -> list[CustomTool]:
        return await self.storage.tools.list_tools()

    async def get_tool_by_id(self, id: str) -> CustomTool:
        return await self.storage.tools.get_tool_by_id(id)

    async def create_tool(self, name: str, description: str, parameters: dict[str, Any]) -> CustomTool:
        return await self.storage.tools.create_tool(name, description, parameters)

    async def update_tool(self, id: str, name: str, description: str, parameters: dict[str, Any]) -> CustomTool:
        return await self.storage.tools.update_tool(id, name, description, parameters)

    async def delete_tool(self, id: str) -> None:
        await self.storage.tools.delete_tool(id)

    @classmethod
    def hosted_tools(cls) -> list[Tool]:
        return [d.definition for d in WorkflowAIRunner.internal_tools.values()]
