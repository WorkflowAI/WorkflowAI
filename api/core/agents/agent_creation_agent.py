import json
import logging
import os
from typing import Any, AsyncIterator

from openai import AsyncOpenAI
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

INSTRUCTIONS = """
You are a helpful assistant that helps users create new agents.
Trigger agent creation when you have enough information to create a new agent.
"""


class CreateAgentToolCall(BaseModel):
    agent_name: str = Field(description="The name of the agent to create, in snake_case")
    system_message_content: str = Field(description="The system message content")
    user_message_content: str | None = Field(description="The user message content")
    response_format: dict[str, Any] | None = Field(
        description="In case the agent needs to output structured data, the schema of the data to be output, always strating with `type: object`, `properties`: [...], `required`: [...]",
    )


def parse_tool_call(tool_call: Any) -> CreateAgentToolCall | None:
    if not tool_call.function or not tool_call.function.arguments:
        return None

    function_name = tool_call.function.name
    arguments = json.loads(tool_call.function.arguments)

    if function_name == "create_agent":
        return CreateAgentToolCall(
            **arguments,
        )

    raise ValueError(f"Unknown tool call: {function_name}")


class AgentCreationAgentOutput(BaseModel):
    assistant_answer: str
    agent_creation_tool_call: CreateAgentToolCall | None


async def agent_creation_agent(
    messages: list[ChatCompletionMessageParam],
) -> AsyncIterator[AgentCreationAgentOutput]:
    client = AsyncOpenAI(
        api_key=os.environ["WORKFLOWAI_API_KEY"],
        base_url=f"{os.environ['WORKFLOWAI_API_URL']}/v1",
    )

    response = await client.chat.completions.create(
        model="agent-creation-agent/claude-sonnet-4-latest",
        messages=[
            {"role": "system", "content": INSTRUCTIONS},
            {
                "role": "user",
                "content": "Your answer is:",
            },
            *messages,
        ],
        stream=True,
        temperature=0.0,
        extra_body={
            "temperature": 0.0,
            "use_cache": "never",
        },
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "create_agent",
                    "description": "Create a new agent",
                    "parameters": CreateAgentToolCall.model_json_schema(),
                },
            },
        ],
    )

    parsed_tool_call: CreateAgentToolCall | None = None
    async for chunk in response:
        logging.info(f"inner agent_creation_agent Chunk: {chunk}")

        if chunk.choices[0].delta.tool_calls:
            tool_call = chunk.choices[0].delta.tool_calls[0]
            parsed_tool_call = parse_tool_call(tool_call)

    yield AgentCreationAgentOutput(
        assistant_answer="",
        agent_creation_tool_call=parsed_tool_call,
    )
