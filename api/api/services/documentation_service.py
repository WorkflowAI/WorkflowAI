import asyncio
import logging
import os
from typing import Literal

import httpx

from core.agents.pick_relevant_documentation_categories import (
    PickRelevantDocumentationSectionsInput,
    pick_relevant_documentation_sections,
)
from core.domain.documentation_section import DocumentationSection
from core.domain.fields.chat_message import ChatMessage
from core.utils.redis_cache import redis_cached

_logger = logging.getLogger(__name__)


# TODO: we won't need this when the playground agent will be directly connected to update to date WorkflowAI docs
DEFAULT_DOC_SECTIONS: list[DocumentationSection] = [
    DocumentationSection(
        title="Business Associate Agreements (BAA)",
        content="WorkflowAI has signed BBAs with all the providers offered on the WorkflowAI platform (OpenAI, Anthropic, Fireworks, etc.).",
    ),
    DocumentationSection(
        title="Hosting of DeepSeek models",
        content="Also alse the DeepSeek models offered by WorkflowAI are US hosted.",
    ),
]

# local reads from local docsv2 folder,
# 'remote' reads from the fumadocs nextjs app instance
# TODO: totally decomission local mode
DocModeEnum = Literal["local", "remote"]

WORKFLOWAI_DOCS_URL = os.getenv("WORKFLOWAI_DOCS_URL", "http://docs2.workflowai.com")


class DocumentationService:
    _LOCAL_DOCS_DIR: str = "docsv2"
    _LOCAL_FILE_EXTENSIONS: list[str] = [".mdx", ".md"]

    async def _get_all_doc_sections_local(self) -> list[DocumentationSection]:
        doc_sections: list[DocumentationSection] = []
        base_dir: str = self._LOCAL_DOCS_DIR
        if not os.path.isdir(base_dir):
            _logger.error("Documentation directory not found", extra={"base_dir": base_dir})
            return []

        for root, _, files in os.walk(base_dir):
            for file in files:
                if not file.endswith(tuple(self._LOCAL_FILE_EXTENSIONS)):
                    continue
                if file.startswith("."):  # Ignore hidden files like .DS_Store
                    continue
                full_path: str = os.path.join(root, file)
                relative_path: str = os.path.relpath(full_path, base_dir)
                try:
                    with open(full_path, "r") as f:  # noqa: ASYNC230
                        doc_sections.append(
                            DocumentationSection(title=relative_path, content=f.read()),
                        )
                except Exception as e:
                    _logger.exception(
                        "Error reading or processing documentation file",
                        extra={"file_path": full_path},
                        exc_info=e,
                    )
        return doc_sections

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
                    page_title = page_raw["title"]
                    doc_sections.append(
                        DocumentationSection(title=page_title, content=page_content),
                    )

            except Exception as e:
                _logger.exception(
                    "Failed to fetch documentation page list",
                    exc_info=e,
                )

        return doc_sections

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

    async def get_all_doc_sections(self, mode: DocModeEnum = "remote") -> list[DocumentationSection]:
        """Get all documentation sections based on the configured mode"""
        match mode:
            case "local":
                return await self._get_all_doc_sections_local()
            case "remote":
                return await self._get_all_doc_sections_remote()

    async def _get_documentation_by_path_local(self, pathes: list[str]) -> list[DocumentationSection]:
        all_doc_sections: list[DocumentationSection] = await self._get_all_doc_sections_local()
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
                if content:
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
        mode: DocModeEnum = "remote",
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
        mode: DocModeEnum = "remote",
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

        return DEFAULT_DOC_SECTIONS + [
            document_section for document_section in all_doc_sections if document_section.title in relevant_doc_sections
        ]
