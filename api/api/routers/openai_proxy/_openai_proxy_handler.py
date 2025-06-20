import json
import logging
from typing import Any, NamedTuple

from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

from api.services.feedback_svc import FeedbackTokenGenerator
from api.services.groups import GroupService
from api.services.messages.messages_utils import json_schema_for_template
from api.services.models import ModelsService
from api.services.run import RunService
from api.utils import get_start_time
from core.domain.analytics_events.analytics_events import SourceType, TaskProperties
from core.domain.consts import INPUT_KEY_MESSAGES, METADATA_KEY_DEPLOYMENT_ENVIRONMENT, WORKFLOWAI_APP_URL
from core.domain.errors import BadRequestError
from core.domain.events import EventRouter, ProxyAgentCreatedEvent
from core.domain.message import Message, Messages
from core.domain.models.model_datas_mapping import MODEL_COUNT
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_io import RawJSONMessageSchema, RawMessagesSchema, RawStringMessageSchema, SerializableTaskIO
from core.domain.task_variant import SerializableTaskVariant
from core.domain.tenant_data import PublicOrganizationData
from core.domain.types import AgentOutput, CacheUsage
from core.domain.version_reference import VersionReference
from core.providers.base.provider_error import MissingModelError
from core.storage import ObjectNotFoundException
from core.storage.backend_storage import BackendStorage
from core.utils.schemas import schema_from_data
from core.utils.strings import slugify, to_pascal_case
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
        group_service: GroupService,
        storage: BackendStorage,
        run_service: RunService,
        event_router: EventRouter,
        feedback_generator: FeedbackTokenGenerator,
    ):
        self._group_service = group_service
        self._storage = storage
        self._run_service = run_service
        self._event_router = event_router
        self._feedback_generator = feedback_generator

    @classmethod
    def _raw_string_mapper(cls, output: Any) -> str | None:
        return output or None

    @classmethod
    def _output_json_mapper(cls, output: AgentOutput) -> str:
        return json.dumps(output)

    @classmethod
    def _json_schema_from_input(
        cls,
        messages: Messages,
        input: dict[str, Any] | None,
    ) -> tuple[SerializableTaskIO, int]:
        if input is None:
            # No body was sent with the request, so we treat the messages as a raw string
            return RawMessagesSchema, -1

        schema_from_input: dict[str, Any] | None = schema_from_data(input) if input else None
        schema_from_template, last_templated_index = json_schema_for_template(
            messages.messages,
            base_schema=schema_from_input,
        )
        if not schema_from_template:
            if schema_from_input:
                raise BadRequestError("Input variables are provided but the messages do not contain a valid template")
            return RawMessagesSchema, -1
        if not schema_from_input:
            raise BadRequestError("Messages are templated but no input variables are provided")
        return SerializableTaskIO.from_json_schema(
            {**schema_from_template, "format": "messages"},
            streamline=True,
        ), last_templated_index

    def _update_task_properties(self, tenant_data: PublicOrganizationData, variant: SerializableTaskVariant):
        try:
            properties = TaskProperties.build(
                variant.task_id,
                variant.task_schema_id,
                tenant_data,
            )
            self._event_router.task_properties = properties  # pyright: ignore [reportAttributeAccessIssue]
            self._run_service.analytics_service.task_properties = properties  # pyright: ignore [reportAttributeAccessIssue]
            self._group_service.analytics_service.task_properties = properties  # pyright: ignore[reportAttributeAccessIssue]
        except Exception:
            _logger.exception("Could not set task properties for event router, run service or group service")

    @classmethod
    def _build_variant(
        cls,
        messages: Messages,
        agent_slug: str | None,
        input: dict[str, Any] | None,
        response_format: OpenAIProxyResponseFormat | None,
    ) -> tuple[SerializableTaskVariant, int]:
        """Returns a variant and the index of the last templated message"""
        try:
            input_schema, last_templated_index = cls._json_schema_from_input(messages, input)
        except InvalidTemplateError as e:
            raise BadRequestError(
                f"Invalid template: {e.message}. Templates must use Jinja2 formatting.",
                details=e.serialize_details(),
            )

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

        slugified_agent_slug = slugify(agent_slug)

        return SerializableTaskVariant(
            id="",
            task_schema_id=0,
            task_id=slugified_agent_slug,
            input_schema=input_schema,
            output_schema=output_schema,
            # If the agent_id was already a slug, then we convert to pascal case, or we use as is.
            name=to_pascal_case(agent_slug, separator=" ") if slugified_agent_slug == agent_slug else agent_slug,
        ), last_templated_index

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
        agent_id = slugify(agent_ref.agent_id)
        try:
            deployment = await self._storage.task_deployments.get_task_deployment(
                agent_id,
                agent_ref.schema_id,
                agent_ref.environment,
            )
        except ObjectNotFoundException:
            raise BadRequestError(
                f"Deployment not found for agent {agent_id}/{agent_ref.schema_id} in "
                f"environment {agent_ref.environment}. Check your deployments "
                f"at {tenant_data.app_deployments_url(agent_id, agent_ref.schema_id)}",
            )
        properties = deployment.properties
        if variant_id := deployment.properties.task_variant_id:
            variant = await self._storage.task_version_resource_by_id(
                agent_id,
                variant_id,
            )
        else:
            _logger.warning(
                "No variant id found for deployment, building a new variant",
                extra={"agent_ref": agent_ref},
            )
            variant, _ = self._build_variant(messages, agent_ref.agent_id, input, response_format)
            variant, _ = await self._storage.store_task_resource(variant)
        self._update_task_properties(tenant_data, variant)

        if not properties.messages:
            # The version does not contain any messages so the input is the messages
            final_input: Messages | dict[str, Any] = messages
            if input:
                raise BadRequestError(
                    "You send input variables but the deployment you are trying to use does not expect any. "
                    "You likely have a typo in your schema id. Check the deployment at "
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
                    # TODO: Pretty idiotic to dump here we should just build a StoredMessage instead
                    INPUT_KEY_MESSAGES: messages.model_dump(mode="json", exclude_none=True)[INPUT_KEY_MESSAGES],
                }

        return self.PreparedRun(properties=properties, variant=variant, final_input=final_input)

    async def _prepare_for_variant_id(
        self,
        agent_id: str,
        model: str,
        variant_id: str,
        version_messages: list[Message] | None,
        input: dict[str, Any] | None,
        tenant_data: PublicOrganizationData,
    ) -> PreparedRun:
        variant = await self._storage.task_version_resource_by_id(
            agent_id,
            variant_id,
        )
        properties = TaskGroupProperties(model=model, messages=version_messages)
        properties.task_variant_id = variant.id
        self._update_task_properties(tenant_data, variant)
        # Here the input is exactly what we expect in run.task_input
        return self.PreparedRun(properties=properties, variant=variant, final_input=input or {})

    async def _prepare_for_model(
        self,
        agent_ref: ModelRef,
        tenant_data: PublicOrganizationData,
        messages: Messages,
        input: dict[str, Any] | None,
        response_format: OpenAIProxyResponseFormat | None,
    ) -> PreparedRun:
        raw_variant, last_templated_index = self._build_variant(
            messages,
            agent_ref.agent_id,
            input=input,
            response_format=response_format,
        )
        variant, new_variant_created = await self._storage.store_task_resource(raw_variant)
        self._update_task_properties(tenant_data, variant)

        if new_variant_created:
            self._event_router(
                ProxyAgentCreatedEvent(
                    agent_slug=variant.task_id,
                    task_id=variant.task_id,
                    task_schema_id=variant.task_schema_id,
                ),
            )

        properties = TaskGroupProperties(model=agent_ref.model)
        properties.task_variant_id = variant.id

        if input is not None:
            # We split the messages into two parts:
            # - The part that is templated (or the first system message)
            # - The part that is not templated
            # We don't remove any extras from the input, we just validate it
            if last_templated_index == -1:
                if messages.messages[0].role == "system":
                    cutoff_index = 1
                else:
                    cutoff_index = 0
            else:
                cutoff_index = last_templated_index + 1

            properties.messages = messages.messages[:cutoff_index]
            final_input: dict[str, Any] | Messages = input
            if len(messages.messages) > cutoff_index:
                final_input = {
                    **final_input,
                    INPUT_KEY_MESSAGES: messages.messages[cutoff_index:],
                }
        else:
            final_input = messages

        return self.PreparedRun(properties=properties, variant=variant, final_input=final_input)

    def _check_final_input(
        self,
        input_io: SerializableTaskIO,
        final_input: dict[str, Any] | Messages,
        agent_ref: EnvironmentRef | ModelRef,
        tenant_data: PublicOrganizationData,
        request_input_was_empty: bool,
    ):
        if isinstance(final_input, Messages) or request_input_was_empty:
            # That can happen if the user passed a None input
            if input_io.uses_raw_messages:
                # Everything is ok here, we received messages with no input and expected no input
                return

            # We are not good here
            # We should have a proper input dict
            raise (
                BadRequestError(
                    f"Your deployment on schema #{agent_ref.schema_id} expects input variables but you did not send any."
                    f"Please check your schema at {tenant_data.app_schema_url(agent_ref.agent_id, agent_ref.schema_id)}",
                )
                if isinstance(agent_ref, EnvironmentRef)
                else BadRequestError("It seems that your messages expect templated variables but you did not send any.")
            )

        if input_io.uses_raw_messages and not request_input_was_empty:
            raise (
                BadRequestError(
                    f"You passed input variables to a deployment on schema #{agent_ref.schema_id} but schema "
                    f"#{agent_ref.schema_id} does not expect any."
                    "You likely have a typo in your schema number."
                    f"Please check your schema at {tenant_data.app_schema_url(agent_ref.agent_id, agent_ref.schema_id)}",
                )
                if isinstance(agent_ref, EnvironmentRef)
                else BadRequestError(
                    "It looks like you sent input variables but there are no input variables in your messages.",
                )
            )

        input_io.enforce(final_input, files_as_strings=True)

    async def _prepare_run(self, body: OpenAIProxyChatCompletionRequest, tenant_data: PublicOrganizationData):
        if body.workflowai_internal:
            # "Internal way" of using the proxy endpoint
            # this is used by the playground to easily run a single variant, since it already
            # knows:
            # - the variant that should be used (including the schema)
            # - the agent_id
            # - the messages that go into the version vs the ones in the input
            # -
            if not body.agent_id:
                raise BadRequestError("Agent id is required when a variant id is provided")
            if body.messages:
                raise BadRequestError("Messages are not supported when a variant id is provided")
            if body.response_format:
                raise BadRequestError("Response format is not supported when a variant id is provided")
            return await self._prepare_for_variant_id(
                agent_id=body.agent_id,
                model=body.model,
                variant_id=body.workflowai_internal.variant_id,
                version_messages=body.workflowai_internal.version_messages,
                input=body.input,
                tenant_data=tenant_data,
            )

        messages = Messages.with_messages(*body.domain_messages())

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
            # Keep track the run was made from a deployment
            # TODO: Adding to the body is not great. We should add metadata to the prepared run and even remove the 'full_metadata'
            body.register_metadata({METADATA_KEY_DEPLOYMENT_ENVIRONMENT: agent_ref.environment})
        else:
            prepared_run = await self._prepare_for_model(
                agent_ref=agent_ref,
                tenant_data=tenant_data,
                messages=messages,
                input=body.input,
                response_format=body.response_format,
            )

        self._check_final_input(
            prepared_run.variant.input_schema,
            prepared_run.final_input,
            agent_ref,
            tenant_data,
            request_input_was_empty=not body.input,
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

        try:
            parsed_fallback = body.parsed_use_fallback()
        except MissingModelError as e:
            raise await self.missing_model_error(e.extras.get("model"), prefix="fallback ")

        aggregate_content = body.stream_options.valid_json_chunks if body.stream_options else None

        runner, _ = await self._group_service.sanitize_groups_for_internal_runner(
            task_id=prepared_run.variant.task_id,
            task_schema_id=prepared_run.variant.task_schema_id,
            reference=VersionReference(properties=prepared_run.properties),
            provider_settings=None,
            variant=prepared_run.variant,
            stream_deltas=body.stream is True and not aggregate_content,
            use_fallback=parsed_fallback,
        )

        output_mapper = (
            self._raw_string_mapper
            if prepared_run.variant.output_schema.version == RawStringMessageSchema.version
            else self._output_json_mapper
        )

        builder = await self._run_service.prepare_builder(
            runner=runner,
            task_input=prepared_run.final_input,
            task_run_id=None,
            metadata=body.full_metadata(request.headers),
            start_time=get_start_time(request),
            is_different_version=False,
            author_tenant=None,
            private_fields=set(),
            conversation_id=body.conversation_id,
        )
        cache: CacheUsage = body.use_cache or "auto"
        trigger = "user"
        source = SourceType.PROXY

        def _feedback_generator(run_id: str) -> str:
            return self._feedback_generator.generate_token(
                prepared_run.variant.task_uid,
                prepared_run.variant.task_schema_id,
                run_id,
            )

        if not body.stream:
            task_run = await self._run_service.run_from_builder(
                builder=builder,
                runner=runner,
                cache=cache,
                trigger=trigger,
                source=source,
                store_inline=False,
            )
            response_object = OpenAIProxyChatCompletionResponse.from_domain(
                task_run,
                output_mapper=output_mapper,
                model=body.model,
                deprecated_function=body.uses_deprecated_functions,
                feedback_generator=_feedback_generator,
            )
            return JSONResponse(content=response_object.model_dump(mode="json", exclude_none=True))

        return StreamingResponse(
            self._run_service.stream_run(
                builder=builder,
                runner=runner,
                cache=cache,
                trigger=trigger,
                chunk_serializer=OpenAIProxyChatCompletionChunk.stream_serializer(
                    agent_id=prepared_run.variant.task_id,
                    model=body.model,
                    output_mapper=output_mapper,
                    deprecated_function=body.uses_deprecated_functions,
                    aggregate_content=aggregate_content,
                ),
                serializer=OpenAIProxyChatCompletionChunk.serializer(
                    model=body.model,
                    deprecated_function=body.uses_deprecated_functions,
                    output_mapper=output_mapper,
                    feedback_generator=_feedback_generator,
                    aggregate_content=aggregate_content,
                ),
                source=source,
            ),
            media_type="text/event-stream",
        )

    @classmethod
    async def missing_model_error(cls, model: str | None, prefix: str = ""):
        _check_lineup = f"Check the lineup 👉 {WORKFLOWAI_APP_URL} ({MODEL_COUNT} models)"
        _curl_command = "curl https://run.workflowai.com/v1/models"
        if not model:
            return BadRequestError(
                f"""Empty model
{_check_lineup}
To list all models programmatically: {_curl_command}""",
            )

        components = [
            f"Unknown {prefix}model: {model}",
            _check_lineup,
            f"To list all models programmatically: {_curl_command}",
        ]
        if suggested := await ModelsService.suggest_model(model):
            components.insert(1, f"Did you mean {suggested}?")
        return BadRequestError("\n".join(components))
