import os
from typing import Optional

from pydantic import BaseModel, Field

from core.domain.models import Model, Provider
from core.domain.task_group_properties import FewShotExample
from core.domain.tool import Tool
from core.runners.workflowai.templates import TemplateName
from core.tools import ToolKind

GLOBAL_DEFAULT_MODEL = Model(os.environ.get("WORKFLOWAI_DEFAULT_MODEL", Model.GPT_4O_2024_08_06))
TEXT_EQUIVALENCE_TASK_MODEL = Model(Model.GEMINI_1_5_PRO_001)


# TODO: we should just use the TaskGroupProperties here instead
class WorkflowAIRunnerOptions(BaseModel):
    instructions: str | None = Field(description="The instructions used to run the task")

    provider: Provider | None = Field(
        description="""The provider to use for the task.
        If specified explicitly and the provider is not compatible with the model,
        a ProviderDoesNotSupportModelError is raised. Otherwise the runner will pick
        the first provider that is properly configured and that supports the model.""",
    )
    model: Model = Field(
        description="""The model to use for the task.
        If not specified, the runner will pick the default model.""",
    )

    temperature: float = Field(default=0, description="The temperature to use for the task")

    max_tokens: Optional[int] = Field(default=None, description="The maximum number of tokens to generate for the task")

    examples: list[FewShotExample] | None = None

    template_name: TemplateName | None = None

    is_chain_of_thought_enabled: bool | None = None

    enabled_tools: list[ToolKind | Tool] | None = None

    is_structured_generation_enabled: bool | None = None

    has_templated_instructions: bool | None = None
