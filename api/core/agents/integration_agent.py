import datetime
from typing import Literal

import workflowai
from pydantic import BaseModel, Field


class IntegrationAgentChatMessage(BaseModel):
    role: Literal["USER", "PLAYGROUND", "ASSISTANT"] = Field(
        description="The role of the message sender, 'USER' is the actual human user, 'PLAYGROUND' are automated messages, and 'ASSISTANT' is the agent.",
    )
    content: str = Field(
        description="The content of the message",
    )


class IntegrationAgentInput(BaseModel):
    current_datetime: datetime.datetime = Field(
        description="The current datetime",
    )
    messages: list[IntegrationAgentChatMessage] = Field(
        description="The list of messages in the conversation, the last message being the most recent one.",
    )


class IntegrationAgentOutput(BaseModel):
    content: str | None = Field(
        default=None,
        description="The content of the answer message from the integration-agent.",
    )


INTEGRATION_AGENT_INSTRUCTIONS = """You are WorkflowAI's integration agent. Your goal is to help users integrate WorkflowAI into their code.
You will guide the user through a multi-step process.
Initially, you will provide a code snippet for basic integration.
After the user has successfully run their code and a run is received, you will provide a second, more advanced code snippet.
You must also be able to answer any questions the user might have between these steps.
"""


@workflowai.agent(
    version=workflowai.VersionProperties(
        instructions=INTEGRATION_AGENT_INSTRUCTIONS,
        model=workflowai.Model.CLAUDE_3_7_SONNET_20250219,  # Using a default model for now
    ),
)
async def integration_chat_agent(_: IntegrationAgentInput) -> IntegrationAgentOutput: ...
