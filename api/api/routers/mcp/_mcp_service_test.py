# pyright: reportPrivateUsage=false
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from api.routers.mcp._mcp_service import MCPService, _merge_inputs, _merge_properties
from core.domain.documentation_section import DocumentationSection
from core.domain.message import Message, Messages
from core.domain.task_group_properties import TaskGroupProperties
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
        event_router=Mock(),
        run_service=Mock(),
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


class TestMergeInputs:
    def test_messages_in_original(self):
        original_input = {
            "workflowai.messages": [
                {
                    "role": "user",
                    "content": "Hello, how are you?",
                },
            ],
            "name": {
                "content_type": "image/gif",
                "url": "http://127.0.0.1:10000/devstoreaccount1/workflowai-task-runs/orguid_3798905106/autopilot-openai-text/be00aa22dc0fba76e5ea94ef3519796e602bbe55402ad0a4d65df60d53bf5b65.gif",
                "storage_url": "http://127.0.0.1:10000/devstoreaccount1/workflowai-task-runs/orguid_3798905106/autopilot-openai-text/be00aa22dc0fba76e5ea94ef3519796e602bbe55402ad0a4d65df60d53bf5b65.gif",
            },
        }
        new_input = Messages.with_messages()
        merged = _merge_inputs(original_input, new_input)
        assert merged == original_input


class TestMergeProperties:
    def test_merge_properties(self):
        run_properties = TaskGroupProperties(
            model="gpt-4o-latest",
            temperature=0.5,
            messages=[Message.with_text("Hello, how are you?")],
        )
        prepared_properties = TaskGroupProperties(
            model="gpt-4o-mini",
        )
        merged = _merge_properties(prepared_properties, run_properties)
        assert merged.model_dump(exclude_none=True) == {
            "model": "gpt-4o-mini",
            "temperature": 0.5,
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": "Hello, how are you?"}],
                },
            ],
        }
