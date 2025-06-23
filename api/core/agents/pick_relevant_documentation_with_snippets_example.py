"""Example usage of the enhanced documentation snippet picker agent."""

import asyncio

from core.agents.documentation_snippet_extractor import extract_all_snippets, merge_overlapping_snippets
from core.domain.documentation_section import DocumentationSection
from core.domain.fields.chat_message import ChatMessage


async def example_usage():
    """Example showing how to use the enhanced documentation snippet picker."""

    # Sample documentation sections
    documentation_sections = [
        DocumentationSection(
            title="API Reference",
            content="""
# API Reference

## Authentication
All API requests require authentication using an API key.

### Getting Started
1. Sign up for an account
2. Navigate to Settings > API Keys
3. Generate a new API key
4. Include the key in your requests

### Request Format
Include your API key in the Authorization header:
```
Authorization: Bearer YOUR_API_KEY_HERE
```

### Rate Limits
- Free tier: 100 requests per hour
- Pro tier: 1000 requests per hour
- Enterprise: Unlimited

### Error Handling
If authentication fails, you'll receive a 401 status code.
            """,
        ),
        DocumentationSection(
            title="Data Formats",
            content="""
# Data Formats

## JSON Response Format
All API responses are returned in JSON format by default.

### Standard Response
```json
{
  "status": "success",
  "data": {
    "id": 123,
    "name": "Example"
  }
}
```

### Error Response
```json
{
  "status": "error",
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Missing required parameter: id"
  }
}
```

## XML Format
You can request XML format by setting the Accept header to application/xml.
            """,
        ),
    ]

    # Sample conversation
    chat_messages = [
        ChatMessage(
            role="user",
            content="How do I authenticate with the API and what format should I use for the authorization header?",
        ),
        ChatMessage(
            role="assistant",
            content="I'll help you with API authentication.",
        ),
        ChatMessage(
            role="user",
            content="Also, what happens if my authentication fails?",
        ),
    ]

    # In a real scenario, you would create input and call the agent:
    # agent_input = PickRelevantDocumentationWithSnippetsInput(
    #     chat_messages=chat_messages,
    #     agent_instructions="You are an API documentation assistant.",
    #     available_doc_sections=documentation_sections,
    # )
    # output = await pick_relevant_documentation_with_snippets(agent_input)

    # For this example, let's simulate the agent's output
    from core.agents.pick_relevant_documentation_with_snippets import (
        DocumentationSnippet,
        PickRelevantDocumentationWithSnippetsOutput,
    )

    simulated_output = PickRelevantDocumentationWithSnippetsOutput(
        overall_reason="User needs information about API authentication headers and error handling.",
        relevant_snippets=[
            DocumentationSnippet(
                section_title="API Reference",
                snippet_beginning="Include your API key",
                snippet_ending="YOUR_API_KEY_HERE\n```",
                relevance_reason="User specifically asked about the authorization header format",
            ),
            DocumentationSnippet(
                section_title="API Reference",
                snippet_beginning="### Error Handling",
                snippet_ending="401 status code.",
                relevance_reason="User asked what happens when authentication fails",
            ),
        ],
    )

    # Extract the actual snippets from the documentation
    extracted_snippets = extract_all_snippets(
        documentation_sections,
        simulated_output.relevant_snippets,
        case_sensitive=True,
    )

    print("=== Agent Output ===")
    print(f"Reason: {simulated_output.overall_reason}")
    print(f"\nFound {len(simulated_output.relevant_snippets)} relevant snippets:")

    for i, snippet_ref in enumerate(simulated_output.relevant_snippets, 1):
        print(f"\n{i}. From section: {snippet_ref.section_title}")
        print(f"   Reason: {snippet_ref.relevance_reason}")
        print(f"   Beginning: '{snippet_ref.snippet_beginning}'")
        print(f"   Ending: '{snippet_ref.snippet_ending}'")

    print("\n=== Extracted Snippets ===")
    for section_title, snippets in extracted_snippets.items():
        print(f"\nFrom {section_title}:")
        for snippet in snippets:
            print("-" * 50)
            print(snippet)
            print("-" * 50)

    # Example of merging overlapping snippets
    if "API Reference" in extracted_snippets:
        api_content = next(
            (doc.content for doc in documentation_sections if doc.title == "API Reference"),
            "",
        )
        merged = merge_overlapping_snippets(extracted_snippets["API Reference"], api_content)
        print("\n=== After Merging Overlaps ===")
        print(f"Original snippets: {len(extracted_snippets['API Reference'])}")
        print(f"Merged snippets: {len(merged)}")


if __name__ == "__main__":
    # Run the example
    asyncio.run(example_usage())
