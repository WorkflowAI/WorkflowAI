"""
Pydantic models for the /v1/models endpoint.

This module defines the standardized response format for the OpenAI-compatible
/v1/models API endpoint.
"""

import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from core.domain.models.model_data import FinalModelData
from core.domain.models.model_data_supports import ModelDataSupports


class ModelPricing(BaseModel):
    """Pricing information for a model."""

    input_token_usd: float = Field(description="Cost per input token in USD")
    output_token_usd: float = Field(description="Cost per output token in USD")


class ModelCapabilities(BaseModel):
    """Model capabilities and supported features."""

    # Core capabilities
    json_mode: bool = Field(description="Whether the model supports JSON mode")
    structured_output: bool = Field(description="Whether the model supports structured output")
    tool_calling: bool = Field(description="Whether the model supports tool calling")
    parallel_tool_calls: bool = Field(description="Whether the model supports parallel tool calls")

    # Input modalities
    input_text: bool = Field(default=True, description="Whether the model supports text input")
    input_image: bool = Field(description="Whether the model supports image input")
    input_pdf: bool = Field(description="Whether the model supports PDF input")
    input_audio: bool = Field(description="Whether the model supports audio input")

    # Output modalities
    output_text: bool = Field(default=True, description="Whether the model supports text output")
    output_image: bool = Field(description="Whether the model supports image output")

    # Other features
    system_messages: bool = Field(description="Whether the model supports system messages")
    input_schema: bool = Field(description="Whether the model supports input schema")
    audio_only: bool = Field(description="Whether the model supports audio-only mode")

    @classmethod
    def from_model_data_supports(cls, supports: ModelDataSupports) -> "ModelCapabilities":
        """Create ModelCapabilities from ModelDataSupports."""
        return cls(
            json_mode=supports.supports_json_mode,
            structured_output=supports.supports_structured_output,
            tool_calling=supports.supports_tool_calling,
            parallel_tool_calls=supports.supports_parallel_tool_calls,
            input_text=True,  # All models support text input
            input_image=supports.supports_input_image,
            input_pdf=supports.supports_input_pdf,
            input_audio=supports.supports_input_audio,
            output_text=supports.supports_output_text,
            output_image=supports.supports_output_image,
            system_messages=supports.support_system_messages,
            input_schema=supports.support_input_schema,
            audio_only=supports.supports_audio_only,
        )


class ModelItem(BaseModel):
    """Individual model item in the /v1/models response."""

    id: str = Field(description="The model identifier")
    object: Literal["model"] = Field(default="model", description="The object type")
    created: int = Field(description="Unix timestamp of when the model was created")
    owned_by: str = Field(description="The organization that owns the model")
    display_name: str = Field(description="Human-readable display name for the model")
    icon_url: str = Field(description="URL to the model's icon")
    release_date: datetime.date = Field(description="The date the model was released")

    # Capabilities and pricing
    capabilities: ModelCapabilities = Field(description="Model capabilities and supported features")
    pricing: ModelPricing = Field(description="Pricing information for the model")

    # Legacy support field for backward compatibility
    supports: dict[str, Any] = Field(description="Legacy supports field for backward compatibility")

    @classmethod
    def from_model_data(cls, id: str, model: FinalModelData) -> "ModelItem":
        """Create a ModelItem from FinalModelData."""
        provider_data = model.providers[0][1]
        capabilities = ModelCapabilities.from_model_data_supports(model)

        # Create legacy supports dict for backward compatibility
        supports = {
            k.removeprefix("supports_"): v
            for k, v in model.model_dump(
                mode="json",
                include=set(ModelDataSupports.model_fields.keys()),
            ).items()
        }

        return cls(
            id=id,
            created=int(datetime.datetime.combine(model.release_date, datetime.time(0, 0)).timestamp()),
            owned_by=model.provider_name,
            display_name=model.display_name,
            icon_url=model.icon_url,
            release_date=model.release_date,
            capabilities=capabilities,
            pricing=ModelPricing(
                input_token_usd=provider_data.text_price.prompt_cost_per_token,
                output_token_usd=provider_data.text_price.completion_cost_per_token,
            ),
            supports=supports,
        )


class V1ModelsResponse(BaseModel):
    """Response format for the /v1/models endpoint."""

    object: Literal["list"] = Field(default="list", description="The object type")
    data: list[ModelItem] = Field(description="List of available models")

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "object": "list",
                "data": [
                    {
                        "id": "gpt-4o-latest",
                        "object": "model",
                        "created": 1677649963,
                        "owned_by": "openai",
                        "display_name": "GPT-4o (latest)",
                        "icon_url": "https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
                        "release_date": "2024-05-13",
                        "capabilities": {
                            "json_mode": True,
                            "structured_output": True,
                            "tool_calling": True,
                            "parallel_tool_calls": True,
                            "input_text": True,
                            "input_image": True,
                            "input_pdf": False,
                            "input_audio": False,
                            "output_text": True,
                            "output_image": False,
                            "system_messages": True,
                            "input_schema": True,
                            "audio_only": False,
                        },
                        "pricing": {
                            "input_token_usd": 0.0000025,
                            "output_token_usd": 0.00001,
                        },
                        "supports": {
                            "json_mode": True,
                            "structured_output": True,
                            "tool_calling": True,
                            "parallel_tool_calls": True,
                        },
                    },
                ],
            },
        }
