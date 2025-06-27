import os
from typing import Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, Field


class MCPFeedbackProcessingOutput(BaseModel):
    summary: str = Field(description="A concise summary of the feedback")
    sentiment: Literal["positive", "negative", "neutral"] = Field(description="The categorized sentiment")
    key_themes: list[str] = Field(description="Key themes or topics identified in the feedback")
    suggested_improvements: list[str] = Field(
        description="Suggested improvements to the MCP server based on the feedback",
    )
    confidence: float = Field(description="Confidence score (0.0-1.0) for the sentiment classification")


async def mcp_feedback_processing_agent(
    feedback: str,
    context: str | None = None,
    user_agent: str | None = None,
    organization_name: str | None = None,
    user_email: str | None = None,
) -> MCPFeedbackProcessingOutput | None:
    """Process MCP client feedback and provide structured analysis"""

    system_message = """You are a feedback agent that receives feedback from MCP clients about their experience using the MCP server.
    Your goal is to summarize the feedback and categorize the feedback into a sentiment: positive, negative, neutral.

    The feedback comes from MCP clients reporting on their experience with MCP server tools and operations.

    Provide structured analysis including:
    - A concise summary of the main points
    - Sentiment classification (positive, negative, neutral)
    - Key themes or topics identified in the feedback
    - Confidence score for your sentiment classification
    """

    user_message = """Please analyze the following MCP client feedback:

Feedback: {{feedback}}
{% if context %}Context: {{context}}{% endif %}
{% if mcp_client_user_agent %}User Agent: {{mcp_client_user_agent}}{% endif %}

Analyze this feedback and provide a structured response with summary, sentiment classification, key themes, and confidence score."""

    client = AsyncOpenAI(
        api_key=os.environ["WORKFLOWAI_API_KEY"],
        base_url=f"{os.environ['WORKFLOWAI_API_URL']}/v1",
    )

    # Build metadata for tracking
    metadata = {
        "agent_id": "mcp-feedback-processing-agent",
    }
    if organization_name:
        metadata["organization_name"] = organization_name
    if user_email:
        metadata["user_email"] = user_email
    if user_agent:
        metadata["mcp_client_user_agent"] = user_agent
    # TODO: add some mcp-session_id to be able to fetch the full MCP conversation too

    response = await client.beta.chat.completions.parse(
        model="claude-sonnet-4-latest",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ],
        extra_body={
            "input": {
                "feedback": feedback,
                "context": context or "",
                "mcp_client_user_agent": user_agent or "unknown",
            },
        },
        response_format=MCPFeedbackProcessingOutput,
        metadata=metadata,
        temperature=0.0,
    )

    return response.choices[0].message.parsed
