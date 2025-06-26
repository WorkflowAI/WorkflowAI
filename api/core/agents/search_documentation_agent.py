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


async def search_documentation_agent(
    query: str,
    available_doc_sections: list[DocumentationSection],
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
            "content": """You are an expert documentation search agent specifically designed for MCP (Model Context Protocol) clients such as Cursor IDE and other code editors.

Your primary purpose is to help developers find the most relevant WorkflowAI documentation sections to answer their specific queries about building, deploying, and using AI agents.


## Your Task
Given a search query and all available documentation sections, you must:
1. Analyze the query to understand the developer's intent and needs
2. Select the most relevant documentation sections that will help answer their question
3. Prioritize sections that directly address the query over tangentially related content
4. Avoid selecting unnecessary sections to minimize cost and processing time
5. Return the picked docuementationt section titl(s) in a 'relevant_doc_sections' list. You MUST ONLY return section titles that exist in the available 'Available Documentation Sections' sections.

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
            },
            "provider": "google_gemini",  # use Google Gemini to have implicit caching (https://ai.google.dev/gemini-api/docs/caching?lang=node&hl=fr#implicit-caching)
        },
        metadata={
            "agent_id": "search-documentation-agent",
        },
    )

    return completion.choices[0].message.parsed
