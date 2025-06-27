import datetime
from datetime import date
from typing import TypeVar

from pydantic import BaseModel, Field

from core.domain.models import Model
from core.domain.models._sourced_base_model import SourcedBaseModel
from core.domain.models.model_data_supports import ModelDataSupports


# TODO: we should sanitize the threshold concept
class ThresholdedTextPricePerToken(BaseModel):
    # Only used for Gemini model on VertexAI for now
    threshold: int = Field(description="The threshold from which the cost per token changes")
    prompt_cost_per_token_over_threshold: float
    completion_cost_per_token_over_threshold: float


class ThresholdedAudioPricePerSecond(BaseModel):
    threshold: int = Field(description="The threshold from which the cost per second changes")
    cost_per_second_over_threshold: float


# TODO: name is not super accurate. It should just be PricePerToken
# Since a token count can represent a text token, an image token, an audio token, etc.
class TextPricePerToken(SourcedBaseModel):
    prompt_cost_per_token: float
    prompt_image_cost_per_token: float | None = None
    prompt_cached_tokens_discount: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="The discount between 0 and 1 on the cost per token for cached tokens in the prompt.",
    )
    completion_cost_per_token: float
    completion_image_cost_per_token: float | None = None

    thresholded_prices: list[ThresholdedTextPricePerToken] | None = None


class AudioPricePerToken(BaseModel):
    audio_input_cost_per_token: float
    # TODO: Add audio completion/output cost per token


class AudioPricePerSecond(BaseModel):
    cost_per_second: float

    thresholded_prices: list[ThresholdedAudioPricePerSecond] | None = None


class ThresholdedImageFixedPrice(BaseModel):
    threshold: int = Field(description="The threshold from which the cost per image changes")
    cost_per_image_over_threshold: float


class ImageFixedPrice(BaseModel):
    cost_per_image: float

    thresholded_prices: list[ThresholdedImageFixedPrice] | None = None


# --- Lifecyle-related data models --- #


class LifecycleData(SourcedBaseModel):
    release_date: date | None = Field(default=None, description="The date at which the model was released.")
    sunset_date: date = Field(description="The date at which the model will be decomissioned, if known.")
    post_sunset_replacement_model: Model | None = Field(
        default=None,
        description="The model that will replace this model after sunset.",
    )

    def is_sunset(self, now: datetime.date) -> bool:
        return self.sunset_date <= now


class ModelIsMissingReplacementModel(Exception):
    pass


_T = TypeVar("_T", bound=ModelDataSupports)


class ModelDataSupportsOverride(BaseModel):
    supports_json_mode: bool | None = None
    supports_input_image: bool | None = None
    supports_input_pdf: bool | None = None
    supports_input_audio: bool | None = None
    supports_audio_only: bool | None = None
    supports_system_messages: bool | None = None
    supports_structured_output: bool | None = None
    supports_input_schema: bool | None = None
    supports_output_image: bool | None = None
    supports_output_text: bool | None = None
    supports_tool_calling: bool | None = None
    supports_parallel_tool_calls: bool | None = None

    def override(self, data: _T) -> _T:
        return data.model_copy(update=self.model_dump(exclude_none=True))


class ModelProviderData(BaseModel):
    text_price: TextPricePerToken

    image_price: ImageFixedPrice | None = Field(
        default=None,
        description="The cost per image for the model, if applicable.",
    )
    image_output_price: ImageFixedPrice | None = Field(
        default=None,
        description="The cost per image output for the model, if applicable.",
    )

    audio_price: AudioPricePerToken | AudioPricePerSecond | None = Field(
        default=None,
        description="The cost per audio for the model, if applicable.",
    )

    lifecycle_data: LifecycleData | None = Field(
        default=None,
        description="Any lifecycle data for the model (release date, sunset date, replacement model, etc.)",
    )

    supports_override: ModelDataSupportsOverride | None = None

    def is_available(self, now: datetime.date) -> bool:
        return not self.lifecycle_data or not self.lifecycle_data.is_sunset(now)

    def replacement_model(self, now: datetime.date) -> Model | None:
        if self.is_available(now):
            return None

        if not self.lifecycle_data or not self.lifecycle_data.post_sunset_replacement_model:
            raise ModelIsMissingReplacementModel("No replacement model found for model")

        return self.lifecycle_data.post_sunset_replacement_model

    def override(self, data: _T) -> _T:
        if not self.supports_override:
            return data

        return self.supports_override.override(data)
