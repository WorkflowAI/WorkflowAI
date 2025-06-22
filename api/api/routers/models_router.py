import datetime
from collections.abc import Iterator
from typing import Literal, Self

from fastapi import APIRouter
from pydantic import BaseModel, Field

from core.domain.models import Model as ModelID
from core.domain.models.model_data import FinalModelData, LatestModel, MaxTokensData
from core.domain.models.model_data_supports import ModelDataSupports
from core.domain.models.model_datas_mapping import MODEL_DATAS
from core.domain.models.model_provider_data import ModelProviderData

router = APIRouter(prefix="/v1/models")


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

    @classmethod
    def from_domain(cls, model: ModelDataSupports) -> Self:
        return cls(
            input=SupportsModality(
                image=model.supports_input_image,
                audio=model.supports_input_audio,
                pdf=model.supports_input_pdf,
                # TODO: we need to overhaul the model data to
                # add a proper support field for input test
                # See https://linear.app/workflowai/issue/WOR-4926/sanitize-model-supports-to-include-temperature-and-other-parameters
                text=not model.supports_audio_only,
            ),
            output=SupportsModality(
                image=model.supports_output_image,
                audio=False,
                pdf=False,
                text=model.supports_output_text,
            ),
            parallel_tool_calls=model.supports_parallel_tool_calls,
            tools=model.supports_tool_calling,
            # TODO: see https://linear.app/workflowai/issue/WOR-4926/sanitize-model-supports-to-include-temperature-and-other-parameters
            top_p=True,
            temperature=True,
        )


class ModelPricing(BaseModel):
    """Pricing information for model usage in USD per token."""

    input_token_usd: float = Field(
        description="Cost per input token in USD.",
    )
    output_token_usd: float = Field(
        description="Cost per output token in USD.",
    )

    @classmethod
    def from_domain(cls, model: ModelProviderData) -> Self:
        return cls(
            input_token_usd=model.text_price.prompt_cost_per_token,
            output_token_usd=model.text_price.completion_cost_per_token,
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

    @classmethod
    def from_domain(cls, model: MaxTokensData) -> Self:
        return cls(
            max_tokens=model.max_tokens,
            max_output_tokens=model.max_output_tokens or model.max_tokens,
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

    @classmethod
    def from_domain(cls, id: str, model: FinalModelData) -> Self:
        provider_data = model.providers[0][1]

        # Determine reasoning capabilities based on reasoning_level
        reasoning = None
        if model.reasoning_level and model.reasoning_level != "none":
            # Calculate reasoning budgets based on max output tokens
            max_output = model.max_tokens_data.max_output_tokens or model.max_tokens_data.max_tokens
            reasoning = ModelReasoning(
                can_be_disabled=True,  # Most reasoning models can disable reasoning
                low_effort_reasoning_budget=int(max_output * 0.2),  # 20% of max output tokens
                medium_effort_reasoning_budget=int(max_output * 0.5),  # 50% of max output tokens
                high_effort_reasoning_budget=int(max_output * 0.8),  # 80% of max output tokens
            )

        return cls(
            id=id,
            created=int(datetime.datetime.combine(model.release_date, datetime.time(0, 0)).timestamp()),
            owned_by="WorkflowAI",
            display_name=model.display_name,
            icon_url=model.icon_url,
            supports=ModelSupports.from_domain(model),
            pricing=ModelPricing.from_domain(provider_data),
            release_date=model.release_date,
            reasoning=reasoning,
            context_window=ModelContextWindow.from_domain(model.max_tokens_data),
        )


class ModelResponse(BaseModel):
    object: Literal["list"] = "list"

    data: list[Model]


def _model_data_iterator() -> Iterator[Model]:
    for model in ModelID:
        data = MODEL_DATAS[model]
        if isinstance(data, LatestModel):
            yield Model.from_domain(model.value, MODEL_DATAS[data.model])  # pyright: ignore [reportArgumentType]
        elif isinstance(data, FinalModelData):
            yield Model.from_domain(model.value, data)
        else:
            # Skipping deprecated models
            continue


@router.get("")
async def list_models(reasoning: bool | None = None) -> ModelResponse:
    """List available models.

    Args:
        reasoning: If True, only return models that support reasoning.
                  If False, only return models that don't support reasoning.
                  If None, return all models.
    """
    models = list(_model_data_iterator())

    if reasoning is not None:
        if reasoning:
            # Filter for models that support reasoning
            models = [model for model in models if model.reasoning is not None]
        else:
            # Filter for models that don't support reasoning
            models = [model for model in models if model.reasoning is None]

    return ModelResponse(data=models)


# Because the run and api containers are deployed at different times,
# the run container must be the source of truth for available models, otherwise
# the API might believe that some models are available when they are not.
@router.get("/ids", include_in_schema=False)
async def list_model_ids() -> list[str]:
    # No need to filter anything here as the raw models will not be exposed
    # The api container will filter the models based on the task schema
    return list(ModelID)
