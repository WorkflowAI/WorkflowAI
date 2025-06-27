import os

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, Field


class DocumentationSection(BaseModel):
    title: str = Field(description="The title of the documentation section")
    content: str = Field(description="The content of the documentation section")


class SearchDocumentationOutput(BaseModel):
    relevant_doc_sections: list[str] | None = Field(
        default=None,
        description="List of documentation section titles that are most relevant to answer the query.",
    )
    missing_docs_feedback: str | None = Field(
        default=None,
        description="Optional. Feedback when useful documentation appears to be missing or when the query cannot be adequately answered with existing documentation.",
    )


client = OpenAI(
    api_key=os.environ["WORKFLOWAI_API_KEY"],
    base_url=f"{os.environ['WORKFLOWAI_API_URL']}/v1",
)


def search_documentation_agent(
    query: str,
    available_doc_sections: list[DocumentationSection],
) -> SearchDocumentationOutput | None:
    formatted_docs = ""

    for doc_section in available_doc_sections:
        formatted_docs += f"## title: {doc_section.title}\n content: {doc_section.content}\n\n"

    messages: list[ChatCompletionMessageParam] = [
        {
            "role": "system",
            "content": """You are an expert documentation search agent specifically designed for MCP (Model Context Protocol) clients such as Cursor IDE and other code editors.

Your primary purpose is to help developers find the most relevant WorkflowAI documentation sections to answer their specific queries about building, deploying, and using AI agents.

Do not output null values or empty strings or lists


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

    completion = client.beta.chat.completions.parse(
        model=os.environ.get("WORKFLOWAI_TEST_MODEL", "gemini-2.5-flash"),
        messages=messages,
        response_format=SearchDocumentationOutput,
        extra_body={
            "input": {
                "query": query,
                "formatted_docs": formatted_docs,
            },
        },
        metadata={
            "agent_id": "test-search-documentation-agent",
        },
    )

    return completion.choices[0].message.parsed


if __name__ == "__main__":
    value = search_documentation_agent(
        "What is the maximum number of tokens that can be used for reasoning at low effort for the model?",
        available_doc_sections=[],
    )
    print(value)
