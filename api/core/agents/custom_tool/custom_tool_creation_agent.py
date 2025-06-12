from typing import AsyncIterator

import workflowai
from pydantic import BaseModel, Field

from core.domain.fields.custom_tool_creation_chat_message import CustomToolCreationChatMessage


class CustomToolCreationAgentInput(BaseModel):
    chat_messages: list[CustomToolCreationChatMessage] | None = Field(
        default=None,
        description="The list of previous messages in the conversation, the last message is the most recent one",
    )


class CustomToolCreationAgentOutput(BaseModel):
    answer: CustomToolCreationChatMessage | None = Field(
        default=None,
        description="The agent answer to the user",
    )


INSTRUCTIONS = """You are a tool creation specialist helping users design and define new tools through conversation. Your role is to assist in creating well-defined tools while maintaining a helpful dialogue.

    Based on the conversation history in the messages array, provide a response as an assistant that helps guide the tool creation process. If the user provides requirements or specifications for a tool, help refine them into a concrete tool definition. If a tool is already being discussed, provide constructive feedback and suggestions for improvement.

    Your response should include:

    - A clear and helpful message in the content field addressing the user's latest input
    - When appropriate, a tool field containing the proposed or refined tool specification with:
    - A clear, descriptive name
    - A comprehensive description of the tool's purpose and functionality
    - A well-defined parameters object in JSON Schema format.
    - The role field set to 'ASSISTANT'

    Focus on understanding the user's needs and iteratively improving the tool definition through conversation. Ensure any proposed tools are practical, well-structured, and align with the user's requirements.

    In case the users passes a JSON schema already just double check everythin is OK and remove OpenAI specific keywords like strict=true, or additionalProperties=false."""


@workflowai.agent(
    id="tool-creation-chat",
    version=workflowai.VersionProperties(
        model=workflowai.Model.CLAUDE_3_7_SONNET_20250219,
        max_tokens=1000,
        instructions=INSTRUCTIONS,
    ),
)
def stream_custom_tool_creation_agent(
    task_input: CustomToolCreationAgentInput,
) -> AsyncIterator[CustomToolCreationAgentOutput]: ...
