import json
import logging
from typing import Any, AsyncIterator

from workflowai import Model

from api.services.internal_tasks._internal_tasks_utils import officially_suggested_tools
from core.agents.chat_task_schema_generation.apply_field_updates import (
    InputFieldUpdate,
    OutputFieldUpdate,
    apply_field_updates,
)
from core.agents.improve_prompt import (
    ImprovePromptAgentInput,
    ImprovePromptAgentOutput,
    run_improve_prompt_agent,
)
from core.agents.improve_version_messages_agent import (
    ImproveVersionMessagesInput,
    ImproveVersionMessagesResponse,
    improve_version_messages_agent,
)
from core.domain.agent_run import AgentRun
from core.domain.message import Message
from core.domain.task_group import TaskGroup
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_io import SerializableTaskIO
from core.domain.task_variant import SerializableTaskVariant
from core.storage import TaskTuple
from core.storage.backend_storage import BackendStorage
from core.utils.models.dumps import safe_dump_pydantic_model
from core.utils.schema_sanitation import streamline_schema
from core.utils.schemas import strip_json_schema_metadata_keys
from core.utils.templates import extract_variable_schema
from core.utils.url_utils import extract_and_fetch_urls

IMPROVE_PROMPT_MODELS = (
    Model.GEMINI_2_0_FLASH_001,  # To iterate really quick, and smartly
    Model.O3_MINI_2025_01_31_MEDIUM_REASONING_EFFORT,  # Strong struct gen model, if Gemini fails
    Model.CLAUDE_3_7_SONNET_20250219,  # In case OpenAI is down...
)


class ImprovePromptService:
    def __init__(self, storage: BackendStorage):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._storage = storage

    async def improve_version_messages(
        self,
        version_messages: list[Message],
        run: AgentRun | None = None,
        improvement_instructions: str | None = None,
    ) -> AsyncIterator[ImproveVersionMessagesResponse]:
        agent_input = ImproveVersionMessagesInput(
            initial_messages=[message.model_dump(exclude_none=True) for message in version_messages or []],
            run=ImproveVersionMessagesInput.Run(
                input=json.dumps(run.task_input) if run.task_input else "",
                output=json.dumps(run.task_output) if run.task_output else "",
            )
            if run
            else None,
            improvement_instructions=improvement_instructions,
        )

        async for chunk in improve_version_messages_agent(agent_input):
            yield chunk

    async def _prepare_improve_prompt_input(
        self,
        task_tuple: TaskTuple,
        run_id: str | None,
        variant_id: str | None,
        instructions: str | None,
        user_evaluation: str,
    ):
        """Returns a tuple of ImprovePromptAgentInput, variant and baseline task group properties"""

        run: AgentRun | None = None
        version: TaskGroup | None = None
        if run_id:
            run = await self._storage.task_runs.fetch_task_run_resource(
                task_tuple,
                run_id,
                include={"version_id", "task_input", "task_output"},
            )
            version = await self._storage.task_groups.get_task_group_by_id(task_tuple[0], run.group.id)
            instructions = version.properties.instructions  # OK to override non-mutable parameters
            variant_id = version.properties.task_variant_id  # OK to override non-mutable parameters

        variant = await self._storage.task_version_resource_by_id(task_tuple[0], variant_id) if variant_id else None
        url_contents = await extract_and_fetch_urls(user_evaluation)

        input_ = ImprovePromptAgentInput(
            original_agent_config=ImprovePromptAgentInput.AgentConfig(
                prompt=instructions,
                input_schema=variant.input_schema.json_schema if variant else None,
                output_schema=variant.output_schema.json_schema if variant else None,
            ),
            agent_run=ImprovePromptAgentInput.AgentRun(
                run_input=json.dumps(run.task_input),
                run_output=json.dumps(run.task_output),
                user_evaluation=user_evaluation,
                user_evaluation_url_contents=url_contents,
            )
            if run
            else None,
            user_evaluation=user_evaluation,
            available_tools_description=officially_suggested_tools(),
        )
        return input_, variant, version.properties.model_dump(exclude_none=True) if version else {}

    async def run(
        self,
        task_tuple: TaskTuple,
        run_id: str | None,
        variant_id: str | None,
        instructions: str | None,
        user_evaluation: str,
    ):
        improve_prompt_input, variant, properties = await self._prepare_improve_prompt_input(
            task_tuple,
            run_id,
            variant_id,
            instructions,
            user_evaluation,
        )

        for model in IMPROVE_PROMPT_MODELS:
            try:
                res = await run_improve_prompt_agent(improve_prompt_input, model=model)
                updated_properties = {**properties, "instructions": res.improved_prompt}

                if not self._ensure_no_new_input_variables_added(instructions or "", res.improved_prompt or ""):
                    # No input variables should be added by the improve prompt agent, if that happens, we return the original properties
                    self._logger.warning(
                        "New input variables were added by improve prompt agent",
                        extra={
                            "original_instructions": instructions,
                            "improved_instructions": res.improved_prompt,
                        },
                    )
                    return TaskGroupProperties.model_validate(properties), ["Failed to improve prompt"]

                if created := await self._safe_handle_improved_output_schema(
                    variant,
                    res.input_field_updates,
                    res.output_field_updates,
                ):
                    updated_properties["task_variant_id"] = created
                return TaskGroupProperties.model_validate(updated_properties), res.changelog
            except Exception as e:
                self._logger.exception(
                    "Error running improve prompt",
                    exc_info=e,
                )
        # If all model have failed, there is something weird with the use case, we return the original properties
        return TaskGroupProperties.model_validate(properties), ["Failed to improve prompt"]

    def _ensure_no_new_input_variables_added(self, original_instructions: str, improved_instructions: str) -> bool:
        original_variables = extract_variable_schema(original_instructions)
        improved_variables = extract_variable_schema(improved_instructions)
        return original_variables == improved_variables

    async def stream(
        self,
        task_tuple: TaskTuple,
        run_id: str | None,
        variant_id: str | None,
        instructions: str | None,
        user_evaluation: str,
    ) -> AsyncIterator[tuple[TaskGroupProperties, list[str] | None]]:
        improve_prompt_input, variant, properties = await self._prepare_improve_prompt_input(
            task_tuple,
            run_id,
            variant_id,
            instructions,
            user_evaluation,
        )

        chunk: ImprovePromptAgentOutput | None = None

        for model in IMPROVE_PROMPT_MODELS:
            try:
                async for payload in run_improve_prompt_agent.stream(improve_prompt_input, model=model):
                    chunk = payload.output
                    yield (
                        TaskGroupProperties.model_validate(
                            {**properties, "instructions": chunk.improved_prompt},
                        ),
                        chunk.changelog,
                    )

                if (
                    chunk
                    and chunk.improved_prompt
                    and not self._ensure_no_new_input_variables_added(instructions or "", chunk.improved_prompt)
                ):
                    # No input variables should be added by the improve prompt agent, if that happens, we return the original properties
                    self._logger.warning(
                        "New input variables were added by improve prompt agent",
                        extra={
                            "original_instructions": instructions,
                            "improved_instructions": chunk.improved_prompt,
                        },
                    )
                    yield (
                        TaskGroupProperties.model_validate(
                            {**properties, "instructions": instructions},
                        ),
                        [],
                    )
                    return

                if chunk:
                    if created_variant := await self._safe_handle_improved_output_schema(
                        variant,
                        chunk.input_field_updates,
                        chunk.output_field_updates,
                    ):
                        # We yield one last time to include the new variant
                        yield (
                            TaskGroupProperties.model_validate(
                                {
                                    **properties,
                                    "instructions": chunk.improved_prompt,
                                    "task_variant_id": created_variant,
                                },
                            ),
                            chunk.changelog,
                        )

                return
            except Exception as e:
                self._logger.exception(
                    "Error streaming improve prompt",
                    exc_info=e,
                )
        # If all model have failed, there is something weird with the use case, we return the original properties
        yield (TaskGroupProperties.model_validate(properties), ["Failed to improve prompt"])

    async def _safe_handle_improved_output_schema(
        self,
        task_variant: SerializableTaskVariant | None,
        input_field_updates: list[InputFieldUpdate] | None,
        output_field_updates: list[OutputFieldUpdate] | None,
    ):
        if not task_variant:
            return None

        try:
            return await self._handle_improved_output_schema(task_variant, input_field_updates, output_field_updates)
        except Exception as e:
            self._logger.exception(
                "Error handling improved output schema",
                exc_info=e,
                extra={
                    "output_schema": task_variant.output_schema.json_schema,
                    "input_field_updates": safe_dump_pydantic_model(input_field_updates),
                    "output_field_updates": safe_dump_pydantic_model(output_field_updates),
                },
            )
            return None

    def _schema_with_updates(
        self,
        schema: dict[str, Any],
        updates: list[InputFieldUpdate] | list[OutputFieldUpdate],
    ) -> dict[str, Any]:
        if not updates:
            return schema

        computed = streamline_schema(apply_field_updates(schema, updates))
        # Removing examples from non string or enum fields
        # TODO: is that actually desired ? we might have weird cases where
        # the changelog is different from what actually happned
        return strip_json_schema_metadata_keys(
            computed,
            {"examples"},
            filter=lambda d: d.get("type") != "string" or "enum" in d,
        )

    async def _handle_improved_output_schema(
        self,
        task_variant: SerializableTaskVariant,
        input_field_updates: list[InputFieldUpdate] | None,
        output_field_updates: list[OutputFieldUpdate] | None,
    ):
        # No update to apply, early return
        if not input_field_updates and not output_field_updates:
            return None

        input_schema = (
            self._schema_with_updates(task_variant.input_schema.json_schema, input_field_updates)
            if input_field_updates is not None
            else task_variant.input_schema.json_schema
        )

        output_schema = (
            self._schema_with_updates(task_variant.output_schema.json_schema, output_field_updates)
            if output_field_updates is not None
            else task_variant.output_schema.json_schema
        )

        # Store the new task variant
        new_task_variant = SerializableTaskVariant(
            id="",
            task_id=task_variant.task_id,
            task_schema_id=0,
            name="",
            input_schema=SerializableTaskIO.from_json_schema(input_schema),
            output_schema=SerializableTaskIO.from_json_schema(output_schema),
        )
        created, _ = await self._storage.store_task_resource(new_task_variant)
        return created.id
