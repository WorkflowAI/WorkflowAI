# Cerebras Provider Implementation

This document summarizes the implementation of the Cerebras provider for WorkflowAI.

## Overview

The Cerebras provider has been successfully implemented as a new provider for WorkflowAI, enabling users to utilize Cerebras's fast inference capabilities. The implementation reuses the OpenAI provider base since Cerebras is OpenAI-compatible, as mentioned in the documentation.

## Implementation Details

### Files Created/Modified

1. **Provider Implementation**
   - `api/core/providers/cerebras/__init__.py` - Package initialization
   - `api/core/providers/cerebras/cerebras_provider.py` - Main provider implementation
   - `api/core/providers/cerebras/cerebras_provider_test.py` - Basic test cases

2. **Core Domain Updates**
   - `api/core/domain/models/providers.py` - Added CEREBRAS to Provider enum
   - `api/core/domain/models/_displayed_provider.py` - Added CEREBRAS to DisplayedProvider enum
   - `api/core/domain/models/model_provider_data_mapping.py` - Added pricing data (set to 0 as requested)

3. **Configuration Updates**
   - `api/core/providers/base/config.py` - Added CerebrasConfig to provider config union
   - `api/core/providers/factory/local_provider_factory.py` - Added CerebrasProvider to provider factory

4. **Client-Side Updates**
   - `client/src/types/workflowAI/models.ts` - Added cerebras to Provider type
   - `client/src/components/ProxyModelsCombobox/utils.tsx` - Added Cerebras provider metadata
   - `client/src/components/AIModelsCombobox/utils.tsx` - Added Cerebras provider metadata

## Features Implemented

### Core Features
- **Streaming Support**: Inherits streaming capabilities from OpenAI provider base
- **Structured Output**: Supports structured generation through OpenAI-compatible interface
- **Tool Calling**: Supports function calling/tools through OpenAI-compatible interface
- **Multiple Models**: Supports DeepSeek, Llama, and other models available on Cerebras

### API Compatibility
- **OpenAI-Compatible**: Uses the same request/response format as OpenAI
- **Authentication**: Bearer token authentication with API key
- **Endpoint**: `https://api.cerebras.ai/v1/chat/completions`

### Supported Models
The implementation includes pricing data (set to 0 as requested) for the following models:
- `DEEPSEEK_R1_0528`
- `DEEPSEEK_V3_0324`
- `LLAMA_3_1_8B` (default model)
- `LLAMA_3_1_70B`
- `LLAMA_3_3_70B`

### Configuration
- **Environment Variable**: `CEREBRAS_API_KEY`
- **Optional URL Override**: `CEREBRAS_URL`
- **Default URL**: `https://api.cerebras.ai/v1/chat/completions`

## Usage

### Environment Setup
```bash
export CEREBRAS_API_KEY="your_api_key_here"
```

### Optional URL Override
```bash
export CEREBRAS_URL="https://custom.cerebras.api.endpoint"
```

### Provider Configuration
The provider is automatically discovered and available through the WorkflowAI provider factory.

## Technical Details

### Provider Class Structure
```python
class CerebrasProvider(OpenAIProviderBase[CerebrasConfig]):
    - Uses OpenAI provider base for maximum compatibility
    - Inherits streaming, tool calling, and structured output capabilities
    - Simple bearer token authentication
    - Configurable API endpoint
```

### Request Headers
```python
{
    "Authorization": f"Bearer {api_key}",
}
```

### Default Model
The provider defaults to `LLAMA_3_1_8B` if no model is specified.

## Benefits

1. **High Performance**: Cerebras is known for extremely fast inference speeds (>2,500 tokens/second)
2. **OpenAI Compatibility**: Seamless integration with existing OpenAI-compatible applications
3. **Feature Complete**: Supports all major features including streaming, tools, and structured output
4. **Easy Configuration**: Simple API key setup
5. **Cost Effective**: Currently set to 0 cost as requested

## Testing

Basic test coverage has been implemented in `cerebras_provider_test.py` including:
- Provider name validation
- Required environment variables
- Default model configuration
- Request URL generation
- Authentication header generation
- Configuration string representation

## Next Steps

1. **Add More Models**: Additional models can be added to the pricing data as they become available
2. **Update Pricing**: Real pricing data can be added when available
3. **Integration Testing**: Full integration tests can be run once the environment is properly configured
4. **Documentation**: User-facing documentation can be created for the Cerebras provider

## Conclusion

The Cerebras provider has been successfully implemented with full feature parity to other providers in the WorkflowAI system. It leverages the OpenAI provider base for maximum compatibility while providing access to Cerebras's ultra-fast inference capabilities.