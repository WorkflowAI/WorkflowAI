import datetime
from typing import Any, Literal

from pydantic import BaseModel

from core.domain.models.model_data import FinalModelData


class StandardModelResponse(BaseModel):
    """A model response compatible with the OpenAI API"""

    object: Literal["list"] = "list"

    class ModelItem(BaseModel):
        id: str
        object: Literal["model"] = "model"
        created: int
        display_name: str
        icon_url: str
        supports: dict[str, Any]

        @classmethod
        def from_model_data(cls, id: str, model: FinalModelData):
            # Whitelist of support fields to include in the API response
            included_support_fields = {
                "supports_input_image",
                "supports_input_pdf",
                "supports_input_audio",
                "supports_output_image",
                "supports_output_text",
                "supports_audio_only",
                "supports_tool_calling",
                "supports_parallel_tool_calls",
            }

            return cls(
                id=id,
                created=int(datetime.datetime.combine(model.release_date, datetime.time(0, 0)).timestamp()),
                display_name=model.display_name,
                icon_url=model.icon_url,
                supports={
                    k.removeprefix("supports_"): v
                    for k, v in model.model_dump(
                        mode="json",
                        include=included_support_fields,
                    ).items()
                },
            )

    data: list[ModelItem]
