# Plan to expose pricing on /v1/models endpoint

1. **Review existing endpoint**
   - `api/api/main.py` defines `list_all_available_models` which returns models in `StandardModelResponse` format.
   - `StandardModelResponse.ModelItem` currently exposes only id, created, owned_by, display_name, icon_url and supports fields.
   - Pricing information already exists within `ModelProviderData` (see `api/core/domain/models/model_provider_data.py`).

2. **Extend API schema**
   - Update `StandardModelResponse.ModelItem` to include two new pricing fields:
     - `price_per_input_token_usd`
     - `price_per_output_token_usd`
   - The values come from the text pricing data of the model's default provider.
   - Modify `from_model_data` classmethod to populate these values accordingly.

   Example entry returned by `/v1/models`:

   ```json
   {
     "id": "gpt-4",
     "object": "model",
     "created": 1710000000,
     "owned_by": "openai",
     "display_name": "GPT-4",
     "icon_url": "https://...",
     "supports": {"text": true},
     "price_per_input_token_usd": 0.00002,
     "price_per_output_token_usd": 0.00004
   }
   ```

3. **Update endpoint logic**
   - `list_all_available_models` should keep iterating over `MODEL_DATAS` but now return the extended `ModelItem` with pricing.
   - For latest models (`LatestModel`), use the underlying `FinalModelData` to access provider pricing.

4. **Testing**
   - Add unit tests in `api/api/main_test.py` asserting the presence and correctness of the new fields.
   - Ensure `ruff` and `pyright` checks run successfully and execute affected pytest suites.

5. **Documentation**
   - No documentation changes are planned in this task. Documentation will be updated separately once the API change is merged.

6. **Migration considerations**
   - Since this endpoint is used for OpenAI compatibility, ensure added fields do not break existing clients— they can ignore unknown keys. Document the change in `CHANGELOG` if required.

This approach keeps the existing endpoint behaviour while enriching the response with pricing information derived from the provider metadata already present in the codebase.
