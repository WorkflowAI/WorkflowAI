from collections.abc import AsyncIterator
from typing import Literal

import workflowai
from pydantic import BaseModel, Field

from core.domain.fields.chat_message import ChatMessage
from core.runners.workflowai.internal_tool import InternalTool


class SuggestedAgent(BaseModel):
    explanation: str | None = Field(
        default=None,
        description="The explanation of why the agent is useful for the company",
    )
    agent_description: str | None = Field(
        default=None,
        description="The description of what the agent does",
    )
    department: str | None = Field(
        default=None,
        description="The department the agent is for",
    )
    input_specifications: str | None = Field(
        default=None,
        description="A description of what the agent input is",
    )
    output_specifications: str | None = Field(
        default=None,
        description="A description of what the agent output is",
    )


class AgentSuggestionChatMessage(BaseModel):
    role: Literal["USER", "ASSISTANT"] | None = Field(
        default=None,
        description="The role of the message sender, either the user or the agent suggestion agent",
        examples=["USER", "ASSISTANT"],
    )
    content_str: str | None = Field(
        default=None,
        description="The content of the message",
        examples=[
            "Thank you for your help!",
            "What is the weather forecast for tomorrow?",
        ],
    )

    suggested_agents: list[SuggestedAgent] | None = Field(
        default=None,
        description="The list of suggested agents attached to the message",
    )

    def to_chat_message(self) -> ChatMessage:
        return ChatMessage(
            role=self.role or "USER",
            content=self.content_str or "",
        )


class SuggestLlmAgentForCompanyInput(BaseModel):
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
                description=tool.definition.description or "",
            )

    available_tools: list[ToolDescription] | None = Field(
        default=None,
        description="The list of available tools that can be used by suggested agents",
    )

    class CompanyContext(BaseModel):
        company_name: str | None = None
        company_description: str | None = None
        existing_agents: list[str] | None = Field(
            default=None,
            description="The list of existing agents for the company",
        )

    company_context: CompanyContext | None = Field(
        default=None,
        description="The context of the company",
    )

    chat_messages: list[AgentSuggestionChatMessage] | None = Field(
        default=None,
        description="The list of previous messages in the conversation, the last message is the most recent one",
    )


class SuggestLlmAgentForCompanyOutput(BaseModel):
    assistant_message: AgentSuggestionChatMessage | None = Field(
        default=None,
        description="The assistant's message to the user",
    )


INSTRUCTIONS = """Your role is to generate a comprehensive list of LLM-powered structured generation agents and engage in a chat-based interaction about agent suggestions. Follow these guidelines to ensure clarity and specificity in your suggestions:

    - Begin by analyzing the company context, including:
    - The company name and description to understand their domain and business focus.
    - Their existing agents to avoid duplicating functionality and identify complementary agents.
    - Their specific needs and potential areas for improvement.

    - Analyze the input data, including the chat history, supported agent input types, supported agent output types, and any context provided in the messages.

    - Based on the available information and existing capabilities, brainstorm potential LLM-powered structured generation agents that could benefit the company.

    - For each suggested agent:
    - Ensure that the agent represents one specific operation, avoiding multiple operations within a single agent.
    - Provide a clear explanation of why this agent is recommended for the company, considering their business and current capabilities.
    - Write a concise description of the agent suitable for display on a UI, including its benefits to the company (e.g., "Summarize patient nutrition history to create a pre-consultation briefing."). Target length is 80 characters.
    - Specify which department would benefit most from this agent (e.g., operations, finance, HR, marketing, sales, product, customer support, legal and compliance, or strategy).
    - Detail the exact input specifications required for the agent to function, based on data the company is likely storing in their database or as files (e.g., images, audio). Ensure that only one input type is specified (e.g., "Patient intake forms with fields for dietary preferences, health conditions, and contact information").
    - Detail the exact output specifications that the agent will produce (e.g., "Patient nutrition history with key dates and summary points.").

    - Ensure that the suggested agents are relevant to the company's domain and can be realistically implemented using LLM technology.

    - Consider the supported agent input and output types when suggesting agents to ensure compatibility with the company's existing systems.

    - Also consider the 'available_tools' that can give suggested agent more capabilities.

    - You can use the 'existing agents' to avoid generating duplicates of existing agents, and to propose new agents that make sense based on the agents the client is already using.

    - Include agents related to content moderation where applicable. For example, moderating user-generated content into categories like violence, self-harm, sexual, and hate.

    - Format the output with an appropriate assistant message that responds to the user's message in a conversational manner and includes the suggested agents.

    - Aim to provide a diverse set of agent suggestions that cover different aspects of the company's potential needs.

    Be creative yet practical in your suggestions, focusing on how LLM technology can add value to the company's departments:
    - operations
    - finance
    - HR
    - marketing
    - sales
    - product
    - customer support
    - legal and compliance
    - strategy

    - Generate up to 15 agent suggestions per response, except if the user comes up with a specific feature he want to build (in the 'messages' ), in this case you can only generate one feature suggestion that he asked for.

    Below you will find a list of example agent ideas, both industry-specific and generalist, to inspire your suggestions:

    SECTION: TEXT / CONTENT GENERATION
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
    - Generate Title for a Linear Issue from a Slack message.
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

    SECTION: CODE GENERATION
    - Explain code.
    - Using natural language to query SQL database.

    SECTION: SUMMARIZATION
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

    SECTION: IMAGE
    - Extract a description of the meal from a photo, along with the total calories, and the different ingredients with calories for each.
    Relevant for: nutrition app.
    - From an image, write a description (ALT tag).
    - Give recipes ideas from an image.
    - Extract the city and country from an image.
    - Classify a photo as either appropriate or inappropriate content.
    Relevant for: apps with User-Generated content.
    - Given a menu from a restaurant, and an allergy, identify what meals are OK for my food restrictions.
    - From a screenshot of a webpage, extract structured information.

    SECTION: REASONING
    - Given a chess board state, generate the AI player's next move.

    SECTION: AUDIO
    - Transcribe a phone call.
    - Transcribe a podcast.
    - Translate a phone call into another language.

    SECTION: CLASSIFICATION
    - Given a product review, extract the main sentiment.
    - Given a new message, classify if the message is urgent, or not.
    - Given a prompt, classify if the prompt is a prompt injection, along with a confidence score and a reason.
    - Classify if a conversation is a SCAM or not.
    - Moderation and content safety for AI-generated content.
    - Given a chat bot conversation between a user and an assistant — evaluate the quality of the chatbot responses.
    - Language style detection.

    SECTION: INFORMATION_EXTRACTION
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
    - Analyze last week's review, and extract positive and negative points.

    SECTION: MARKETING
    - Generate marketing copy (ads, social media posts, website content) based on product specifications and target audience.
    Relevant for: company selling physical products."""


@workflowai.agent(
    id="suggest-llmfeatures-for-company",
    version=workflowai.VersionProperties(
        model=workflowai.Model.CLAUDE_3_7_SONNET_20250219,
        max_tokens=2500,  # Generated suggested features can be lengthy, so 2500 instead of 1000 of most Claude agents
        instructions=INSTRUCTIONS,
    ),
)
def suggest_llm_agents_for_company(
    input: SuggestLlmAgentForCompanyInput,
) -> AsyncIterator[SuggestLlmAgentForCompanyOutput]: ...
