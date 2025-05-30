import datetime
from typing import Literal

import workflowai
from pydantic import BaseModel, Field

from core.domain.documentation_section import DocumentationSection
from core.domain.integration.integration_domain import Integration


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
    documentation: list[DocumentationSection] = Field(
        description="The documentation sections that are relevant to the conversation.",
    )
    messages: list[IntegrationAgentChatMessage] = Field(
        description="The list of messages in the conversation, the last message being the most recent one.",
    )
    integration: Integration = Field(
        description="The integration that the user is integrating WorkflowAI into.",
    )


class IntegrationAgentOutput(BaseModel):
    content: str | None = Field(
        default=None,
        description="The content of the answer message from the integration-agent.",
    )


INTEGRATION_AGENT_INSTRUCTIONS = """You are WorkflowAI's integration agent. Your goal is to help users integrate WorkflowAI into their code using WorkflowAI's OpenAI-compatible chat completion endpoint.
Theoretically, any package that uses the OpenAI chat completion endpoint will work using the WorkflowAI chat completion endpoint, even outside the "integration" in the input.
Answer any questions that the user would have for based on the 'documentation' in the input.
When relevant, provide a code snippet to the user based on the integration he is using, his programming language, and the discussion in the 'messages' in the input.
Always surround the code snippet with ``` tags.
To ease the process with the user, you can ask the user to copy and paste their existing code so you can update it.
Note that only /v1/chat/completions is supported, not embeddings, transcription, or OpenAI's ResponseAPI.

You must return the code snippet wrapped in markdown code blocks with the appropriate language specified. For example:
```python
# Python code
```
or
```typescript
// TypeScript code
"""


@workflowai.agent(
    version=workflowai.VersionProperties(
        instructions=INTEGRATION_AGENT_INSTRUCTIONS,
        model=workflowai.Model.CLAUDE_3_7_SONNET_20250219,  # Using a default model for now
    ),
)
async def integration_chat_agent(_: IntegrationAgentInput) -> IntegrationAgentOutput: ...
