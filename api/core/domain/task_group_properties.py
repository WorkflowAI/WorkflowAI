import logging
from typing import Any, Literal, Optional, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.domain.fields.image_options import ImageOptions
from core.domain.message import Message
from core.domain.reasoning_effort import ReasoningEffort
from core.domain.tool import Tool
from core.tools import ToolKind
from core.utils.hash import compute_model_hash, compute_obj_hash
from core.utils.iter_utils import safe_map
from core.utils.tags import compute_tags
from core.utils.templates import TemplateManager


class FewShotExample(BaseModel):
    task_input: dict[str, Any]
    task_output: dict[str, Any]


class FewShotConfiguration(BaseModel):
    count: int | None = Field(
        default=None,
        description="The number of few-shot examples to use for the task",
    )

    selection: Literal["latest", "manual"] | str | None = Field(
        default=None,
        description="The selection method to use for few-shot examples",
    )

    examples: list["FewShotExample"] | None = Field(
        default=None,
        description="The few-shot examples used for the task. If provided, count and selection are ignored. "
        "If not provided, count and selection are used to select examples and the examples list will be set "
        "in the final group.",
    )

    def model_hash(self) -> str:
        return compute_model_hash(self, exclude_none=True)

    def compute_tags(self) -> list[str]:
        return compute_tags(self.model_dump(exclude_none=True))


_SIMILARITY_HASH_FIELDS = {
    "instructions",
    "temperature",
    "task_variant_id",
    "messages",
    "top_p",
    "frequency_penalty",
    "presence_penalty",
}
"""The portion of version properties that are used to compute the similarity hash,
meaning that any change in any of these fields will cause a new major version to be created."""


class ToolChoiceFunction(BaseModel):
    name: str


ToolChoice: TypeAlias = Literal["auto", "none", "required"] | ToolChoiceFunction


class TaskGroupProperties(BaseModel):
    """Properties that described a way a task run was executed.
    Although some keys are provided as an example, any key:value are accepted"""

    # Allow extra fields to support custom options
    model_config = ConfigDict(extra="allow")

    model: Optional[str] = Field(default=None, description="The LLM model used for the run")
    provider: Optional[str] = Field(default=None, description="The LLM provider used for the run")
    temperature: Optional[float] = Field(default=None, description="The temperature for generation")
    instructions: Optional[str] = Field(
        default=None,
        description="The instructions passed to the runner in order to generate the prompt.",
    )
    max_tokens: Optional[int] = Field(
        default=None,
        description="The maximum tokens to generate in the prompt",
    )

    runner_name: Optional[str] = Field(default=None, description="The name of the runner used")

    runner_version: Optional[str] = Field(default=None, description="The version of the runner used")

    few_shot: "FewShotConfiguration | None" = Field(default=None, description="Few shot configuration")

    template_name: Optional[str] = Field(default=None, description="The template name used for the task")

    is_chain_of_thought_enabled: bool | None = Field(
        default=None,
        description="Whether to use chain of thought prompting for the task",
    )
    # A set would have been nicer but isn't JSON serializable for storage and would require custom code.
    # Pass a full tool to enable external tools

    # We use a str fallback to let the runner decide how to handle the tool
    enabled_tools: list[ToolKind | Tool] | None = None

    is_structured_generation_enabled: bool | None = Field(
        default=None,
        description="Whether to use structured generation for the task",
    )

    has_templated_instructions: bool | None = None

    image_options: ImageOptions | None = None

    tool_choice: ToolChoice | None = None

    top_p: float | None = None

    presence_penalty: float | None = None

    frequency_penalty: float | None = None

    parallel_tool_calls: bool | None = Field(
        default=None,
        description="Whether to allow the model to output mutliple tool calls",
    )

    messages: list[Message] | None = None

    reasoning_effort: ReasoningEffort | None = None

    reasoning_budget: int | None = None

    def model_hash(self) -> str:
        # Excluding fields are compiled from other fields
        return compute_model_hash(self, exclude_none=True, exclude={"has_templated_instructions"})

    def compute_tags(self) -> list[str]:
        dumped = self.model_dump(exclude_none=True, exclude={"few_shot", "has_templated_instructions"})
        if self.few_shot:
            if self.few_shot.count:
                dumped["few_shot.count"] = self.few_shot.count
            if self.few_shot.selection:
                dumped["few_shot.selection"] = self.few_shot.selection

        return compute_tags(dumped)

    def model_dump_without_extras(self, exclude_none: bool = True) -> dict[str, Any]:
        extras = set(self.model_extra.keys()) if self.model_extra else set[str]()
        return self.model_dump(exclude=extras, exclude_none=exclude_none)

    @property
    def task_variant_id(self) -> str | None:
        return self.model_extra.get("task_variant_id") if self.model_extra else None

    @task_variant_id.setter
    def task_variant_id(self, value: str) -> None:
        if not self.__pydantic_extra__:
            self.__pydantic_extra__ = {"task_variant_id": value}
        else:
            self.__pydantic_extra__["task_variant_id"] = value

    @property
    def similarity_hash(self) -> str:
        properties_dict = self.model_dump(
            exclude_none=True,
            include=_SIMILARITY_HASH_FIELDS,
        )
        return compute_obj_hash(properties_dict)

    @model_validator(mode="after")
    def fill_missing_fields(self):
        if self.has_templated_instructions is None and self.instructions:
            self.has_templated_instructions = TemplateManager.is_template(self.instructions)
        return self

    # TODO: this validation should happen at the storage layer. Some old groups have enabled_tools that have
    # deprecated names
    @field_validator("enabled_tools", mode="before")
    def validate_enabled_tools(cls, v: list[str | ToolKind | Tool | dict[str, Any]] | None):
        if v is None:
            return None

        def _map_tool(tool: str | ToolKind | Tool | dict[str, Any]):
            if isinstance(tool, ToolKind) or isinstance(tool, Tool):
                return tool
            if isinstance(tool, str):
                return ToolKind.from_str(tool)
            if isinstance(tool, dict):  #  pyright: ignore [reportUnknownArgumentType, reportUnnecessaryIsInstance]
                return Tool.model_validate(tool)
            raise ValueError(f"Invalid tool type: {type(tool)}")

        return safe_map(v, _map_tool, logger=logging.getLogger(__name__))

    # Returns only the model
    def simplified(self):
        return TaskGroupProperties(
            model=self.model,
        )
