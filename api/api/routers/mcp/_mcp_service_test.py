# pyright: reportPrivateUsage=false
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from api.routers.mcp._mcp_service import MCPService
from core.domain.documentation_section import DocumentationSection
from core.domain.tenant_data import PublicOrganizationData


@pytest.fixture
def mcp_service():
    """Create a MCPService instance for testing search_documentation."""
    return MCPService(
        storage=Mock(),
        ai_engineer_service=Mock(),
        runs_service=Mock(),
        versions_service=Mock(),
        models_service=Mock(),
        task_deployments_service=Mock(),
        user_email=None,
        tenant=PublicOrganizationData(slug="test-tenant"),
    )


class TestMCPServiceSearchDocumentation:
    @patch("api.routers.mcp._mcp_service.DocumentationService")
    async def test_search_documentation_query_mode_success(
        self,
        mock_documentation_service_class: Any,
        mcp_service: MCPService,
    ):
        """Test search_documentation in query mode with successful results."""
        # Arrange
        mock_service = Mock()
        mock_documentation_service_class.return_value = mock_service

        mock_sections = [
            DocumentationSection(
                title="getting-started.mdx",
                content="This is a comprehensive guide to get started with WorkflowAI. Follow these detailed steps to create your first agent and understand the platform's capabilities.",
            ),
            DocumentationSection(
                title="api-auth.mdx",
                content="Authentication is required for all API calls. Use Bearer tokens with your API key to authenticate requests.",
            ),
        ]
        mock_service.get_relevant_doc_sections = AsyncMock(return_value=mock_sections)

        # Act
        result = await mcp_service.search_documentation(query="how to get started")

        # Assert
        assert result.success is True
        assert result.data is not None
        assert result.data.query_results is not None
        search_results = result.data.query_results
        assert len(search_results) == 2
        # TODO: should likely be getting-started without the .mdx extension ?
        assert search_results[0].source_page == "getting-started.mdx"
        assert "get started with WorkflowAI" in search_results[0].content_snippet
        assert search_results[1].source_page == "api-auth.mdx"
        assert "Authentication is required" in search_results[1].content_snippet
        assert result.message and "Successfully found relevant documentation sections" in result.message

    @patch("api.routers.mcp._mcp_service.DocumentationService")
    async def test_search_documentation_page_mode_success(
        self,
        mock_documentation_service_class: Any,
        mcp_service: MCPService,
    ):
        """Test search_documentation in page mode with existing page."""
        # Arrange
        mock_service = Mock()
        mock_documentation_service_class.return_value = mock_service

        mock_sections = [
            DocumentationSection(
                title="getting-started.mdx",
                content="Complete getting started guide content here with detailed instructions...",
            ),
        ]
        mock_service.get_documentation_by_path = AsyncMock(return_value=mock_sections)

        # Act
        result = await mcp_service.search_documentation(page="getting-started.mdx")

        # Assert
        assert result.success is True
        assert result.data is not None
        assert result.data.page_content == "Complete getting started guide content here with detailed instructions..."
        assert result.message == "Retrieved content for page: getting-started.mdx"

    @patch("api.routers.mcp._mcp_service.DocumentationService")
    async def test_search_documentation_page_mode_not_found(
        self,
        mock_documentation_service_class: Any,
        mcp_service: MCPService,
    ):
        """Test search_documentation in page mode with non-existent page."""
        # Arrange
        mock_service = Mock()
        mock_documentation_service_class.return_value = mock_service

        # Mock get_documentation_by_path to return empty list (page not found)
        mock_service.get_documentation_by_path = AsyncMock(return_value=[])

        # Mock get_all_doc_sections for available pages listing
        mock_sections = [
            DocumentationSection(title="existing1.mdx", content="content1"),
            DocumentationSection(title="existing2.mdx", content="content2"),
        ]
        mock_service.get_all_doc_sections = AsyncMock(return_value=mock_sections)

        # Act
        result = await mcp_service.search_documentation(page="non-existent.mdx")

        # Assert
        assert result.success is False
        assert "Page 'non-existent.mdx' not found" in result.error  # type: ignore
        assert "Available pages: existing1.mdx, existing2.mdx" in result.error  # type: ignore

    @patch("api.routers.mcp._mcp_service.DocumentationService")
    async def test_search_documentation_page_mode_many_available_pages(
        self,
        mock_documentation_service_class: Any,
        mcp_service: MCPService,
    ):
        """Test search_documentation limits available pages list when many exist."""
        # Arrange
        mock_service = Mock()
        mock_documentation_service_class.return_value = mock_service

        # Mock get_documentation_by_path to return empty list (page not found)
        mock_service.get_documentation_by_path = AsyncMock(return_value=[])

        # Create more than 10 sections to test truncation
        mock_sections = [DocumentationSection(title=f"page{i}.mdx", content=f"content{i}") for i in range(15)]
        mock_service.get_all_doc_sections = AsyncMock(return_value=mock_sections)

        # Act
        result = await mcp_service.search_documentation(page="non-existent.mdx")

        # Assert
        assert result.success is False
        assert "Page 'non-existent.mdx' not found" in result.error  # type: ignore

    async def test_search_documentation_both_parameters(self, mcp_service: MCPService):
        """Test search_documentation with both parameters (should fail)."""
        # Act
        result = await mcp_service.search_documentation(query="test", page="test.mdx")

        # Assert
        assert result.success is False
        assert "Use either 'query' OR 'page' parameter, not both" in result.error  # type: ignore

    async def test_search_documentation_no_parameters(self, mcp_service: MCPService):
        """Test search_documentation with no parameters (should fail)."""
        # Act
        result = await mcp_service.search_documentation()

        # Assert
        assert result.success is False
        assert "Provide either 'query' or 'page' parameter" in result.error  # type: ignore

    @patch("api.routers.mcp._mcp_service.DocumentationService")
    async def test_search_documentation_query_mode_exception(
        self,
        mock_documentation_service_class: Any,
        mcp_service: MCPService,
    ):
        """Test search_documentation handles exceptions in query mode."""
        # Arrange
        mock_service = Mock()
        mock_documentation_service_class.return_value = mock_service
        mock_service.get_relevant_doc_sections = AsyncMock(side_effect=Exception("LLM service unavailable"))

        # Act
        with pytest.raises(Exception):
            await mcp_service.search_documentation(query="test")

    @patch("api.routers.mcp._mcp_service.DocumentationService")
    async def test_search_documentation_page_mode_exception(
        self,
        mock_documentation_service_class: Any,
        mcp_service: MCPService,
    ):
        """Test search_documentation handles exceptions in page mode."""
        # Arrange
        mock_service = Mock()
        mock_documentation_service_class.return_value = mock_service
        mock_service.get_documentation_by_path = AsyncMock(side_effect=Exception("File system error"))

        # Act
        with pytest.raises(Exception):
            await mcp_service.search_documentation(page="test.mdx")
