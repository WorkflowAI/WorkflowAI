from collections.abc import AsyncIterator

import workflowai
from pydantic import BaseModel, Field

from core.runners.workflowai.internal_tool import InternalTool


class SuggestedAgent(BaseModel):
    name: str | None = Field(
        default=None,
        description="The name of the agent",
    )
    description: str | None = Field(
        default=None,
        description="The description of the agent",
    )


class SuggestAgentForCompanyInput(BaseModel):
    supported_agent_input_types: list[str] | None = Field(
        default=None,
        description="The list of supported agent input types, that will influence which type of agents can be suggested",
    )
    supported_agent_output_types: list[str] | None = Field(
        default=None,
        description="The list of supported agent output types, that will influence which type of agents can be suggested",
    )

    class ToolDescription(BaseModel):
        """
        A short (without input_json_schema and output_json_schema) tool description that uses a 'string' handle instead of 'ToolHandle'.
        In order to the used in tasks without having to update schema every time the 'ToolHandle' type is updated.
        """

        handle: str = Field(description="The handle of the tool", examples=["@browser-text", "@search-google"])
        description: str = Field(description="The description of the tool")

        @classmethod
        def from_internal_tool(cls, tool: InternalTool):
            return cls(
                handle=tool.definition.name,
                description=tool.definition.description,
            )

    available_tools: list[ToolDescription] | None = Field(
        default=None,
        description="The list of available tools that can be used by suggested agents",
    )

    class CompanyContext(BaseModel):
        company_url: str | None = Field(
            default=None,
            description="An URL provided by the client in order for they to get agent suggestions",
        )
        company_url_content: str | None = Field(
            default=None,
            description="The content of the 'company_url'",
        )
        latest_news: str | None = Field(
            default=None,
            description="A description of the latest news for the company (ex: new product launch, new features, acquisitions, new regulations, industry trends, competitors news)",
        )
        existing_agents: list[str] | None = Field(
            default=None,
            description="The list of existing agents for the company",
        )

    company_context: CompanyContext | None = Field(
        default=None,
        description="The context of the company",
    )


class SuggestAgentForCompanyOutput(BaseModel):
    suggested_agents: list[SuggestedAgent] | None = Field(
        default=None,
        description="The list of suggested agents",
    )


INSTRUCTIONS = """Your role is to generate a comprehensive list of exactly 10 agents suggestions that can be used to power features for our clients, based on:

    - 'company_url' and 'company_url_content' (in order to understand the company and propose agents that make sense based on the company's context)
    - the 'supported_agent_input_types' and 'supported_agent_output_types' that explains the type of agents input and output that can be suggested.
    - consider the 'available_tools' that can give suggested agent more capabilities.
    - use 'latest_news' to propose agents that are super relevant and impactful for the company based on the latest news. Offer features that works well with the latest product and features, and aligns with the company goals from 'latest_news'. Most of the proposed agents should be related to the latest news if enough news are provided.
    - their existing agents (in order to avoid duplicates, and propose new agents that make sense based on the agents the client is already using)


    # Guidelines for choosing suggested agents
    - Propose features that are scalable and can be seamlessly integrated into the client's existing products.
    - Prioritize features that solve key problems or enhance user experience.
    - Avoid "one-off" agents that won't fit in the user's product on the long term.
    - Avoid image generation and design use cases as we currently do not support images in the output (see 'supported_agent_output_types')
    - Avoid use cases that do not make sense with LLM technology and work perfectly well with deterministic code (ex: arithmetic operation, calculators, deterministic data analysis, etc. basically nothing you can write code to do). Also avoid hardware optimization agents since they probably require human engineering skills that are beyong LLM capabilities. Focus on software oriented agents.
    - Don't forget to proposed chat-based agents that the company can use to power its products (INPUT: messages with special payload based on the use case, domain specific, etc. OUTPUT: answer message with special payload based on the use case). For chat based agent, make sure to include 'Chat' in the 'suggested_agents.name'.
    - Avoid agent targeted at the internal functions (software development, documentation, accounting, HR, etc.). Focus on CLIENT-FACING agents that DIRECTLY IMPACT the final user's experience.
    - Ensure that the agent represents one specific operation that: takes a structured input of 'supported_agent_input_types', optionally uses 'available_tools' and LLM reasoning in order to output a structured output of 'supported_agent_output_types', avoiding multiple operations within a single agent.
    - Ensure that the suggested agents are relevant to the company's domain and can be realistically implemented using LLM technology.
    - Aim to provide a diverse set of agent suggestions that cover different aspects of the company's potential needs.

    # Guidelines for writing the name and description of the suggested agents
    - the 'suggested_agents.name' must follow the following convention: [subject that is acted upon] + [the action], in Title Case. Ex: 'Sentiment Analysis', 'Text Summarization', 'Location Detection'. Avoid using "Generation" in the agent name, as all agents perform generation anyway.
    - the 'suggested_agents.description' must be a description of the what the agent does (input, output, purpose) and how this agent would benefit the company. When relevant, talk in terms of product management metrics: activation, engagement, retention, monetization, growth (referral) and asking youself "what metric(s) might be positively impacted by this AI feature" ?  300 Chars max.
    """


@workflowai.agent(
    id="suggest-llmagents-for-company",
    version=workflowai.VersionProperties(
        model=workflowai.Model.CLAUDE_3_7_SONNET_20250219,
        max_tokens=2500,  # Generated suggested featuress can be lengthy, so 2500 instead of 1000 of most Claude agents
        instructions=INSTRUCTIONS,
    ),
)
def stream_suggest_agents_for_company(
    input: SuggestAgentForCompanyInput,
) -> AsyncIterator[SuggestAgentForCompanyOutput]: ...
