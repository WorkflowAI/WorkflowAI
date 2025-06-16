import pytest

from core.agents.mcp_feedback_processing_agent import (
    MCPFeedbackProcessingInput,
    mcp_feedback_processing_agent,
)


@pytest.mark.parametrize(
    "feedback,expected_sentiment",
    [
        ("MCP server worked great, all tools responded quickly", "positive"),
        ("MCP operations failed, tools were unresponsive", "negative"),
        ("MCP server functioned as expected", "neutral"),
    ],
)
async def test_mcp_feedback_basic_sentiment_classification(feedback, expected_sentiment):
    """Basic test to ensure sentiment classification works"""
    input_data = MCPFeedbackProcessingInput(feedback=feedback, context=None)

    responses = []
    async for response in mcp_feedback_processing_agent(input_data, "test-org", None):
        responses.append(response)

    assert len(responses) == 1
    assert responses[0].analysis.sentiment == expected_sentiment


async def test_mcp_feedback_with_context():
    """Test that feedback processing works with context"""
    input_data = MCPFeedbackProcessingInput(
        feedback="The server was slow today",
        context="Testing during peak load hours",
    )

    responses = []
    async for response in mcp_feedback_processing_agent(input_data, "test-org", "test@example.com"):
        responses.append(response)

    assert len(responses) == 1
    assert responses[0].analysis.summary is not None
    assert len(responses[0].analysis.key_themes) >= 0
    assert 0.0 <= responses[0].analysis.confidence <= 1.0


async def test_mcp_feedback_structured_output():
    """Test that the structured output format is correct"""
    input_data = MCPFeedbackProcessingInput(
        feedback="Tools worked perfectly, very responsive",
        context=None,
    )

    responses = []
    async for response in mcp_feedback_processing_agent(input_data, "test-org", None):
        responses.append(response)

    assert len(responses) == 1
    analysis = responses[0].analysis

    # Check all required fields are present and have correct types
    assert isinstance(analysis.summary, str)
    assert analysis.sentiment in ["positive", "negative", "neutral"]
    assert isinstance(analysis.key_themes, list)
    assert isinstance(analysis.confidence, float)
    assert 0.0 <= analysis.confidence <= 1.0
