# MCP Send Feedback Tool Implementation Spec

## Overview

This specification outlines the implementation of a new MCP tool `send_feedback` that allows MCP clients to submit feedback which will be sent to a dedicated AI agent running on WorkflowAI. The agent will categorize and summarize feedback using structured output, but the MCP tool will only acknowledge receipt.

## Goal

Add a new MCP tool in `api/api/routers/mcp/mcp_server.py` that:
1. Accepts feedback from MCP clients
2. Sends the feedback to a dedicated AI agent for processing (fire-and-forget)
3. Returns simple acknowledgment that feedback was received and sent for processing
4. Uses metadata to track organization and user information for analytics

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
    
    system_message = """You are a feedback agent that receives feedback from MCP clients. 
    Your goal is to summarize the feedback and categorize the feedback into a sentiment: positive, negative, neutral.
    
    Provide structured analysis including:
    - A concise summary of the main points
    - Sentiment classification (positive, negative, neutral)
    - Key themes or topics identified
    - Confidence score for your sentiment classification
    """

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
        model="gpt-4o-mini-latest",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": "Analyze the provided feedback and return structured analysis."},
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
    feedback: str = Field(description="The feedback text to be processed")
    context: str | None = Field(default=None, description="Optional context about the feedback")

@_mcp.tool()
async def send_feedback(request: SendFeedbackRequest) -> MCPToolReturn:
    """<when_to_use>
    When the user wants to submit feedback that will be processed by an AI agent.
    This tool accepts feedback and sends it for analysis, returning a simple acknowledgment.
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
    """Send feedback to processing agent and return acknowledgment"""
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
                "message": "Feedback received and sent for processing",
                "feedback_length": len(feedback),
                "has_context": context is not None
            }
        )
    except Exception as e:
        return MCPToolReturn(
            success=False,
            error=f"Failed to send feedback for processing: {str(e)}"
        )

async def _process_feedback_async(
    self, 
    agent_input: MCPFeedbackProcessingInput, 
    organization_name: str | None, 
    user_email: str | None
):
    """Background task to process feedback with the agent"""
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
            print(f"Feedback processed for {organization_name}: {response.analysis.sentiment} sentiment")
            
    except Exception as e:
        # Log error but don't fail the MCP tool response
        print(f"Error processing feedback: {str(e)}")
```

### 4. Testing Strategy

**Unit Tests**: `api/core/agents/mcp_feedback_processing_agent_test.py`
- Test various feedback scenarios (positive, negative, neutral)
- Test edge cases (empty feedback, very long feedback)
- Test confidence scoring accuracy
- Test structured output parsing
- Test metadata handling

**Integration Tests**: `api/api/routers/mcp/mcp_server_test.py`
- Test MCP tool registration and execution
- Test error handling and validation
- Test acknowledgment response format
- Test that background processing doesn't block tool response
- Test organization/user context extraction

**Example Test Cases**:
```python
@pytest.mark.parametrize("feedback,expected_sentiment", [
    ("This is amazing! Great work!", "positive"),
    ("This is terrible and broken", "negative"),
    ("It works as expected", "neutral"),
])
async def test_mcp_feedback_sentiment_classification(feedback, expected_sentiment):
    input_data = MCPFeedbackProcessingInput(
        feedback=feedback,
        context=None
    )
    
    responses = []
    async for response in mcp_feedback_processing_agent(
        input_data, 
        organization_name="test-org", 
        user_email="test@example.com"
    ):
        responses.append(response)
    
    assert len(responses) == 1
    assert responses[0].analysis.sentiment == expected_sentiment
    assert 0.0 <= responses[0].analysis.confidence <= 1.0

async def test_send_feedback_mcp_tool():
    """Test that MCP tool returns acknowledgment without waiting for processing"""
    request = SendFeedbackRequest(
        feedback="This is test feedback",
        context="Testing context"
    )
    
    result = await send_feedback(request)
    
    assert result.success is True
    assert "received and sent for processing" in result.result["message"]
    assert result.result["feedback_length"] == len(request.feedback)
    assert result.result["has_context"] is True

async def test_metadata_tracking():
    """Test that agent runs are tagged with proper metadata for tracking"""
    # This would require integration testing with actual WorkflowAI backend
    # to verify the metadata is properly attached to the run
    pass
```

## Benefits of Metadata Approach

### 1. **Tracking and Analytics**
- Can filter runs by organization: `metadata.organization_name = "acme-corp"`
- Can filter runs by user: `metadata.user_email = "john@acme-corp.com"`
- Can analyze feedback patterns per organization
- Can track usage by different teams/users

### 2. **Simplified Architecture**
- No need to pass datetime information
- Agent identification via metadata instead of model parameter
- Cleaner separation of concerns

### 3. **Searchability**
Using the existing `search_runs_by_metadata` MCP tool, users can find feedback processing runs:
```python
# Find all feedback processing runs for a specific organization
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
- **Rationale**: Follows existing pattern in `core/agents/` directory with "mcp" prefix to indicate it's specifically for MCP feedback

### 2. API Key Configuration
**Recommendation**: Use `WORKFLOWAI_API_KEY` environment variable
- **Rationale**: 
  - Consistent with existing agent patterns (see `integration_code_block_agent.py`)
  - Already available in the environment based on existing usage
  - Follows security best practices for internal agent-to-agent communication
- **Implementation**: `api_key=os.environ["WORKFLOWAI_API_KEY"]`

### 3. Additional Configuration Questions

**Model Selection**:
- **Recommendation**: `gpt-4o-mini-latest` (in model parameter, not embedded in agent name)
- **Rationale**: Cost-effective for sentiment analysis, sufficient capability for this task

**Metadata Extraction**:
- **Question**: What's the best way to extract user email from MCP context?
- **Recommendation**: Start with organization name from tenant, add user email later if available

**Background Processing**:
- **Question**: Should we implement proper background task queue or use simple asyncio.create_task()?
- **Recommendation**: Start with asyncio.create_task(), upgrade to proper task queue later if needed

**Error Handling Strategy**:
- **Recommendation**: MCP tool always succeeds with acknowledgment, background processing errors are logged but don't affect tool response

## Implementation Steps

1. **Phase 1: Core Agent**
   - [ ] Create `mcp_feedback_processing_agent.py` with simplified OpenAI SDK pattern
   - [ ] Implement metadata-based agent identification
   - [ ] Add unit tests for the agent

2. **Phase 2: MCP Integration**
   - [ ] Add `send_feedback` tool to MCP server
   - [ ] Implement `MCPService.send_feedback()` method with metadata extraction
   - [ ] Add integration tests focusing on acknowledgment response

3. **Phase 3: Testing & Validation**
   - [ ] End-to-end testing with actual MCP clients
   - [ ] Verify metadata tracking works correctly
   - [ ] Test searchability using existing metadata search tools

4. **Phase 4: Production Readiness**
   - [ ] Error handling and monitoring for background processing
   - [ ] Analytics dashboard for feedback patterns by organization
   - [ ] Consider task queue for background processing

## Dependencies

- No new external dependencies required
- Uses existing WorkflowAI agent infrastructure (OpenAI SDK pattern)
- Leverages existing MCP tool framework
- Relies on existing OpenAI SDK integration
- Uses existing metadata search capabilities

## Security Considerations

- Feedback content should be sanitized/validated
- Organization and user information handled securely
- Use existing authentication patterns for internal agent communication
- Consider feedback content size limits
- Background processing errors should not expose internal details

## Monitoring & Observability

- Track feedback submission success/failure rates per organization
- Monitor MCP tool response times (should be fast)
- Log background processing completion/failure
- Monitor feedback processing agent performance
- Analytics on feedback sentiment patterns by organization
- Alert on background processing errors

## Future Enhancements

1. **Advanced Analytics**: Dashboard showing feedback trends by organization
2. **User Email Tracking**: Extract user email from MCP context for finer-grained analytics
3. **Proper Task Queue**: Replace asyncio.create_task with proper background job system
4. **Feedback Categorization**: Extend beyond sentiment to functional categories
5. **Integration with Existing Feedback System**: Connect with current feedback token workflow
6. **Rate Limiting**: Add rate limiting for feedback submissions per organization