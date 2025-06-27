from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.dependencies.latest_task_variant import TaskVariantDep
from api.dependencies.path_params import TaskSchemaID
from api.dependencies.services import ModelsServiceDep, RunsSearchServiceDep
from api.dependencies.task_info import TaskTupleDep
from api.schemas.models import ModelMetadata, ModelResponse
from api.services.models import ModelForTask
from core.domain.page import Page
from core.domain.search_query import SearchFieldOption
from core.utils.schemas import FieldType
from core.utils.templates import InvalidTemplateError, TemplateManager

router = APIRouter(prefix="/v1/{tenant}/agents/{agent_id}/schemas/{task_schema_id}")


class AgentModelResponse(ModelResponse):
    is_not_supported_reason: str | None = Field(
        description="Why the model does not support the current schema. "
        "Only provided if the model is not supported by the current schema.",
    )
    average_cost_per_run_usd: float | None = Field(
        description="The average cost per run in USD",
    )

    @classmethod
    def from_model(cls, model: ModelForTask):
        return cls(
            id=model.id,
            name=model.name,
            icon_url=model.icon_url,
            modes=model.modes,
            is_not_supported_reason=model.is_not_supported_reason,
            average_cost_per_run_usd=model.average_cost_per_run_usd,
            is_latest=model.is_latest,
            metadata=ModelMetadata.from_service(model),
            is_default=model.is_default,
            providers=model.providers,
            reasoning=cls.Reasoning.from_domain(model.model_data.reasoning) if model.model_data.reasoning else None,
        )


@router.get("/models", description="List models for a task schema", response_model_exclude_none=True, deprecated=True)
async def list_models_for_task_schema(
    task: TaskVariantDep,
    models_service: ModelsServiceDep,
) -> Page[AgentModelResponse]:
    models = await models_service.models_for_task(task, instructions=None, requires_tools=False)
    return Page(items=[AgentModelResponse.from_model(model) for model in models])


class ListModelsRequest(BaseModel):
    instructions: str | None = Field(
        default=None,
        description="The instructions to use to build the models list, because instructions contains tools, and not all models support all tools.",
    )
    requires_tools: bool = Field(
        default=False,
        description="Wether the agent is using tools. This flag is mainly fed by the SDK when external tools are used.",
    )


@router.post("/models", description="List models for a task schema and instructions", response_model_exclude_none=True)
async def list_models_for_task_schema_and_instructions(
    task: TaskVariantDep,
    models_service: ModelsServiceDep,
    request: ListModelsRequest | None = None,
) -> Page[AgentModelResponse]:
    models = await models_service.models_for_task(
        task,
        instructions=request.instructions if request else None,
        requires_tools=request.requires_tools if request else None,
    )
    return Page(items=[AgentModelResponse.from_model(model) for model in models])


class SearchFields(BaseModel):
    class Item(BaseModel):
        field_name: str
        operators: list[str] = Field(description="The operators that can be used with the field")
        suggestions: list[Any] | None = Field(
            default=None,
            description="The suggestions for the field",
        )
        type: FieldType = Field(description="The type of the field")

        @classmethod
        def from_domain(cls, field: SearchFieldOption):
            return cls(
                field_name=field.field_name if not field.key_path else f"{field.field_name.value}.{field.key_path}",
                operators=[o.value for o in field.operators],
                suggestions=field.suggestions,
                type=field.type,
            )

    fields: list[Item] = Field(description="The fields that can be used in the search")


@router.get("/runs/search/fields")
async def list_task_runs_search_fields(
    task_tuple: TaskTupleDep,
    task_schema_id: TaskSchemaID,
    runs_search_service: RunsSearchServiceDep,
) -> SearchFields:
    fields = [
        SearchFields.Item.from_domain(f)
        async for f in runs_search_service.schemas_search_fields(task_tuple, task_schema_id)
    ]
    return SearchFields(fields=fields)


class CheckInstructionsRequest(BaseModel):
    instructions: str = Field(min_length=1)


class CheckInstructionsResponse(BaseModel):
    is_template: bool
    is_valid: bool

    class Error(BaseModel):
        message: str
        line_number: int | None
        missing_keys: set[str] | None = None

    error: Error | None = None

    @classmethod
    def from_error(cls, e: InvalidTemplateError):
        return cls(
            is_template=True,
            is_valid=False,
            error=cls.Error(message=e.message, line_number=e.line_number),
        )

    @classmethod
    def from_missing_keys(cls, missing_keys: set[str]):
        return cls(
            is_template=True,
            is_valid=False,
            error=cls.Error(
                message="The template is referencing keys that are not present in the input",
                line_number=None,
                missing_keys=missing_keys,
            ),
        )


@router.post("/instructions/check", response_model_exclude_none=True)
async def check_instructions(task: TaskVariantDep, request: CheckInstructionsRequest) -> CheckInstructionsResponse:
    if not TemplateManager.is_template(request.instructions):
        return CheckInstructionsResponse(is_template=False, is_valid=True)

    try:
        _, template_keys = await TemplateManager.compile_template(request.instructions)
    except InvalidTemplateError as e:
        return CheckInstructionsResponse.from_error(e)

    # Now check if all the template keys are present in the task
    # The template always returns root keys so we don't have to worry about nesting
    root_keys = set(task.input_schema.json_schema["properties"].keys())

    missing_keys = template_keys - root_keys
    if missing_keys:
        return CheckInstructionsResponse.from_missing_keys(missing_keys)

    return CheckInstructionsResponse(is_template=True, is_valid=True)
