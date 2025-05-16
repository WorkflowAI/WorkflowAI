import json
import logging
from typing import Any, NamedTuple

from fastapi import Request

from api.dependencies.event_router import EventRouterDep
from api.dependencies.services import GroupServiceDep, RunServiceDep
from api.dependencies.storage import StorageDep
from api.services.models import ModelsService
from api.utils import get_start_time
from core.domain.analytics_events.analytics_events import SourceType
from core.domain.consts import INPUT_KEY_MESSAGES, WORKFLOWAI_APP_URL
from core.domain.errors import BadRequestError
from core.domain.events import ProxyAgentCreatedEvent
from core.domain.message import Message, Messages
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_io import RawJSONMessageSchema, RawMessagesSchema, RawStringMessageSchema, SerializableTaskIO
from core.domain.task_variant import SerializableTaskVariant
from core.domain.tenant_data import PublicOrganizationData
from core.domain.types import AgentOutput
from core.domain.version_reference import VersionReference
from core.providers.base.provider_error import MissingModelError
from core.storage import ObjectNotFoundException
from core.utils.schemas import schema_from_data
from core.utils.strings import to_pascal_case
from core.utils.templates import InvalidTemplateError

from ._openai_proxy_models import (
    EnvironmentRef,
    ModelRef,
    OpenAIProxyChatCompletionChunk,
    OpenAIProxyChatCompletionRequest,
    OpenAIProxyChatCompletionResponse,
    OpenAIProxyResponseFormat,
)

_logger = logging.getLogger("OpenAIProxy")


class OpenAIProxyHandler:
    def __init__(
        self,
        group_service: GroupServiceDep,
        storage: StorageDep,
        run_service: RunServiceDep,
        event_router: EventRouterDep,
    ):
        self._group_service = group_service
        self._storage = storage
        self._run_service = run_service
        self._event_router = event_router

    @classmethod
    def _raw_string_mapper(cls, output: Any) -> str:
        return output

    @classmethod
    def _output_json_mapper(cls, output: AgentOutput) -> str:
        return json.dumps(output)

    @classmethod
    def _json_schema_from_input(cls, messages: Messages, input: dict[str, Any] | None) -> SerializableTaskIO:
        if input is None:
            # No body was sent with the request, so we treat the messages as a raw string
            return RawMessagesSchema

        schema_from_input: dict[str, Any] | None = schema_from_data(input) if input else None
        schema_from_template = messages.json_schema_for_template(base_schema=schema_from_input)
        if not schema_from_template:
            if schema_from_input:
                raise BadRequestError("Input variables are provided but the messages do not contain a valid template")
            return RawMessagesSchema
        if not schema_from_input:
            raise BadRequestError("Messages are templated but no input variables are provided")
        return SerializableTaskIO.from_json_schema({**schema_from_template, "format": "messages"}, streamline=True)

    @classmethod
    def _build_variant(
        cls,
        messages: Messages,
        agent_slug: str | None,
        input: dict[str, Any] | None,
        response_format: OpenAIProxyResponseFormat | None,
    ):
        try:
            input_schema = cls._json_schema_from_input(messages, input)
        except InvalidTemplateError as e:
            raise BadRequestError(f"Invalid template: {e.message}")

        if response_format:
            match response_format.type:
                case "text":
                    output_schema = RawStringMessageSchema
                case "json_object":
                    output_schema = RawJSONMessageSchema
                case "json_schema":
                    if not response_format.json_schema:
                        raise BadRequestError("JSON schema is required for json_schema response format")
                    output_schema = SerializableTaskIO.from_json_schema(response_format.json_schema.schema_)
                case _:
                    raise BadRequestError(f"Invalid response format: {response_format.type}")
        else:
            output_schema = RawStringMessageSchema

        if not agent_slug:
            agent_slug = "default"

        return SerializableTaskVariant(
            id="",
            task_schema_id=0,
            task_id=agent_slug,
            input_schema=input_schema,
            output_schema=output_schema,
            name=to_pascal_case(agent_slug),
        )

    class PreparedRun(NamedTuple):
        properties: TaskGroupProperties
        variant: SerializableTaskVariant
        final_input: dict[str, Any] | Messages

    def _check_for_duplicate_messages(self, property_messages: list[Message] | None, input_messages: Messages):
        """We try to check if the entirety of property messages are passed in the input messages.
        This is to avoid a user remove the messages from the openai sdk after switching to a deployment
        """
        if (
            not property_messages
            or not input_messages.messages
            or len(input_messages.messages) < len(property_messages)
        ):
            return

        if input_messages.messages[: len(property_messages)] == property_messages:
            raise BadRequestError(
                f"It looks like you send messages that are already included in your deployment. "
                f"The deployment already includes your first {len(property_messages)} messages so they "
                "should be omitted from the messages array (it's ok to send an empty message array if needed !)",
            )

    async def _prepare_for_deployment(
        self,
        agent_ref: EnvironmentRef,
        tenant_data: PublicOrganizationData,
        messages: Messages,
        input: dict[str, Any] | None,
        response_format: OpenAIProxyResponseFormat | None,
    ) -> PreparedRun:
        try:
            deployment = await self._storage.task_deployments.get_task_deployment(
                agent_ref.agent_id,
                agent_ref.schema_id,
                agent_ref.environment,
            )
        except ObjectNotFoundException:
            raise BadRequestError(
                f"Deployment not found for agent {agent_ref.agent_id}/{agent_ref.schema_id} in "
                f"environment {agent_ref.environment}. Check your deployments "
                f"at {tenant_data.app_deployments_url(agent_ref.agent_id, agent_ref.schema_id)}",
            )
        properties = deployment.properties
        if variant_id := deployment.properties.task_variant_id:
            variant = await self._storage.task_version_resource_by_id(
                agent_ref.agent_id,
                variant_id,
            )
        else:
            _logger.warning(
                "No variant id found for deployment, building a new variant",
                extra={"agent_ref": agent_ref},
            )
            variant = self._build_variant(messages, agent_ref.agent_id, input, response_format)

        if not properties.messages:
            # The version does not contain any messages so the input is the messages
            final_input: Messages | dict[str, Any] = messages
            if input:
                raise BadRequestError(
                    "The deployment you are trying to use does not contain any messages but you "
                    "sent input variables. Check the deployment at "
                    f"{tenant_data.app_deployments_url(agent_ref.agent_id, agent_ref.schema_id)}",
                )
        else:
            # It is possible that we used deployments that contained no input variables for example
            # If a user saved a non templated system message. In which case the input is None
            final_input = input or {}
            if messages.messages:
                # Here we try and avoid duplicate messages so we check the message replies
                self._check_for_duplicate_messages(properties.messages, input_messages=messages)

                final_input = {
                    **final_input,
                    INPUT_KEY_MESSAGES: messages.model_dump(mode="json", exclude_none=True)["messages"],
                }

        return self.PreparedRun(properties=properties, variant=variant, final_input=final_input)

    async def _prepare_for_model(
        self,
        agent_ref: ModelRef,
        messages: Messages,
        input: dict[str, Any] | None,
        response_format: OpenAIProxyResponseFormat | None,
    ) -> PreparedRun:
        raw_variant = self._build_variant(messages, agent_ref.agent_id, input=input, response_format=response_format)
        variant, new_variant_created = await self._storage.store_task_resource(raw_variant)

        if new_variant_created:
            self._event_router(
                ProxyAgentCreatedEvent(
                    agent_slug=raw_variant.task_id,
                    task_id=variant.task_id,
                    task_schema_id=variant.task_schema_id,
                ),
            )

        properties = TaskGroupProperties(model=agent_ref.model)
        properties.task_variant_id = variant.id

        if input:
            # If we have an input, the input schema in the variant must not be the RawMessagesSchema
            # otherwise _build_variant would have raised an error
            # So we can check that the input schema matches and then template the messages as needed
            # We don't remove any extras from the input, we just validate it
            properties.messages = messages.messages
            final_input: dict[str, Any] | Messages = input
        else:
            final_input = messages

        return self.PreparedRun(properties=properties, variant=variant, final_input=final_input)

    def _check_final_input(
        self,
        input_io: SerializableTaskIO,
        final_input: dict[str, Any] | Messages,
        agent_ref: EnvironmentRef | ModelRef,
        tenant_data: PublicOrganizationData,
    ):
        if isinstance(final_input, Messages):
            if input_io.version == RawMessagesSchema.version:
                # Everything is ok here
                return
            raise (
                BadRequestError(
                    f"You passed input variables to a deployment on schema #{agent_ref.schema_id} but schema "
                    f"#{agent_ref.schema_id} does not expect any."
                    "You likely have a typo in your schema number."
                    f"Please check your schema at {tenant_data.app_schema_url(agent_ref.agent_id, agent_ref.schema_id)}",
                )
                if isinstance(agent_ref, EnvironmentRef)
                else BadRequestError(
                    "It looks like you are using input variables but there are no input variables in your messages.",
                )
            )

        input_io.enforce(final_input)

    async def _prepare_run(self, body: OpenAIProxyChatCompletionRequest, tenant_data: PublicOrganizationData):
        messages = Messages(messages=[m.to_domain() for m in body.messages])

        # First we need to locate the agent
        try:
            agent_ref = body.extract_references()
        except MissingModelError as e:
            raise await self.missing_model_error(e.extras.get("model"))

        if isinstance(agent_ref, EnvironmentRef):
            prepared_run = await self._prepare_for_deployment(
                agent_ref=agent_ref,
                tenant_data=tenant_data,
                messages=messages,
                input=body.input,
                response_format=body.response_format,
            )
        else:
            prepared_run = await self._prepare_for_model(
                agent_ref=agent_ref,
                messages=messages,
                input=body.input,
                response_format=body.response_format,
            )

        self._check_final_input(
            prepared_run.variant.input_schema,
            prepared_run.final_input,
            agent_ref,
            tenant_data,
        )
        body.apply_to(prepared_run.properties)

        return prepared_run

    async def handle(
        self,
        body: OpenAIProxyChatCompletionRequest,
        request: Request,
        tenant_data: PublicOrganizationData,
    ):
        body.check_supported_fields()

        prepared_run = await self._prepare_run(body, tenant_data)

        runner, _ = await self._group_service.sanitize_groups_for_internal_runner(
            task_id=prepared_run.variant.task_id,
            task_schema_id=prepared_run.variant.task_schema_id,
            reference=VersionReference(properties=prepared_run.properties),
            provider_settings=None,
            variant=prepared_run.variant,
            stream_deltas=body.stream is True,
        )

        output_mapper = (
            self._raw_string_mapper
            if prepared_run.variant.output_schema.version == RawStringMessageSchema.version
            else self._output_json_mapper
        )

        return await self._run_service.run(
            runner=runner,
            task_input=prepared_run.final_input,
            task_run_id=None,
            cache=body.use_cache or "auto",
            metadata=body.full_metadata(request.headers),
            trigger="user",
            source=SourceType.PROXY,
            serializer=OpenAIProxyChatCompletionResponse.serializer(
                model=body.model,
                deprecated_function=body.uses_deprecated_functions,
                output_mapper=output_mapper,
            ),
            start_time=get_start_time(request),
            stream_serializer=OpenAIProxyChatCompletionChunk.stream_serializer(
                model=body.model,
                deprecated_function=body.uses_deprecated_functions,
            )
            if body.stream is True
            else None,
        )

    @classmethod
    async def missing_model_error(cls, model: str | None):
        _check_lineup = f"Check the lineup 👉 {WORKFLOWAI_APP_URL}/models (25+ models)"
        if not model:
            return BadRequestError(
                f"""Empty model
{_check_lineup}""",
            )

        components = [
            f"Unknown model: {model}",
            _check_lineup,
        ]
        if suggested := await ModelsService.suggest_model(model):
            components.insert(1, f"Did you mean {suggested}?")
        return BadRequestError("\n".join(components))
