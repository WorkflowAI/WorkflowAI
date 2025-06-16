import os
from typing import AsyncIterator, Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, Field


class MCPFeedbackProcessingInput(BaseModel):
    feedback: str = Field(description="The raw feedback from the MCP client")
    context: str | None = Field(default=None, description="Optional context about what the feedback relates to")


class MCPFeedbackProcessingOutput(BaseModel):
    summary: str = Field(description="A concise summary of the feedback")
    sentiment: Literal["positive", "negative", "neutral"] = Field(description="The categorized sentiment")
    key_themes: list[str] = Field(description="Key themes or topics identified in the feedback")
    confidence: float = Field(description="Confidence score (0.0-1.0) for the sentiment classification")


class MCPFeedbackProcessingResponse(BaseModel):
    analysis: MCPFeedbackProcessingOutput


async def mcp_feedback_processing_agent(
    input: MCPFeedbackProcessingInput,
    organization_name: str | None = None,
    user_email: str | None = None,
) -> AsyncIterator[MCPFeedbackProcessingResponse]:
    """Process MCP client feedback and provide structured analysis"""

    system_message = """You are a feedback agent that receives feedback from MCP clients about their experience using the MCP server. 
    Your goal is to summarize the feedback and categorize the feedback into a sentiment: positive, negative, neutral.
    
    The feedback comes from AI agents (MCP clients) reporting on their experience with MCP server tools and operations.
    
    Provide structured analysis including:
    - A concise summary of the main points
    - Sentiment classification (positive, negative, neutral)
    - Key themes or topics identified in the feedback
    - Confidence score for your sentiment classification
    """

    user_message = """Please analyze the following MCP client feedback:

Feedback: {{feedback}}
{% if context %}Context: {{context}}{% endif %}

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

    response = await client.chat.completions.create(
        model="gemini-2.0-flash-latest",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ],
        extra_body={
            "input": {
                "feedback": input.feedback,
                "context": input.context or "",
            },
        },
        metadata=metadata,
        response_format=MCPFeedbackProcessingOutput,
        temperature=0.0,
    )

    # Parse the structured response
    analysis = MCPFeedbackProcessingOutput.model_validate_json(response.choices[0].message.content)

    yield MCPFeedbackProcessingResponse(analysis=analysis)
