from datetime import date

from pydantic import BaseModel, Field

from api.services import models
from core.domain.models.providers import Provider


class ModelMetadata(BaseModel):
    provider_name: str = Field(description="The name of the provider for the model")
    price_per_input_token_usd: float = Field(description="The price per input token in USD")
    price_per_output_token_usd: float = Field(description="The price per output token in USD")
    release_date: date = Field(description="The date the model was released")
    context_window_tokens: int = Field(description="The context window of the model in tokens")
    quality_index: int = Field(description="The quality index of the model")

    @classmethod
    def from_service(cls, model: "models.ModelForTask"):
        return cls(
            provider_name=model.provider_name,
            price_per_input_token_usd=model.price_per_input_token_usd,
            price_per_output_token_usd=model.price_per_output_token_usd,
            release_date=model.release_date,
            context_window_tokens=model.context_window_tokens,
            quality_index=model.quality_index,
        )


class ModelResponse(BaseModel):
    id: str
    name: str
    icon_url: str = Field(description="The url of the icon to display for the model")
    modes: list[str] = Field(description="The modes supported by the model")

    is_latest: bool = Field(
        description="Whether the model is the latest in its family. In other words"
        "by default, only models with is_latest=True should be displayed.",
    )

    # The model list enum will determine the column/priority order
    is_default: bool = Field(
        description="If true, the model will be used as default model.",
        default=False,
    )

    providers: list[Provider] = Field(description="The providers that support this model")

    metadata: ModelMetadata = Field(description="The metadata of the model")

    @classmethod
    def from_service(cls, model: "models.ModelForTask"):
        return cls(
            id=model.id,
            name=model.name,
            icon_url=model.icon_url,
            modes=model.modes,
            is_latest=model.is_latest,
            metadata=ModelMetadata.from_service(model),
            is_default=model.is_default,
            providers=model.providers,
        )
