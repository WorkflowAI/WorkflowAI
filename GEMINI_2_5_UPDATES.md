# Gemini 2.5 Model Updates

Based on the [Google blog post](https://developers.googleblog.com/en/gemini-2-5-thinking-model-updates/) from June 17, 2025, this PR implements the necessary changes to support the updated Gemini 2.5 model family.

## Key Changes from Google

### New Models Available
- **Gemini 2.5 Pro** - Now generally available and stable (same as 06-05 preview)
- **Gemini 2.5 Flash** - Now generally available and stable (same as 05-20 preview)  
- **Gemini 2.5 Flash-Lite** - New preview model with lowest latency and cost in 2.5 family

### Pricing Updates for Gemini 2.5 Flash
- **Input tokens**: $0.30 / 1M tokens (increased from $0.15)
- **Output tokens**: $2.50 / 1M tokens (decreased from $3.50)
- **Unified pricing**: Removed thinking vs non-thinking price difference
- **Single tier**: Same price regardless of input token size

### Model Names
- Stable models use: `gemini-2.5-flash` and `gemini-2.5-pro`
- New Flash-Lite model: `gemini-2.5-flash-lite`

### Deprecation Timeline
- **Gemini 2.5 Flash Preview 04-17**: Deprecated July 15, 2025
- **Gemini 2.5 Pro Preview 05-06**: Deprecated June 19, 2025

### New Features
- All Gemini 2.5 models are "thinking models" with configurable thinking budgets
- Flash-Lite has thinking off by default (unlike other models)
- API parameter for thinking budget control

## Implementation Changes

### 1. Model Enum Updates (`models.py`)
Added new stable model identifiers:
- `GEMINI_2_5_PRO = "gemini-2.5-pro"`
- `GEMINI_2_5_FLASH = "gemini-2.5-flash"`  
- `GEMINI_2_5_FLASH_LITE = "gemini-2.5-flash-lite"`

### 2. Pricing Updates (`model_provider_datas_mapping.py`)
Updated both Google Vertex AI and Google Gemini API provider pricing:

**Google Provider Data:**
- Added pricing for new stable models
- Updated Flash pricing to unified $0.30/$2.50 structure
- Added Flash-Lite pricing (estimated at $0.075/$0.30 as cheapest in family)

**Google Gemini API Provider Data:**
- Added corresponding pricing entries for API access
- Maintained same price structure across both providers

### 3. Model Data Definitions
*Note: Model data definitions in `model_datas_mapping.py` need to be added but were not completed due to file corruption issues during implementation.*

**Planned additions:**
- `GEMINI_2_5_FLASH`: Stable Flash model with configurable reasoning
- `GEMINI_2_5_FLASH_LITE`: Cost-optimized model with thinking off by default
- `GEMINI_2_5_PRO`: Stable Pro model with advanced reasoning capabilities

All new models support:
- JSON mode, multimodal input (images, audio, PDFs)
- Tool calling and function calling
- 1M+ token context windows
- Configurable thinking budgets via `reasoning_level="configurable"`

## Benefits for Users

1. **Cost Optimization**: Flash-Lite provides cheapest option for cost-sensitive use cases
2. **Simplified Pricing**: Unified Flash pricing removes confusion about thinking costs
3. **Stable Models**: Production-ready stable versions replace preview models
4. **Enhanced Reasoning**: All models include thinking capabilities with budget controls

## Next Steps

1. Complete model data definitions in `model_datas_mapping.py`
2. Update any test files that reference deprecated model names
3. Update documentation to reflect new model availability
4. Consider updating default model recommendations based on new pricing

## Compatibility

- Existing preview models remain available until deprecation dates
- Pricing changes affect new requests immediately
- Applications should migrate to stable model names before deprecation