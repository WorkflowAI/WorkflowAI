from datetime import date
from typing import Any, cast

from api.routers.mcp._mcp_models import StandardModelResponse
from core.domain.models.model_data import FinalModelData, ModelData, QualityData
from core.domain.models.model_data_pricing import (
    FixedPricing,
    MaxTokensData,
    TextModelPricing,
)
from core.domain.models.model_provider_data import (
    DisplayedProvider,
    ModelProviderData,
)


class TestMCPStandardModelResponse:
    def test_model_item_has_whitelisted_fields_only(self):
        """Test that MCP ModelItem only includes whitelisted root fields"""
        # Create sample model data
        model_data = ModelData(
            display_name="Test Model",
            icon_url="https://example.com/icon.svg",
            max_tokens_data=MaxTokensData(
                max_tokens=128000,
                max_output_tokens=4096,
                source="test",
            ),
            release_date=date(2024, 6, 15),
            quality_data=QualityData(mmlu=85.0, gpqa=50.0),
            provider_name=DisplayedProvider.OPEN_AI.value,
            supports_json_mode=True,
            supports_structured_output=True,
            support_system_messages=True,
            supports_tool_calling=True,
            supports_parallel_tool_calls=True,
            supports_input_image=True,
            supports_input_pdf=False,
            supports_input_audio=True,
            supports_output_image=False,
            supports_output_text=True,
            supports_audio_only=False,
            support_input_schema=True,
        )

        # Create provider data
        provider_data = ModelProviderData(
            text_price=TextModelPricing(
                pricing=FixedPricing(
                    prompt_cost_per_token=0.001,
                    completion_cost_per_token=0.002,
                ),
            ),
        )

        # Create final model data
        final_model_data = FinalModelData(
            model_data=model_data,
            providers=[(DisplayedProvider.OPEN_AI, provider_data)],
        )

        # Create the response item
        response_item = StandardModelResponse.ModelItem.from_model_data("test-model", final_model_data)

        # Convert to dict for field checking
        item_dict = response_item.model_dump()

        # Define expected root fields
        expected_root_fields = {
            "id",
            "object",
            "created",
            "display_name",
            "icon_url",
            "supports",
            "pricing",
            "release_date",
        }

        # Check that all expected fields are present
        for field in expected_root_fields:
            assert field in item_dict, f"Expected field '{field}' missing from MCP model response"

        # Check that no unexpected fields are present
        actual_fields = set(item_dict.keys())
        unexpected_fields = actual_fields - expected_root_fields
        assert len(unexpected_fields) == 0, f"Unexpected fields found in MCP response: {unexpected_fields}"

        # Verify field values
        assert item_dict["id"] == "test-model"
        assert item_dict["object"] == "model"
        assert item_dict["display_name"] == "Test Model"
        assert item_dict["icon_url"] == "https://example.com/icon.svg"
        assert isinstance(item_dict["created"], int)
        assert item_dict["release_date"] == date(2024, 6, 15)

    def test_pricing_structure(self):
        """Test that pricing has correct structure"""
        # Create minimal test data
        model_data = ModelData(
            display_name="Test Model",
            icon_url="https://example.com/icon.svg",
            max_tokens_data=MaxTokensData(max_tokens=1000, source="test"),
            release_date=date(2024, 6, 15),
            quality_data=QualityData(mmlu=80.0),
            provider_name=DisplayedProvider.OPEN_AI.value,
            supports_tool_calling=True,
            supports_input_image=False,
            supports_input_pdf=False,
            supports_input_audio=False,
        )

        provider_data = ModelProviderData(
            text_price=TextModelPricing(
                pricing=FixedPricing(
                    prompt_cost_per_token=0.005,
                    completion_cost_per_token=0.010,
                ),
            ),
        )

        final_model_data = FinalModelData(
            model_data=model_data,
            providers=[(DisplayedProvider.OPEN_AI, provider_data)],
        )

        response_item = StandardModelResponse.ModelItem.from_model_data("test-model", final_model_data)
        item_dict = response_item.model_dump()

        # Check pricing structure
        assert "pricing" in item_dict
        pricing = cast(dict[str, Any], item_dict["pricing"])

        expected_pricing_fields = {"input_token_usd", "output_token_usd"}
        actual_pricing_fields = set(pricing.keys())

        assert actual_pricing_fields == expected_pricing_fields, (
            f"Pricing fields mismatch. Expected: {expected_pricing_fields}, Got: {actual_pricing_fields}"
        )

        assert pricing["input_token_usd"] == 0.005
        assert pricing["output_token_usd"] == 0.010

    def test_supports_field_whitelisting(self):
        """Test that supports field contains only whitelisted support fields"""
        # Create model with all support fields set to True
        model_data = ModelData(
            display_name="Test Model",
            icon_url="https://example.com/icon.svg",
            max_tokens_data=MaxTokensData(max_tokens=1000, source="test"),
            release_date=date(2024, 6, 15),
            quality_data=QualityData(mmlu=80.0),
            provider_name=DisplayedProvider.OPEN_AI.value,
            # Set ALL support fields to True to test filtering
            supports_json_mode=True,
            supports_structured_output=True,
            support_system_messages=True,
            supports_tool_calling=True,
            supports_parallel_tool_calls=True,
            supports_input_image=True,
            supports_input_pdf=True,
            supports_input_audio=True,
            supports_output_image=True,
            supports_output_text=True,
            supports_audio_only=True,
            support_input_schema=True,
        )

        provider_data = ModelProviderData(
            text_price=TextModelPricing(
                pricing=FixedPricing(prompt_cost_per_token=0.001, completion_cost_per_token=0.002),
            ),
        )

        final_model_data = FinalModelData(
            model_data=model_data,
            providers=[(DisplayedProvider.OPEN_AI, provider_data)],
        )

        response_item = StandardModelResponse.ModelItem.from_model_data("test-model", final_model_data)
        item_dict = response_item.model_dump()

        # Check supports structure
        assert "supports" in item_dict
        supports = cast(dict[str, Any], item_dict["supports"])

        # Define expected support fields (should match the whitelist)
        expected_support_fields = {
            "input_image",
            "input_pdf",
            "input_audio",
            "output_image",
            "output_text",
            "audio_only",
            "tool_calling",
            "parallel_tool_calls",
        }

        actual_support_fields = set(supports.keys())

        # Check that all expected support fields are present
        for field in expected_support_fields:
            assert field in supports, f"Expected support field '{field}' missing from MCP response"

        # Check that no unexpected support fields are present
        unexpected_support_fields = actual_support_fields - expected_support_fields
        assert len(unexpected_support_fields) == 0, (
            f"Unexpected support fields found in MCP response: {unexpected_support_fields}"
        )

        # Verify that excluded fields are NOT present
        excluded_fields = {"json_mode", "structured_output", "system_messages", "input_schema"}
        for field in excluded_fields:
            assert field not in supports, f"Excluded field '{field}' should not be present in MCP supports"

        # Verify all included fields are True (since we set them all to True in model_data)
        for field in expected_support_fields:
            assert supports[field] is True, f"Support field '{field}' should be True"

    def test_standard_model_response_structure(self):
        """Test that StandardModelResponse has correct structure"""
        # Create sample data list
        model_items = []

        response = StandardModelResponse(data=model_items)
        response_dict = response.model_dump()

        # Check top-level structure
        expected_top_fields = {"object", "data"}
        actual_top_fields = set(response_dict.keys())

        assert actual_top_fields == expected_top_fields, (
            f"Top-level fields mismatch. Expected: {expected_top_fields}, Got: {actual_top_fields}"
        )

        assert response_dict["object"] == "list"
        assert isinstance(response_dict["data"], list)
