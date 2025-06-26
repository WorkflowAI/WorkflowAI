from pydantic import BaseModel, Field, model_validator

from core.domain.models import Model
from core.domain.models.model_data import DeprecatedModel
from core.domain.models.model_data_mapping import MODEL_DATAS
from core.domain.task_group_properties import TaskGroupProperties


def _model_name_and_icon(model: str):
    try:
        model_data = MODEL_DATAS[Model(model)]
        if isinstance(model_data, DeprecatedModel):
            return None, None
    except (KeyError, ValueError):
        return None, None
    return model_data.display_name, model_data.icon_url


# A subset of TaskGroupProperties
class ShortVersionProperties(BaseModel):
    model: str | None = Field(default=None, description="The LLM model used for the run")
    model_name: str | None = Field(default=None, description="The name of the model")
    model_icon: str | None = Field(default=None, description="The icon of the model")
    provider: str | None = Field(default=None, description="The LLM provider used for the run")
    temperature: float | None = Field(default=None, description="The temperature for generation")

    @classmethod
    def from_domain(cls, properties: TaskGroupProperties):
        return cls(
            model=properties.model,
            provider=properties.provider,
            temperature=properties.temperature,
        )

    @model_validator(mode="after")
    def set_model_name_and_icon(self):
        if self.model and (not self.model_name or not self.model_icon):
            self.model_name, self.model_icon = _model_name_and_icon(self.model)
        return self


class FullVersionProperties(TaskGroupProperties):
    model_name: str | None = Field(default=None, description="The name of the model")
    model_icon: str | None = Field(default=None, description="The icon of the model")

    @classmethod
    def from_domain(cls, properties: TaskGroupProperties):
        return cls(**properties.model_dump())

    @model_validator(mode="after")
    def set_model_name_and_icon(self):
        if self.model and (not self.model_name or not self.model_icon):
            self.model_name, self.model_icon = _model_name_and_icon(self.model)
        return self
