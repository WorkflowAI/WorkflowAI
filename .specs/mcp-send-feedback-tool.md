# MCP Send Feedback Tool Implementation Spec

## Overview

This specification outlines the implementation of a new MCP tool `send_feedback` that allows MCP clients to submit feedback which will be processed by a dedicated AI agent running on WorkflowAI. The agent will categorize and summarize feedback using structured output.

## Goal

Add a new MCP tool in `api/api/routers/mcp/mcp_server.py` that:
1. Accepts feedback from MCP clients
2. Sends the feedback to a dedicated AI agent for processing
3. Returns the agent's analysis (summary and sentiment categorization)

## Current State Analysis

### Existing MCP Tools Pattern
- Located in `api/api/routers/mcp/mcp_server.py`
- Use `@_mcp.tool()` decorator
- Return `MCPToolReturn` objects
- Have access to `MCPService` via `get_mcp_service()`

### Existing Feedback System
- Feedback tokens and `FeedbackService` already exist
- Feedback domain models in `core/domain/feedback.py`
- Current feedback flow: client → feedback token → WorkflowAI dashboard

### Existing Agent Patterns
- Agents use OpenAI SDK with `WORKFLOWAI_API_KEY` environment variable
- Base URL: `f"{os.environ['WORKFLOWAI_API_URL']}/v1"`
- Pattern: `client = AsyncOpenAI(api_key=os.environ["WORKFLOWAI_API_KEY"], base_url=...)`
- Examples in `core/agents/` directory

## Implementation Plan

### 1. Create Feedback Processing Agent

**Location**: `api/core/agents/feedback_processing_agent.py`

**Agent Structure**:
```python
@workflowai.agent(
    id="feedback-processing-agent",
    model=workflowai.Model.GPT_4O_MINI_LATEST  # Cost-effective for this task
)
async def feedback_processing_agent(
    input: FeedbackProcessingInput,
) -> FeedbackProcessingOutput:
    """You are a feedback agent that receives feedback from a MCP client. 
    Your goal is to summarize the feedback and categorize the feedback into a sentiment: positive, negative, neutral"""
```

**Input/Output Models**:
```python
class FeedbackProcessingInput(BaseModel):
    feedback: str = Field(description="The raw feedback from the MCP client")
    context: str | None = Field(default=None, description="Optional context about what the feedback relates to")

class FeedbackProcessingOutput(BaseModel):
    summary: str = Field(description="A concise summary of the feedback")
    sentiment: Literal["positive", "negative", "neutral"] = Field(description="The categorized sentiment")
    key_themes: list[str] = Field(description="Key themes or topics identified in the feedback")
    confidence: float = Field(description="Confidence score (0.0-1.0) for the sentiment classification")
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
    When the user wants to submit feedback that should be analyzed and categorized by an AI agent.
    This tool processes feedback through WorkflowAI's feedback processing agent to provide
    structured analysis including sentiment categorization and key themes.
    </when_to_use>
    <returns>
    Returns the AI agent's analysis of the feedback including:
    - summary: A concise summary of the feedback
    - sentiment: Categorized as positive, negative, or neutral
    - key_themes: List of key themes identified
    - confidence: Confidence score for the sentiment classification
    </returns>"""
    service = await get_mcp_service()
    return await service.send_feedback(request.feedback, request.context)
```

### 3. Add MCPService Method

**Location**: `api/api/routers/mcp/_mcp_service.py`

**Service Method**:
```python
async def send_feedback(self, feedback: str, context: str | None = None) -> MCPToolReturn:
    """Process feedback through the feedback processing agent"""
    try:
        from core.agents.feedback_processing_agent import feedback_processing_agent, FeedbackProcessingInput
        
        # Run the feedback through the processing agent
        result = await feedback_processing_agent(
            FeedbackProcessingInput(
                feedback=feedback,
                context=context
            )
        )
        
        return MCPToolReturn(
            success=True,
            result={
                "summary": result.summary,
                "sentiment": result.sentiment,
                "key_themes": result.key_themes,
                "confidence": result.confidence,
                "processed_at": datetime.datetime.now().isoformat()
            }
        )
    except Exception as e:
        return MCPToolReturn(
            success=False,
            error=f"Failed to process feedback: {str(e)}"
        )
```

### 4. Testing Strategy

**Unit Tests**: `api/core/agents/feedback_processing_agent_test.py`
- Test various feedback scenarios (positive, negative, neutral)
- Test edge cases (empty feedback, very long feedback)
- Test confidence scoring accuracy

**Integration Tests**: `api/api/routers/mcp/mcp_server_test.py`
- Test MCP tool registration and execution
- Test error handling and validation
- Test end-to-end feedback processing flow

**Example Test Cases**:
```python
@pytest.mark.parametrize("feedback,expected_sentiment", [
    ("This is amazing! Great work!", "positive"),
    ("This is terrible and broken", "negative"),
    ("It works as expected", "neutral"),
])
async def test_feedback_sentiment_classification(feedback, expected_sentiment):
    # Test implementation
```

## Open Questions & Decisions Needed

### 1. Agent Location in Codebase
**Recommendation**: `api/core/agents/feedback_processing_agent.py`
- **Rationale**: Follows existing pattern in `core/agents/` directory alongside other WorkflowAI agents like `meta_agent.py`, `integration_code_block_agent.py`
- **Alternative**: Could be in a dedicated `feedback/` subdirectory if planning multiple feedback-related agents

### 2. API Key Configuration
**Recommendation**: Use `WORKFLOWAI_API_KEY` environment variable
- **Rationale**: 
  - Consistent with existing agent patterns (see `meta_agent_proxy.py`, `integration_code_block_agent.py`)
  - Already available in the environment based on existing usage
  - Follows security best practices for internal agent-to-agent communication
- **Implementation**: `api_key=os.environ["WORKFLOWAI_API_KEY"]`

### 3. Additional Configuration Questions

**Model Selection**:
- **Recommendation**: `workflowai.Model.GPT_4O_MINI_LATEST`
- **Rationale**: Cost-effective for sentiment analysis, sufficient capability for this task

**Error Handling Strategy**:
- **Recommendation**: Graceful degradation with structured error responses
- **Fallback**: Return error in MCPToolReturn format rather than raising exceptions

**Rate Limiting**:
- **Question**: Should we implement rate limiting for feedback submissions?
- **Recommendation**: Start without, add if needed based on usage patterns

**Persistence**:
- **Question**: Should processed feedback be stored in the database?
- **Recommendation**: Initially return analysis only, add persistence later if needed for analytics

## Implementation Steps

1. **Phase 1: Core Agent**
   - [ ] Create `feedback_processing_agent.py` with input/output models
   - [ ] Implement agent with structured output
   - [ ] Add unit tests for the agent

2. **Phase 2: MCP Integration**
   - [ ] Add `send_feedback` tool to MCP server
   - [ ] Implement `MCPService.send_feedback()` method
   - [ ] Add integration tests

3. **Phase 3: Testing & Validation**
   - [ ] End-to-end testing with actual MCP clients
   - [ ] Performance testing and optimization
   - [ ] Documentation updates

4. **Phase 4: Production Readiness**
   - [ ] Error handling and monitoring
   - [ ] Rate limiting if needed
   - [ ] Analytics and logging

## Dependencies

- No new external dependencies required
- Uses existing WorkflowAI agent infrastructure
- Leverages existing MCP tool framework
- Relies on existing OpenAI SDK integration

## Security Considerations

- Feedback content should be sanitized/validated
- No sensitive information should be logged
- Use existing authentication patterns for internal agent communication
- Consider feedback content size limits

## Monitoring & Observability

- Track feedback processing success/failure rates
- Monitor agent response times
- Log sentiment distribution for insights
- Alert on processing errors

## Future Enhancements

1. **Feedback Categorization**: Extend beyond sentiment to functional categories
2. **Feedback Routing**: Route different types of feedback to different agents
3. **Feedback Persistence**: Store processed feedback for analytics
4. **Feedback Aggregation**: Provide summary reports across multiple feedback items
5. **Integration with Existing Feedback System**: Connect with current feedback token workflow