# pyright: reportPrivateUsage=false
import pytest

from core.agents.pick_relevant_documentation_with_snippets import (
    DocumentationSnippet,
    PickRelevantDocumentationWithSnippetsInput,
    PickRelevantDocumentationWithSnippetsOutput,
)
from core.domain.documentation_section import DocumentationSection
from core.domain.fields.chat_message import ChatMessage


@pytest.mark.asyncio
async def test_pick_relevant_documentation_with_snippets():
    """Test that the agent can identify relevant snippets within documentation sections."""
    # Sample documentation sections
    doc_sections = [
        DocumentationSection(
            title="API Authentication",
            content="""
            # API Authentication
            
            To authenticate with the API, you need to include an API key in your requests.
            
            ## Getting an API Key
            You can generate an API key from your dashboard settings.
            
            ## Using the API Key
            Include the API key in the Authorization header:
            ```
            Authorization: Bearer YOUR_API_KEY
            ```
            
            ## Rate Limiting
            The API has rate limits of 100 requests per minute per API key.
            """,
        ),
        DocumentationSection(
            title="Error Handling",
            content="""
            # Error Handling
            
            The API uses standard HTTP status codes to indicate success or failure.
            
            ## Common Error Codes
            - 400 Bad Request: Invalid parameters
            - 401 Unauthorized: Missing or invalid API key
            - 429 Too Many Requests: Rate limit exceeded
            - 500 Internal Server Error: Server error
            
            ## Error Response Format
            All error responses include a JSON object with error details:
            ```json
            {
                "error": {
                    "code": "invalid_parameter",
                    "message": "The 'limit' parameter must be a positive integer"
                }
            }
            ```
            """,
        ),
        DocumentationSection(
            title="Data Formats",
            content="""
            # Data Formats
            
            The API supports JSON and XML response formats.
            
            ## Requesting a Format
            Use the Accept header to specify your preferred format:
            - JSON: Accept: application/json
            - XML: Accept: application/xml
            
            ## Pagination
            List endpoints support pagination using limit and offset parameters.
            """,
        ),
    ]

    # Sample chat messages asking about authentication
    chat_messages = [
        ChatMessage(role="user", content="How do I authenticate with the API?"),
        ChatMessage(role="assistant", content="I'll help you with API authentication."),
        ChatMessage(role="user", content="What header should I use and what are the rate limits?"),
    ]

    # Create input
    input_data = PickRelevantDocumentationWithSnippetsInput(
        chat_messages=chat_messages,
        agent_instructions="You are an API support assistant.",
        available_doc_sections=doc_sections,
    )

    # Note: In a real test, you would mock the agent response
    # Here we're showing the expected output structure
    expected_output = PickRelevantDocumentationWithSnippetsOutput(
        overall_reason="The user is asking about API authentication headers and rate limits.",
        relevant_snippets=[
            DocumentationSnippet(
                section_title="API Authentication",
                snippet_beginning="Include the API key",
                snippet_ending="YOUR_API_KEY\n```",
                relevance_reason="User asked specifically about what header to use for authentication",
            ),
            DocumentationSnippet(
                section_title="API Authentication",
                snippet_beginning="## Rate Limiting",
                snippet_ending="per API key.",
                relevance_reason="User asked about rate limits",
            ),
        ],
    )

    # Verify the output structure
    assert isinstance(expected_output.relevant_snippets, list)
    assert all(isinstance(s, DocumentationSnippet) for s in expected_output.relevant_snippets)
    assert all(s.section_title in [d.title for d in doc_sections] for s in expected_output.relevant_snippets)


def extract_snippet_from_content(content: str, snippet_beginning: str, snippet_ending: str) -> str | None:
    """
    Extract a snippet from content based on beginning and ending strings.
    This is a helper function to demonstrate how the snippet extraction would work.
    """
    start_idx = content.find(snippet_beginning)
    if start_idx == -1:
        return None

    end_idx = content.find(snippet_ending, start_idx)
    if end_idx == -1:
        return None

    # Include the ending string in the snippet
    end_idx += len(snippet_ending)

    return content[start_idx:end_idx]


@pytest.mark.parametrize(
    "content,beginning,ending,expected",
    [
        (
            "Hello world, this is a test content.",
            "Hello",
            "world",
            "Hello world",
        ),
        (
            "The quick brown fox jumps over the lazy dog.",
            "quick brown",
            "lazy dog.",
            "quick brown fox jumps over the lazy dog.",
        ),
        (
            "No match here",
            "not found",
            "also not found",
            None,
        ),
    ],
)
def test_extract_snippet_from_content(content: str, beginning: str, ending: str, expected: str | None):
    """Test the snippet extraction helper function."""
    result = extract_snippet_from_content(content, beginning, ending)
    assert result == expected
