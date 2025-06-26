import logging
import os

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, Field

from core.domain.documentation_section import DocumentationSection

logger = logging.getLogger(__name__)


class SearchDocumentationOutput(BaseModel):
    relevant_doc_sections: list[str] | None = Field(
        default=None,
        description="List of documentation section titles that are most relevant to answer the query.",
    )
    missing_doc_sections_feedback: str | None = Field(
        default=None,
        description="When relevant, output a feedback to explain which documentation sections are missing to fully answer the user's query and why.",
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
    client = AsyncOpenAI(
        api_key=os.environ["WORKFLOWAI_API_KEY"],
        base_url=f"{os.environ['WORKFLOWAI_API_URL']}/v1",
    )

    formatted_docs = ""

    for doc_section in available_doc_sections:
        formatted_docs += f"## title: {doc_section.title}\n content: {doc_section.content}\n\n"

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
1. Analyze the query to understand the user's intent and needs
2. Select the most relevant documentation sections that will help answer the 'Search Query' below
3. Prioritize sections that directly address the 'Search Query' below over tangentially related content
4. Return the picked documentation section title(s) in a 'relevant_doc_sections' list and optionally a 'missing_doc_sections_feedback' if you think some documentation sections are missing to fully answer the user's query. You MUST ONLY return section titles that exist in the available 'Available Documentation Sections' sections.

## Available Documentation Sections:
{{formatted_docs}}""",
        },
        {
            "role": "user",
            "content": "Search Query: {{query}}",
        },
    ]

    completion = await client.beta.chat.completions.parse(
        model="gemini-2.5-flash",
        messages=messages,
        response_format=SearchDocumentationOutput,
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
    return completion.choices[0].message.parsed
