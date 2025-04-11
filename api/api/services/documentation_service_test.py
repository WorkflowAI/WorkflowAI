# Removed the test for the private function _extract_doc_title as it's no longer used.
import os
from typing import NamedTuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.documentation_service import DEFAULT_DOC_SECTIONS, DocumentationService
from core.domain.documentation_section import DocumentationSection

API_DOCS_DIR = "api/docs"
EXPECTED_FILE_COUNT = 48


@patch("api.services.documentation_service.DocumentationService._DOCS_DIR", API_DOCS_DIR)
def test_get_all_doc_sections_uses_real_files() -> None:
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
    doc_sections: list[DocumentationSection] = service.get_all_doc_sections()

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
