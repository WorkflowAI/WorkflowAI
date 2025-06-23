# Enhanced Documentation Snippet Picker Agent

## Overview

The `pick_relevant_documentation_with_snippets` agent is an enhanced version of the `pick_relevant_documentation_sections` agent. While the original agent only identifies which documentation sections are relevant, this enhanced version can pinpoint specific snippets within those sections.

## Key Features

1. **Precise Snippet Selection**: Instead of returning entire documentation sections, the agent identifies specific relevant snippets
2. **String-Based Matching**: Uses beginning and ending strings for snippet identification, allowing regex or string matching for extraction
3. **Context-Aware**: Provides reasons for why each specific snippet is relevant to the user's query
4. **Minimal Overhead**: Agent only generates snippet boundaries, not full content

## Components

### 1. Agent: `pick_relevant_documentation_with_snippets.py`

The main agent that analyzes chat history and documentation to identify relevant snippets.

**Input Schema:**
- `chat_messages`: Conversation history
- `agent_instructions`: Agent's internal instructions  
- `available_doc_sections`: List of documentation sections to search

**Output Schema:**
- `overall_reason`: Explanation for the snippet selections
- `relevant_snippets`: List of `DocumentationSnippet` objects containing:
  - `section_title`: Which documentation section the snippet is from
  - `snippet_beginning`: First 10-20 characters to identify snippet start
  - `snippet_ending`: Last 10-20 characters to identify snippet end
  - `relevance_reason`: Why this specific snippet is relevant

### 2. Utilities: `documentation_snippet_extractor.py`

Helper functions for extracting snippets from documentation content:

- `extract_snippet()`: Basic string matching extraction
- `extract_snippet_with_regex()`: Regex-based extraction with special character escaping
- `extract_all_snippets()`: Extract all snippets referenced by the agent
- `merge_overlapping_snippets()`: Combine overlapping snippets to avoid duplication

### 3. Example: `pick_relevant_documentation_with_snippets_example.py`

Demonstrates the complete workflow from agent input to extracted snippets.

## Usage Example

```python
from core.agents.pick_relevant_documentation_with_snippets import (
    PickRelevantDocumentationWithSnippetsInput,
    pick_relevant_documentation_with_snippets
)
from core.agents.documentation_snippet_extractor import extract_all_snippets

# Prepare input
input_data = PickRelevantDocumentationWithSnippetsInput(
    chat_messages=chat_messages,
    agent_instructions="You are a helpful assistant.",
    available_doc_sections=documentation_sections
)

# Call agent
output = await pick_relevant_documentation_with_snippets(input_data)

# Extract actual snippets
snippets = extract_all_snippets(
    documentation_sections,
    output.relevant_snippets
)
```

## Benefits Over Original Agent

1. **Reduced Token Usage**: Only relevant parts of documentation are processed
2. **Better Precision**: Pinpoints exact information needed
3. **Improved Context**: Each snippet has a specific relevance reason
4. **Flexible Extraction**: Supports both exact and regex-based matching

## Implementation Notes

- The agent generates snippet boundaries (beginning/end strings) rather than full content
- String matching is performed post-agent to extract actual snippets
- Overlapping snippets can be merged to avoid duplication
- Case-sensitive and case-insensitive matching are both supported