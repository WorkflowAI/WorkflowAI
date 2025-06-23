"""Utility functions for extracting documentation snippets based on agent output."""

import re

from core.agents.pick_relevant_documentation_with_snippets import DocumentationSnippet
from core.domain.documentation_section import DocumentationSection


def extract_snippet(
    content: str,
    snippet_beginning: str,
    snippet_ending: str,
    case_sensitive: bool = True,
) -> str | None:
    """
    Extract a snippet from content based on beginning and ending strings.

    Args:
        content: The full content to extract from
        snippet_beginning: The beginning string to match
        snippet_ending: The ending string to match
        case_sensitive: Whether to perform case-sensitive matching

    Returns:
        The extracted snippet including the beginning and ending strings,
        or None if not found.
    """
    if not case_sensitive:
        content_lower = content.lower()
        beginning_lower = snippet_beginning.lower()
        ending_lower = snippet_ending.lower()

        start_idx = content_lower.find(beginning_lower)
        if start_idx == -1:
            return None

        end_idx = content_lower.find(ending_lower, start_idx + len(beginning_lower))
        if end_idx == -1:
            return None

        # Use original content with found indices
        end_idx += len(snippet_ending)
        return content[start_idx:end_idx]
    start_idx = content.find(snippet_beginning)
    if start_idx == -1:
        return None

    end_idx = content.find(snippet_ending, start_idx + len(snippet_beginning))
    if end_idx == -1:
        return None

    end_idx += len(snippet_ending)
    return content[start_idx:end_idx]


def extract_snippet_with_regex(
    content: str,
    snippet_beginning: str,
    snippet_ending: str,
    case_sensitive: bool = True,
) -> str | None:
    """
    Extract a snippet using regex for more flexible matching.
    Special regex characters in the beginning/ending strings are escaped.

    Args:
        content: The full content to extract from
        snippet_beginning: The beginning string to match (will be escaped)
        snippet_ending: The ending string to match (will be escaped)
        case_sensitive: Whether to perform case-sensitive matching

    Returns:
        The extracted snippet including the beginning and ending strings,
        or None if not found.
    """
    # Escape special regex characters
    beginning_escaped = re.escape(snippet_beginning)
    ending_escaped = re.escape(snippet_ending)

    # Build pattern that captures everything between beginning and ending
    pattern = f"({beginning_escaped}.*?{ending_escaped})"

    flags = 0 if case_sensitive else re.IGNORECASE
    flags |= re.DOTALL  # Make . match newlines

    match = re.search(pattern, content, flags)
    if match:
        return match.group(1)
    return None


def extract_all_snippets(
    documentation_sections: list[DocumentationSection],
    snippet_references: list[DocumentationSnippet],
    case_sensitive: bool = True,
) -> dict[str, list[str]]:
    """
    Extract all referenced snippets from documentation sections.

    Args:
        documentation_sections: List of available documentation sections
        snippet_references: List of snippet references from the agent
        case_sensitive: Whether to perform case-sensitive matching

    Returns:
        Dictionary mapping section titles to lists of extracted snippets
    """
    # Create a mapping of section titles to content
    section_map = {section.title: section.content for section in documentation_sections}

    # Extract snippets grouped by section
    results: dict[str, list[str]] = {}

    for snippet_ref in snippet_references:
        if snippet_ref.section_title not in section_map:
            continue

        content = section_map[snippet_ref.section_title]
        extracted = extract_snippet(
            content,
            snippet_ref.snippet_beginning,
            snippet_ref.snippet_ending,
            case_sensitive,
        )

        if extracted:
            if snippet_ref.section_title not in results:
                results[snippet_ref.section_title] = []
            results[snippet_ref.section_title].append(extracted)

    return results


def merge_overlapping_snippets(snippets: list[str], content: str) -> list[str]:
    """
    Merge overlapping snippets to avoid duplication.

    Args:
        snippets: List of extracted snippets
        content: The original content the snippets were extracted from

    Returns:
        List of merged snippets without overlaps
    """
    if not snippets:
        return []

    # Find positions of each snippet in the content
    positions: list[tuple[int, int, str]] = []
    for snippet in snippets:
        start = content.find(snippet)
        if start != -1:
            positions.append((start, start + len(snippet), snippet))

    # Sort by start position
    positions.sort(key=lambda x: x[0])

    # Merge overlapping snippets
    merged = []
    current_start, current_end, current_snippet = positions[0]

    for start, end, snippet in positions[1:]:
        if start <= current_end:
            # Overlapping - extend the current snippet
            if end > current_end:
                current_end = end
                current_snippet = content[current_start:current_end]
        else:
            # No overlap - save current and start new
            merged.append(current_snippet)
            current_start, current_end, current_snippet = start, end, snippet

    merged.append(current_snippet)
    return merged
