# Removed the test for the private function _extract_doc_title as it's no longer used.
# pyright: reportPrivateUsage=false
# pyright: reportMissingTypeStubs=false
import logging
import os
import tempfile
from typing import NamedTuple
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from api.services.documentation_service import WORKFLOWAI_DOCS_URL, DocumentationService
from core.domain.documentation_section import DocumentationSection

API_DOCS_DIR = "api/docsv2"
EXPECTED_FILE_COUNT = 48


@patch("api.services.documentation_service.DocumentationService._LOCAL_DOCS_DIR", API_DOCS_DIR)
async def test_get_all_doc_sections_uses_real_files() -> None:
    """
    Tests that get_all_doc_sections correctly counts files in the actual api/docs directory.
    """
    # Arrange
    # Ensure the directory exists before running the test fully
    # Note: This assumes the test environment has access to the api/docs directory
    if not os.path.isdir(API_DOCS_DIR):
        pytest.skip(f"Real documentation directory not found at {API_DOCS_DIR}")

    service = DocumentationService()

    # Act
    doc_sections: list[DocumentationSection] = await service.get_all_doc_sections(mode="local")

    # Assert
    # Check that the correct number of sections were created based on the actual file count
    assert len(doc_sections) == EXPECTED_FILE_COUNT
    # Optionally, add basic checks like ensuring titles are non-empty strings
    for section in doc_sections:
        assert isinstance(section.file_path, str)
        assert len(section.file_path) > 0
        assert isinstance(section.content, str)
        # We don't check content length as some files might be empty


@pytest.fixture
def documentation_service() -> DocumentationService:
    """Fixture to provide a DocumentationService instance."""
    return DocumentationService()


@patch("api.services.documentation_service.pick_relevant_documentation_sections", new_callable=AsyncMock)
@patch.object(DocumentationService, "get_all_doc_sections")
async def test_get_relevant_doc_sections_success(
    mock_get_all_sections: MagicMock,
    mock_pick_relevant: AsyncMock,
    documentation_service: DocumentationService,
):
    """Tests get_relevant_doc_sections successfully filters sections."""
    all_sections = [
        DocumentationSection(file_path="section1.md", content="Content 1"),
        DocumentationSection(file_path="section2.md", content="Content 2"),
        DocumentationSection(file_path="security.md", content="Security Content"),
    ]
    mock_get_all_sections.return_value = all_sections

    # Mock the return value of pick_relevant_documentation_sections
    class MockPickOutput(NamedTuple):
        relevant_doc_sections: list[str]

    mock_pick_relevant.return_value = MockPickOutput(relevant_doc_sections=["security.md", "section1.md"])

    agent_instructions = "Focus on security."
    relevant_sections = await documentation_service.get_relevant_doc_sections([], agent_instructions)

    # Expected sections: Defaults + the ones identified as relevant
    expected_sections = [
        DocumentationSection(file_path="section1.md", content="Content 1"),
        DocumentationSection(file_path="security.md", content="Security Content"),
    ]

    # Convert to sets of tuples for order-independent comparison
    actual_section_tuples = {(s.file_path, s.content) for s in relevant_sections}
    expected_section_tuples = {(s.file_path, s.content) for s in expected_sections}

    assert actual_section_tuples == expected_section_tuples
    mock_get_all_sections.assert_called_once()
    mock_pick_relevant.assert_called_once()
    # You could add more specific assertions on the input to mock_pick_relevant if needed


@patch("api.services.documentation_service.pick_relevant_documentation_sections", new_callable=AsyncMock)
@patch.object(DocumentationService, "get_all_doc_sections")
async def test_get_relevant_doc_sections_pick_error(
    mock_get_all_sections: MagicMock,
    mock_pick_relevant: AsyncMock,
    documentation_service: DocumentationService,
):
    """Tests get_relevant_doc_sections falls back to all sections when pick_relevant_documentation_sections fails."""
    all_sections = [
        DocumentationSection(file_path="section1.md", content="Content 1"),
        DocumentationSection(file_path="section2.md", content="Content 2"),
        DocumentationSection(file_path="security.md", content="Security Content"),
    ]
    mock_get_all_sections.return_value = all_sections

    # Simulate an error during the picking process
    mock_pick_relevant.side_effect = Exception("LLM call failed")

    agent_instructions = "Focus on security."
    relevant_sections = await documentation_service.get_relevant_doc_sections([], agent_instructions)

    # Convert to sets of tuples for order-independent comparison
    actual_section_tuples = {(s.file_path, s.content) for s in relevant_sections}
    expected_section_tuples = {(s.file_path, s.content) for s in all_sections}

    assert actual_section_tuples == expected_section_tuples
    mock_get_all_sections.assert_called_once()
    mock_pick_relevant.assert_called_once()


async def test_get_documentation_by_path_with_existing_paths(documentation_service: DocumentationService):
    """Tests that get_documentation_by_path returns sections matching the provided paths."""
    sections = [
        DocumentationSection(file_path="a.md", content="A content"),
        DocumentationSection(file_path="b.md", content="B content"),
    ]
    # Patch get_all_doc_sections to return our dummy sections
    with patch.object(DocumentationService, "_get_all_doc_sections_local", return_value=sections):
        result = await documentation_service.get_documentation_by_path(["b.md", "a.md"], mode="local")
        # Order follows the order in all_doc_sections
        expected_titles = ["a.md", "b.md"]
        assert [s.file_path for s in result] == expected_titles
        assert [s.content for s in result] == ["A content", "B content"]


async def test_get_documentation_by_path_with_missing_paths_logs_error(
    documentation_service: DocumentationService,
    caplog: pytest.LogCaptureFixture,
):
    """Tests that get_documentation_by_path logs an error for missing paths and returns only found sections."""
    sections = [
        DocumentationSection(file_path="a.md", content="A content"),
    ]
    # Patch get_all_doc_sections to return our dummy sections
    with patch.object(DocumentationService, "_get_all_doc_sections_local", return_value=sections):
        caplog.set_level(logging.ERROR, logger="api.services.documentation_service")
        result = await documentation_service.get_documentation_by_path(["a.md", "c.md"], mode="local")
        # Only the existing section should be returned
        assert [s.file_path for s in result] == ["a.md"]
        # The missing path should trigger an error log
        assert "Documentation not found for paths: c.md" in caplog.text


@pytest.mark.asyncio
async def test_get_all_doc_sections_local_excludes_private_files(documentation_service: DocumentationService):
    """Tests that _get_all_doc_sections_local excludes files with .private in their name."""
    # Create a temporary directory structure for testing
    import os

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test files
        public_file = os.path.join(temp_dir, "public.mdx")
        private_file = os.path.join(temp_dir, "page.private.mdx")
        hidden_file = os.path.join(temp_dir, ".hidden.mdx")

        # Write content to files
        with open(public_file, "w") as f:  # noqa: ASYNC230
            f.write("# Public content")
        with open(private_file, "w") as f:  # noqa: ASYNC230
            f.write("# Private content")
        with open(hidden_file, "w") as f:  # noqa: ASYNC230
            f.write("# Hidden content")

        # Patch the LOCAL_DOCS_DIR to use our temp directory
        with patch.object(DocumentationService, "_LOCAL_DOCS_DIR", temp_dir):
            result = documentation_service._get_all_doc_sections_local()

            # Should only include the public file
            assert len(result) == 1
            assert result[0].file_path == "public"
            assert result[0].content == "# Public content"

            # Private and hidden files should be excluded
            titles = [section.file_path for section in result]
            assert "page.private" not in titles
            assert ".hidden" not in titles


# Remote functionality tests


async def test_get_all_doc_sections_remote_success(documentation_service: DocumentationService):
    """Tests successful fetching of all documentation sections from remote."""
    # Mock API response
    mock_pages_response = {
        "pages": [
            {"url": "/getting-started/index", "title": "Getting Started"},
            {"url": "/reference/api", "title": "API Reference"},
        ],
    }

    mock_page_contents = [
        "# Getting Started\nThis is the getting started content.",
        "# API Reference\nThis is the API reference content.",
    ]

    with patch("httpx.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_pages_response
        mock_response.raise_for_status.return_value = None

        mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

        # Mock the _fetch_page_content method to return our mock contents
        with patch.object(documentation_service, "_fetch_page_content", side_effect=mock_page_contents):
            result = await documentation_service._get_all_doc_sections_remote()

            assert len(result) == 2
            assert result[0].file_path == "getting-started/index"
            assert result[0].content == "# Getting Started\nThis is the getting started content."
            assert result[1].file_path == "reference/api"
            assert result[1].content == "# API Reference\nThis is the API reference content."


async def test_get_all_doc_sections_remote_api_error(
    documentation_service: DocumentationService,
    caplog: pytest.LogCaptureFixture,
):
    """Tests handling of API errors when fetching all documentation sections from remote."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get.side_effect = httpx.HTTPStatusError(
            "Server error",
            request=MagicMock(),
            response=MagicMock(),
        )

        caplog.set_level(logging.ERROR, logger="api.services.documentation_service")
        result = await documentation_service._get_all_doc_sections_remote()

        assert result == []
        assert "Failed to fetch documentation page list" in caplog.text


async def test_fetch_page_content_success(documentation_service: DocumentationService):
    """Tests successful fetching of page content."""
    page_path = "getting-started/index"
    expected_content = "# Getting Started\nThis is the content."

    with patch("httpx.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.text = expected_content
        mock_response.raise_for_status.return_value = None
        mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

        result = await documentation_service._fetch_page_content(page_path)

        assert result == expected_content
        mock_client.return_value.__aenter__.return_value.get.assert_called_once_with(
            f"{WORKFLOWAI_DOCS_URL}/{page_path}?reader=ai",
        )


async def test_fetch_page_content_404_error(
    documentation_service: DocumentationService,
    caplog: pytest.LogCaptureFixture,
):
    """Tests handling of 404 errors when fetching page content."""
    page_path = "non-existent-page"

    with patch("httpx.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_error = httpx.HTTPStatusError("Not found", request=MagicMock(), response=mock_response)
        mock_client.return_value.__aenter__.return_value.get.side_effect = mock_error

        caplog.set_level(logging.ERROR, logger="api.services.documentation_service")
        result = await documentation_service._fetch_page_content(page_path)

        assert result == "Page not found"
        assert "Documentation page not found" in caplog.text


async def test_fetch_page_content_server_error(
    documentation_service: DocumentationService,
    caplog: pytest.LogCaptureFixture,
):
    """Tests handling of server errors when fetching page content."""
    page_path = "getting-started/index"

    with patch("httpx.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_error = httpx.HTTPStatusError("Server error", request=MagicMock(), response=mock_response)
        mock_client.return_value.__aenter__.return_value.get.side_effect = mock_error

        caplog.set_level(logging.ERROR, logger="api.services.documentation_service")

        with pytest.raises(httpx.HTTPStatusError):
            await documentation_service._fetch_page_content(page_path)


async def test_fetch_page_content_general_error(
    documentation_service: DocumentationService,
    caplog: pytest.LogCaptureFixture,
):
    """Tests handling of general errors when fetching page content."""
    page_path = "getting-started/index"

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get.side_effect = Exception("Network error")

        caplog.set_level(logging.ERROR, logger="api.services.documentation_service")
        result = await documentation_service._fetch_page_content(page_path)

        assert result == "Error fetching page content"
        assert "Error fetching page content" in caplog.text


async def test_get_documentation_by_path_remote_success(documentation_service: DocumentationService):
    """Tests successful fetching of documentation by path from remote."""
    paths = ["getting-started/index", "reference/api"]
    expected_contents = [
        "# Getting Started\nThis is the getting started content.",
        "# API Reference\nThis is the API reference content.",
    ]

    with patch.object(documentation_service, "_fetch_page_content", side_effect=expected_contents):
        result = await documentation_service.get_documentation_by_path_remote(paths)

        assert len(result) == 2
        assert result[0].file_path == "getting-started/index"
        assert result[0].content == expected_contents[0]
        assert result[1].file_path == "reference/api"
        assert result[1].content == expected_contents[1]


async def test_get_documentation_by_path_remote_with_errors(
    documentation_service: DocumentationService,
    caplog: pytest.LogCaptureFixture,
):
    """Tests handling of errors when fetching documentation by path from remote."""
    paths = ["valid-path", "invalid-path"]

    async def mock_fetch_page_content(path: str) -> str:
        if path == "valid-path":
            return "Valid content"
        raise Exception("Page not found")

    with patch.object(documentation_service, "_fetch_page_content", side_effect=mock_fetch_page_content):
        caplog.set_level(logging.WARNING, logger="api.services.documentation_service")
        result = await documentation_service.get_documentation_by_path_remote(paths)

        # Only the valid path should be returned
        assert len(result) == 1
        assert result[0].file_path == "valid-path"
        assert result[0].content == "Valid content"

        # Error should be logged
        assert "Failed to fetch documentation by path" in caplog.text


async def test_get_all_doc_sections_mode_selection(documentation_service: DocumentationService):
    """Tests that get_all_doc_sections correctly selects local vs remote mode."""
    mock_local_sections = [DocumentationSection(file_path="local.md", content="Local content")]
    mock_remote_sections = [DocumentationSection(file_path="Remote Page", content="Remote content")]

    with patch.object(documentation_service, "_get_all_doc_sections_local", return_value=mock_local_sections):
        with patch.object(documentation_service, "_get_all_doc_sections_remote", return_value=mock_remote_sections):
            # Test local mode
            result_local = await documentation_service.get_all_doc_sections(mode="local")
            assert result_local == mock_local_sections


async def test_get_documentation_by_path_mode_selection(documentation_service: DocumentationService):
    """Tests that get_documentation_by_path correctly selects local vs remote mode."""
    paths = ["test-path"]
    mock_local_sections = [DocumentationSection(file_path="test-path", content="Local content")]
    mock_remote_sections = [DocumentationSection(file_path="test-path", content="Remote content")]

    with patch.object(documentation_service, "_get_documentation_by_path_local", return_value=mock_local_sections):
        with patch.object(documentation_service, "get_documentation_by_path_remote", return_value=mock_remote_sections):
            # Test local mode
            result_local = await documentation_service.get_documentation_by_path(paths, mode="local")
            assert result_local == mock_local_sections


# Tests for new dynamic page description functionality


def test_extract_summary_from_content_with_frontmatter(documentation_service: DocumentationService):
    """Test extracting summary from markdown frontmatter summary field."""
    content = """---
title: Getting Started
summary: Learn how to get started with WorkflowAI platform
---

# Getting Started

Some content here."""

    result = documentation_service._extract_summary_from_content(content)
    assert result == "Learn how to get started with WorkflowAI platform"


def test_extract_summary_from_content_no_frontmatter(documentation_service: DocumentationService):
    """Test that function returns empty string when no frontmatter summary is found."""
    content = """# Authentication Guide

This guide covers API authentication using bearer tokens and best practices for security.

More detailed content follows..."""

    result = documentation_service._extract_summary_from_content(content)
    assert result == ""


def test_get_available_pages_descriptions_success(documentation_service: DocumentationService):
    """Test successful generation of available pages descriptions."""
    # NOTE: DocumentationSection.title is misleadingly named - it's actually the page path/identifier,
    # not the human-readable title. The human-readable title is in the frontmatter "title:" field.
    mock_sections = [
        DocumentationSection(
            file_path="index",  # This is the page path, not the display title
            content="---\nsummary: Getting started guide\n---\n\n# Welcome",
        ),
        DocumentationSection(
            file_path="reference/auth",
            content="---\nsummary: API authentication docs\n---\n\n# Auth",
        ),
        DocumentationSection(
            file_path="use-cases/chatbot",
            content="---\nsummary: Chatbot building guide\n---\n\n# Chatbot",
        ),
    ]

    with patch.object(documentation_service, "_get_all_doc_sections_local", return_value=mock_sections):
        result = documentation_service.get_available_pages_descriptions()

        expected = """     - 'index' - Getting started guide
     - 'reference/auth' - API authentication docs
     - 'use-cases/chatbot' - Chatbot building guide"""

        assert result == expected


class TestGetAllSectionsLocal:
    async def test_not_empty(self, documentation_service: DocumentationService):
        sections = documentation_service._get_all_doc_sections_local()
        assert len(sections) > 0


# Tests for search_documentation_by_query functionality


@patch("api.services.documentation_service.search_documentation_agent", new_callable=AsyncMock)
@patch.object(DocumentationService, "get_all_doc_sections")
async def test_search_documentation_by_query_success(
    mock_get_all_sections: MagicMock,
    mock_search_agent: AsyncMock,
    documentation_service: DocumentationService,
):
    """Tests successful search with relevant sections returned."""
    all_sections = [
        DocumentationSection(file_path="getting-started/index", content="Getting started content"),
        DocumentationSection(file_path="reference/api", content="API reference content"),
        DocumentationSection(file_path="guides/authentication", content="Authentication guide"),
    ]
    mock_get_all_sections.return_value = all_sections

    # Mock the search agent response
    class MockSearchResult(NamedTuple):
        relevant_documentation_file_paths: list[str]
        missing_doc_sections_feedback: str | None
        unsupported_feature_detected: None

    mock_search_agent.return_value = MockSearchResult(
        relevant_documentation_file_paths=["reference/api", "guides/authentication"],
        missing_doc_sections_feedback=None,
        unsupported_feature_detected=None,
    )

    query = "How to authenticate with the API?"
    usage_context = "Test context for MCP client"
    result, _ = await documentation_service.search_documentation_by_query(query, usage_context)

    # Should return only the relevant sections
    expected_sections = [
        DocumentationSection(file_path="reference/api", content="API reference content"),
        DocumentationSection(file_path="guides/authentication", content="Authentication guide"),
    ]

    # Convert to sets of tuples for order-independent comparison
    actual_section_tuples = {(s.file_path, s.content) for s in result}
    expected_section_tuples = {(s.file_path, s.content) for s in expected_sections}

    assert actual_section_tuples == expected_section_tuples
    mock_get_all_sections.assert_called_once_with("local")
    mock_search_agent.assert_called_once_with(
        query=query,
        available_doc_sections=all_sections,
        usage_context=usage_context,
    )


@patch("api.services.documentation_service.search_documentation_agent", new_callable=AsyncMock)
@patch.object(DocumentationService, "get_all_doc_sections")
async def test_search_documentation_by_query_empty_results(
    mock_get_all_sections: MagicMock,
    mock_search_agent: AsyncMock,
    documentation_service: DocumentationService,
):
    """Tests search when no relevant sections are found."""
    all_sections = [
        DocumentationSection(file_path="getting-started/index", content="Getting started content"),
        DocumentationSection(file_path="reference/api", content="API reference content"),
    ]
    mock_get_all_sections.return_value = all_sections

    # Mock the search agent to return empty results
    class MockSearchResult(NamedTuple):
        relevant_documentation_file_paths: list[str]
        missing_doc_sections_feedback: str | None
        unsupported_feature_detected: None

    mock_search_agent.return_value = MockSearchResult(
        relevant_documentation_file_paths=[],
        missing_doc_sections_feedback=None,
        unsupported_feature_detected=None,
    )

    query = "How to build a rocket ship?"
    usage_context = "Test context for MCP client"
    result, _ = await documentation_service.search_documentation_by_query(query, usage_context)

    assert result == []
    mock_get_all_sections.assert_called_once_with("local")
    mock_search_agent.assert_called_once_with(
        query=query,
        available_doc_sections=all_sections,
        usage_context=usage_context,
    )


@patch("api.services.documentation_service.search_documentation_agent", new_callable=AsyncMock)
@patch.object(DocumentationService, "get_all_doc_sections")
async def test_search_documentation_by_query_none_result(
    mock_get_all_sections: MagicMock,
    mock_search_agent: AsyncMock,
    documentation_service: DocumentationService,
):
    """Tests search when search agent returns None."""
    all_sections = [
        DocumentationSection(file_path="getting-started/index", content="Getting started content"),
    ]
    mock_get_all_sections.return_value = all_sections

    # Mock the search agent to return None
    mock_search_agent.return_value = None

    query = "test query"
    usage_context = "Test context for MCP client"
    result, _ = await documentation_service.search_documentation_by_query(query, usage_context)

    assert result == []
    mock_get_all_sections.assert_called_once_with("local")
    mock_search_agent.assert_called_once()


@patch("api.services.documentation_service.search_documentation_agent", new_callable=AsyncMock)
@patch.object(DocumentationService, "get_all_doc_sections")
async def test_search_documentation_by_query_agent_error(
    mock_get_all_sections: MagicMock,
    mock_search_agent: AsyncMock,
    documentation_service: DocumentationService,
    caplog: pytest.LogCaptureFixture,
):
    """Tests search when search agent throws an exception."""
    all_sections = [
        DocumentationSection(file_path="getting-started/index", content="Getting started content"),
        DocumentationSection(file_path="reference/api", content="API reference content"),
    ]
    mock_get_all_sections.return_value = all_sections

    # Mock the search agent to throw an exception
    mock_search_agent.side_effect = Exception("Search agent failed")

    caplog.set_level(logging.ERROR, logger="api.services.documentation_service")
    query = "How to authenticate?"
    usage_context = "Test context for MCP client"
    result, _ = await documentation_service.search_documentation_by_query(query, usage_context)

    # Should return empty list when search agent fails
    assert result == []
    mock_get_all_sections.assert_called_once_with("local")
    mock_search_agent.assert_called_once_with(
        query=query,
        available_doc_sections=all_sections,
        usage_context=usage_context,
    )
    assert "Error in search documentation agent" in caplog.text


@patch("api.services.documentation_service.search_documentation_agent", new_callable=AsyncMock)
@patch.object(DocumentationService, "get_all_doc_sections")
async def test_search_documentation_by_query_mode_selection(
    mock_get_all_sections: MagicMock,
    mock_search_agent: AsyncMock,
    documentation_service: DocumentationService,
):
    """Tests that search_documentation_by_query correctly passes mode to get_all_doc_sections."""
    all_sections = [
        DocumentationSection(file_path="test-section", content="Test content"),
    ]
    mock_get_all_sections.return_value = all_sections

    class MockSearchResult(NamedTuple):
        relevant_documentation_file_paths: list[str]
        missing_doc_sections_feedback: str | None
        unsupported_feature_detected: None

    mock_search_agent.return_value = MockSearchResult(
        relevant_documentation_file_paths=["test-section"],
        missing_doc_sections_feedback=None,
        unsupported_feature_detected=None,
    )

    # Test with remote mode
    query = "test query"
    usage_context = "Test context for MCP client"
    await documentation_service.search_documentation_by_query(query, usage_context, mode="remote")

    mock_get_all_sections.assert_called_with("remote")

    # Test with local mode (default)
    await documentation_service.search_documentation_by_query(query, usage_context)
    mock_get_all_sections.assert_called_with("local")


@patch("api.services.documentation_service.search_documentation_agent", new_callable=AsyncMock)
@patch.object(DocumentationService, "get_all_doc_sections")
async def test_search_documentation_by_query_partial_matches(
    mock_get_all_sections: MagicMock,
    mock_search_agent: AsyncMock,
    documentation_service: DocumentationService,
):
    """Tests search when some returned sections don't exist in all_sections."""
    all_sections = [
        DocumentationSection(file_path="existing-section", content="Existing content"),
        DocumentationSection(file_path="another-section", content="Another content"),
    ]
    mock_get_all_sections.return_value = all_sections

    # Mock the search agent to return some valid and some invalid section names
    class MockSearchResult(NamedTuple):
        relevant_documentation_file_paths: list[str]
        missing_doc_sections_feedback: str | None
        unsupported_feature_detected: None

    mock_search_agent.return_value = MockSearchResult(
        relevant_documentation_file_paths=["existing-section", "non-existent-section", "another-section"],
        missing_doc_sections_feedback=None,
        unsupported_feature_detected=None,
    )

    query = "test query"
    usage_context = "Test context for MCP client"
    result, _ = await documentation_service.search_documentation_by_query(query, usage_context)

    # Should only return sections that actually exist
    expected_sections = [
        DocumentationSection(file_path="existing-section", content="Existing content"),
        DocumentationSection(file_path="another-section", content="Another content"),
    ]

    actual_section_tuples = {(s.file_path, s.content) for s in result}
    expected_section_tuples = {(s.file_path, s.content) for s in expected_sections}

    assert actual_section_tuples == expected_section_tuples
