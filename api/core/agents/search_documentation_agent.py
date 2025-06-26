import json
import logging
import os
from typing import Any

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, Field

from core.domain.documentation_section import DocumentationSection

logger = logging.getLogger(__name__)


def create_search_documentation_json_schema(available_section_file_paths: list[str]) -> dict[str, Any]:
    """Create a JSON schema with enum constraints for documentation section file paths."""
    return {
        "type": "object",
        "properties": {
            "relevant_documentation_file_paths": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": available_section_file_paths,
                },
                "description": "List of documentation section file paths that are most relevant to answer the query.",
                "default": None,
            },
            "missing_doc_sections_feedback": {
                "type": "string",
                "description": "When relevant, output a feedback to explain which documentation sections are missing to fully answer the user's query. Only applies to WorkflowAI related queries.",
                "default": None,
            },
        },
        "additionalProperties": False,
    }


class SearchDocumentationOutput(BaseModel):
    """Base model for search documentation output."""

    relevant_documentation_file_paths: list[str] | None = Field(
        default=None,
        description="List of documentation section file paths that are most relevant to answer the query.",
    )
    missing_doc_sections_feedback: str | None = Field(
        default=None,
        description="When relevant, output a feedback to explain which documentation sections are missing to fully answer the user's query. Only applies to WorkflowAI related queries.",
        examples=[
            "I could not find any documentation section regarding ...",
            "There is no section about ...",
        ],
    )


async def search_documentation_agent(
    query: str,
    available_doc_sections: list[DocumentationSection],
    usage_context: str | None = None,
) -> SearchDocumentationOutput | None:
    # Dynamically create JSON schema with enum constraints for available documentation sections
    available_section_paths = [section.file_path for section in available_doc_sections]
    json_schema = create_search_documentation_json_schema(available_section_paths)

    client = AsyncOpenAI(
        api_key=os.environ["WORKFLOWAI_API_KEY"],
        base_url=f"{os.environ['WORKFLOWAI_API_URL']}/v1",
    )

    formatted_docs = ""

    for doc_section in available_doc_sections:
        formatted_docs += f"## file_path: {doc_section.file_path}\n content: {doc_section.content}\n\n"

    messages: list[ChatCompletionMessageParam] = [
        {
            "role": "system",
            "content": """You are an expert documentation search agent specifically designed for picking the most relevant documentation sections based on the provided query{% if usage_context %} and the usage context{% endif %}.

{% if usage_context %}
## Context
The usage context is:
{{usage_context}}
{% endif %}


## Your Task
Given a search query and all available documentation sections, you must:
1. Analyze the query to understand the user's intent and needs. If the query is not related to the WorkflowAI platform, you should return an empty list of relevant documentation sections
2. Select the most relevant documentation sections that will help answer the 'Search Query' below. Aim for 1 to 5 of the most relevant sections for the search query.
3. Prioritize sections that directly address the 'Search Query' below over tangentially related content
4. Return the picked documentation section file_path(s) in a 'relevant_documentation_file_paths' list and optionally a 'missing_doc_sections_feedback' if you think some documentation sections are missing to fully answer the user's query.
You MUST ONLY return section 'file_path' that exist in the available 'Available Documentation Sections' sections.

## Available Documentation Sections:
{{formatted_docs}}""",
        },
        {
            "role": "user",
            "content": "Search Query: {{query}}",
        },
    ]

    completion = await client.chat.completions.create(
        model="gemini-2.5-flash",
        messages=messages,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "SearchDocumentationOutput",
                "schema": json_schema,
            },
        },
        extra_body={
            "input": {
                "query": query,
                "formatted_docs": formatted_docs,
                "usage_context": usage_context,
            },
            "provider": "google_gemini",  # use Google Gemini to have implicit caching (https://ai.google.dev/gemini-api/docs/caching?lang=node&hl=fr#implicit-caching)
        },
        metadata={
            "agent_id": "search-documentation-agent",
        },
    )

    if completion.choices[0].message.content:
        response_data = json.loads(completion.choices[0].message.content)
        return SearchDocumentationOutput.model_validate(response_data)

    return None
