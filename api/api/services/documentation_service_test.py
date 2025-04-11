from typing import NamedTuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.documentation_service import DEFAULT_DOC_SECTIONS, DocumentationService
from core.domain.documentation_section import DocumentationSection

# Removed the test for the private function _extract_doc_title as it's no longer used.


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
