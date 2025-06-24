import re
from pathlib import Path

import yaml


class DocumentationDiscovery:
    """Dynamically discovers and parses documentation from the docsv2 directory."""

    _DOCS_DIR = "docsv2/content/docs"
    _FILE_EXTENSIONS = [".mdx", ".md"]

    @classmethod
    def _parse_frontmatter(cls, content: str) -> dict[str, str] | None:
        """Parse YAML frontmatter from MDX/MD content.

        Returns:
            Dictionary with frontmatter fields, or None if no frontmatter found
        """
        # Match frontmatter between --- markers at the start of the file
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if not match:
            return None

        try:
            frontmatter_str = match.group(1)
            return yaml.safe_load(frontmatter_str)
        except yaml.YAMLError:
            return None

    @classmethod
    def _get_page_key(cls, file_path: Path, base_dir: Path) -> str:
        """Convert file path to page key format (e.g., 'use-cases/chatbot')."""
        relative_path = file_path.relative_to(base_dir)
        # Remove file extension and convert to string
        page_key = str(relative_path.with_suffix(""))
        # Convert backslashes to forward slashes for consistency
        return page_key.replace("\\", "/")

    @classmethod
    async def discover_documentation_structure(cls) -> dict[str, dict[str, str]]:
        """Discover all documentation pages and their metadata.

        Returns:
            Dictionary mapping page keys to their metadata (title, summary)
        """
        docs_structure: dict[str, dict[str, str]] = {}
        base_dir = Path(cls._DOCS_DIR)

        if not base_dir.exists() or not base_dir.is_dir():
            return docs_structure

        # Walk through all documentation files
        for file_path in base_dir.rglob("*"):
            # Skip directories and non-documentation files
            if file_path.is_dir() or file_path.suffix not in cls._FILE_EXTENSIONS:
                continue

            # Skip hidden files
            if file_path.name.startswith("."):
                continue

            # Skip meta.json files
            if file_path.name == "meta.json":
                continue

            try:
                # Read file content
                content = file_path.read_text(encoding="utf-8")

                # Parse frontmatter
                frontmatter = cls._parse_frontmatter(content)
                if not frontmatter:
                    continue

                # Get page key
                page_key = cls._get_page_key(file_path, base_dir)

                # Extract metadata
                page_metadata = {
                    "title": frontmatter.get("title", page_key),
                    "summary": frontmatter.get("summary", frontmatter.get("description", "")),
                }

                # Only include if we have at least a title
                if page_metadata["title"]:
                    docs_structure[page_key] = page_metadata

            except Exception:
                # Skip files that can't be read or parsed
                continue

        return docs_structure

    @classmethod
    def format_available_pages_docstring(cls, docs_structure: dict[str, dict[str, str]]) -> str:
        """Format the documentation structure into a docstring for the MCP tool.

        Args:
            docs_structure: Dictionary mapping page keys to metadata

        Returns:
            Formatted docstring with categorized documentation pages
        """
        if not docs_structure:
            return "No documentation pages available."

        # Categorize pages
        categories: dict[str, list[tuple[str, dict[str, str]]]] = {
            "Getting Started": [],
            "Use Cases": [],
            "API Reference": [],
            "Quickstarts": [],
            "Playground": [],
            "Observability": [],
            "Inference": [],
            "Deployments": [],
            "Evaluations": [],
            "Agents": [],
            "AI Engineer": [],
            "Components": [],
        }

        # Sort pages into categories
        for page_key, metadata in sorted(docs_structure.items()):
            if page_key.startswith("use-cases/"):
                categories["Use Cases"].append((page_key, metadata))
            elif page_key.startswith("reference/"):
                categories["API Reference"].append((page_key, metadata))
            elif page_key.startswith("quickstarts/"):
                categories["Quickstarts"].append((page_key, metadata))
            elif page_key.startswith("playground/"):
                categories["Playground"].append((page_key, metadata))
            elif page_key.startswith("observability/"):
                categories["Observability"].append((page_key, metadata))
            elif page_key.startswith("inference/"):
                categories["Inference"].append((page_key, metadata))
            elif page_key.startswith("deployments/"):
                categories["Deployments"].append((page_key, metadata))
            elif page_key.startswith("evaluations/"):
                categories["Evaluations"].append((page_key, metadata))
            elif page_key.startswith("agents/"):
                categories["Agents"].append((page_key, metadata))
            elif page_key.startswith("ai-engineer/"):
                categories["AI Engineer"].append((page_key, metadata))
            elif page_key.startswith("components/"):
                categories["Components"].append((page_key, metadata))
            else:
                # Root level pages go to Getting Started
                categories["Getting Started"].append((page_key, metadata))

        # Build the docstring
        lines = ["The following documentation pages are available for direct access:\n"]

        for category, pages in categories.items():
            if not pages:
                continue

            lines.append(f"     **{category}:**")
            for page_key, metadata in pages:
                title = metadata["title"]
                summary = metadata["summary"]

                # Format the entry
                if summary:
                    lines.append(f"     - '{page_key}' - {title}. {summary}")
                else:
                    lines.append(f"     - '{page_key}' - {title}")

            lines.append("")  # Empty line between categories

        return "\n".join(lines).rstrip()
