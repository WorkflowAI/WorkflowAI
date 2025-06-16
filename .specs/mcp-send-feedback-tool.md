# MCP Send Feedback Tool Implementation Spec

## Overview

This specification outlines the implementation of a new MCP tool `send_feedback` that allows MCP clients (AI agents) to automatically send feedback about their experience using the MCP server. This feedback will be processed by a dedicated AI agent running on WorkflowAI for analysis and categorization, but the MCP tool will only acknowledge receipt.

## Goal

Add a new MCP tool in `api/api/routers/mcp/mcp_server.py` that:
1. Accepts feedback from MCP clients about their MCP server experience
2. Sends the feedback to a dedicated AI agent for processing (fire-and-forget)
3. Returns simple acknowledgment that feedback was received and sent for processing
4. Uses metadata to track organization and user information for analytics

## Use Case

This tool enables MCP clients (AI agents) to automatically provide feedback about:
- Their experience using MCP server tools
- Success/failure of MCP operations
- Performance or usability issues
- Suggestions for improvement
- Overall satisfaction with MCP server capabilities

The feedback is sent automatically by the MCP client after completing operations, not triggered by end-users.

## Current State Analysis

### Existing MCP Tools Pattern
- Located in `api/api/routers/mcp/mcp_server.py`
- Use `@_mcp.tool()` decorator
- Return `MCPToolReturn` objects
- Have access to `MCPService` via `get_mcp_service()`
- Access to tenant/organization info via authentication

### Existing Feedback System
- Feedback tokens and `FeedbackService` already exist
- Feedback domain models in `core/domain/feedback.py`
- Current feedback flow: client → feedback token → WorkflowAI dashboard

### Current Agent Patterns (OpenAI SDK)
- Agents use OpenAI SDK with `WORKFLOWAI_API_KEY` environment variable
- Base URL: `f"{os.environ['WORKFLOWAI_API_URL']}/v1"`
- Pattern: `client = AsyncOpenAI(api_key=os.environ["WORKFLOWAI_API_KEY"], base_url=...)`
- Use `response_format` for structured output
- Use `extra_body={"input": {...}}` for input variables
- Use `metadata={"agent_id": "..."}` for agent identification
- Examples in `core/agents/integration_code_block_agent.py`

## Implementation Plan

### 1. Create MCP Feedback Processing Agent

**Location**: `api/core/agents/mcp_feedback_processing_agent.py`

**Agent Structure** (simplified with metadata):
```python
import os
from typing import AsyncIterator

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
        "agent_id": "mcp-feedback-processing-agent"
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
```

### 2. Add MCP Tool

**Location**: `api/api/routers/mcp/mcp_server.py`

**Tool Implementation**:
```python
class SendFeedbackRequest(BaseModel):
    feedback: str = Field(description="Feedback about the MCP client's experience using the MCP server")
    context: str | None = Field(default=None, description="Optional context about the MCP operations that generated this feedback")

@_mcp.tool()
async def send_feedback(request: SendFeedbackRequest) -> MCPToolReturn:
    """<when_to_use>
    When an MCP client (AI agent) wants to provide feedback about its experience using the MCP server.
    This tool is designed for automated feedback collection from MCP clients after they complete operations,
    not for end-user feedback. The feedback helps improve MCP server functionality and user experience.
    </when_to_use>
    <returns>
    Returns acknowledgment that the feedback was received and sent for processing.
    The actual analysis is handled asynchronously by the feedback processing agent.
    </returns>"""
    service = await get_mcp_service()
    return await service.send_feedback(request.feedback, request.context)
```

### 3. Add MCPService Method

**Location**: `api/api/routers/mcp/_mcp_service.py`

**Service Method** (with tenant/user context extraction):
```python
import asyncio

async def send_feedback(self, feedback: str, context: str | None = None) -> MCPToolReturn:
    """Send MCP client feedback to processing agent and return acknowledgment"""
    try:
        from core.agents.mcp_feedback_processing_agent import (
            mcp_feedback_processing_agent, 
            MCPFeedbackProcessingInput
        )
        
        # Create input for the agent
        agent_input = MCPFeedbackProcessingInput(
            feedback=feedback,
            context=context
        )
        
        # Extract organization and user info from storage/tenant context
        # The storage already has tenant information from the authentication flow
        organization_name = getattr(self.storage, 'tenant', None)
        user_email = None  # Could be extracted from user context if available
        
        # Fire-and-forget: start the agent processing but don't wait for results
        asyncio.create_task(self._process_feedback_async(agent_input, organization_name, user_email))
        
        return MCPToolReturn(
            success=True,
            result={
                "message": "MCP client feedback received and sent for processing",
                "feedback_length": len(feedback),
                "has_context": context is not None
            }
        )
    except Exception as e:
        return MCPToolReturn(
            success=False,
            error=f"Failed to send MCP client feedback for processing: {str(e)}"
        )

async def _process_feedback_async(
    self, 
    agent_input: MCPFeedbackProcessingInput, 
    organization_name: str | None, 
    user_email: str | None
):
    """Background task to process MCP client feedback with the agent"""
    try:
        from core.agents.mcp_feedback_processing_agent import mcp_feedback_processing_agent
        
        # Process feedback with the agent, including metadata for tracking
        async for response in mcp_feedback_processing_agent(
            agent_input, 
            organization_name=organization_name, 
            user_email=user_email
        ):
            # Log the analysis or store it somewhere if needed
            # For now, just log that processing completed
            print(f"MCP client feedback processed for {organization_name}: {response.analysis.sentiment} sentiment")
            
    except Exception as e:
        # Log error but don't fail the MCP tool response
        print(f"Error processing MCP client feedback: {str(e)}")
```

### 4. Testing Strategy (Simplified)

Since this is not a critical feature, we'll keep testing minimal but effective:

**Basic Unit Tests**: `api/core/agents/mcp_feedback_processing_agent_test.py`
- Test one positive, one negative, one neutral sentiment classification
- Test basic structured output parsing
- No extensive edge case testing

**Basic Integration Tests**: `api/api/routers/mcp/mcp_server_test.py`
- Test MCP tool returns successful acknowledgment
- Test error handling for malformed requests
- No complex scenario testing

**Example Minimal Test Cases**:
```python
@pytest.mark.parametrize("feedback,expected_sentiment", [
    ("MCP server worked great, all tools responded quickly", "positive"),
    ("MCP operations failed, tools were unresponsive", "negative"),
    ("MCP server functioned as expected", "neutral"),
])
async def test_mcp_feedback_basic_sentiment_classification(feedback, expected_sentiment):
    """Basic test to ensure sentiment classification works"""
    input_data = MCPFeedbackProcessingInput(feedback=feedback, context=None)
    
    responses = []
    async for response in mcp_feedback_processing_agent(input_data, "test-org", None):
        responses.append(response)
    
    assert len(responses) == 1
    assert responses[0].analysis.sentiment == expected_sentiment

async def test_send_feedback_mcp_tool_basic():
    """Basic test to ensure MCP tool returns acknowledgment"""
    request = SendFeedbackRequest(feedback="Basic test feedback")
    result = await send_feedback(request)
    
    assert result.success is True
    assert "received and sent for processing" in result.result["message"]
```

## Benefits of Metadata Approach

### 1. **MCP Client Analytics**
- Track feedback patterns by organization using MCP server
- Identify common issues or successful patterns
- Monitor MCP server performance from client perspective

### 2. **Simplified Architecture**
- Minimal testing overhead for non-critical feature
- Clean separation between acknowledgment and processing
- Automated feedback collection without user intervention

### 3. **Searchability**
Using the existing `search_runs_by_metadata` MCP tool, administrators can find MCP client feedback:
```python
# Find all MCP client feedback for a specific organization
search_runs_by_metadata({
    "agent_id": "mcp-feedback-processing-agent",
    "field_queries": [
        {
            "field_name": "metadata.organization_name",
            "operator": "is",
            "values": ["acme-corp"]
        }
    ]
})
```

## Open Questions & Decisions Needed

### 1. Agent Location in Codebase
**Recommendation**: `api/core/agents/mcp_feedback_processing_agent.py`
- **Rationale**: Follows existing pattern in `core/agents/` directory with "mcp" prefix

### 2. API Key Configuration
**Recommendation**: Use `WORKFLOWAI_API_KEY` environment variable
- **Rationale**: Consistent with existing agent patterns
- **Implementation**: `api_key=os.environ["WORKFLOWAI_API_KEY"]`

### 3. Additional Configuration Questions

**Model Selection**:
- **Recommendation**: `gemini-2.0-flash-latest`
- **Rationale**: Cost-effective, fast, good for sentiment analysis

**Testing Strategy**:
- **Recommendation**: Minimal testing since feature is not critical
- **Focus**: Basic functionality validation only

**Background Processing**:
- **Recommendation**: Simple asyncio.create_task() approach
- **Rationale**: Keep it simple for non-critical feature

## Implementation Steps

1. **Phase 1: Core Agent**
   - [ ] Create `mcp_feedback_processing_agent.py` with simplified OpenAI SDK pattern
   - [ ] Implement metadata-based agent identification
   - [ ] Add minimal unit tests (3-4 basic test cases)

2. **Phase 2: MCP Integration**
   - [ ] Add `send_feedback` tool to MCP server
   - [ ] Implement `MCPService.send_feedback()` method with metadata extraction
   - [ ] Add basic integration tests (2-3 test cases)

3. **Phase 3: Validation**
   - [ ] Basic end-to-end testing with MCP client
   - [ ] Verify feedback processing works
   - [ ] No extensive testing needed

4. **Phase 4: Deployment**
   - [ ] Basic error monitoring
   - [ ] Simple logging for processed feedback
   - [ ] No complex analytics needed initially

## Dependencies

- No new external dependencies required
- Uses existing WorkflowAI agent infrastructure (OpenAI SDK pattern)
- Leverages existing MCP tool framework
- Minimal testing dependencies

## Security Considerations

- MCP client feedback should be sanitized/validated
- Organization information handled securely
- No sensitive information should be logged in feedback
- Consider feedback content size limits

## Monitoring & Observability

- Basic logging for feedback submission success/failure
- Simple monitoring of MCP tool response times
- Log background processing completion (no complex metrics needed)
- Basic alerting on processing errors

## Future Enhancements

1. **Analytics Dashboard**: Simple view of MCP client feedback trends
2. **Feedback Aggregation**: Basic reports on common issues
3. **Integration with Existing Systems**: Connect with current feedback workflows if needed
4. **Enhanced Categorization**: Extend beyond sentiment if patterns emerge