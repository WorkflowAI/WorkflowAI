# pyright: reportPrivateUsage=false

import tempfile
from pathlib import Path

import pytest

from ._doc_discovery import DocDiscovery


@pytest.fixture
def temp_docs_dir():
    """Create a temporary docs directory with sample MDX files for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        docs_root = Path(tmpdir) / "docs"
        docs_root.mkdir()

        # Create root index file
        (docs_root / "index.mdx").write_text("""---
title: Overview
summary: Introduction to the platform
---

# Overview
Content here""")

        # Create use-cases directory with files
        use_cases_dir = docs_root / "use-cases"
        use_cases_dir.mkdir()

        (use_cases_dir / "chatbot.mdx").write_text("""---
title: Building Chatbots
summary: Guide for building conversational AI chatbots
---

# Chatbot Guide
Content here""")

        (use_cases_dir / "index.mdx").write_text("""---
title: Use Cases Overview
summary: Overview of different use cases for the platform
---

# Use Cases
Content here""")

        # Create reference directory
        ref_dir = docs_root / "reference"
        ref_dir.mkdir()

        (ref_dir / "authentication.mdx").write_text("""---
title: Authentication
summary: API authentication using bearer tokens
---

# Authentication
Content here""")

        # Create file without frontmatter (should be ignored)
        (docs_root / "no-frontmatter.mdx").write_text("# No Frontmatter\nThis file has no frontmatter")

        # Create partials file (should be ignored)
        partials_dir = docs_root / "partials"
        partials_dir.mkdir()
        (partials_dir / "partial.mdx").write_text("""---
title: Partial
summary: This should be ignored
---

# Partial Content""")

        yield str(docs_root)


def test_doc_discovery_parsing(temp_docs_dir):
    """Test that DocDiscovery correctly parses MDX files."""
    discovery = DocDiscovery(temp_docs_dir)
    pages = discovery.get_pages()

    # Should find 4 pages (excluding partials and no-frontmatter files)
    assert len(pages) == 4

    # Check that all pages have required fields
    for page in pages:
        assert page.title
        assert page.summary
        assert page.path
        assert page.category
        assert page.file_path

    # Verify specific pages
    page_paths = {page.path for page in pages}
    assert "index" in page_paths
    assert "use-cases/chatbot" in page_paths
    assert "use-cases" in page_paths
    assert "reference/authentication" in page_paths


def test_category_mapping(temp_docs_dir):
    """Test that categories are correctly assigned."""
    discovery = DocDiscovery(temp_docs_dir)
    pages = discovery.get_pages()

    page_categories = {page.path: page.category for page in pages}

    assert page_categories["index"] == "Getting Started"
    assert page_categories["use-cases/chatbot"] == "Use Cases"
    assert page_categories["use-cases"] == "Use Cases"
    assert page_categories["reference/authentication"] == "API Reference"


def test_generate_available_pages_description(temp_docs_dir):
    """Test that the available pages description is generated correctly."""
    discovery = DocDiscovery(temp_docs_dir)
    description = discovery.generate_available_pages_description()

    # Should contain the required structure
    assert "The following documentation pages are available for direct access:" in description
    assert "**API Reference:**" in description
    assert "**Getting Started:**" in description
    assert "**Use Cases:**" in description

    # Should contain specific pages
    assert "'index' - Introduction to the platform" in description
    assert "'use-cases/chatbot' - Guide for building conversational AI chatbots" in description
    assert "'reference/authentication' - API authentication using bearer tokens" in description


def test_caching(temp_docs_dir):
    """Test that caching works correctly."""
    discovery = DocDiscovery(temp_docs_dir)

    # First call should scan directory
    pages1 = discovery.get_pages()

    # Second call should use cache
    pages2 = discovery.get_pages()

    # Should be the same objects (due to caching)
    assert pages1 is pages2

    # Force refresh should rescan
    pages3 = discovery.get_pages(force_refresh=True)
    assert pages3 is not pages1
    assert len(pages3) == len(pages1)


def test_frontmatter_parsing():
    """Test frontmatter parsing with various formats."""
    discovery = DocDiscovery()

    # Valid frontmatter
    content1 = """---
title: Test Title
summary: Test summary
---

# Content"""
    frontmatter1 = discovery._parse_frontmatter(content1)
    assert frontmatter1["title"] == "Test Title"
    assert frontmatter1["summary"] == "Test summary"

    # No frontmatter
    content2 = "# Just content"
    frontmatter2 = discovery._parse_frontmatter(content2)
    assert frontmatter2 == {}

    # Invalid YAML
    content3 = """---
title: Test Title
invalid: [unclosed
---

# Content"""
    frontmatter3 = discovery._parse_frontmatter(content3)
    assert frontmatter3 == {}


def test_empty_directory():
    """Test behavior with empty or non-existent directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        non_existent = Path(tmpdir) / "non-existent"
        discovery = DocDiscovery(str(non_existent))
        pages = discovery.get_pages()
        assert pages == []

        description = discovery.generate_available_pages_description()
        assert description == "No documentation pages found."
