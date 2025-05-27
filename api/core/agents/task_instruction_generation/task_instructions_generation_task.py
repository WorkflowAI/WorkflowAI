from typing import Any

import workflowai
from pydantic import BaseModel, Field

from core.domain.fields.chat_message import ChatMessage


class AgentInstructionsGenerationTaskInput(BaseModel):
    chat_messages: list[ChatMessage] = Field(description="The chat messages that originated the creation of the agent")

    class Agent(BaseModel):
        name: str = Field(description="The name of the agent")
        input_json_schema: dict[str, Any] = Field(description="The JSON schema of the agent input")
        output_json_schema: dict[str, Any] = Field(description="The JSON schema of the agent output")

    agent: Agent = Field(description="The agent to generate the instructions for")

    available_tools_description: str = Field(
        description="The description of the available tools, potentially available for the agent we are generating the schema for",
    )


class AgentInstructionsGenerationTaskOutput(BaseModel):
    agent_instructions: str | None = Field(
        default=None,
        description="The instructions on how to complete the agent",
    )


INSTRUCTIONS = """When audio files are in input DO NOT mention "audio", just refer to "the input". DO NOT add the "audio" word in the instructions.
    The instructions must start with a short "role prompting" sentence based on the context, ex: "You are a financial analysis assistant specializing in extracting precise data from financial documents. <rest of the instructions>"
    Do not be overly verbose, just explicit any info not explicit in the schema, based on the chat messages from the user, if relevant.
    Do not add constraints or fields that are not present in the input/output schema.
    Do NOT mention the need for the output to be a valid "JSON" anywhere in the instructions as these instructions should be agnostic to serialization format of the input/output data.
    Do NOT mention "JSON", unless very specific case, for example when the field names contain "JSON" or the fields content contains JSON.
    Do NOT use markdown.
    Keep in mind that the tools in 'available_tools_description' are available: You can include those tools in the instructions when pertinent. Always refer to the tools as '@tool_name'
    When the instruction must include parts of content you really can not redact yourself, use [the context required from the user], ex: "[Insert your SOPs here]. Take into account the likely length of the content the user will insert. If the content is long, prefer putting line breaks before and after the [Insert ...]. Always include square brackets in this case.

# Image generation agents
- make sure the agent_instructions explicitly refer to generating an image

# Migrating user prompts
When the user has passed in its messages a well-formed prompt, you MUST generate instructions that are identical to the initial user prompt. The only exception is if the user has passed templating elements (ex: variable injection, ifs) you must convert the instructions to jinja2 format and use the variables present in 'task.input_json_schema.json_schema'

## Jinja2 cheat sheet
{% raw %}
inject variable with: {{ variable_name }}
conditions:
{% if condition %}
some text
{% endif %}
{% endraw %}
"""

VERSION = workflowai.VersionProperties(
    model=workflowai.Model.CLAUDE_3_7_SONNET_20250219,
    max_tokens=1000,
    instructions=INSTRUCTIONS,
)


@workflowai.agent(version=VERSION)
async def agent_instructions_redaction(
    input: AgentInstructionsGenerationTaskInput,
) -> AgentInstructionsGenerationTaskOutput:
    ...
