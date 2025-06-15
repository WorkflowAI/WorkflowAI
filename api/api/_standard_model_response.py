import datetime
from typing import Any, Literal

from pydantic import BaseModel

from core.domain.models.model_data import FinalModelData
from core.domain.models.model_data_supports import ModelDataSupports


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
        usage_guidelines: str | None = None

        class Pricing(BaseModel):
            input_token_usd: float
            output_token_usd: float

        pricing: Pricing

        release_date: datetime.date

        @classmethod
        def from_model_data(cls, id: str, model: FinalModelData):
            provider_data = model.providers[0][1]

            # Generate usage guidelines based on model characteristics
            usage_guidelines = None
            if "preview" in id.lower() or "experimental" in id.lower() or "exp" in id.lower():
                usage_guidelines = "Preview model with lower rate limits - not recommended for production use"
            elif "audio" in id.lower() and "preview" in id.lower():
                usage_guidelines = "Audio preview model - use for audio processing tasks but not recommended for production due to rate limits"
            elif model.quality_data and hasattr(model.quality_data, "index") and model.quality_data.index < 300:
                usage_guidelines = "Lower quality model - suitable for simple tasks where cost is a priority"
            elif hasattr(model, "reasoning_level") and model.reasoning_level == "high":
                usage_guidelines = (
                    "High reasoning model - best for complex analytical tasks but slower and more expensive"
                )

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
                usage_guidelines=usage_guidelines,
                pricing=cls.Pricing(
                    input_token_usd=provider_data.text_price.prompt_cost_per_token,
                    output_token_usd=provider_data.text_price.completion_cost_per_token,
                ),
                release_date=model.release_date,
            )

    data: list[ModelItem]
