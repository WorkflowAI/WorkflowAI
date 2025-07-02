from typing import Any, Literal

from pydantic import BaseModel, Field

from core.agents.chat_task_schema_generation.chat_task_schema_generation_task import AgentSchemaJson
from core.domain.fields.chat_message import AssistantChatMessage, ChatMessage, UserChatMessage


class BuildAgentMessage(BaseModel):
    content: str
    role: Literal["USER", "ASSISTANT"]

    class AgentSchema(BaseModel):
        agent_name: str = Field(description="The name of the agent in Title Case", serialization_alias="agent_name")
        output_json_schema: dict[str, Any] | None = Field(
            default=None,
            description="The JSON schema of the agent output",
        )

    agent_schema: AgentSchema | None = Field(
        default=None,
        description="The agent schema returned as part of the message",
    )


class BuildAgentRequest(BaseModel):
    messages: list[BuildAgentMessage] | None = Field(
        default=None,
        description="The previous messages of the agent builder process",
    )

    @property
    def chat_messages(self) -> list[ChatMessage]:
        """Convert BuildAgentMessage format to ChatMessage format for internal service"""
        if not self.messages:
            return []

        chat_messages: list[ChatMessage] = []
        for msg in self.messages:
            if msg.role == "USER":
                chat_messages.append(UserChatMessage(content=msg.content))
            elif msg.role == "ASSISTANT":
                chat_messages.append(AssistantChatMessage(content=msg.content))

        return chat_messages

    @property
    def existing_schema(self) -> AgentSchemaJson | None:
        """Extract the most recent agent schema from the messages"""
        if not self.messages:
            return None

        # Look for the most recent assistant message with an agent schema
        for msg in reversed(self.messages):
            if msg.role == "ASSISTANT" and msg.agent_schema:
                return AgentSchemaJson(
                    agent_name=msg.agent_schema.agent_name,
                    input_json_schema=None,  # Build agent only deals with output schemas
                    output_json_schema=msg.agent_schema.output_json_schema,
                )

        return None


class BuildAgentResponse(BaseModel):
    message: BuildAgentMessage
