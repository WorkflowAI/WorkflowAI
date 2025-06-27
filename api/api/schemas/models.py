from datetime import date

from pydantic import BaseModel, Field

from api.services import models
from core.domain.models.model_data import ModelReasoningBudget
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

    # TODO: use same models as models_router
    class Reasoning(BaseModel):
        """Configuration for reasoning capabilities of the model.

        A mapping from a reasoning effort (disabled, low, medium, high) to a
        reasoning token budget. The reasoning token budget represents the maximum number
        of tokens that can be used for reasoning.
        """

        can_be_disabled: bool = Field(
            description="Whether the reasoning can be disabled for the model.",
        )
        low_effort_reasoning_budget: int = Field(
            description="The maximum number of tokens that can be used for reasoning at low effort for the model.",
        )
        medium_effort_reasoning_budget: int = Field(
            description="The maximum number of tokens that can be used for reasoning at medium effort for the model.",
        )
        high_effort_reasoning_budget: int = Field(
            description="The maximum number of tokens that can be used for reasoning at high effort for the model.",
        )

        @classmethod
        def from_domain(cls, model: ModelReasoningBudget):
            return cls(
                can_be_disabled=model.disabled is not None,
                low_effort_reasoning_budget=model.low or 0,
                medium_effort_reasoning_budget=model.medium or 0,
                high_effort_reasoning_budget=model.high or 0,
            )

    reasoning: Reasoning | None

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
            reasoning=cls.Reasoning.from_domain(model.model_data.reasoning) if model.model_data.reasoning else None,
        )
