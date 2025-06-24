import pytest
from httpx import AsyncClient

from core.tools import ToolKind


class TestHostedToolsRouter:
    @pytest.mark.unauthenticated
    # It should work with or without auth
    @pytest.mark.parametrize("token", ["", "Bearer hello"])
    async def test_list_hosted_tools(self, test_api_client: AsyncClient, token: str):
        response = await test_api_client.get("/v1/tools/hosted", headers={"Authorization": token})
        assert response.status_code == 200
        items = response.json()["items"]
        for item in items:
            assert item["name"] in ToolKind
            assert "description" in item
            assert item["description"]
