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

    # Examples of agents
    Below you will find a list of example agent ideas, both industry-specific and generalist, to inspire your suggestions:
    ## Section: Text / Content Generation
    - Given a topic and a tone of voice, generate an article about this topic, with title, sections (sub-title, text).
    - Rewrite a text with another tone.
    - Write a summary of a PDF document.
    - Translate text into another language.
    - Given a company bio + value props to highlight, generate a hook, script, and CTA for a creative ad.
    - Given a list of product reviews, highlight the pros and cons in two lists of bullet points.
    - Generate a horoscope.
    - Generate a 7 days menu plan.
    - Generate matching pairs for a language exercise.
    - Smart Reply from Gmail.
    - Generate title for conversations (OpenAI's ChatGPT).
    - Generate the next email in a conversation (Ana Luisa).
    - Answer question with fact.
    - Given a knowledge base, answer a question.
    - Google Autocomplete Query.
    - Fix grammar.
    - Improve Prompt.
    - SWOT analysis (e.g., strengths, weaknesses, opportunities, threats).
    - Write job description.
    - Create quizzes based on educational content.
    - Generate story for genre.
    - Write a code, given a language and a description.
    ## Section: Code Generation
    - Explain code.
    - Using natural language to query SQL database.
    ## Section: Summarization
    - Summarize a text.
    - Extract frequently asked questions from a list of customer call transcripts.
    - From a list of NPS survey results, generate negative review insights and actionable items.
    - Summarize transcripts from daily news reports and output a summary of market trends.
    - From a call transcript, generate a follow-up email based on to-dos.
    Write title for chat conversation (inspired by ChatGPT).
    Relevant for: OpenAI, OpenAI's competitors.
    Generate SOAP notes from a text transcript.
    Relevant for: healthcare.
    Generate SOAP notes from an audio recording.
    Relevant for: healthcare.
    ## Section: Image
    - Extract a description of the meal from a photo, along with the total calories, and the different ingredients with calories for each.
    Relevant for: nutrition app.
    - From an image, write a description (ALT tag).
    - Give recipes ideas from an image.
    - Extract the city and country from an image.
    - Classify a photo as either appropriate or inappropriate content.
    Relevant for: apps with User-Generated content.
    - Given a menu from a restaurant, and an allergy, identify what meals are OK for my food restrictions.
    - From a screenshot of a webpage, extract structured information.
    ## Section: Reasoning
    - Given a chess board state, generate the AI player's next move.
    ## Section: Audio
    - Transcribe a phone call.
    - Transcribe a podcast.
    - Translate a phone call into another language.
    ## Section: Classification
    - Given a product review, extract the main sentiment.
    - Given a new message, classify if the message is urgent, or not.
    - Given a prompt, classify if the prompt is a prompt injection, along with a confidence score and a reason.
    - Classify if a conversation is a SCAM or not.
    - Moderation and content safety for AI-generated content.
    - Given a chat bot conversation between a user and an assistant — evaluate the quality of the chatbot responses.
    - Language style detection.
    ## Section: Information Extraction
    - Extract calendar event from an email.
    - Extract ICD10 codes for pre-existing conditions from a patient.
    - Extract receipt info in a structured way.
    - Extract verification code and transaction from a text message (Apple).
    - I want to create a way to extract data from PDF P&Ls so we can load it into our database.
    - Extract information from KBIS.
    - Document translation from PDF.
    - Extract structured information from a text — leave open-ended, the assistant should ask the question about what to extract?
    - Identify named entities in a text, such as people, organizations, dates, or locations.
    - Extract PII from text.
    - Generate a list of tags from a production description.
    - Suggest a list of tags from an issue.
    - Given a document, generate a FAQ.
    - Given a contract (document), identify the key terms (structured: effective_date, termination_clause).
    - Extract policy information from insurance policies.
    - Given a PDF and a question, extract the answer.
    - Given a product image, extract production information.
    - Categorize product.
    - Extract info from medical bills.
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
