from typing import Literal, TypeAlias

from pydantic import BaseModel, Field


class BaseFeature(BaseModel):
    name: str = Field(description="The name of the feature, will be used if the feature is created")
    tag_line: str | None = Field(
        default=None,
        description="A tag line for the feature, displayed in the feature suggestion UI",
    )
    description: str = Field(description="A description of the feature, displayed in the UI")
    specifications: str | None = Field(
        description="The specifications of the feature, used to generate the feature input and output schema, for internal use only, NOT displayed in the UI. To be provided for 'static' feature suggestions only, null otherwise",
    )

    @property
    def display_str(self) -> str:
        return f"""*{self.name}*

{self.description}"""


class FeatureWithImage(BaseFeature):
    image_url: str


class DirectToAgentBuilderFeature(FeatureWithImage):
    # Special case where we do not want to generate a schema via "/preview" but we want to open the agent builder with a specific message instead
    open_agent_builder_with_message: str | None = Field(
        default=None,
        description="The message to open the agent builder with, if the feature is selected",
    )


tag_kind: TypeAlias = Literal["static", "company_specific"]


class FeatureTag(BaseModel):
    name: str
    features: list[BaseFeature]
    kind: tag_kind


class FeatureSection(BaseModel):
    name: str
    tags: list[FeatureTag]


# TODO: Feed the mapping with real examples from Anya.
