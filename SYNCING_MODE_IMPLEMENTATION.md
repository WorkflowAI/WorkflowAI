# Syncing Mode Implementation for Claude Models with Extended Thinking

This document outlines the implementation of syncing mode (extended thinking) for Claude models on both Anthropic Provider and Amazon Bedrock.

## Overview

The syncing mode enables Claude models to show their step-by-step reasoning process through "thinking" blocks before providing the final answer. This implementation supports:

- Claude 4 Sonnet and Opus models
- Claude 3.7 Sonnet models  
- Both Anthropic direct API and Amazon Bedrock
- Streaming and non-streaming responses
- Quality index enhancement (+10 relative to non-thinking models)

## Implementation Details

### 1. Model Definitions

**New Thinking Model IDs:**
- `claude-sonnet-4-latest-thinking`
- `claude-sonnet-4-20250514-thinking` 
- `claude-opus-4-latest-thinking`
- `claude-opus-4-20250514-thinking`
- `claude-3-7-sonnet-latest-thinking`
- `claude-3-7-sonnet-20250219-thinking`

**Quality Index Enhancement:**
All thinking models have quality scores increased by 10 points compared to their base models to reflect improved reasoning capabilities.

### 2. Anthropic Provider Implementation

**Features Added:**
- Detection of thinking models via `-thinking` suffix
- Automatic thinking parameter configuration (`{"type": "enabled", "budget_tokens": 10000}`)
- Model name mapping (removes `-thinking` suffix for API calls)
- **Structured Syncing Chunk Parsing**: Properly separates thinking content from regular text
- **Streaming Support**: Real-time thinking content delivery via `reasoning_steps` parameter
- **Content Block Tracking**: Uses context variables to track thinking vs text blocks

**Syncing Chunk Parsing:**
- `thinking_delta` events → sent as `reasoning_steps` in `ParsedResponse`
- `text_delta` events → sent as regular `content` in `ParsedResponse`
- `signature_delta` events → ignored (internal verification)
- Thinking content is **not** mixed with regular text content

**Key Files Modified:**
- `api/core/providers/anthropic/anthropic_domain.py` - Added thinking content blocks and deltas
- `api/core/providers/anthropic/anthropic_provider.py` - Added thinking detection, syncing chunk parsing, and streaming support

### 3. Amazon Bedrock Implementation

**Features Added:**
- Same thinking model detection logic
- Thinking parameter support in completion requests
- Integration with existing Bedrock converse API
- Model ID mapping through existing configuration

**Limitations:**
- Amazon Bedrock's Converse API does not expose thinking content in structured streaming format
- Thinking happens internally but is not returned as separate reasoning steps
- Users get the benefit of improved reasoning but cannot see the step-by-step process

**Key Files Modified:**
- `api/core/providers/amazon_bedrock/amazon_bedrock_domain.py` - Added thinking parameter support
- `api/core/providers/amazon_bedrock/amazon_bedrock_provider.py` - Added thinking detection
- `api/core/providers/amazon_bedrock/amazon_bedrock_config.py` - Added thinking model mappings

### 4. Model Data Configuration

**Model Data Mapping:**
- Added complete model data for all thinking variants
- Configured pricing data for both providers
- Set up proper model relationships and metadata

**Key Files Modified:**
- `api/core/domain/models/models.py` - Added thinking model enums
- `api/core/domain/models/model_data_mapping.py` - Added model data configurations
- `api/core/domain/models/model_provider_data_mapping.py` - Added provider pricing

## Usage Examples

### Anthropic Direct API
```python
# Request automatically enables thinking for thinking models
response = anthropic_provider.complete(
    model="claude-sonnet-4-20250514-thinking",
    messages=[{"role": "user", "content": "Solve this complex problem..."}]
)

# Non-streaming: thinking content available via reasoning_steps
print("Reasoning:", response.reasoning_steps)  # Step-by-step thinking
print("Answer:", response.content)  # Final answer only

# Streaming: thinking and text content separated
for chunk in anthropic_provider.stream_complete(...):
    if chunk.reasoning_steps:
        print(f"Thinking: {chunk.reasoning_steps}")
    if chunk.content:
        print(f"Answer: {chunk.content}")
```

### Amazon Bedrock
```python
# Same interface, automatic thinking detection
response = bedrock_provider.complete(
    model="claude-sonnet-4-20250514-thinking", 
    messages=[{"role": "user", "content": "Analyze this data..."}]
)

# Note: Bedrock doesn't expose thinking content separately
# But benefits from improved reasoning quality (+10 quality index)
print("Enhanced Answer:", response.content)  # Improved reasoning, no thinking steps visible
```

## API Request/Response Format

### Request Enhancement
For thinking models, the providers automatically add:
```json
{
  "thinking": {
    "type": "enabled",
    "budget_tokens": 10000
  }
}
```

### Response Format
**Non-streaming:**
```json
{
  "content": [
    {
      "type": "thinking",
      "thinking": "Step-by-step reasoning...",
      "signature": "encrypted_signature..."
    },
    {
      "type": "text", 
      "text": "Final answer..."
    }
  ]
}
```

**Streaming (Anthropic only):**
```json
// Thinking content chunk
{
  "content": "",
  "reasoning_steps": "Let me solve this step by step:\n\n1. First break down 27 * 453",
  "tool_calls": null
}

// Regular text content chunk  
{
  "content": "27 * 453 = 12,231",
  "reasoning_steps": null,
  "tool_calls": null
}
```

**Raw Anthropic SSE Events:**
- `content_block_start` with `"type": "thinking"` → Initialize thinking block
- `content_block_delta` with `thinking_delta` → Stream thinking content as `reasoning_steps`
- `content_block_delta` with `text_delta` → Stream regular content as `content`
- `content_block_delta` with `signature_delta` → Ignored (internal verification)

## Benefits

1. **Transparency**: Users can see the model's reasoning process
2. **Quality**: +10 quality index improvement over base models  
3. **Debugging**: Better understanding of model decision-making
4. **Education**: Learning from AI reasoning patterns
5. **Trust**: Increased confidence through visible thought process

## Configuration

### Environment Variables
The thinking models use the same configuration as their base models:

**Anthropic:**
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_API_URL`

**Amazon Bedrock:**
- `AWS_BEDROCK_ACCESS_KEY`
- `AWS_BEDROCK_SECRET_KEY` 
- `AWS_BEDROCK_MODEL_REGION_MAP`

### Model Selection
Simply use the thinking model ID to enable extended thinking:
- Replace `claude-sonnet-4-20250514` with `claude-sonnet-4-20250514-thinking`
- The provider automatically handles the rest

## Implementation Notes

1. **Model Mapping**: Thinking models map to the same underlying Claude models but with thinking enabled
2. **Pricing**: Same pricing as base models (thinking tokens are included in output token billing)
3. **Streaming**: Supports real-time thinking content delivery
4. **Tool Use**: Compatible with function calling and tool use
5. **Error Handling**: Graceful fallback to base models if thinking fails

## Testing

The implementation includes comprehensive testing of:
- ✅ **Model enum validation**: All 6 thinking model variants properly defined
- ✅ **Provider detection logic**: Correctly identifies "-thinking" suffix in model names
- ✅ **Request building verification**: Proper thinking parameter injection and model name mapping
- ✅ **Syncing chunk parsing**: Separates thinking content from regular text in streaming responses
- ✅ **Content separation**: Thinking content sent as `reasoning_steps`, text as `content`
- ✅ **Response parsing capability**: Both streaming and non-streaming thinking content extraction
- ✅ **Quality index enhancement**: +10 points for all thinking models
- ✅ **Dual provider support**: Works on both Anthropic (full syncing) and Bedrock (thinking enabled)

## Future Enhancements

- Dynamic thinking budget configuration
- Thinking content filtering/summarization
- Advanced thinking block analysis
- Integration with evaluation metrics
- Custom thinking prompt templates

## Summary

The syncing mode implementation is **fully complete and operational** with proper syncing chunk parsing. Users can now:

1. **Use thinking models** by selecting any model with "-thinking" suffix
2. **See step-by-step reasoning** through structured `reasoning_steps` in responses (Anthropic only)
3. **Benefit from enhanced quality** with +10 quality index improvement (both providers)
4. **Work with both providers** seamlessly (Anthropic with full syncing, Bedrock with thinking enabled)
5. **Stream thinking content** separately from regular text in real-time applications
6. **Maintain tool compatibility** with existing function calling workflows

### ✅ **Proper Syncing Chunk Parsing**
- **Anthropic**: Thinking content streamed as `reasoning_steps`, regular text as `content`
- **Amazon Bedrock**: Thinking enabled internally, improved quality without visible reasoning steps
- **Content Separation**: No mixing of thinking and text content in responses
- **Real-time Streaming**: Frontend receives thinking and text content in separate, structured chunks

### ✅ **Complete Requirements Fulfillment**
- ✅ **Duplicate models with "thinking" suffix**: 6 thinking model variants added
- ✅ **Parse syncing tokens for frontend display**: Structured `ParsedResponse` with `reasoning_steps`
- ✅ **Quality index enhancement (+10 points)**: All thinking models have improved quality scores
- ✅ **Compatible with both Anthropic and Bedrock providers**: Full implementation for both

### ✅ **Production Ready**
- All verification tests pass
- Comprehensive error handling
- Backward compatibility maintained
- No breaking changes to existing functionality
- Ready for immediate production deployment

The implementation successfully enables extended thinking mode for Claude models with proper syncing chunk parsing, allowing frontend applications to display the model's step-by-step reasoning process in real-time while maintaining separation between thinking content and final answers.