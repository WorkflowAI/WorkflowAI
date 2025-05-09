import json
from typing import Any

from fastapi import APIRouter, Request, Response

from api.dependencies.event_router import EventRouterDep
from api.dependencies.services import GroupServiceDep, RunServiceDep
from api.dependencies.storage import StorageDep
from api.routers.openai_proxy_models import (
    OpenAIProxyChatCompletionChunk,
    OpenAIProxyChatCompletionRequest,
    OpenAIProxyChatCompletionResponse,
    OpenAIProxyResponseFormat,
)
from api.utils import get_start_time
from core.domain.errors import BadRequestError
from core.domain.events import ProxyAgentCreatedEvent
from core.domain.message import Messages
from core.domain.models.models import Model
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_io import RawJSONMessageSchema, RawMessagesSchema, RawStringMessageSchema, SerializableTaskIO
from core.domain.task_variant import SerializableTaskVariant
from core.domain.types import AgentOutput
from core.domain.version_reference import VersionReference

router = APIRouter(prefix="", tags=["openai"])


_model_mapping = {
    "gpt-4o": Model.GPT_4O_LATEST,
}


def _parse_model(model: str) -> Model:
    if model in _model_mapping:
        return _model_mapping[model]

    # We try to parse the model as a Model
    try:
        return Model(model)
    except ValueError:
        pass

    # Then we check if it's a unversioned model, called "latest" here
    try:
        return Model(model + "-latest")
    except ValueError:
        pass

    raise BadRequestError(f"Model does not exist {model}")


def _agent_and_model(model: str) -> tuple[str | None, Model]:
    agent_and_model = model.split("/")
    if len(agent_and_model) > 2:
        raise BadRequestError(f"Invalid model: {model}")

    if len(agent_and_model) == 1:
        agent_name = None
        model_str = agent_and_model[0]
    else:
        agent_name = agent_and_model[0]
        model_str = agent_and_model[1]

    return agent_name, _parse_model(model_str)


def _raw_string_mapper(output: Any) -> str:
    return output


def _output_json_mapper(output: AgentOutput) -> str:
    return json.dumps(output)


def _build_variant(agent_slug: str, response_format: OpenAIProxyResponseFormat | None):
    if response_format:
        match response_format.type:
            case "text":
                output_schema = RawStringMessageSchema
                mapper = _raw_string_mapper
            case "json_object":
                output_schema = RawJSONMessageSchema
                mapper = _output_json_mapper
            case "json_schema":
                if not response_format.json_schema:
                    raise BadRequestError("JSON schema is required for json_schema response format")
                output_schema = SerializableTaskIO.from_json_schema(response_format.json_schema.schema_)
                mapper = _output_json_mapper
            case _:
                raise BadRequestError(f"Invalid response format: {response_format.type}")
    else:
        output_schema = RawStringMessageSchema
        mapper = _raw_string_mapper

    return SerializableTaskVariant(
        id="",
        task_schema_id=0,
        task_id=agent_slug,
        input_schema=RawMessagesSchema,
        output_schema=output_schema,
        name=agent_slug,
    ), mapper


@router.post(
    "/v1/chat/completions",
    responses={
        200: {
            "content": {
                "text/event-stream": {
                    "schema": OpenAIProxyChatCompletionChunk.model_json_schema(),
                },
                "application/json": {
                    "schema": OpenAIProxyChatCompletionResponse.model_json_schema(),
                },
            },
        },
    },
)
async def chat_completions(
    body: OpenAIProxyChatCompletionRequest,
    group_service: GroupServiceDep,
    storage: StorageDep,
    run_service: RunServiceDep,
    event_router: EventRouterDep,
    request: Request,
) -> Response:
    request_start_time = get_start_time(request)
    # First we need to locate the agent
    agent_slug, model = _agent_and_model(body.model)
    if not agent_slug:
        agent_slug = body.agent_id or "default"

    raw_variant, output_mapper = _build_variant(agent_slug, body.response_format)
    variant, new_variant_created = await storage.store_task_resource(raw_variant)

    if new_variant_created:
        event_router(
            ProxyAgentCreatedEvent(
                agent_slug=agent_slug,
                task_id=variant.task_id,
                task_schema_id=variant.task_schema_id,
            ),
        )

    tool_calls, deprecated_function = body.domain_tools()
    properties = TaskGroupProperties(
        model=model,
        enabled_tools=tool_calls,
        max_tokens=body.max_completion_tokens or body.max_tokens,
        temperature=body.temperature,
        provider=body.workflowai_provider,
        tool_choice=body.worflowai_tool_choice,
    )
    properties.task_variant_id = variant.id

    runner, _ = await group_service.sanitize_groups_for_internal_runner(
        task_id=variant.task_id,
        task_schema_id=variant.task_schema_id,
        reference=VersionReference(properties=properties),
        provider_settings=None,
        variant=variant,
        stream_deltas=body.stream is True,
    )

    return await run_service.run(
        runner=runner,
        task_input=Messages(messages=[m.to_domain() for m in body.messages]),
        task_run_id=None,
        cache="auto",
        metadata=body.full_metadata(request.headers),
        trigger="user",
        serializer=OpenAIProxyChatCompletionResponse.serializer(
            model=body.model,
            deprecated_function=deprecated_function,
            output_mapper=output_mapper,
        ),
        start_time=request_start_time,
        stream_serializer=OpenAIProxyChatCompletionChunk.stream_serializer(
            model=body.model,
            deprecated_function=deprecated_function,
        )
        if body.stream is True
        else None,
    )
