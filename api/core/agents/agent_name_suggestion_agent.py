import workflowai
from pydantic import BaseModel, Field


class AgentNameSuggestionAgentInput(BaseModel):
    raw_llm_content: str = Field(description="The raw LLM content to suggest an agent name for")


class AgentNameSuggestionAgentOutput(BaseModel):
    agent_name: str = Field(description="The suggested agent name")


AGENT_ID = "agent-name-suggestion-agent"

INSTRUCTIONS = """You are an expert at suggesting AI agent names.

You will be given a raw LLM content, and you need to suggest an agent name for it.

The agent name should be a short name that is easy to remember and that is relevant to the content.
The agent name should use kebab case, ex: meeting-notes, spam-detection, etc.
Do not use 'agent' in the name, it is implied.
"""


@workflowai.agent(
    id=AGENT_ID,
    version=workflowai.VersionProperties(
        instructions=INSTRUCTIONS,
        model=workflowai.Model.GEMINI_2_0_FLASH_001,  # Very fast and high reasoning capabilities
        temperature=0.5,  # Mix between creativity and focus on instructions
    ),
)
async def agent_name_suggestion_agent(_: AgentNameSuggestionAgentInput) -> AgentNameSuggestionAgentOutput: ...
