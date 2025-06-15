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
                    if k not in {"supports_structured_output", "supports_json_mode", "support_system_messages"}
                },
                pricing=cls.Pricing(
                    input_token_usd=provider_data.text_price.prompt_cost_per_token,
                    output_token_usd=provider_data.text_price.completion_cost_per_token,
                ),
                release_date=model.release_date,
            )

    data: list[ModelItem]
