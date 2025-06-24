import tempfile
from pathlib import Path

import pytest

from api.routers.mcp._utils.documentation_discovery import DocumentationDiscovery

# pyright: reportPrivateUsage=false


@pytest.mark.asyncio
async def test_parse_frontmatter():
    """Test the frontmatter parsing functionality."""
    # Test valid frontmatter
    content = """---
title: Test Page
summary: This is a test page summary
---

# Page content
Some content here."""

    result = DocumentationDiscovery._parse_frontmatter(content)
    assert result is not None
    assert result["title"] == "Test Page"
    assert result["summary"] == "This is a test page summary"

    # Test content without frontmatter
    content_no_frontmatter = "# Just a heading\nSome content"
    result = DocumentationDiscovery._parse_frontmatter(content_no_frontmatter)
    assert result is None

    # Test invalid YAML in frontmatter
    content_invalid_yaml = """---
title: : : Invalid YAML
---
Content"""
    result = DocumentationDiscovery._parse_frontmatter(content_invalid_yaml)
    assert result is None


@pytest.mark.asyncio
async def test_get_page_key():
    """Test the page key generation."""
    base_dir = Path("/workspace/docsv2/content/docs")

    # Test root level file
    file_path = base_dir / "index.mdx"
    assert DocumentationDiscovery._get_page_key(file_path, base_dir) == "index"

    # Test nested file
    file_path = base_dir / "use-cases" / "chatbot.mdx"
    assert DocumentationDiscovery._get_page_key(file_path, base_dir) == "use-cases/chatbot"

    # Test deeply nested file
    file_path = base_dir / "reference" / "api" / "errors.md"
    assert DocumentationDiscovery._get_page_key(file_path, base_dir) == "reference/api/errors"


@pytest.mark.asyncio
async def test_discover_documentation_structure():
    """Test the documentation discovery with a temporary directory structure."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a mock documentation structure
        docs_dir = Path(temp_dir) / "docsv2" / "content" / "docs"
        docs_dir.mkdir(parents=True)

        # Save original directory
        original_docs_dir = DocumentationDiscovery._DOCS_DIR
        DocumentationDiscovery._DOCS_DIR = str(docs_dir)

        try:
            # Create test files with frontmatter
            test_files = {
                "index.mdx": """---
title: Overview
summary: Introduction to the documentation
---
Content""",
                "use-cases/chatbot.mdx": """---
title: Building a Chatbot
summary: Guide for creating AI chatbots
---
Content""",
                "reference/api-errors.mdx": """---
title: API Error Reference
summary: Common API errors and solutions
---
Content""",
                # File without summary
                "quickstarts/no-code.mdx": """---
title: No-Code Quickstart
---
Content""",
                # File without frontmatter (should be skipped)
                "invalid.mdx": "# No frontmatter here",
                # Hidden file (should be skipped)
                ".hidden.mdx": """---
title: Hidden
---
Content""",
                # meta.json (should be skipped)
                "meta.json": '{"order": ["index", "quickstarts"]}',
            }

            # Create the test files
            for file_path, content in test_files.items():
                full_path = docs_dir / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)

            # Run discovery
            result = await DocumentationDiscovery.discover_documentation_structure()

            # Verify results
            assert len(result) == 4  # Should find 4 valid files

            # Check specific entries
            assert "index" in result
            assert result["index"]["title"] == "Overview"
            assert result["index"]["summary"] == "Introduction to the documentation"

            assert "use-cases/chatbot" in result
            assert result["use-cases/chatbot"]["title"] == "Building a Chatbot"
            assert result["use-cases/chatbot"]["summary"] == "Guide for creating AI chatbots"

            assert "reference/api-errors" in result
            assert result["reference/api-errors"]["title"] == "API Error Reference"

            assert "quickstarts/no-code" in result
            assert result["quickstarts/no-code"]["title"] == "No-Code Quickstart"
            assert result["quickstarts/no-code"]["summary"] == ""  # No summary provided

            # Verify skipped files
            assert "invalid" not in result
            assert ".hidden" not in result
            assert "meta.json" not in result

        finally:
            # Restore original directory
            DocumentationDiscovery._DOCS_DIR = original_docs_dir


@pytest.mark.asyncio
async def test_format_available_pages_docstring():
    """Test the docstring formatting."""
    docs_structure = {
        "index": {"title": "Overview", "summary": "Main documentation page"},
        "use-cases/chatbot": {"title": "Chatbot Guide", "summary": "Building chatbots"},
        "reference/api": {"title": "API Reference", "summary": ""},
        "quickstarts/python": {"title": "Python Quickstart", "summary": "Get started with Python"},
    }

    result = DocumentationDiscovery.format_available_pages_docstring(docs_structure)

    # Check that categories are present
    assert "**Getting Started:**" in result
    assert "**Use Cases:**" in result
    assert "**API Reference:**" in result
    assert "**Quickstarts:**" in result

    # Check specific entries
    assert "'index' - Overview. Main documentation page" in result
    assert "'use-cases/chatbot' - Chatbot Guide. Building chatbots" in result
    assert "'reference/api' - API Reference" in result  # No summary
    assert "'quickstarts/python' - Python Quickstart. Get started with Python" in result

    # Test empty structure
    empty_result = DocumentationDiscovery.format_available_pages_docstring({})
    assert empty_result == "No documentation pages available."
