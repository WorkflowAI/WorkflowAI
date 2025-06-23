# Removed the test for the private function _extract_doc_title as it's no longer used.
# pyright: reportPrivateUsage=false
import logging
import os
from typing import NamedTuple
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from api.services.documentation_service import DEFAULT_DOC_SECTIONS, WORKFLOWAI_DOCS_URL, DocumentationService
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
        assert isinstance(section.title, str)
        assert len(section.title) > 0
        assert isinstance(section.content, str)
        # We don't check content length as some files might be empty


@pytest.fixture
def documentation_service() -> DocumentationService:
    """Fixture to provide a DocumentationService instance."""
    return DocumentationService()


@pytest.mark.asyncio
@patch("api.services.documentation_service.pick_relevant_documentation_sections", new_callable=AsyncMock)
@patch.object(DocumentationService, "get_all_doc_sections")
async def test_get_relevant_doc_sections_success(
    mock_get_all_sections: MagicMock,
    mock_pick_relevant: AsyncMock,
    documentation_service: DocumentationService,
):
    """Tests get_relevant_doc_sections successfully filters sections."""
    all_sections = [
        DocumentationSection(title="section1.md", content="Content 1"),
        DocumentationSection(title="section2.md", content="Content 2"),
        DocumentationSection(title="security.md", content="Security Content"),
    ]
    mock_get_all_sections.return_value = all_sections

    # Mock the return value of pick_relevant_documentation_sections
    class MockPickOutput(NamedTuple):
        relevant_doc_sections: list[str]

    mock_pick_relevant.return_value = MockPickOutput(relevant_doc_sections=["security.md", "section1.md"])

    agent_instructions = "Focus on security."
    relevant_sections = await documentation_service.get_relevant_doc_sections([], agent_instructions)

    # Expected sections: Defaults + the ones identified as relevant
    expected_sections = DEFAULT_DOC_SECTIONS + [
        DocumentationSection(title="section1.md", content="Content 1"),
        DocumentationSection(title="security.md", content="Security Content"),
    ]

    # Convert to sets of tuples for order-independent comparison
    actual_section_tuples = {(s.title, s.content) for s in relevant_sections}
    expected_section_tuples = {(s.title, s.content) for s in expected_sections}

    assert actual_section_tuples == expected_section_tuples
    mock_get_all_sections.assert_called_once()
    mock_pick_relevant.assert_called_once()
    # You could add more specific assertions on the input to mock_pick_relevant if needed


@pytest.mark.asyncio
@patch("api.services.documentation_service.pick_relevant_documentation_sections", new_callable=AsyncMock)
@patch.object(DocumentationService, "get_all_doc_sections")
async def test_get_relevant_doc_sections_pick_error(
    mock_get_all_sections: MagicMock,
    mock_pick_relevant: AsyncMock,
    documentation_service: DocumentationService,
):
    """Tests get_relevant_doc_sections falls back to all sections when pick_relevant_documentation_sections fails."""
    all_sections = [
        DocumentationSection(title="section1.md", content="Content 1"),
        DocumentationSection(title="section2.md", content="Content 2"),
        DocumentationSection(title="security.md", content="Security Content"),
    ]
    mock_get_all_sections.return_value = all_sections

    # Simulate an error during the picking process
    mock_pick_relevant.side_effect = Exception("LLM call failed")

    agent_instructions = "Focus on security."
    relevant_sections = await documentation_service.get_relevant_doc_sections([], agent_instructions)

    # Expected sections: Defaults + all available sections as fallback
    expected_sections = DEFAULT_DOC_SECTIONS + all_sections

    # Convert to sets of tuples for order-independent comparison
    actual_section_tuples = {(s.title, s.content) for s in relevant_sections}
    expected_section_tuples = {(s.title, s.content) for s in expected_sections}

    assert actual_section_tuples == expected_section_tuples
    mock_get_all_sections.assert_called_once()
    mock_pick_relevant.assert_called_once()


async def test_get_documentation_by_path_with_existing_paths(documentation_service: DocumentationService):
    """Tests that get_documentation_by_path returns sections matching the provided paths."""
    sections = [
        DocumentationSection(title="a.md", content="A content"),
        DocumentationSection(title="b.md", content="B content"),
    ]
    # Patch get_all_doc_sections to return our dummy sections
    with patch.object(DocumentationService, "_get_all_doc_sections_local", return_value=sections):
        result = await documentation_service.get_documentation_by_path(["b.md", "a.md"], mode="local")
        # Order follows the order in all_doc_sections
        expected_titles = ["a.md", "b.md"]
        assert [s.title for s in result] == expected_titles
        assert [s.content for s in result] == ["A content", "B content"]


async def test_get_documentation_by_path_with_missing_paths_logs_error(
    documentation_service: DocumentationService,
    caplog: pytest.LogCaptureFixture,
):
    """Tests that get_documentation_by_path logs an error for missing paths and returns only found sections."""
    sections = [
        DocumentationSection(title="a.md", content="A content"),
    ]
    # Patch get_all_doc_sections to return our dummy sections
    with patch.object(DocumentationService, "_get_all_doc_sections_local", return_value=sections):
        caplog.set_level(logging.ERROR, logger="api.services.documentation_service")
        result = await documentation_service.get_documentation_by_path(["a.md", "c.md"], mode="local")
        # Only the existing section should be returned
        assert [s.title for s in result] == ["a.md"]
        # The missing path should trigger an error log
        assert "Documentation not found for paths: c.md" in caplog.text


# Remote functionality tests


@pytest.mark.asyncio
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
            assert result[0].title == "Getting Started"
            assert result[0].content == "# Getting Started\nThis is the getting started content."
            assert result[1].title == "API Reference"
            assert result[1].content == "# API Reference\nThis is the API reference content."


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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
        assert result[0].title == "getting-started/index"
        assert result[0].content == expected_contents[0]
        assert result[1].title == "reference/api"
        assert result[1].content == expected_contents[1]


@pytest.mark.asyncio
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
        assert result[0].title == "valid-path"
        assert result[0].content == "Valid content"

        # Error should be logged
        assert "Failed to fetch documentation by path" in caplog.text


@pytest.mark.asyncio
async def test_get_documentation_by_path_remote_missing_paths_logs_error(
    documentation_service: DocumentationService,
    caplog: pytest.LogCaptureFixture,
):
    """Tests that get_documentation_by_path_remote logs an error for missing paths."""
    paths = ["existing-path", "missing-path"]

    async def mock_fetch_page_content(path: str) -> str:
        if path == "existing-path":
            return "Existing content"
        return ""  # Empty content for missing path

    with patch.object(documentation_service, "_fetch_page_content", side_effect=mock_fetch_page_content):
        caplog.set_level(logging.ERROR, logger="api.services.documentation_service")
        result = await documentation_service.get_documentation_by_path_remote(paths)

        # Only the existing path should be returned (empty content filtered out)
        assert len(result) == 1
        assert result[0].title == "existing-path"

        # Missing path should trigger an error log
        assert "Documentation not found for paths: missing-path" in caplog.text


@pytest.mark.asyncio
async def test_get_all_doc_sections_mode_selection(documentation_service: DocumentationService):
    """Tests that get_all_doc_sections correctly selects local vs remote mode."""
    mock_local_sections = [DocumentationSection(title="local.md", content="Local content")]
    mock_remote_sections = [DocumentationSection(title="Remote Page", content="Remote content")]

    with patch.object(documentation_service, "_get_all_doc_sections_local", return_value=mock_local_sections):
        with patch.object(documentation_service, "_get_all_doc_sections_remote", return_value=mock_remote_sections):
            # Test local mode
            result_local = await documentation_service.get_all_doc_sections(mode="local")
            assert result_local == mock_local_sections


@pytest.mark.asyncio
async def test_get_documentation_by_path_mode_selection(documentation_service: DocumentationService):
    """Tests that get_documentation_by_path correctly selects local vs remote mode."""
    paths = ["test-path"]
    mock_local_sections = [DocumentationSection(title="test-path", content="Local content")]
    mock_remote_sections = [DocumentationSection(title="test-path", content="Remote content")]

    with patch.object(documentation_service, "_get_documentation_by_path_local", return_value=mock_local_sections):
        with patch.object(documentation_service, "get_documentation_by_path_remote", return_value=mock_remote_sections):
            # Test local mode
            result_local = await documentation_service.get_documentation_by_path(paths, mode="local")
            assert result_local == mock_local_sections
