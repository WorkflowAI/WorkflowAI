import asyncio
import copy
import json
import logging
import os
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Annotated, Any, AsyncIterator, Literal, NamedTuple, Optional, Sequence, overload

import workflowai

from api.services.internal_tasks._internal_tasks_utils import (
    OFFICIALLY_SUGGESTED_TOOLS,
    file_to_image,
    internal_tools_description,
    officially_suggested_tools,
)
from api.services.internal_tasks.improve_prompt_service import ImprovePromptService
from api.services.internal_tasks.instructions_service import InstructionsService
from api.services.internal_tasks.moderation_service import ModerationService
from api.services.internal_tasks.task_input_service import TaskInputService
from api.services.tasks import list_agent_summaries
from core.agents.chat_task_schema_generation.chat_task_schema_generation_task import (
    INSTRUCTIONS as AGENT_BUILDER_INSTRUCTIONS,
)
from core.agents.chat_task_schema_generation.chat_task_schema_generation_task import (
    OUTPUT_SCHEMA_INSTRUCTIONS,
    AgentBuilderInput,
    AgentBuilderOutput,
    AgentSchemaJson,
    ChatMessageWithExtractedURLContent,
    InputObjectFieldConfig,
    OutputObjectFieldConfig,
    agent_builder,
    agent_builder_wrapper,
    output_schema_builder_wrapper,
)
from core.agents.chat_task_schema_generation.chat_task_schema_generation_task_utils import (
    build_json_schema_with_defs,
    sanitize_agent_name,
)
from core.agents.describe_images import DescribeImagesWithContextTaskInput, describe_images_with_context
from core.agents.evaluate_output import EvaluateOutputTaskInput, evaluate_output
from core.agents.extract_company_info_from_domain_task import safe_generate_company_description_from_email
from core.agents.generate_changelog import (
    GenerateChangelogFromPropertiesTaskInput,
    Properties,
    Schema,
    TaskGroupWithSchema,
    generate_changelog_from_properties,
)
from core.agents.generate_task_preview import (
    GenerateTaskPreviewTaskInput,
    GenerateTaskPreviewTaskOutput,
    stream_generate_task_preview,
)
from core.agents.input_generation_instructions_agent import (
    InputGenerationInstructionsInput,
    run_input_generation_instructions,
)
from core.agents.reformat_instructions_task import (
    AgentInstructionsReformatingInput,
    format_instructions,
)
from core.agents.task_description_generation_task import (
    TaskDescriptionGenerationTaskInput,
    stream_task_description_generation,
)
from core.agents.task_input_example.task_input_example_task import (
    TaskInputExampleTaskInput,
    TaskInputExampleTaskOutput,
    run_task_input_example_task,
    stream_task_input_example_task,
)
from core.agents.task_input_example.task_input_migration_task import (
    TaskInputMigrationTaskInput,
    run_task_input_migration_task,
    stream_task_input_migration_task,
)
from core.agents.task_instruction_generation.task_instructions_generation_task import (
    AgentInstructionsGenerationTaskInput,
    agent_instructions_redaction,
)
from core.agents.task_instruction_required_tools_picking.task_instructions_required_tools_picking_task import (
    TaskInstructionsRequiredToolsPickingTaskInput,
    run_task_instructions_required_tools_picking,
)
from core.agents.task_instructions_migration_task import (
    AgentInstructionsMigrationInput,
    agent_instructions_migration,
)
from core.agents.update_correct_outputs_and_instructions import (
    PreviousEvaluationResult,
    UpdateCorrectOutputsAndInstructionsTaskInput,
    update_correct_outputs_and_instructions,
)
from core.agents.url_finder_agent import URLFinderAgentInput, url_finder_agent
from core.domain.changelogs import VersionChangelog
from core.domain.errors import InternalError, JSONSchemaValidationError, UnparsableChunkError
from core.domain.events import AgentInstructionsGeneratedEvent, EventRouter
from core.domain.fields.chat_message import ChatMessage
from core.domain.input_evaluation import InputEvaluation
from core.domain.models import Model
from core.domain.run_identifier import RunIdentifier
from core.domain.task_evaluation import TaskEvaluationScore
from core.domain.task_evaluator import EvalV2Evaluator
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_io import SerializableTaskIO
from core.domain.task_variant import SerializableTaskVariant
from core.domain.types import AgentInput
from core.domain.url_content import URLContent
from core.providers.base.provider_error import FailedGenerationError
from core.runners.workflowai.utils import FileWithKeyPath
from core.runners.workflowai.workflowai_runner import WorkflowAIRunner
from core.storage.backend_storage import BackendStorage, SystemBackendStorage
from core.tools import ToolKind
from core.utils.schema_sanitation import streamline_schema
from core.utils.schemas import EXPLAINATION_KEY, schema_needs_explanation, strip_json_schema_metadata_keys
from core.utils.url_utils import extract_and_fetch_urls


class AgentUids(NamedTuple):
    agent_uid: int
    tenant_uid: int


QUICK_MODEL = Model(os.environ.get("QUICK_MODEL", Model.GPT_4O_MINI_2024_07_18))
AUDIO_TRANSCRIPTION_MODEL = Model(os.environ.get("AUDIO_TRANSCRIPTION_MODEL", Model.GEMINI_1_5_FLASH_002))

DEFAULT_NEW_TASK_ASSISTANT_ANSWER_WITH_SCHEMA = "Here is the schema for task."
DEFAULT_NEW_TASK_ASSISTANT_ANSWER_WITHOUT_SCHEMA = "I did not understand your request. Can you try again ?"


class InternalTasksService:
    def __init__(self, storage: BackendStorage, event_router: EventRouter):
        self.logger = logging.getLogger(self.__class__.__name__)

        self.storage = storage
        self._event_router = event_router

    @property
    def input_import(self) -> TaskInputService:
        return TaskInputService()

    @property
    def improve_prompt(self) -> ImprovePromptService:
        return ImprovePromptService(self.storage)

    @property
    def instructions(self) -> InstructionsService:
        return InstructionsService()

    @property
    def moderation(self) -> ModerationService:
        return ModerationService()

    # ----------------------------------------
    # New task schema creation (new_task)

    async def _extract_url_content(self, text: str) -> list[URLContent]:
        return await extract_and_fetch_urls(text)

    async def _prepare_agent_builder_input(
        self,
        chat_messages: list[ChatMessage],
        user_email: str | None,
        existing_task: AgentSchemaJson | None = None,
    ) -> AgentBuilderInput:
        # Concurrently extract company info and list current agents
        company_description, current_agents = await asyncio.gather(
            safe_generate_company_description_from_email(
                user_email,
            ),
            list_agent_summaries(self.storage, limit=10),
        )
        current_agents = [str(agent) for agent in current_agents]

        new_message = chat_messages[-1]

        return AgentBuilderInput(
            previous_messages=chat_messages[:-1],
            new_message=ChatMessageWithExtractedURLContent(
                role=new_message.role,
                content=new_message.content,
                extracted_url_content=await self._extract_url_content(new_message.content),
            ),
            existing_agent_schema=existing_task,
            user_context=AgentBuilderInput.UserContent(
                company_name=company_description.company_name if company_description else None,
                company_description=company_description.description if company_description else None,
                company_locations=company_description.locations if company_description else None,
                company_industries=company_description.industries if company_description else None,
                company_products=company_description.products if company_description else None,
                current_agents=current_agents,
            ),
            available_tools_description=officially_suggested_tools(),
        )

    def _build_input_schema(self, input_schema: InputObjectFieldConfig | None) -> dict[str, Any] | None:
        computed = build_json_schema_with_defs(input_schema)
        if not computed:
            return None
        computed = streamline_schema(computed)
        return strip_json_schema_metadata_keys(
            computed,
            {"examples"},
        )

    def _build_output_schema(self, output_schema: OutputObjectFieldConfig | None) -> dict[str, Any] | None:
        computed = build_json_schema_with_defs(output_schema)
        if not computed:
            return None
        computed = streamline_schema(computed)
        return strip_json_schema_metadata_keys(
            computed,
            {"examples"},
            filter=lambda d: d.get("type") != "string" or "enum" in d,
        )

    def _build_agent_schema(
        self,
        name: str,
        input_schema: InputObjectFieldConfig | None,
        output_schema: OutputObjectFieldConfig | None,
        partial: bool,
    ) -> AgentSchemaJson:
        output_json_schema = self._build_output_schema(output_schema)
        if output_json_schema and not partial:
            # We only add explaination when the schema is finalized to avoid mistakenly adding it to an intermediate state
            output_json_schema = self.add_explanation_to_schema_if_needed(output_json_schema, self.logger)

        return AgentSchemaJson(
            agent_name=sanitize_agent_name(name),
            input_json_schema=self._build_input_schema(input_schema),
            output_json_schema=output_json_schema,
        )

    @classmethod
    def add_explanation_to_schema_if_needed(cls, schema: dict[str, Any], logger: logging.Logger) -> dict[str, Any]:
        updated_schema = copy.deepcopy(schema)
        try:
            # TODO: there is some logic overlap between 'add_explanation_to_schema_if_needed' and 'schema_needs_explanation'
            # Merge functions ?
            if schema_needs_explanation(updated_schema):
                if not updated_schema.get("type") == "object" or not updated_schema.get("properties"):
                    logger.warning(
                        "Schema is an enum or boolean, but is not an object with properties",
                        extra={"schema": updated_schema},
                    )
                    return updated_schema

                if EXPLAINATION_KEY in updated_schema["properties"]:
                    logger.warning(
                        "Explanation already exists in schema",
                        extra={"schema": updated_schema},
                    )
                    return updated_schema

                updated_schema["properties"] = {
                    EXPLAINATION_KEY: {
                        "type": "string",
                        "description": "Explanation of the choices made in the output",
                    },
                    **updated_schema["properties"],
                }
            return updated_schema
        except Exception:
            logger.warning(
                "Error adding explanation to schema",
                exc_info=True,
            )
            return updated_schema

    async def run_task_schema_iterations(
        self,
        chat_messages: list[ChatMessage],
        user_email: str | None,
        existing_task: AgentSchemaJson | None = None,
    ) -> tuple[
        Annotated[Optional[AgentSchemaJson], "The generated task schema (if any)"],
        Annotated[str, "The assistant's answer message"],
    ]:
        """
        Generates a new task (name, schema) based on natural language messages from the user.
        An optional existing task can be provided, in order to be updated
        """
        io_generation_output = await agent_builder(
            await self._prepare_agent_builder_input(chat_messages, user_email, existing_task),
            use_cache="always",
        )

        schema = None
        default_answer_to_user = DEFAULT_NEW_TASK_ASSISTANT_ANSWER_WITHOUT_SCHEMA
        if new_task_schema := io_generation_output.new_agent_schema:
            schema = self._build_agent_schema(
                new_task_schema.agent_name,
                new_task_schema.input_schema,
                new_task_schema.output_schema,
                partial=False,
            )
            default_answer_to_user = DEFAULT_NEW_TASK_ASSISTANT_ANSWER_WITH_SCHEMA

        return (
            schema,
            io_generation_output.answer_to_user or default_answer_to_user,
        )

    def _handle_stream_task_iterations_chunk(
        self,
        chunk: AgentBuilderOutput,
        partial: bool,
    ) -> tuple[Optional[AgentSchemaJson], str]:
        if not hasattr(chunk, "new_agent_schema") or chunk.new_agent_schema is None:
            return None, chunk.answer_to_user
        try:
            new_task_schema = self._build_agent_schema(
                chunk.new_agent_schema.agent_name,
                chunk.new_agent_schema.input_schema,
                chunk.new_agent_schema.output_schema,
                partial=partial,
            )

            return (
                new_task_schema,
                chunk.answer_to_user,
            )
        except Exception as e:
            raise UnparsableChunkError from e

    async def stream_task_schema_iterations(
        self,
        chat_messages: list[ChatMessage],
        user_email: str | None,
        existing_task: AgentSchemaJson | None = None,
        is_proxy_agent: bool = False,
    ) -> AsyncIterator[
        tuple[
            Annotated[Optional[AgentSchemaJson], "The generated task schema (if any)"],
            Annotated[str, "The assistant's answer message"],
        ]
    ]:
        AGENT_BUILDER_MODELS = [
            Model.CLAUDE_4_SONNET_20250514,
            Model.GPT_41_2025_04_14,  # TODO: use workflowai.Model when the model will be in the SDK
            Model.GROK_3_BETA,  # TODO: use workflowai.Model when the model will be in the SDK
        ]

        agent_input = await self._prepare_agent_builder_input(chat_messages, user_email, existing_task)

        for model in AGENT_BUILDER_MODELS:
            is_last_chance = model == AGENT_BUILDER_MODELS[-1]

            if is_proxy_agent:
                version = workflowai.VersionProperties(
                    model=model,
                    max_tokens=2500,  # Generated schema can be lengthy, so 2500 instead of 1000 of most Claude agents
                    instructions=OUTPUT_SCHEMA_INSTRUCTIONS,
                )

                iterator = output_schema_builder_wrapper(
                    agent_input,
                    version=version,
                    use_cache="always",
                )
            else:
                version = workflowai.VersionProperties(
                    model=model,
                    max_tokens=2500,  # Generated schema can be lengthy, so 2500 instead of 1000 of most Claude agents
                    instructions=AGENT_BUILDER_INSTRUCTIONS,
                )

                iterator = agent_builder_wrapper(
                    agent_input,
                    version=version,
                    use_cache="always",
                )
            chunk: AgentBuilderOutput | None = None
            latest_chunk_is_error = False
            async for chunk in iterator:
                try:
                    yield self._handle_stream_task_iterations_chunk(chunk, partial=True)
                    latest_chunk_is_error = False
                except UnparsableChunkError:
                    latest_chunk_is_error = True
                    # If anything goes wrong, we skip the chunk, because we may be in an intermediate state in the generation
            if chunk:
                try:
                    # We stream the last chunk with partial=False, because it is the final chunk
                    yield self._handle_stream_task_iterations_chunk(chunk, partial=False)
                    latest_chunk_is_error = False
                except UnparsableChunkError:
                    latest_chunk_is_error = True
                    # If anything goes wrong, we skip the chunk, because we may be in an intermediate state in the generation
            else:
                if is_last_chance:
                    error_message = "No agent builder chunk was generated"
                    self.logger.error(
                        error_message,
                    )
                    raise FailedGenerationError(error_message)
                else:
                    self.logger.warning(
                        "Agent builder failed to generate a valid chunk, trying with a different model",
                        extra={"model": model},
                    )
                    continue

            if latest_chunk_is_error:
                if is_last_chance:
                    error_message = "Agent builder failed to generate a final valid chunk"
                    self.logger.error(
                        error_message,
                    )
                    raise FailedGenerationError(error_message)
                else:
                    self.logger.warning(
                        "Agent builder failed to generate a valid chunk, trying with a different model",
                        extra={"model": model},
                    )
                    continue
            else:
                # We have a valid final chunk, we can return
                return

    async def generate_agent_instructions(
        self,
        task_id: str,
        task_schema_id: int,
        chat_messages: list[ChatMessage],
        task: AgentSchemaJson,
        required_tool_kinds: set[ToolKind],
    ) -> str:
        agent_instruction_generation_output = await agent_instructions_redaction(
            AgentInstructionsGenerationTaskInput(
                chat_messages=chat_messages,
                agent=AgentInstructionsGenerationTaskInput.Agent(
                    name=task.agent_name,
                    input_json_schema=task.input_json_schema or {},
                    output_json_schema=task.output_json_schema or {},
                ),
                available_tools_description=internal_tools_description(include=required_tool_kinds),
            ),
        )
        agent_instructions = agent_instruction_generation_output.agent_instructions

        if not agent_instructions:
            return ""

        self._event_router(
            AgentInstructionsGeneratedEvent(
                task_id=task_id,
                task_schema_id=task_schema_id,
                agent_instructions=agent_instructions,
            ),
        )

        agent_instructions_reformating_output = await format_instructions(
            AgentInstructionsReformatingInput(inital_agent_instructions=agent_instructions),
        )

        return agent_instructions_reformating_output.reformated_agent_instructions

    async def stream_agent_instructions(
        self,
        task_id: str,
        task_schema_id: int,
        chat_messages: list[ChatMessage],
        agent_schema: AgentSchemaJson,
        required_tool_kinds: set[ToolKind],
    ) -> AsyncIterator[str]:
        instrution_generation_input = AgentInstructionsGenerationTaskInput(
            chat_messages=chat_messages,
            agent=AgentInstructionsGenerationTaskInput.Agent(
                name=agent_schema.agent_name,
                input_json_schema=agent_schema.input_json_schema or {},
                output_json_schema=agent_schema.output_json_schema or {},
            ),
            available_tools_description=internal_tools_description(include=required_tool_kinds),
        )

        instructions_chunk = ""
        async for chunk in agent_instructions_redaction.stream(
            instrution_generation_input,
        ):
            if hasattr(chunk.output, "agent_instructions"):
                instructions_chunk = chunk.output.agent_instructions
                yield instructions_chunk or ""

        if not instructions_chunk:
            return

        self._event_router(
            AgentInstructionsGeneratedEvent(
                task_id=task_id,
                task_schema_id=task_schema_id,
                agent_instructions=instructions_chunk,
            ),
        )

        instructions_formating_output = await format_instructions(
            AgentInstructionsReformatingInput(inital_agent_instructions=instructions_chunk),
        )
        yield instructions_formating_output.reformated_agent_instructions

    async def update_task_instructions(
        self,
        initial_task_schema: AgentSchemaJson,
        initial_task_instructions: str,
        new_task_schema: AgentSchemaJson,
        chat_messages: list[ChatMessage],
        required_tool_kinds: set[ToolKind],
    ) -> str:
        task_instruction_update_output = await agent_instructions_migration(
            AgentInstructionsMigrationInput(
                initial_task_instructions=initial_task_instructions,
                initial_task_schema=initial_task_schema,
                chat_messages=chat_messages,
                new_task_schema=new_task_schema,
                available_tools_description=internal_tools_description(include=required_tool_kinds),
            ),
        )
        task_instructions = task_instruction_update_output.new_task_instructions

        task_reformating_output = await format_instructions(
            AgentInstructionsReformatingInput(inital_agent_instructions=task_instructions),
        )

        return task_reformating_output.reformated_agent_instructions

    async def stream_updated_instructions(
        self,
        initial_task_schema: AgentSchemaJson,
        initial_task_instructions: str,
        new_task_schema: AgentSchemaJson,
        chat_messages: list[ChatMessage],
        required_tool_kinds: set[ToolKind],
    ) -> AsyncIterator[str]:
        task_input = AgentInstructionsMigrationInput(
            initial_task_instructions=initial_task_instructions,
            initial_task_schema=initial_task_schema,
            chat_messages=chat_messages,
            new_task_schema=new_task_schema,
            available_tools_description=internal_tools_description(include=required_tool_kinds),
        )

        instructions_chunk = ""
        async for chunk in agent_instructions_migration.stream(
            task_input,
        ):
            if hasattr(chunk.output, "new_task_instructions"):
                instructions_chunk = chunk.output.new_task_instructions
                yield instructions_chunk

        task_reformating_output = await format_instructions(
            AgentInstructionsReformatingInput(inital_agent_instructions=instructions_chunk),
        )
        # To avoid starting over from the beginning of the instructions, and because the reformating task is fast,
        # we yield the result of the reformating task as an additional chunk.
        yield task_reformating_output.reformated_agent_instructions

    async def stream_suggested_instructions(
        self,
        task: SerializableTaskVariant,
        chat_messages: list[ChatMessage],
    ) -> AsyncIterator[str]:
        async def new_instructions_stream(
            required_tool_kinds: set[ToolKind],
        ):
            async for chunk in self.stream_agent_instructions(
                task_id=task.task_id,
                task_schema_id=task.task_schema_id,
                chat_messages=chat_messages,
                agent_schema=AgentSchemaJson(
                    agent_name=task.name,
                    input_json_schema=task.input_schema.model_dump(),
                    output_json_schema=task.output_schema.model_dump(),
                ),
                required_tool_kinds=required_tool_kinds,
            ):
                yield chunk

        async def migrated_instructions_stream(
            former_task: SerializableTaskVariant,
            initial_task_instructions: str,
            chat_messages: list[ChatMessage],
            required_tool_kinds: set[ToolKind],
        ):
            async for chunk in self.stream_updated_instructions(
                initial_task_schema=AgentSchemaJson(
                    agent_name=former_task.name,
                    input_json_schema=former_task.input_schema.json_schema,
                    output_json_schema=former_task.output_schema.json_schema,
                ),
                initial_task_instructions=initial_task_instructions,
                chat_messages=chat_messages,
                new_task_schema=AgentSchemaJson(
                    agent_name=task.name,
                    input_json_schema=task.input_schema.json_schema,
                    output_json_schema=task.output_schema.json_schema,
                ),
                required_tool_kinds=required_tool_kinds,
            ):
                yield chunk

        required_tool_kinds = await self.get_required_tool_kinds(
            task_name=task.name,
            input_json_schema=task.input_schema.json_schema,
            output_json_schema=task.output_schema.json_schema,
            chat_messages=chat_messages,
        )

        # First schema, generate new instructions.
        if task.task_schema_id == 1:
            return new_instructions_stream(required_tool_kinds)

        latest_group_same_schema = await self.storage.task_groups.get_latest_group_iteration(
            task.task_id,
            task.task_schema_id,
        )
        # If there is a group with the same schema id, generate new instructions, since the user new completly new instructions/
        if latest_group_same_schema:
            return new_instructions_stream(required_tool_kinds)

        latest_group_former_schema = await self.storage.task_groups.get_latest_group_iteration(
            task.task_id,
            task.task_schema_id - 1,
        )

        # If there is a group on a former schema, migrate those instructions
        if latest_group_former_schema is not None and latest_group_former_schema.properties.instructions:
            former_task = await self.storage.task_variants.get_latest_task_variant(
                task.task_id,
                task.task_schema_id - 1,
            )
            if former_task:
                return migrated_instructions_stream(
                    former_task=former_task,
                    initial_task_instructions=latest_group_former_schema.properties.instructions,
                    chat_messages=chat_messages,
                    required_tool_kinds=required_tool_kinds,
                )

        # In all other cases, generate new instructions
        return new_instructions_stream(required_tool_kinds)

    @classmethod
    def _get_available_tool_descriptions(
        cls,
    ) -> list[TaskInstructionsRequiredToolsPickingTaskInput.ToolDescriptionStr]:
        return [
            TaskInstructionsRequiredToolsPickingTaskInput.ToolDescriptionStr.from_tool_description(
                tool.definition,
            )
            for tool_kind, tool in WorkflowAIRunner.internal_tools.items()
            if tool_kind in OFFICIALLY_SUGGESTED_TOOLS
        ]

    async def _sanitize_required_tools(
        self,
        task_name: str,
        input_json_schema: dict[str, Any],
        required_tools_picking_run_id: str,
        picked_tools: set[ToolKind],
    ) -> set[ToolKind]:
        if picked_tools == {ToolKind.WEB_BROWSER_TEXT}:
            sanitized_picked_tools: set[ToolKind] = set()

            # If the only required tool is WEB_BROWSER_TEXT, we need to check if the agent is a 'scraping' agent
            # In order not to add WEB_BROWSER_TEXT for wrong reasons
            try:
                url_finder_run = await url_finder_agent(
                    URLFinderAgentInput(
                        agent_name=task_name,
                        agent_input_json_schema=input_json_schema,
                    ),
                )
                if url_finder_run.is_schema_containing_url:
                    # The agent is a 'scraping' agent, so we keep WEB_BROWSER_TEXT
                    sanitized_picked_tools = {ToolKind.WEB_BROWSER_TEXT}
                else:
                    self.logger.warning(
                        "The agent is not a 'scraping' agent, so we remove WEB_BROWSER_TEXT",
                        extra={"tool_picking_run": required_tools_picking_run_id},
                    )
                    # The agent is not a 'scraping' agent, so we remove WEB_BROWSER_TEXT
            except Exception as e:
                self.logger.exception("Error running URL finder agent", exc_info=e)

            return sanitized_picked_tools

        return picked_tools

    async def get_required_tool_kinds(
        self,
        task_name: str,
        input_json_schema: dict[str, Any],
        output_json_schema: dict[str, Any],
        chat_messages: list[ChatMessage],
    ) -> set[ToolKind]:
        required_tools_picking_run = await run_task_instructions_required_tools_picking(
            TaskInstructionsRequiredToolsPickingTaskInput(
                chat_messages=chat_messages,
                task=TaskInstructionsRequiredToolsPickingTaskInput.Task(
                    name=task_name,
                    input_json_schema=input_json_schema,
                    output_json_schema=output_json_schema,
                ),
                available_tools_description=self._get_available_tool_descriptions(),
            ),
            use_cache="always",
        )
        out: set[ToolKind] = set()
        for tool_handle in required_tools_picking_run.output.required_tools:
            try:
                out.add(ToolKind(tool_handle))
            except ValueError:
                self.logger.warning("Tool handle not found in ToolKind", extra={"tool_handle": tool_handle})
                continue

        return await self._sanitize_required_tools(task_name, input_json_schema, required_tools_picking_run.id, out)

    async def set_task_description_if_missing(
        self,
        task_id: str,
        task_schema_id: int,
        instructions: str,
    ) -> AsyncIterator[str]:
        """
        Generates and streams a concise description for a given task schema, if needed.
        """

        task_info = await self.storage.tasks.get_task_info(task_id)

        if task_info.description:
            yield task_info.description
            return

        task_variant = await self.storage.task_variant_latest_by_schema_id(task_id, task_schema_id)

        task_schema = AgentSchemaJson(
            agent_name=task_variant.name,
            input_json_schema=task_variant.input_schema.json_schema,
            output_json_schema=task_variant.output_schema.json_schema,
        )

        task_input = TaskDescriptionGenerationTaskInput(
            chat_messages=[],
            task_schema=AgentSchemaJson(
                agent_name=task_schema.agent_name,
                input_json_schema=task_schema.input_json_schema,
                output_json_schema=task_schema.output_json_schema,
            ),
            task_instructions=instructions,
        )

        description_chunk = ""
        async for chunk in stream_task_description_generation(task_input):
            description_chunk = chunk.task_description
            yield description_chunk

        # Persist the complete task description in storage
        await self.storage.set_task_description(task_id, description_chunk or "")

    # ----------------------------------------
    # Generate inputs

    async def _get_input_gen_task_uid_and_tenant_uid(self) -> AgentUids | None:
        try:
            if not stream_task_input_example_task.agent_uid or not stream_task_input_example_task.tenant_uid:
                await stream_task_input_example_task.register()
            return AgentUids(
                agent_uid=stream_task_input_example_task.agent_uid,
                tenant_uid=stream_task_input_example_task.tenant_uid,
            )
        except Exception as e:
            self.logger.exception("Error while fetching task input example task", exc_info=e)
            return None

    async def _fetch_previous_task_inputs(
        self,
        task: SerializableTaskVariant,
        system_storage: SystemBackendStorage,
        memory_id: str,
    ) -> list[dict[str, Any]] | None:
        # TODO: there is a chance that the run will occur in a different environment that the
        # current one. For example, if staging uses the production run endpoint. This would
        # mean that the query will never return any results.
        # Ultimately we should integrate the fetching to the SDK. `run_task_input_example_task.list_runs`
        # To ensure that we always fetch from the same environment.

        input_gen_agent_uids = await self._get_input_gen_task_uid_and_tenant_uid()
        if input_gen_agent_uids is None or not input_gen_agent_uids.agent_uid or not input_gen_agent_uids.tenant_uid:
            self.logger.exception("Can't find the task input example task")
            return None

        validated = list[dict[str, Any]]()
        async for run in system_storage.task_runs.list_runs_for_memory_id(
            tenant_uid=input_gen_agent_uids.tenant_uid,
            task_uid=input_gen_agent_uids.agent_uid,
            memory_id=memory_id,
            limit=15,  # 15 to have even more diversity
        ):
            try:
                output = TaskInputExampleTaskOutput.model_validate(run.task_output)
                if output.task_input:
                    validated.append(output.task_input)
            except Exception:
                self.logger.exception(
                    "Failed to validate previous task input",
                    extra={"run": run.model_dump(mode="json")},
                )

        return validated or None

    @overload
    async def generate_task_input(
        self,
        task: SerializableTaskVariant,
        input_instructions: str,
        system_storage: SystemBackendStorage,
        stream: Literal[False],
    ) -> AgentInput:
        pass

    @overload
    async def generate_task_input(
        self,
        task: SerializableTaskVariant,
        input_instructions: str,
        system_storage: SystemBackendStorage,
        stream: Literal[True],
    ) -> AsyncIterator[AgentInput]:
        pass

    async def generate_task_input(
        self,
        task: SerializableTaskVariant,
        input_instructions: str,
        system_storage: SystemBackendStorage,
        stream: bool,
    ) -> AgentInput | AsyncIterator[AgentInput]:
        task_input_generation_instructions_run = await run_input_generation_instructions(
            InputGenerationInstructionsInput(
                creation_chat_messages=task.creation_chat_messages,
                agent_name=task.name,
                input_json_schema=task.input_schema.json_schema,
                output_json_schema=task.output_schema.json_schema,
            ),
        )

        gen_task_input = TaskInputExampleTaskInput(
            current_datetime=datetime.now(timezone.utc).isoformat(),
            task_name=task.name,
            input_json_schema=task.input_schema.json_schema,
            output_json_schema=task.output_schema.json_schema,
            additional_instructions=input_instructions
            + (task_input_generation_instructions_run.input_generation_instructions or ""),
            additional_instructions_url_contents=await extract_and_fetch_urls(input_instructions),
        )
        metadata = {"memory_id": gen_task_input.memory_id()}

        try:
            gen_task_input.previous_task_inputs = await self._fetch_previous_task_inputs(
                task=task,
                system_storage=system_storage,
                memory_id=metadata["memory_id"],
            )
        except Exception as e:
            self.logger.exception("Failed to fetch previous task inputs", exc_info=e)
            gen_task_input.previous_task_inputs = None

        if stream:
            return self._stream_task_inputs(
                input_factory=lambda i: task.validate_input(i, partial=True),
                input=gen_task_input,
                metadata=metadata,
            )

        task_run = await run_task_input_example_task(
            gen_task_input,
            metadata=metadata,
        )
        return task.validate_input(task_run.task_input)

    async def _stream_task_inputs(
        self,
        input_factory: Callable[[dict[str, Any]], AgentInput],
        input: TaskInputExampleTaskInput,
        metadata: dict[str, Any],
    ):
        async for chunk in stream_task_input_example_task(
            input,
            metadata=metadata,
        ):
            if not chunk.task_input:
                continue

            yield input_factory(chunk.task_input)

    async def _stream_migrated_task_inputs(
        self,
        input_factory: Callable[[dict[str, Any]], AgentInput],
        input: TaskInputMigrationTaskInput,
    ):
        async for chunk in stream_task_input_migration_task(
            input,
        ):
            if not chunk.migrated_task_input:
                continue

            yield input_factory(chunk.migrated_task_input)

    @overload
    async def get_task_input(
        self,
        task: SerializableTaskVariant,
        input_instructions: str,
        base_input: dict[str, Any] | None,
        system_storage: SystemBackendStorage,
        stream: Literal[False] = False,
    ) -> AgentInput:
        pass

    @overload
    async def get_task_input(
        self,
        task: SerializableTaskVariant,
        input_instructions: str,
        base_input: dict[str, Any] | None,
        system_storage: SystemBackendStorage,
        stream: Literal[True],
    ) -> AsyncIterator[AgentInput]:
        pass

    async def get_task_input(
        self,
        task: SerializableTaskVariant,
        input_instructions: str,
        base_input: dict[str, Any] | None,
        system_storage: SystemBackendStorage,
        stream: bool = False,
    ) -> AgentInput | AsyncIterator[AgentInput]:
        if base_input:  # In this case we migrate the 'base_input' to the new schema
            migration_input = TaskInputMigrationTaskInput(
                current_datetime=datetime.now(timezone.utc).isoformat(),
                task_name=task.name,
                base_input=base_input,
                input_json_schema=task.input_schema.json_schema,
                output_json_schema=task.output_schema.json_schema,
            )

            if stream:
                return self._stream_migrated_task_inputs(
                    input_factory=lambda i: task.validate_input(i, partial=True),
                    input=migration_input,
                )

            migration_output = await run_task_input_migration_task(
                migration_input,
            )
            return task.validate_input(migration_output.migrated_task_input)

        # If there is no base input, we generate a completelly new input
        if stream:  # This if is purely for typing reasons
            return await self.generate_task_input(
                task=task,
                input_instructions=input_instructions,
                system_storage=system_storage,
                stream=True,
            )

        return await self.generate_task_input(
            task=task,
            input_instructions=input_instructions,
            system_storage=system_storage,
            stream=False,
        )

    async def generate_changelog(
        self,
        tenant: str,
        task_id: str,
        task_schema_id: int,
        major_from: int,
        old_task_group: TaskGroupProperties,
        major_to: int,
        new_task_group: TaskGroupProperties,
    ) -> VersionChangelog | None:
        new_task_variant_id = new_task_group.task_variant_id
        old_task_variant_id = old_task_group.task_variant_id

        old_task_group_with_schema = TaskGroupWithSchema(
            properties=Properties(
                instructions=old_task_group.instructions,
                temperature=old_task_group.temperature,
                few_shot=old_task_group.few_shot is not None,
            ),
            schema=None,
        )

        new_task_group_with_schema = TaskGroupWithSchema(
            properties=Properties(
                instructions=new_task_group.instructions,
                temperature=new_task_group.temperature,
                few_shot=new_task_group.few_shot is not None,
            ),
            schema=None,
        )

        generate_changelog_input = GenerateChangelogFromPropertiesTaskInput(
            old_task_group=old_task_group_with_schema,
            new_task_group=new_task_group_with_schema,
        )

        if new_task_variant_id and old_task_variant_id and new_task_variant_id != old_task_variant_id:
            old_task_schema = await self.storage.task_version_resource_by_id(task_id, old_task_variant_id)
            new_task_schema = await self.storage.task_version_resource_by_id(task_id, new_task_variant_id)

            old_task_group_with_schema.schema_ = Schema.from_task_variant(old_task_schema)
            new_task_group_with_schema.schema_ = Schema.from_task_variant(new_task_schema)

        changelog_response = await generate_changelog_from_properties(
            generate_changelog_input,
            metadata={
                "changelog.tenant": tenant,
                "changelog.task_id": task_id,
                "changelog.task_schema_id": task_schema_id,
                "changelog.major_from": major_from,
                "changelog.major_to": major_to,
            },
        )
        if not changelog_response.changes:
            return None

        return VersionChangelog(
            task_id=task_id,
            task_schema_id=task_schema_id,
            similarity_hash_from=old_task_group.similarity_hash,
            similarity_hash_to=new_task_group.similarity_hash,
            major_from=major_from,
            major_to=major_to,
            changelog=[c.replace("\\n", "\n") for c in changelog_response.changes],
        )

    # TODO: test
    async def update_correct_outputs_and_instructions(
        self,
        evaluation_instructions: str,
        input_evaluation: InputEvaluation,
        evaluated_output: dict[str, Any],
        previous_evaluation_result: TaskEvaluationScore,
        user_rating_is_correct: bool,
        user_feedback: str | None,
    ) -> tuple[EvalV2Evaluator, InputEvaluation]:
        match previous_evaluation_result:
            case TaskEvaluationScore.PASS:
                prev = PreviousEvaluationResult.PASS
            case TaskEvaluationScore.FAIL:
                prev = PreviousEvaluationResult.FAIL
            case TaskEvaluationScore.UNSURE:
                prev = PreviousEvaluationResult.UNSURE
        task_input = UpdateCorrectOutputsAndInstructionsTaskInput(
            correct_outputs=[json.dumps(i) for i in input_evaluation.correct_outputs],
            incorrect_outputs=[json.dumps(i) for i in input_evaluation.incorrect_outputs],
            evaluated_output=json.dumps(evaluated_output),
            evaluation_result=prev,
            evaluation_instruction=evaluation_instructions,
            why_is_the_evaluated_output_also_correct=user_feedback if user_rating_is_correct else None,
            why_is_the_evaluated_output_incorrect=user_feedback if not user_rating_is_correct else None,
        )
        run = await update_correct_outputs_and_instructions(task_input)

        try:
            new_correct_outputs = (
                [json.loads(i) for i in run.output.updated_correct_outputs]
                if run.output.updated_correct_outputs
                else []
            )
            new_incorrect_outputs = (
                [json.loads(i) for i in run.output.updated_incorrect_outputs]
                if run.output.updated_incorrect_outputs
                else []
            )
        except json.JSONDecodeError as e:
            raise InternalError(
                "Failed to decode task outputs",
                extras={"task_output": run.model_dump(mode="json")},
            ) from e

        run_identifier = RunIdentifier(
            tenant="workflowai",  # TODO: Use the actual tenant
            task_id=run.agent_id,
            task_schema_id=run.schema_id,
            run_id=run.id,
        )

        return EvalV2Evaluator(
            instructions=run.output.updated_evaluation_instruction or "",
            instructions_updated_by=run_identifier,
        ), InputEvaluation(
            task_input_hash=input_evaluation.task_input_hash,
            correct_outputs=new_correct_outputs,
            incorrect_outputs=new_incorrect_outputs,
            created_by=run_identifier,
            evaluation_instruction=run.output.update_evaluation_instruction_for_input,
        )

    async def describe_images(self, images: Sequence[FileWithKeyPath], instructions: str | None) -> list[str] | None:
        task_input = DescribeImagesWithContextTaskInput(
            images=[file_to_image(i) for i in images],
            instructions=instructions or None,
        )
        return (await describe_images_with_context(task_input)).image_descriptions

    async def evaluate_output(self, task_input: EvaluateOutputTaskInput):
        return await evaluate_output(task_input)

    def stream_generate_task_preview(
        self,
        task_input: GenerateTaskPreviewTaskInput,
    ) -> AsyncIterator[GenerateTaskPreviewTaskOutput]:
        self._feed_input_validation_error(task_input)
        self._feed_output_validation_error(task_input)
        return stream_generate_task_preview(task_input)

    def _feed_input_validation_error(self, task_input: GenerateTaskPreviewTaskInput) -> None:
        if task_input.current_preview is None:
            return

        self._validate_preview_field(
            task_input,
            schema=task_input.task_input_schema,
            value=task_input.current_preview.input,
            error_attr="current_preview_input_validation_error",
        )

    def _feed_output_validation_error(self, task_input: GenerateTaskPreviewTaskInput) -> None:
        if task_input.current_preview is None:
            return

        self._validate_preview_field(
            task_input,
            schema=task_input.task_output_schema,
            value=task_input.current_preview.output,
            error_attr="current_preview_output_validation_error",
        )

    def _validate_preview_field(
        self,
        task_input: GenerateTaskPreviewTaskInput,
        schema: dict[str, Any],
        value: dict[str, Any],
        error_attr: str,
    ) -> None:
        try:
            # In some cases, $defs are missing from the schema sent by the frontend.
            # Ex: when the user manually added a "document" field to the schema.
            schema = streamline_schema(schema)

            agent_io = SerializableTaskIO(
                json_schema=schema,
                version="1",
            )
            agent_io.enforce(value)
        except JSONSchemaValidationError as e:
            setattr(task_input, error_attr, str(e))
        except Exception as e:
            self.logger.exception("Unexpected error while validating current preview", exc_info=e)
