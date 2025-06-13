# Recently Added LLM Models in the API

Based on my analysis of the codebase, here are the LLM models that have been recently added to your API:

## OpenAI Models (2025)

### O3 Series (April 2025)
- **o3-2025-04-16-high** - High reasoning effort
- **o3-2025-04-16-medium** - Medium reasoning effort  
- **o3-2025-04-16-low** - Low reasoning effort

### O3 Mini Series (January 2025)
- **o3-mini-2025-01-31-high** - High reasoning effort
- **o3-mini-2025-01-31-medium** - Medium reasoning effort
- **o3-mini-2025-01-31-low** - Low reasoning effort

### O4 Mini Series (April 2025)
- **o4-mini-2025-04-16-high** - High reasoning effort
- **o4-mini-2025-04-16-medium** - Medium reasoning effort
- **o4-mini-2025-04-16-low** - Low reasoning effort

### GPT-4.1 Series (April 2025)
- **gpt-4.1-2025-04-14** - Latest GPT-4.1 model
- **gpt-4.1-mini-2025-04-14** - Mini variant
- **gpt-4.1-nano-2025-04-14** - Nano variant

### GPT-4.5 Preview (February 2025)
- **gpt-4.5-preview-2025-02-27** - Preview of GPT-4.5

### GPT-4o Audio Preview (June 2025)
- **gpt-4o-audio-preview-2025-06-03** - Audio capabilities

## Anthropic Claude Models (2025)

### Claude 4 Series (May 2025)
- **claude-sonnet-4-20250514** - Claude 4 Sonnet
- **claude-opus-4-20250514** - Claude 4 Opus

### Claude 3.7 Series (February 2025)
- **claude-3-7-sonnet-20250219** - Claude 3.7 Sonnet

## Meta Llama Models (2025)

### Llama 4 Series
- **llama4-maverick-instruct-fast** - Fast variant
- **llama4-maverick-instruct-basic** - Basic variant
- **llama4-scout-instruct-fast** - Fast variant
- **llama4-scout-instruct-basic** - Basic variant

## Mistral AI Models (2025)

### New Mistral Models
- **mistral-medium-2505** - Medium model (March 2025)
- **mistral-small-2503** - Small model (March 2025)
- **mistral-small-2501** - Small model (January 2025)
- **mistral-saba-2502** - Saba model (February 2025)
- **magistral-small-2506** - Magistral Small (May 2025)
- **magistral-medium-2506** - Magistral Medium (June 2025)
- **codestral-2501** - Code-focused model (January 2025)

## DeepSeek Models (2025)

### DeepSeek R1 Series
- **deepseek-r1-2501** - Latest R1 model
- **deepseek-r1-2501-basic** - Basic variant
- **deepseek-r1-0528** - May 2025 variant

### DeepSeek V3 Series
- **deepseek-v3-0324** - March 2025 variant
- **deepseek-v3-latest** - Latest version

## Qwen Models (2025)

### Qwen3 Series
- **qwen3-235b-a22b** - 235B parameter model
- **qwen3-30b-a3b** - 30B parameter model

### QWQ Series
- **qwen-qwq-32b** - 32B parameter model
- **qwen-v3p2-32b-instruct** - Instruction-tuned variant

## Google Gemini Models (2025)

### Gemini 2.5 Series
- **gemini-2.5-flash-preview-0417** - Flash preview (April)
- **gemini-2.5-flash-preview-0520** - Flash preview (May)
- **gemini-2.5-pro-preview-0506** - Pro preview (May)
- **gemini-2.5-pro-preview-0605** - Pro preview (June)

### Gemini 2.5 Thinking Models
- **gemini-2.5-flash-thinking-preview-0417** - Thinking capabilities (April)
- **gemini-2.5-flash-thinking-preview-0520** - Thinking capabilities (May)

### Gemini 2.0 Models
- **gemini-2.0-flash-lite-preview-02-05** - Lite variant (February)
- **gemini-2.0-pro-exp-02-05** - Pro experimental (February)
- **gemini-2.0-flash-thinking-exp-1219** - Thinking experimental (December)
- **gemini-2.0-flash-thinking-exp-01-21** - Thinking experimental (January)

## Key Features of Recently Added Models

### Reasoning Models
Many of the new models feature **reasoning capabilities** with different effort levels:
- **High**: Maximum reasoning power, higher cost
- **Medium**: Balanced reasoning and cost
- **Low**: Basic reasoning, lower cost

### Specialized Capabilities
- **Audio Processing**: GPT-4o audio preview models
- **Code Generation**: Codestral models
- **Thinking/Reasoning**: Gemini thinking models and O3/O4 series
- **Multimodal**: Vision and audio capabilities across various models

### Provider Distribution
The new models are distributed across major providers:
- **OpenAI**: Advanced reasoning models (O3, O4, GPT-4.1, GPT-4.5)
- **Anthropic**: Claude 4 series with enhanced capabilities
- **Google**: Gemini 2.5 and thinking models
- **Meta**: Llama 4 series
- **Mistral**: Enhanced model lineup
- **DeepSeek**: R1 and V3 series
- **Qwen**: QWQ and Qwen3 series

## Default Models
The API currently features these as default models (top priority):
- **gpt-4.1-latest**
- **gemini-2.0-flash-latest**
- **claude-sonnet-4-latest**
- **imagen-3.0-generate-latest** (for image generation)

## Featured Models in API Preview
Recent models specifically featured in the `/models` endpoint preview include:
- **deepseek-r1-2501-basic**
- **mistral-large-2-latest**
- **llama4-maverick-instruct-basic**

This represents a significant expansion of the model offerings with enhanced reasoning capabilities, multimodal features, and specialized use cases across all major AI providers.