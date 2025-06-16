"""
Unit tests for the V1ModelsResponse schema.
"""

import datetime
from unittest.mock import Mock

from api.schemas.v1_models import ModelCapabilities, ModelItem, ModelPricing, V1ModelsResponse
from core.domain.models.model_data import FinalModelData
from core.domain.models.model_data_supports import ModelDataSupports
from core.domain.models.model_provider_data import ModelProviderData, TextPricePerToken


class TestModelCapabilities:
    """Test the ModelCapabilities class."""

    def test_from_model_data_supports(self):
        """Test creation from ModelDataSupports."""
        supports = ModelDataSupports(
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_output_image=False,
            supports_output_text=True,
            supports_structured_output=True,
            supports_tool_calling=True,
            supports_parallel_tool_calls=True,
            support_system_messages=True,
            support_input_schema=True,
            supports_audio_only=False,
        )

        capabilities = ModelCapabilities.from_model_data_supports(supports)

        assert capabilities.json_mode is True
        assert capabilities.structured_output is True
        assert capabilities.tool_calling is True
        assert capabilities.parallel_tool_calls is True
        assert capabilities.input_text is True
        assert capabilities.input_image is True
        assert capabilities.input_pdf is False
        assert capabilities.input_audio is False
        assert capabilities.output_text is True
        assert capabilities.output_image is False
        assert capabilities.system_messages is True
        assert capabilities.input_schema is True
        assert capabilities.audio_only is False


class TestModelPricing:
    """Test the ModelPricing class."""

    def test_basic_creation(self):
        """Test basic pricing model creation."""
        pricing = ModelPricing(
            input_token_usd=0.0000025,
            output_token_usd=0.00001,
        )

        assert pricing.input_token_usd == 0.0000025
        assert pricing.output_token_usd == 0.00001


class TestModelItem:
    """Test the ModelItem class."""

    def test_from_model_data(self):
        """Test creation from FinalModelData."""
        # Create mock provider data
        provider_data = Mock(spec=ModelProviderData)
        provider_data.text_price = Mock(spec=TextPricePerToken)
        provider_data.text_price.prompt_cost_per_token = 0.0000025
        provider_data.text_price.completion_cost_per_token = 0.00001

        # Create mock model data
        model_data = Mock(spec=FinalModelData)
        model_data.provider_name = "openai"
        model_data.display_name = "GPT-4o (latest)"
        model_data.icon_url = "https://workflowai.blob.core.windows.net/workflowai-public/openai.svg"
        model_data.release_date = datetime.date(2024, 5, 13)
        model_data.providers = [("openai", provider_data)]

        # Mock the model_dump method
        model_data.model_dump.return_value = {
            "supports_json_mode": True,
            "supports_structured_output": True,
            "supports_tool_calling": True,
            "supports_parallel_tool_calls": True,
            "supports_input_image": True,
            "supports_input_pdf": False,
            "supports_input_audio": False,
            "supports_output_text": True,
            "supports_output_image": False,
            "support_system_messages": True,
            "support_input_schema": True,
            "supports_audio_only": False,
        }

        # Set up the supports attributes directly on the model
        model_data.supports_json_mode = True
        model_data.supports_structured_output = True
        model_data.supports_tool_calling = True
        model_data.supports_parallel_tool_calls = True
        model_data.supports_input_image = True
        model_data.supports_input_pdf = False
        model_data.supports_input_audio = False
        model_data.supports_output_text = True
        model_data.supports_output_image = False
        model_data.support_system_messages = True
        model_data.support_input_schema = True
        model_data.supports_audio_only = False

        model_item = ModelItem.from_model_data("gpt-4o-latest", model_data)

        assert model_item.id == "gpt-4o-latest"
        assert model_item.object == "model"
        assert model_item.owned_by == "openai"
        assert model_item.display_name == "GPT-4o (latest)"
        assert model_item.icon_url == "https://workflowai.blob.core.windows.net/workflowai-public/openai.svg"
        assert model_item.release_date == datetime.date(2024, 5, 13)

        # Test pricing
        assert model_item.pricing.input_token_usd == 0.0000025
        assert model_item.pricing.output_token_usd == 0.00001

        # Test capabilities
        assert model_item.capabilities.json_mode is True
        assert model_item.capabilities.tool_calling is True
        assert model_item.capabilities.input_image is True

        # Test legacy supports field
        assert "json_mode" in model_item.supports
        assert "tool_calling" in model_item.supports
        assert model_item.supports["json_mode"] is True
        assert model_item.supports["tool_calling"] is True


class TestV1ModelsResponse:
    """Test the V1ModelsResponse class."""

    def test_basic_creation(self):
        """Test basic response creation."""
        model_item = ModelItem(
            id="test-model",
            created=1677649963,
            owned_by="test-provider",
            display_name="Test Model",
            icon_url="https://example.com/icon.svg",
            release_date=datetime.date(2024, 1, 1),
            capabilities=ModelCapabilities(
                json_mode=True,
                structured_output=True,
                tool_calling=True,
                parallel_tool_calls=True,
                input_image=True,
                input_pdf=False,
                input_audio=False,
                output_image=False,
                system_messages=True,
                input_schema=True,
                audio_only=False,
            ),
            pricing=ModelPricing(
                input_token_usd=0.001,
                output_token_usd=0.002,
            ),
            supports={"json_mode": True, "tool_calling": True},
        )

        response = V1ModelsResponse(data=[model_item])

        assert response.object == "list"
        assert len(response.data) == 1
        assert response.data[0].id == "test-model"

    def test_serialization(self):
        """Test that the response can be serialized to JSON properly."""
        model_item = ModelItem(
            id="test-model",
            created=1677649963,
            owned_by="test-provider",
            display_name="Test Model",
            icon_url="https://example.com/icon.svg",
            release_date=datetime.date(2024, 1, 1),
            capabilities=ModelCapabilities(
                json_mode=True,
                structured_output=True,
                tool_calling=True,
                parallel_tool_calls=True,
                input_image=True,
                input_pdf=False,
                input_audio=False,
                output_image=False,
                system_messages=True,
                input_schema=True,
                audio_only=False,
            ),
            pricing=ModelPricing(
                input_token_usd=0.001,
                output_token_usd=0.002,
            ),
            supports={"json_mode": True, "tool_calling": True},
        )

        response = V1ModelsResponse(data=[model_item])
        serialized = response.model_dump()

        assert serialized["object"] == "list"
        assert len(serialized["data"]) == 1

        model_data = serialized["data"][0]
        assert model_data["id"] == "test-model"
        assert model_data["object"] == "model"
        assert model_data["owned_by"] == "test-provider"
        assert model_data["display_name"] == "Test Model"
        assert model_data["release_date"] == "2024-01-01"

        # Test capabilities structure
        assert "capabilities" in model_data
        capabilities = model_data["capabilities"]
        assert capabilities["json_mode"] is True
        assert capabilities["tool_calling"] is True
        assert capabilities["input_image"] is True

        # Test pricing structure
        assert "pricing" in model_data
        pricing = model_data["pricing"]
        assert pricing["input_token_usd"] == 0.001
        assert pricing["output_token_usd"] == 0.002

        # Test legacy supports field
        assert "supports" in model_data
        supports = model_data["supports"]
        assert supports["json_mode"] is True
        assert supports["tool_calling"] is True
