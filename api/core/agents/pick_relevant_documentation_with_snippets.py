import workflowai
from pydantic import BaseModel, Field

from core.domain.documentation_section import DocumentationSection
from core.domain.fields.chat_message import ChatMessage


class DocumentationSnippet(BaseModel):
    section_title: str = Field(description="The title of the documentation section this snippet belongs to")
    snippet_beginning: str = Field(
        description="The beginning of the relevant snippet (first 10-20 characters to uniquely identify the start)",
    )
    snippet_ending: str = Field(
        description="The ending of the relevant snippet (last 10-20 characters to uniquely identify the end)",
    )
    relevance_reason: str = Field(
        description="Why this specific snippet is relevant to the user's query",
    )


class PickRelevantDocumentationWithSnippetsInput(BaseModel):
    chat_messages: list[ChatMessage] | None = Field(
        default=None,
        description="The chat messages between the user and the assistant.",
    )
    agent_instructions: str | None = Field(
        default=None,
        description="The agent's internal instructions.",
    )
    available_doc_sections: list[DocumentationSection] | None = Field(
        default=None,
        description="The available documentation sections.",
    )


class PickRelevantDocumentationWithSnippetsOutput(BaseModel):
    overall_reason: str = Field(description="The overall reason for the choice of documentation sections and snippets.")
    relevant_snippets: list[DocumentationSnippet] = Field(
        description="The relevant documentation snippets for the agent.",
    )


@workflowai.agent(model=workflowai.Model.GEMINI_2_0_FLASH_001)
async def pick_relevant_documentation_with_snippets(
    input: PickRelevantDocumentationWithSnippetsInput,
) -> PickRelevantDocumentationWithSnippetsOutput:
    """
    You are an expert at picking relevant documentation sections and pinpointing specific snippets within them.

    Your goal is to analyze the chat history and the agent's instructions, and:
    1. Pick the needed documentation sections from 'available_doc_sections' required to answer the user's question
    2. For each relevant section, identify specific snippet(s) that are most relevant

    For each snippet, you must provide:
    - The section title it belongs to
    - The beginning of the snippet (first 10-20 characters that uniquely identify where the snippet starts)
    - The ending of the snippet (last 10-20 characters that uniquely identify where the snippet ends)
    - A reason why this specific snippet is relevant

    Guidelines for snippet selection:
    - Be precise: Select only the most relevant parts, not entire sections
    - Be specific: The beginning and ending strings should be unique enough to identify the snippet location
    - Be minimal: Avoid selecting overlapping or redundant snippets
    - Focus on the latest user messages and avoid snippets for things already answered in the chat

    You must avoid picking unnecessary sections/snippets, because processing them will cost money and time.
    Unnecessary content includes:
    - Things that the agent already knows about based on the 'agent_instructions'
    - Things that are not directly related to the matters discussed in the 'chat_messages'
    - Things that were already answered in older messages of the 'chat_messages'

    Types of requests that typically do not require any documentation:
    - Instructions improvement
    - Schema updates
    - Picking models
    - Generating agent input
    These cases are usually well covered in the "agent_instructions".

    You MUST ONLY reference documentation sections that exist in 'available_doc_sections.title'
    """
    ...
