"""
Utility module for dynamic documentation discovery.

This module scans the docsv2/content/docs directory and parses MDX files
to extract frontmatter (title and summary) for the MCP search_documentation tool.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class DocPage:
    """Represents a documentation page with its metadata."""

    path: str  # Relative path from docs root (e.g., "use-cases/new_agent")
    title: str
    summary: str
    category: str  # Top-level category (e.g., "Use Cases", "Getting Started")
    file_path: str  # Full file path


class DocDiscovery:
    """Handles discovery and parsing of documentation files."""

    def __init__(self, docs_root: str = "docsv2/content/docs"):
        self.docs_root = Path(docs_root)
        self._pages_cache: list[DocPage] | None = None

    def _parse_frontmatter(self, content: str) -> dict[str, str]:
        """Parse YAML frontmatter from MDX content."""
        frontmatter_pattern = r"^---\s*\n(.*?)\n---\s*\n"
        match = re.match(frontmatter_pattern, content, re.DOTALL)

        if not match:
            return {}

        try:
            return yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            return {}

    def _get_category_name(self, directory: str) -> str:
        """Convert directory name to human-readable category name."""
        category_mapping = {
            "use-cases": "Use Cases",
            "reference": "API Reference",
            "quickstarts": "Quickstarts",
            "playground": "Playground",
            "observability": "Observability",
            "inference": "Inference",
            "deployments": "Deployments",
            "evaluations": "Evaluations",
            "agents": "Agents",
            "ai-engineer": "AI Engineer",
            "components": "Components",
        }
        return category_mapping.get(directory, directory.title())

    def _scan_directory(self) -> list[DocPage]:
        """Scan the documentation directory and parse all MDX files."""
        pages: list[DocPage] = []

        if not self.docs_root.exists():
            return pages

        # Find all MDX files
        mdx_files = list(self.docs_root.rglob("*.mdx"))

        for mdx_file in mdx_files:
            # Skip files in partials directory
            if "partials" in mdx_file.parts:
                continue

            try:
                with open(mdx_file, "r", encoding="utf-8") as f:
                    content = f.read()

                frontmatter = self._parse_frontmatter(content)
                title = frontmatter.get("title", "")
                summary = frontmatter.get("summary", "")

                # Skip files without title or summary
                if not title or not summary:
                    continue

                # Get relative path from docs root
                rel_path = mdx_file.relative_to(self.docs_root)

                # Convert path to page identifier (remove .mdx extension)
                page_path = str(rel_path.with_suffix(""))

                # Handle index files specially
                if rel_path.name == "index.mdx":
                    if rel_path.parent == Path("."):
                        # Root index file
                        page_path = "index"
                        category = "Getting Started"
                    else:
                        # Directory index file
                        page_path = str(rel_path.parent)
                        category = self._get_category_name(rel_path.parent.name)
                else:
                    # Regular file
                    if rel_path.parent == Path("."):
                        # Root level file
                        category = "Getting Started"
                    else:
                        category = self._get_category_name(rel_path.parent.parts[0])

                pages.append(
                    DocPage(
                        path=page_path,
                        title=title,
                        summary=summary,
                        category=category,
                        file_path=str(mdx_file),
                    ),
                )

            except Exception as e:
                # Log error but continue processing other files
                print(f"Error processing {mdx_file}: {e}")
                continue

        return pages

    def get_pages(self, force_refresh: bool = False) -> list[DocPage]:
        """Get all documentation pages, with caching."""
        if self._pages_cache is None or force_refresh:
            self._pages_cache = self._scan_directory()
        return self._pages_cache

    def generate_available_pages_description(self) -> str:
        """Generate the available pages description for the MCP tool docstring."""
        pages = self.get_pages()

        if not pages:
            return "No documentation pages found."

        # Group pages by category
        categories: dict[str, list[DocPage]] = {}
        for page in pages:
            if page.category not in categories:
                categories[page.category] = []
            categories[page.category].append(page)

        # Sort categories and pages within each category
        sorted_categories = sorted(categories.keys())

        description_parts: list[str] = []
        description_parts.append("The following documentation pages are available for direct access:")
        description_parts.append("")

        for category in sorted_categories:
            category_pages = sorted(categories[category], key=lambda p: p.path)
            description_parts.append(f"**{category}:**")

            for page in category_pages:
                description_parts.append(f"- '{page.path}' - {page.summary}")

            description_parts.append("")

        return "\n     ".join(description_parts)


# Global instance for the MCP server
_doc_discovery = DocDiscovery()


def get_doc_discovery() -> DocDiscovery:
    """Get the global DocDiscovery instance."""
    return _doc_discovery
