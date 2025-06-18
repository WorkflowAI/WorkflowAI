import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from core.domain.models.model_data import FinalModelData
from core.domain.models.model_data_supports import ModelDataSupports


class SupportsModality(BaseModel):
    """Defines what modalities (input/output types) are supported by a model."""

    image: bool
    audio: bool
    pdf: bool
    text: bool


class ModelSupports(BaseModel):
    """Data about what the model supports on the WorkflowAI platform.

    Note that a single model might have different capabilities based on the provider.
    """

    input: SupportsModality = Field(
        description="Whether the model supports input of the given modality.",
    )
    output: SupportsModality = Field(
        description="Whether the model supports output of the given modality. "
        "If false, the model will not return any output.",
    )
    parallel_tool_calls: bool = Field(
        description="Whether the model supports parallel tool calls, i.e. if the model can return multiple tool calls "
        "in a single inference. If the model does not support parallel tool calls, the parallel_tool_calls parameter "
        "will be ignored.",
    )
    tools: bool = Field(
        description="Whether the model supports tools. If false, the model will not support tool calling. "
        "Requests containing tools will be rejected.",
    )
    top_p: bool = Field(
        description="Whether the model supports top_p. If false, the top_p parameter will be ignored.",
    )
    temperature: bool = Field(
        description="Whether the model supports temperature. If false, the temperature parameter will be ignored.",
    )


class ModelPricing(BaseModel):
    """Pricing information for model usage in USD per token."""

    input_token_usd: float = Field(
        description="Cost per input token in USD.",
    )
    output_token_usd: float = Field(
        description="Cost per output token in USD.",
    )


class ModelReasoning(BaseModel):
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


class ModelContextWindow(BaseModel):
    """Context window and output token limits for the model."""

    max_tokens: int = Field(
        description="The maximum number of tokens that can be used for the context window for the model. "
        "Input and output combined.",
    )
    max_output_tokens: int = Field(
        description="The maximum number of tokens that the model can output.",
    )


class Model(BaseModel):
    """Complete model information including capabilities, pricing, and metadata."""

    id: str = Field(
        description="Unique identifier for the model, which should be used in the `model` parameter of the OpenAI API.",
    )
    object: Literal["model"] = "model"
    created: int = Field(
        description="Unix timestamp of when the model was created.",
    )
    # Field is not really interesting for us but is required to be compatible with the OpenAI API.
    owned_by: Literal["WorkflowAI"] = "WorkflowAI"
    display_name: str = Field(
        description="Human-readable name for the model.",
    )
    icon_url: str = Field(
        description="URL to the model's icon image.",
    )

    supports: ModelSupports = Field(
        description="Detailed information about what the model supports.",
    )

    pricing: ModelPricing = Field(
        description="Pricing information for the model.",
    )

    release_date: datetime.date = Field(
        description="The date the model was released on the WorkflowAI platform.",
    )

    reasoning: ModelReasoning | None = Field(
        default=None,
        description="Reasoning configuration for the model. None if the model does not support reasoning.",
    )

    context_window: ModelContextWindow = Field(
        description="Context window and output token limits for the model.",
    )


# TODO: use Model above instead of ModelItem
class StandardModelResponse(BaseModel):
    """A model response compatible with the OpenAI API"""

    object: Literal["list"] = "list"

    class ModelItem(BaseModel):
        id: str
        object: Literal["model"] = "model"
        created: int
        owned_by: str
        display_name: str
        icon_url: str
        supports: dict[str, Any]

        class Pricing(BaseModel):
            input_token_usd: float
            output_token_usd: float

        pricing: Pricing

        release_date: datetime.date

        @classmethod
        def from_model_data(cls, id: str, model: FinalModelData):
            provider_data = model.providers[0][1]
            return cls(
                id=id,
                created=int(datetime.datetime.combine(model.release_date, datetime.time(0, 0)).timestamp()),
                owned_by=model.provider_name,
                display_name=model.display_name,
                icon_url=model.icon_url,
                supports={
                    k.removeprefix("supports_"): v
                    for k, v in model.model_dump(
                        mode="json",
                        include=set(ModelDataSupports.model_fields.keys()),
                    ).items()
                },
                pricing=cls.Pricing(
                    input_token_usd=provider_data.text_price.prompt_cost_per_token,
                    output_token_usd=provider_data.text_price.completion_cost_per_token,
                ),
                release_date=model.release_date,
            )

    data: list[ModelItem]
