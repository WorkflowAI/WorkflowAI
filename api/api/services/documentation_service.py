import asyncio
import logging
import os
from typing import Literal

import httpx

from core.agents.pick_relevant_documentation_categories import (
    PickRelevantDocumentationSectionsInput,
    pick_relevant_documentation_sections,
)
from core.agents.search_documentation_agent import (
    search_documentation_agent,
)
from core.domain.documentation_section import DocumentationSection
from core.domain.fields.chat_message import ChatMessage
from core.utils.redis_cache import redis_cached

_logger = logging.getLogger(__name__)


# local reads from local docsv2 folder,
# 'remote' reads from the fumadocs nextjs app instance
# TODO: totally decomission local mode
DocModeEnum = Literal["local", "remote"]

DEFAULT_DOC_MODE: DocModeEnum = "local"

WORKFLOWAI_DOCS_URL = os.getenv("WORKFLOWAI_DOCS_URL", "https://docs2.workflowai.com")


class DocumentationService:
    _LOCAL_DOCS_DIR: str = "docsv2/content/docs"
    _LOCAL_FILE_EXTENSIONS: list[str] = [".mdx", ".md"]

    def _get_all_doc_sections_local(self) -> list[DocumentationSection]:
        doc_sections: list[DocumentationSection] = []
        base_dir: str = self._LOCAL_DOCS_DIR
        if not os.path.isdir(base_dir):
            _logger.error("Documentation directory not found", extra={"base_dir": base_dir})
            return []

        for root, _, files in os.walk(base_dir):
            for file in files:
                if not file.endswith(tuple(self._LOCAL_FILE_EXTENSIONS)):
                    continue
                if file.startswith(".") or ".private" in file:  # Ignore hidden files and private pages
                    continue
                full_path: str = os.path.join(root, file)
                relative_path: str = os.path.relpath(full_path, base_dir)
                try:
                    with open(full_path, "r") as f:
                        doc_sections.append(
                            DocumentationSection(
                                title=relative_path.replace(".mdx", "").replace(".md", ""),
                                content=f.read(),
                            ),
                        )
                except Exception as e:
                    _logger.exception(
                        "Error reading or processing documentation file",
                        extra={"file_path": full_path},
                        exc_info=e,
                    )
        # Sort by title to ensure consistent ordering, for example to trigger LLM provider caching
        return sorted(doc_sections, key=lambda x: x.title)

    async def _get_all_doc_sections_remote(self) -> list[DocumentationSection]:
        """Fetch all documentation sections from remote fumadocs instance"""
        doc_sections: list[DocumentationSection] = []

        async with httpx.AsyncClient() as http_client:
            try:
                _logger.info("Fetching documentation sections from remote fumadocs instance")
                url = f"{WORKFLOWAI_DOCS_URL}/api/ai/index"
                response = await http_client.get(url)
                response.raise_for_status()

                tasks = [self._fetch_page_content(page_raw["url"].lstrip("/")) for page_raw in response.json()["pages"]]
                page_contents = await asyncio.gather(*tasks)

                for page_raw, page_content in zip(response.json()["pages"], page_contents):
                    page_title = page_raw["url"].lstrip("/")
                    doc_sections.append(
                        DocumentationSection(title=page_title, content=page_content),
                    )

            except Exception as e:
                _logger.exception(
                    "Failed to fetch documentation page list",
                    exc_info=e,
                )

        # Sort by title to ensure consistent ordering, for example to trigger LLM provider caching
        return sorted(doc_sections, key=lambda x: x.title)

    @redis_cached(expiration_seconds=60 * 15)
    async def _fetch_page_content(self, page_path: str) -> str:
        """Fetch content for a specific documentation page using the ?reader=ai parameter"""
        async with httpx.AsyncClient() as http_client:
            try:
                url = f"{WORKFLOWAI_DOCS_URL}/{page_path}?reader=ai"
                response = await http_client.get(url)
                response.raise_for_status()

                return response.text

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    _logger.exception(
                        "Documentation page not found",
                        extra={"page_path": page_path},
                        exc_info=e,
                    )
                    return "Page not found"
                raise e
            except Exception as e:
                url = f"{WORKFLOWAI_DOCS_URL}/{page_path}?reader=ai"
                _logger.exception(
                    "Error fetching page content",
                    extra={"page_path": page_path, "url": url},
                    exc_info=e,
                )
                return "Error fetching page content"

    async def get_all_doc_sections(self, mode: DocModeEnum = DEFAULT_DOC_MODE) -> list[DocumentationSection]:
        """Get all documentation sections based on the configured mode"""
        match mode:
            case "local":
                return self._get_all_doc_sections_local()
            case "remote":
                return await self._get_all_doc_sections_remote()

    async def _get_documentation_by_path_local(self, pathes: list[str]) -> list[DocumentationSection]:
        all_doc_sections: list[DocumentationSection] = self._get_all_doc_sections_local()
        found_sections = [doc_section for doc_section in all_doc_sections if doc_section.title in pathes]

        # Check if any paths were not found
        found_paths = {doc_section.title for doc_section in found_sections}
        missing_paths = set(pathes) - found_paths

        if missing_paths:
            _logger.error(f"Documentation not found for paths: {', '.join(missing_paths)}")  # noqa: G004

        return found_sections

    async def get_documentation_by_path_remote(self, paths: list[str]) -> list[DocumentationSection]:
        """Get specific documentation sections by path from remote source"""
        doc_sections: list[DocumentationSection] = []

        for path in paths:
            try:
                content = await self._fetch_page_content(path)
                doc_sections.append(
                    DocumentationSection(title=path, content=content),
                )
            except Exception as e:
                _logger.warning(
                    "Failed to fetch documentation by path",
                    extra={"path": path},
                    exc_info=e,
                )

        # Check if any paths were not found
        found_paths = {doc_section.title for doc_section in doc_sections}
        missing_paths = set(paths) - found_paths

        if missing_paths:
            _logger.error(f"Documentation not found for paths: {', '.join(missing_paths)}")  # noqa: G004

        return doc_sections

    async def get_documentation_by_path(
        self,
        paths: list[str],
        mode: DocModeEnum = DEFAULT_DOC_MODE,
    ) -> list[DocumentationSection]:
        """Get documentation by path based on the configured mode"""
        match mode:
            case "local":
                return await self._get_documentation_by_path_local(paths)
            case "remote":
                return await self.get_documentation_by_path_remote(paths)

    async def get_relevant_doc_sections(
        self,
        chat_messages: list[ChatMessage],
        agent_instructions: str,
        mode: DocModeEnum = DEFAULT_DOC_MODE,
    ) -> list[DocumentationSection]:
        all_doc_sections: list[DocumentationSection] = await self.get_all_doc_sections(mode)

        try:
            relevant_doc_sections: list[str] = (
                await pick_relevant_documentation_sections(
                    PickRelevantDocumentationSectionsInput(
                        available_doc_sections=all_doc_sections,
                        chat_messages=chat_messages,
                        agent_instructions=agent_instructions,
                    ),
                )
            ).relevant_doc_sections
        except Exception as e:
            _logger.exception("Error getting relevant doc sections", exc_info=e)
            # Fallback on all doc sections (no filtering)
            relevant_doc_sections: list[str] = [doc_category.title for doc_category in all_doc_sections]

        return [
            document_section for document_section in all_doc_sections if document_section.title in relevant_doc_sections
        ]

    def _extract_summary_from_content(self, content: str) -> str:
        """Extract a summary from markdown content."""
        lines = content.split("\n")

        # Look for frontmatter summary
        if lines and lines[0].strip() == "---":
            for i in range(1, min(20, len(lines))):  # Check first 20 lines for frontmatter
                line = lines[i].strip()
                if line == "---":
                    break
                if line.startswith("summary:"):
                    return line.split("summary:", 1)[1].strip().strip("\"'")

        # Fallback when no summary is found
        return ""

    # For now, this function cannot be async meaning we can only use the local files
    # It is called from mcp_server.py which resolves the tool description
    def get_available_pages_descriptions(self) -> str:
        """Generate formatted descriptions of all available documentation pages for MCP tool docstring.

        TODO: Add caching (e.g., @redis_cached) to avoid repeated file system scans - good performance optimization.
        """
        try:
            all_sections = self._get_all_doc_sections_local()

            if not all_sections:
                return "No documentation pages found."

            # Build simple list of pages with descriptions
            result_lines: list[str] = []

            for section in sorted(all_sections, key=lambda s: s.title):
                page_path = section.title
                summary = self._extract_summary_from_content(section.content)
                result_lines.append(f"     - '{page_path}' - {summary}")

            return "\n".join(result_lines)

        except Exception as e:
            _logger.exception("Error generating available pages descriptions", exc_info=e)
            # Fallback to empty list when there's an error
            return ""

    async def search_documentation_by_query(
        self,
        query: str,
        mode: DocModeEnum = DEFAULT_DOC_MODE,
    ) -> list[DocumentationSection]:
        all_doc_sections: list[DocumentationSection] = await self.get_all_doc_sections(mode)

        # TODO: have a static list of the most relevant docs as a fallback ?
        fallback_docs_sections: list[DocumentationSection] = []

        try:
            result = await search_documentation_agent(
                query=query,
                available_doc_sections=all_doc_sections,
                usage_context="""The query was made by an MCP (Model Context Protocol) client such as Cursor IDE and other code editors.

Your primary purpose is to help developers find the most relevant WorkflowAI documentation sections to answer their specific queries about building, deploying, and using AI agents.
""",
            )

            if not result:
                _logger.error(
                    "search_documentation_agent did not return any parsed result",
                    extra={"query": query},
                )
                return fallback_docs_sections

            relevant_doc_sections: list[str] = (
                result.relevant_doc_sections if result and result.relevant_doc_sections else []
            )

            # Log warning for cases where the agent has reported a missing doc sections
            if result and result.missing_doc_sections_feedback:
                _logger.warning(
                    "Documentation search agent has reported a missing doc sections",
                    extra={
                        "missing_doc_sections_feedback": result.missing_doc_sections_feedback,
                    },
                )

            # If agent did not report any missing doc sections but no relevant doc sections were found, we log a warning too
            if result and not result.missing_doc_sections_feedback and not result.relevant_doc_sections:
                _logger.warning(
                    "Documentation search agent has not found any relevant doc sections",
                    extra={"query": query},
                )

        except Exception as e:
            _logger.exception("Error in search documentation agent", exc_info=e)
            return fallback_docs_sections

        return [
            document_section for document_section in all_doc_sections if document_section.title in relevant_doc_sections
        ]
