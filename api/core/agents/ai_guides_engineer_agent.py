import json
import logging
import os
from typing import Any, AsyncIterator, NamedTuple

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class AIGuidesEngineerAgentOutput(BaseModel):
    assistant_answer: str | None = None
    search_documentation_query: str | None = None


class ParsedToolCall(NamedTuple):
    search_documentation_query: str | None = None


def parse_tool_call(tool_call: Any) -> ParsedToolCall:
    """Parse a tool call and return the extracted data.

    Returns a ParsedToolCall with the parsed tool data. Fields are populated based on tool type:
    - search_documentation: search_documentation_query
    """
    if not tool_call.function or not tool_call.function.arguments:
        return ParsedToolCall()

    function_name = tool_call.function.name
    try:
        arguments = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError as e:
        logger.error(
            "Error parsing tool call",
            extra={"tool_call": str(tool_call)},
            exc_info=e,
        )
        return ParsedToolCall()

    if function_name == "search_documentation":
        return ParsedToolCall(
            search_documentation_query=arguments.get("search_documentation_query"),
        )

    return ParsedToolCall()


INSTRUCTIONS = """You are an expert AI engineer building AI agents on top of WorkflowAI platform.
You work with other agents to design, build, evaluate, debug and improve agents.
## Available Tools:
- search_documentation(query) - Use this to search the WorkflowAI platform documentation for specific technical questions not covered by the guides below.
## Available Guides:
Based on the user's needs, you can return one or more of the following guides:
<guides>
<guide>
<variable>{{building_new_agent_guide}}</variable>
<when_to_use>When the user wants to build a new agent from scratch.</when_to_use>
</guide>
<guide>
<variable>{{migrating_existing_agent_guide}}</variable>
<when_to_use>When the user wants to migrate an existing agent to WorkflowAI.</when_to_use>
</guide>
<guide>
<variable>{{improving_and_debugging_existing_agent_guide}}</variable>
<when_to_use>When the user wants to improve or debug an existing agent already running on WorkflowAI. For example, when the user wants to find a faster model to run the agent or, or when the user reports an issue with the agent</when_to_use>
</guide>
</guides>
IMPORTANT: When returning a guide, return ONLY the Jinja2 template variable exactly as shown (including the double curly braces). Do NOT expand or fill in the template with actual guide content. The template will be processed later by the system.
<examples>
<example>
<user_message>I want to build a new agent</user_message>
<reply>
Relevant guides:
{{building_new_agent_guide}}
</reply>
</example>
<example>
<user_message>I want to build a new agent, and also, what is the business model of WorkflowAI?</user_message>
You should call the `search_documentation` tool to answer the question about the business model of WorkflowAI.
<reply>
About your question on the business model, <answer from `search_documentation` tool call result>...
Relevant guides:
{{building_new_agent_guide}}
</reply>
</example>
</examples>"""

TOOL_DEFINITIONS: list[ChatCompletionToolParam] = [
    {
        "type": "function",
        "function": {
            "name": "search_documentation",
            "description": "Search the documentation for the given query. Returns the most relevant documentation section(s).",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_documentation_query": {
                        "type": "string",
                        "description": "The query to search the documentation for.",
                    },
                },
                "required": [
                    "search_documentation_query",
                ],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
]


async def ai_guides_engineer_agent(
    messages: list[ChatCompletionMessageParam],
) -> AsyncIterator[AIGuidesEngineerAgentOutput]:
    client = AsyncOpenAI(
        api_key=os.environ["WORKFLOWAI_API_KEY"],
        base_url=f"{os.environ['WORKFLOWAI_API_URL']}/v1",
    )

    response = await client.chat.completions.create(
        model="claude-sonnet-4-20250514",
        messages=[
            {
                "role": "system",
                "content": INSTRUCTIONS,
            },
            *messages,
        ],
        stream=True,
        temperature=0.0,
        tools=TOOL_DEFINITIONS,
        metadata={"agent_id": "ai-guides-engineer-agent"},
    )

    async for chunk in response:
        # Parse tool calls if present
        parsed_tool_call = ParsedToolCall()
        if chunk.choices and chunk.choices[0].delta.tool_calls:
            tool_call = chunk.choices[0].delta.tool_calls[0]
            parsed_tool_call = parse_tool_call(tool_call)

        yield AIGuidesEngineerAgentOutput(
            assistant_answer=chunk.choices[0].delta.content,
            search_documentation_query=parsed_tool_call.search_documentation_query,
        )
