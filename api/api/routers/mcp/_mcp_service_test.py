# pyright: reportPrivateUsage=false
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from api.routers.mcp._mcp_service import MCPService
from core.domain.documentation_section import DocumentationSection


class TestMCPServiceExtractAgentIdAndRunId:
    @pytest.fixture
    def mcp_service(self):
        """Create a MCPService instance for testing."""
        # We only need to test the URL parsing method, so we can pass None for dependencies
        return MCPService(
            storage=Mock(),
            ai_engineer_service=Mock(),
            runs_service=Mock(),
            versions_service=Mock(),
            models_service=Mock(),
            task_deployments_service=Mock(),
            user_email=None,
            tenant_slug=None,
        )

    @pytest.mark.parametrize(
        "url,expected_agent,expected_run",
        [
            # Standard format from original docstring example
            (
                "https://workflowai.com/workflowai/agents/classify-email-domain/runs/019763ae-ba9f-70a9-8d44-5a626c82e888",
                "classify-email-domain",
                "019763ae-ba9f-70a9-8d44-5a626c82e888",
            ),
            # With trailing slash
            (
                "https://workflowai.com/workflowai/agents/test-agent/runs/test-run-id/",
                "test-agent",
                "test-run-id",
            ),
            # With query parameters
            (
                "https://workflowai.com/workflowai/agents/my-agent/runs/my-run?param=value&other=123",
                "my-agent",
                "my-run",
            ),
            # With fragment
            (
                "https://workflowai.com/workflowai/agents/agent-with-fragment/runs/run-with-fragment#section",
                "agent-with-fragment",
                "run-with-fragment",
            ),
            # With query and fragment
            (
                "https://workflowai.com/workflowai/agents/complex-agent/runs/complex-run?param=value#fragment",
                "complex-agent",
                "complex-run",
            ),
            # Different base path
            (
                "https://example.com/other/path/agents/different-agent/runs/different-run",
                "different-agent",
                "different-run",
            ),
            # With hyphens and underscores
            (
                "https://workflowai.com/agents/my_agent-with-special_chars/runs/run_id-with-hyphens_123",
                "my_agent-with-special_chars",
                "run_id-with-hyphens_123",
            ),
            # Different valid formats
            ("http://workflowai.com/agents/simple/runs/123", "simple", "123"),
            ("https://app.workflowai.com/org/agents/org-agent/runs/org-run", "org-agent", "org-run"),
            ("https://workflowai.com/v1/agents/versioned/runs/v1-run", "versioned", "v1-run"),
            # Complex IDs with special characters
            (
                "https://workflowai.com/agents/agent.with.dots/runs/run-with-dashes",
                "agent.with.dots",
                "run-with-dashes",
            ),
            ("https://workflowai.com/agents/agent_123/runs/run_456", "agent_123", "run_456"),
            # Long UUIDs
            (
                "https://workflowai.com/agents/my-agent/runs/01234567-89ab-cdef-0123-456789abcdef",
                "my-agent",
                "01234567-89ab-cdef-0123-456789abcdef",
            ),
            # No protocol (still valid pattern)
            ("example.com/agents/test/runs/123", "test", "123"),
            # Localhost with query parameter
            (
                "http://localhost:3000/workflowai/agents/sentiment/2/runs?page=0&taskRunId=019763a5-12a7-73b7-9b0c-e6413d2da52f",
                "sentiment",
                "019763a5-12a7-73b7-9b0c-e6413d2da52f",
            ),
        ],
    )
    def test_extract_agent_id_and_run_id_valid_cases(
        self,
        mcp_service: MCPService,
        url: str,
        expected_agent: str,
        expected_run: str,
    ):
        """Parametrized test for various valid URL formats."""
        agent_id, run_id = mcp_service._extract_agent_id_and_run_id(url)  # pyright: ignore[reportPrivateUsage]
        assert agent_id == expected_agent
        assert run_id == expected_run

    @pytest.mark.parametrize(
        "invalid_url,expected_error_pattern",
        [
            # Empty and None inputs
            ("", "run_url must be a non-empty string"),
            # Too short URLs
            ("https://example.com", "Invalid run URL format"),
            ("https://example.com/agents", "Invalid run URL format"),
            ("https://example.com/agents/test", "Invalid run URL format"),
            ("https://example.com/short", "Invalid run URL format"),
            # Missing agents keyword
            ("https://example.com/tasks/my-task/executions/run-123", "Invalid run URL format"),
            # Missing runs keyword or wrong pattern
            ("https://example.com/agents/my-agent/executions/run-123", "Invalid run URL format"),
            ("https://example.com/agents/my-agent/tasks/run-123", "Invalid run URL format"),
            ("https://example.com/agents/my-agent/settings", "Invalid run URL format"),
            # Empty components
            ("https://example.com/agents//runs/run-123", "Invalid run URL format"),
            ("https://example.com/agents/agent/runs/", "Invalid run URL format"),
            # Agents at end without proper structure
            ("https://example.com/path/agents", "Invalid run URL format"),
            # Runs at end without run ID
            ("https://example.com/agents/my-agent/runs", "Invalid run URL format"),
            # Malformed URLs
            ("not-a-url", "Invalid run URL format"),
            ("//invalid//url//format", "Invalid run URL format"),
        ],
    )
    def test_extract_agent_id_and_run_id_parametrized_invalid_cases(
        self,
        mcp_service: MCPService,
        invalid_url: str,
        expected_error_pattern: str,
    ):
        """Parametrized test for various invalid URL formats."""
        with pytest.raises(ValueError, match=expected_error_pattern):
            mcp_service._extract_agent_id_and_run_id(invalid_url)  # pyright: ignore[reportPrivateUsage]


class TestMCPServiceSearchDocumentation:
    @pytest.fixture
    def mcp_service(self):
        """Create a MCPService instance for testing search_documentation."""
        return MCPService(
            storage=Mock(),
            ai_engineer_service=Mock(),
            runs_service=Mock(),
            versions_service=Mock(),
            models_service=Mock(),
            task_deployments_service=Mock(),
            user_email=None,
            tenant_slug=None,
        )

    @pytest.mark.asyncio
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
        assert "search_results" in result.data
        search_results = result.data["search_results"]
        assert len(search_results) == 2
        assert search_results[0]["source_page"] == "getting-started.mdx"
        assert "get started with WorkflowAI" in search_results[0]["content_snippet"]
        assert search_results[1]["source_page"] == "api-auth.mdx"
        assert "Authentication is required" in search_results[1]["content_snippet"]
        assert "Successfully found relevant documentation sections" in result.messages[0]  # type: ignore

    @pytest.mark.asyncio
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
        assert "page_content" in result.data
        assert (
            result.data["page_content"] == "Complete getting started guide content here with detailed instructions..."
        )
        assert result.messages == ["Retrieved content for page: getting-started.mdx"]

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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
        assert "..." in result.error  # type: ignore  # Should show truncation indicator

    @pytest.mark.asyncio
    async def test_search_documentation_both_parameters(self, mcp_service: MCPService):
        """Test search_documentation with both parameters (should fail)."""
        # Act
        result = await mcp_service.search_documentation(query="test", page="test.mdx")

        # Assert
        assert result.success is False
        assert "Use either 'query' OR 'page' parameter, not both" in result.error  # type: ignore

    @pytest.mark.asyncio
    async def test_search_documentation_no_parameters(self, mcp_service: MCPService):
        """Test search_documentation with no parameters (should fail)."""
        # Act
        result = await mcp_service.search_documentation()

        # Assert
        assert result.success is False
        assert "Provide either 'query' or 'page' parameter" in result.error  # type: ignore

    @pytest.mark.asyncio
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
        result = await mcp_service.search_documentation(query="test")

        # Assert
        assert result.success is False
        assert "Search failed: LLM service unavailable" in result.error  # type: ignore

    @pytest.mark.asyncio
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
        result = await mcp_service.search_documentation(page="test.mdx")

        # Assert
        assert result.success is False
        assert "Failed to retrieve page: File system error" in result.error  # type: ignore
