import logging
import os

from core.agents.meta_agent import MetaAgentChatMessage
from core.agents.pick_relevant_documentation_categories import (
    PickRelevantDocumentationSectionsInput,
    pick_relevant_documentation_sections,
)
from core.domain.documentation_section import DocumentationSection

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
    _DOCS_DIR: str = "docs"

    def get_all_doc_sections(self) -> list[DocumentationSection]:
        doc_sections: list[DocumentationSection] = []
        base_dir: str = self._DOCS_DIR
        if not os.path.isdir(base_dir):
            _logger.error("Documentation directory not found", extra={"base_dir": base_dir})
            return []

        for root, _, files in os.walk(base_dir):
            for file in files:
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

    @classmethod
    def build_api_docs_prompt(cls, folder_name: str = _DOCS_DIR) -> str:
        api_docs: str = ""
        if not os.path.isdir(folder_name):
            _logger.error("Documentation directory not found for building prompt", extra={"folder_name": folder_name})
            return ""

        for root, _, files in os.walk(folder_name):
            for file in files:
                if file.startswith("."):
                    continue
                full_path: str = os.path.join(root, file)
                relative_path: str = os.path.relpath(full_path, folder_name)
                try:
                    with open(full_path, "r") as f:
                        content: str = f.read()
                        api_docs += f"{relative_path}\n{content}\n\n"
                except Exception as e:
                    _logger.exception(
                        "Error reading documentation file for prompt",
                        extra={"file_path": full_path},
                        exc_info=e,
                    )

        return api_docs

    async def get_relevant_doc_sections(
        self,
        chat_messages: list[MetaAgentChatMessage],
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
