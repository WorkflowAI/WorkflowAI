from datetime import date, datetime
from typing import Any

from pydantic import BaseModel

from core.domain.agent_run import AgentRun
from core.domain.fields.file import File
from core.domain.models._displayed_provider import DisplayedProvider
from core.domain.models.model_data import MaxTokensData, ModelData, QualityData, SpeedData, SpeedIndex
from core.domain.review import Review
from core.domain.task_deployment import TaskDeployment
from core.domain.task_evaluation import TaskEvaluation
from core.domain.task_evaluator import EvaluatorType, FaithfulnessEvaluator, TaskEvaluator
from core.domain.task_example import SerializableTaskExample
from core.domain.task_group import TaskGroup
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_io import SerializableTaskIO
from core.domain.task_variant import SerializableTaskVariant
from core.domain.tool import Tool
from core.domain.tool_call import ToolCall, ToolCallRequestWithID
from core.domain.types import AgentOutput
from core.domain.users import UserIdentifier
from core.domain.version_environment import VersionEnvironment


def task_group(group_id: str | None = None, **kwargs: Any) -> TaskGroup:
    base = TaskGroup(
        id=group_id or "group_alias",
        iteration=1,
        properties=TaskGroupProperties.model_construct(key1="value1"),
        tags=["tag1", "tag2"],
    )
    return TaskGroup.model_validate({**base.model_dump(exclude_none=True), **kwargs})


def task_run_ser(
    task_id: str = "task_id",
    task_schema_id: int = 1,
    task_input: dict[str, Any] | None = None,
    task_output: AgentOutput | None = None,
    group_kwargs: dict[str, Any] | None = None,
    group_id: str | None = None,
    group: TaskGroup | None = None,
    task: SerializableTaskVariant | None = None,
    tool_call_requests: list[ToolCallRequestWithID] | None = None,
    task_uid: int | None = None,
    model: str | None = None,
    id: str = "run_id",
    **kwargs: Any,
) -> AgentRun:
    if not group:
        final_kwargs = group_kwargs or {}
        if "schema_id" not in final_kwargs:
            final_kwargs["schema_id"] = task_schema_id
        properties = final_kwargs.setdefault("properties", {})
        if model:
            properties["model"] = model
        group = task_group(group_id=group_id, **final_kwargs)

    base = AgentRun(
        id=id,
        task_uid=task_uid or 0,
        task_id=task.task_id if task else task_id,
        task_schema_id=task.task_schema_id if task else task_schema_id,
        duration_seconds=1.0,
        task_input={"input": "world"} if task_input is None else task_input,
        task_input_hash="input_hash",
        task_output={"output": 1} if task_output is None else task_output,
        task_output_hash="output_hash",
        group=group or task_group(group_id=group_id, **(group_kwargs or {"schema_id": task_schema_id})),
        tool_call_requests=tool_call_requests or None,
    )

    return AgentRun.model_validate({**base.model_dump(exclude_none=True, exclude={"eval_hash"}), **kwargs})


def task_example_ser(**kwargs: Any) -> SerializableTaskExample:
    base = SerializableTaskExample(
        id="6639a2d4b1057aa2c44de73f",
        task_id="task_id",
        task_schema_id=1,
        task_input={"input": "world"},
        task_input_hash="input_hash",
        task_output={"output": 1},
        task_output_hash="output_hash",
    )

    return SerializableTaskExample.model_validate({**base.model_dump(exclude_none=True), **kwargs})


def task_variant(
    input_schema: dict[str, Any] | None = None,
    input_io: SerializableTaskIO | None = None,
    output_schema: dict[str, Any] | None = None,
    output_io: SerializableTaskIO | None = None,
    input_model: type[BaseModel] | None = None,
    output_model: type[BaseModel] | None = None,
    **kwargs: Any,
) -> SerializableTaskVariant:
    base = SerializableTaskVariant(
        id="task_version_id",
        task_id="task_id",
        name="task_name",
        task_schema_id=1,
        input_schema=input_io
        or (
            SerializableTaskIO.from_model(input_model)
            if input_model
            else SerializableTaskIO(
                version="input_version",
                json_schema=input_schema
                or {"type": "object", "properties": {"input": {"type": "string"}}, "required": ["input"]},
            )
        ),
        output_schema=output_io or SerializableTaskIO.from_model(output_model)
        if output_model
        else SerializableTaskIO(
            version="output_version",
            json_schema=output_schema
            or {"type": "object", "properties": {"output": {"type": "integer"}}, "required": ["output"]},
        ),
    )

    return SerializableTaskVariant.model_validate({**base.model_dump(exclude_none=True), **kwargs})


def task_variant_with_single_file(
    **kwargs: Any,
) -> SerializableTaskVariant:
    base = SerializableTaskVariant(
        id="task_version_id",
        task_id="task_id",
        name="task_name",
        task_schema_id=1,
        input_schema=SerializableTaskIO(
            version="input_version",
            json_schema={
                "$defs": {"File": File.model_json_schema()},
                "properties": {"hello": {"$ref": "#/$defs/File"}},
            },
        ),
        output_schema=SerializableTaskIO(
            version="output_version",
            json_schema={"type": "object", "properties": {"output": {"type": "integer"}}, "required": ["output"]},
        ),
    )

    return SerializableTaskVariant.model_validate({**base.model_dump(exclude_none=True), **kwargs})


def task_variant_with_multiple_images(
    **kwargs: Any,
) -> SerializableTaskVariant:
    base = SerializableTaskVariant(
        id="task_version_id",
        task_id="task_id",
        name="task_name",
        task_schema_id=1,
        input_schema=SerializableTaskIO(
            version="input_version",
            json_schema={
                "$defs": {"File": File.model_json_schema()},
                "properties": {"hello": {"type": "array", "items": {"$ref": "#/$defs/File", "format": "image"}}},
            },
        ),
        output_schema=SerializableTaskIO(
            version="output_version",
            json_schema={"type": "object", "properties": {"output": {"type": "integer"}}, "required": ["output"]},
        ),
    )

    return SerializableTaskVariant.model_validate({**base.model_dump(exclude_none=True), **kwargs})


def _task_variant_with_file(file_format: str, **kwargs: Any) -> SerializableTaskVariant:
    base = SerializableTaskVariant(
        id="task_version_id",
        task_id="task_id",
        name="task_name",
        task_schema_id=1,
        input_schema=SerializableTaskIO(
            version="input_version",
            json_schema={
                "$defs": {"File": File.model_json_schema()},
                "properties": {"file": {"$ref": "#/$defs/File", "format": file_format}},
            },
        ),
        output_schema=SerializableTaskIO(
            version="output_version",
            json_schema={"type": "object", "properties": {"output": {"type": "integer"}}, "required": ["output"]},
        ),
    )

    return SerializableTaskVariant.model_validate({**base.model_dump(exclude_none=True), **kwargs})


def task_variant_with_audio_file(
    **kwargs: Any,
) -> SerializableTaskVariant:
    return _task_variant_with_file("audio", **kwargs)


def task_evaluation(**kwargs: Any) -> TaskEvaluation:
    base = TaskEvaluation(
        score=1.0,
        tags=[],
        comment="score_description",
        evaluator=TaskEvaluation.Evaluator(
            id="evaluator_id",
            name="evaluator_name",
            properties={"key": "value"},
        ),
    )

    return TaskEvaluation.model_validate({**base.model_dump(exclude_none=True), **kwargs})


def task_evaluator(evaluator_type: EvaluatorType | None = None, **kwargs: Any) -> TaskEvaluator:
    base = TaskEvaluator(
        id="evaluator_id",
        name="evaluator_name",
        triggers={"auto"},
        evaluator_type=evaluator_type
        or FaithfulnessEvaluator(
            new_assistant_answer_keypath=["key1", "key2"],
            new_user_message_keypath=["key1", "key2"],
        ),
    )

    return TaskEvaluator.model_validate({**base.model_dump(exclude_none=True), **kwargs})


def wai_task_run(output: Any, **kwargs: Any):
    from workflowai import Run, Version

    kwargs = {"id": "mock_run_id", "task_id": "mock_task_id", "task_schema_id": 1, **kwargs}
    return Run(
        version=Version(),
        output=output,
        **kwargs,
    )


def task_deployment(
    iteration: int = 1,
    version_id: str = "version_id",
    schema_id: int = 1,
    task_id: str = "task_id",
    environment: VersionEnvironment = VersionEnvironment.DEV,
    properties: TaskGroupProperties | None = None,
):
    return TaskDeployment(
        task_id=task_id,
        schema_id=schema_id,
        iteration=iteration,
        version_id=version_id,
        environment=environment,
        deployed_at=datetime.now(),
        deployed_by=UserIdentifier(
            user_id="user_id",
            user_email="user_email@example.com",
        ),
        properties=properties or TaskGroupProperties(model="gpt-4o-2024-08-06"),
    )


def review(**kwargs: Any) -> Review:
    raw = Review(
        id="review_id",
        task_id="task_id",
        task_schema_id=1,
        task_input_hash="input_hash",
        task_output_hash="output_hash",
        outcome="positive",
        status="completed",
        reviewer=Review.UserReviewer(user_id="user_id", user_email="user_email@example.com"),
    )
    return Review.model_validate({**raw.model_dump(exclude_none=True, exclude={"eval_hash"}), **kwargs})


def model_data(**kwargs: Any) -> ModelData:
    return ModelData(
        display_name="Llama 3.1 (70B)",
        supports_json_mode=True,
        supports_input_image=False,
        supports_input_pdf=False,
        supports_input_audio=False,
        max_tokens_data=MaxTokensData(
            max_tokens=128000,
            source="https://github.com/meta-llama/llama-models/blob/main/models/llama3_1/MODEL_CARD.md",
        ),
        icon_url="https://workflowai.blob.core.windows.net/workflowai-public/meta.svg",
        release_date=date(2024, 7, 23),
        quality_data=QualityData(mmlu=86, gpqa=48),
        speed_data=SpeedData(index=SpeedIndex(value=500)),
        provider_name=DisplayedProvider.FIREWORKS.value,
        supports_tool_calling=True,
        fallback=None,
    ).model_copy(update=kwargs)


def tool(**kwargs: Any) -> Tool:
    return Tool(
        name="tool_name",
        description="tool_description",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    ).model_copy(update=kwargs)


def tool_call_request(**kwargs: Any) -> ToolCallRequestWithID:
    return ToolCallRequestWithID(
        id="tool_call_request_id",
        tool_name="tool_name",
        tool_input_dict={"arg": "value"},
    ).model_copy(update=kwargs)


def tool_call(**kwargs: Any) -> ToolCall:
    return ToolCall(
        id="tool_call_id",
        tool_name="tool_name",
        tool_input_dict={"arg": "value"},
        result={"arg": "value"},
    ).model_copy(update=kwargs)
