import logging
import os

from core.agents.pick_relevant_documentation_categories import (
    PickRelevantDocumentationSectionsInput,
    pick_relevant_documentation_sections,
)
from core.domain.documentation_section import DocumentationSection
from core.domain.fields.chat_message import ChatMessage

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


class DocumentationService:
    _DOCS_DIR: str = "docsv2"
    FILE_EXTENSIONS: list[str] = [".mdx", ".md"]

    def get_all_doc_sections(self) -> list[DocumentationSection]:
        doc_sections: list[DocumentationSection] = []
        base_dir: str = self._DOCS_DIR
        if not os.path.isdir(base_dir):
            _logger.error("Documentation directory not found", extra={"base_dir": base_dir})
            return []

        for root, _, files in os.walk(base_dir):
            for file in files:
                if not file.endswith(tuple(self.FILE_EXTENSIONS)):
                    continue
                if file.startswith("."):  # Ignore hidden files like .DS_Store
                    continue
                full_path: str = os.path.join(root, file)
                relative_path: str = os.path.relpath(full_path, base_dir)
                try:
                    with open(full_path, "r") as f:
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

    def get_documentation_by_path(self, pathes: list[str]) -> list[DocumentationSection]:
        all_doc_sections: list[DocumentationSection] = self.get_all_doc_sections()
        found_sections = [doc_section for doc_section in all_doc_sections if doc_section.title in pathes]

        # Check if any paths were not found
        found_paths = {doc_section.title for doc_section in found_sections}
        missing_paths = set(pathes) - found_paths

        if missing_paths:
            _logger.error(f"Documentation not found for paths: {', '.join(missing_paths)}")  # noqa: G004

        return found_sections

    async def get_relevant_doc_sections(
        self,
        chat_messages: list[ChatMessage],
        agent_instructions: str,
    ) -> list[DocumentationSection]:
        all_doc_sections: list[DocumentationSection] = self.get_all_doc_sections()

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
