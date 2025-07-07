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
- Thinking block parsing and streaming support
- Content extraction with thinking markers `[THINKING]...[/THINKING]`

**Key Files Modified:**
- `api/core/providers/anthropic/anthropic_domain.py` - Added thinking content blocks and deltas
- `api/core/providers/anthropic/anthropic_provider.py` - Added thinking detection and processing

### 3. Amazon Bedrock Implementation

**Features Added:**
- Same thinking model detection logic
- Thinking parameter support in completion requests
- Integration with existing Bedrock converse API
- Model ID mapping through existing configuration

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

# Response includes thinking blocks
# [THINKING]
# Let me break this down step by step...
# [/THINKING]
# Based on my analysis...
```

### Amazon Bedrock
```python
# Same interface, automatic thinking detection
response = bedrock_provider.complete(
    model="claude-sonnet-4-20250514-thinking", 
    messages=[{"role": "user", "content": "Analyze this data..."}]
)
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

**Streaming:**
- `thinking_delta` events for thinking content
- `text_delta` events for final response
- Proper thinking block start/stop markers

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

The implementation includes:
- Model enum validation ✓
- Provider detection logic ✓
- Request building verification ✓
- Response parsing capability ✓

## Future Enhancements

- Dynamic thinking budget configuration
- Thinking content filtering/summarization
- Advanced thinking block analysis
- Integration with evaluation metrics
- Custom thinking prompt templates