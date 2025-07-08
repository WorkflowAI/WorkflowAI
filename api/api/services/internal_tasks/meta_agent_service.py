import asyncio
import datetime
import logging
import re
from typing import Any, AsyncIterator, NamedTuple, TypeAlias, cast

import workflowai
from pydantic import BaseModel, Field, model_validator
from typing_extensions import Literal

from api.services.documentation_service import DocumentationService
from api.services.feedback_svc import FeedbackService
from api.services.internal_tasks._internal_tasks_utils import internal_tools_description
from api.services.models import ModelsService
from api.services.reviews import ReviewsService
from api.services.runs.runs_service import RunsService
from api.services.tasks import list_agent_summaries
from api.services.versions import VersionsService
from core.agents.extract_company_info_from_domain_task import (
    ExtractCompanyInfoFromDomainTaskOutput,
    safe_generate_company_description_from_email,
)
from core.agents.input_variables_extractor_agent import InputVariablesExtractorInput, input_variables_extractor_agent
from core.agents.meta_agent import (
    META_AGENT_INSTRUCTIONS,
    EditSchemaToolCallResult,
    GenerateAgentInputToolCallResult,
    ImprovePromptToolCallResult,
    InputFile,
    MetaAgentInput,
    MetaAgentOutput,
    RunCurrentAgentOnModelsToolCallRequest,
    RunCurrentAgentOnModelsToolCallResult,
    SelectedModels,
    meta_agent,
)
from core.agents.meta_agent import (
    MetaAgentChatMessage as MetaAgentChatMessageDomain,
)
from core.agents.meta_agent import (
    PlaygroundState as PlaygroundStateDomain,
)
from core.agents.meta_agent_proxy import (
    GENERIC_INSTRUCTIONS,
    HOSTED_TOOL_UPDATE_INSTRUCTIONS,
    PROPOSE_DEPLOYMENT_INSTRUCTIONS,
    PROPOSE_INPUT_VARIABLES_INSTRUCTIONS,
    PROPOSE_INPUT_VARIABLES_INSTRUCTIONS_NO_VERSION_MESSAGES,
    PROPOSE_NON_OPENAI_MODELS_INSTRUCTIONS,
    PROPOSE_STRUCTURED_OUTPUT_INSTRUCTIONS,
    GenerateAgentInputToolCallRequest,
    ProxyMetaAgentInput,
    ProxyMetaAgentOutput,
    proxy_meta_agent,
)
from core.agents.meta_agent_proxy import (
    AgentRun as ProxyAgentRun,
)
from core.agents.meta_agent_proxy import PlaygroundState as ProxyPlaygroundStateDomain
from core.agents.meta_agent_proxy import (
    ProxyMetaAgentChatMessage as ProxyMetaAgentChatMessageDomain,
)
from core.agents.meta_agent_user_confirmation_agent import (
    MetaAgentUserConfirmationInput,
    meta_agent_user_confirmation_agent,
)
from core.agents.output_schema_extractor_agent import OutputSchemaExtractorInput, output_schema_extractor_agent
from core.domain.agent_run import AgentRun
from core.domain.consts import METADATA_KEY_DEPLOYMENT_ENVIRONMENT
from core.domain.documentation_section import DocumentationSection
from core.domain.events import EventRouter, MetaAgentChatMessagesSent
from core.domain.fields.chat_message import ChatMessage
from core.domain.fields.file import File
from core.domain.integration.integration_domain import (
    Integration,
    ProgrammingLanguage,
)
from core.domain.integration.integration_mapping import (
    default_integration_for_language,
    safe_get_integration_by_kind,
)
from core.domain.models.model_data import LatestModel
from core.domain.models.model_data_mapping import MODEL_DATAS
from core.domain.models.model_provider_data_mapping import AZURE_PROVIDER_DATA, OPENAI_PROVIDER_DATA
from core.domain.models.models import Model
from core.domain.page import Page
from core.domain.task_variant import SerializableTaskVariant
from core.domain.url_content import URLContent
from core.runners.workflowai.utils import extract_files
from core.storage import ObjectNotFoundException, TaskTuple
from core.storage.backend_storage import BackendStorage
from core.tools import ToolKind
from core.utils.hash import compute_obj_hash
from core.utils.tool_utils.tool_utils import get_tools_description_openai_format_str
from core.utils.url_utils import extract_and_fetch_urls

FIRST_MESSAGE_CONTENT = "Hi, I'm WorkflowAI's AI Engineer. How can I help you?"


def _reverse_optional_bool(value: bool | None) -> bool | None:
    if value is None:
        return None
    return not value


def _remove_typescript_comments(content: str) -> str:
    # Remove /* */ comments, since the agent is VERY stubborn adding typescript comments in Python.
    return re.sub(r"/\*.*?\*/", "", content)


class HasActiveRunAndDate(NamedTuple):
    has_active_runs: bool
    latest_active_run_date: datetime.datetime | None


class MetaAgentContext(NamedTuple):
    company_description: ExtractCompanyInfoFromDomainTaskOutput | None
    existing_agents: list[str] | None
    agent_runs: list[AgentRun] | None
    feedback_page: Page[MetaAgentInput.AgentLifecycleInfo.FeedbackInfo.AgentFeedback] | None
    has_active_runs: HasActiveRunAndDate | None
    reviewed_input_count: int | None


class ProxyMetaAgentContext(NamedTuple):
    company_description: ExtractCompanyInfoFromDomainTaskOutput | None
    existing_agents: list[str] | None
    agent_runs: list[AgentRun] | None
    feedback_page: Page[ProxyMetaAgentInput.AgentLifecycleInfo.FeedbackInfo.AgentFeedback] | None
    has_active_runs: HasActiveRunAndDate | None
    reviewed_input_count: int | None
    playground_agent_runs: list[AgentRun] | None


def get_programming_language_for_user_agent(user_agent: str) -> ProgrammingLanguage:
    user_agent = user_agent.lower()
    if "python" in user_agent:
        return ProgrammingLanguage.PYTHON
    if any(kw in user_agent for kw in ("javascript", "js", "typescript", "ts")):
        return ProgrammingLanguage.TYPESCRIPT
    return ProgrammingLanguage.PYTHON


class MetaAgentToolCall(BaseModel):
    tool_name: str = ""

    status: Literal["assistant_proposed", "user_ignored", "completed", "failed"] = "assistant_proposed"

    auto_run: bool | None = Field(
        default=None,
        description="Whether the tool call should be automatically executed by on the frontend (true), or if the user should be prompted to run the tool call (false).",
    )

    tool_call_id: str = ""

    @model_validator(mode="after")
    def post_validate(self):
        if not self.tool_call_id:
            self.tool_call_id = f"{self.tool_name}_{compute_obj_hash(obj={**self.model_dump(), 'ts': datetime.datetime.now(tz=datetime.timezone.utc).isoformat()})}"
        return self


class PlaygroundState(BaseModel):
    is_proxy: bool = Field(
        default=False,
        description="Whether the playground is a proxy playground",
    )

    version_id: str | None = Field(
        default=None,
        description="The id of the version of the agent",
    )

    version_messages: list[dict[str, Any]] | None = Field(
        default=None,
        description="The messages of the version",
    )

    agent_input: dict[str, Any] | None = Field(
        default=None,
        description="The input for the agent",
    )
    agent_instructions: str | None = Field(
        default=None,
        description="The instructions for the agent",
    )

    agent_temperature: float | None = Field(
        default=None,
        description="The temperature for the agent",
    )

    class SelectedModels(BaseModel):
        column_1: str | None = Field(
            description="The id of the model selected in the first column of the playground, if empty, no model is selected in the first column",
        )
        column_2: str | None = Field(
            description="The id of the model selected in the second column of the playground, if empty, no model is selected in the second column",
        )
        column_3: str | None = Field(
            description="The id of the model selected in the third column of the playground, if empty, no model is selected in the third column",
        )

        def to_domain(self) -> SelectedModels:
            return SelectedModels(
                column_1=self.column_1,
                column_2=self.column_2,
                column_3=self.column_3,
            )

    selected_models: SelectedModels = Field(
        description="The models currently selected in the playground",
    )

    agent_run_ids: list[str] = Field(
        description="The ids of the runs currently displayed in the playground",
    )


class ImprovePromptToolCall(MetaAgentToolCall):
    tool_name: str = "improve_agent_instructions"

    run_id: str | None = Field(
        default=None,
        description="The id of the run to improve",
    )
    run_feedback_message: str = Field(
        description="The feedback on the run (what is wrong with the output of the run, what is the expected output, etc.).",
    )

    def to_domain(self) -> ImprovePromptToolCallResult:
        return ImprovePromptToolCallResult(
            tool_name=self.tool_name,
            status=self.status,
            agent_run_id=self.run_id,
            instruction_improvement_request_message=self.run_feedback_message,
            ask_user_confirmation=_reverse_optional_bool(self.auto_run),
        )


class EditSchemaToolCall(MetaAgentToolCall):
    tool_name: str = "edit_agent_schema"

    edition_request_message: str | None = Field(
        default=None,
        description="The message to edit the agent schema with.",
    )

    def to_domain(self) -> EditSchemaToolCallResult:
        return EditSchemaToolCallResult(
            tool_name=self.tool_name,
            status=self.status,
            edition_request_message=self.edition_request_message,
            ask_user_confirmation=_reverse_optional_bool(self.auto_run),
        )


class RunCurrentAgentOnModelsToolCall(MetaAgentToolCall):
    tool_name: str = "run_current_agent_on_models"

    class RunConfig(BaseModel):
        run_on_column: Literal["column_1", "column_2", "column_3"] | None = Field(
            default=None,
            description="The column to run the agent on the agent will be run on all columns",
        )
        model: str | None = Field(
            default=None,
            description="The model to run the agent on the agent will be run on all models",
        )

    run_configs: list[RunConfig] | None = Field(
        default=None,
        description="The list of configurations to run the current agent on.",
    )

    def to_domain(self) -> RunCurrentAgentOnModelsToolCallResult:
        return RunCurrentAgentOnModelsToolCallResult(
            tool_name=self.tool_name,
            status=self.status,
            run_configs=[
                RunCurrentAgentOnModelsToolCallRequest.RunConfig(
                    run_on_column=run_config.run_on_column,
                    model=run_config.model,
                )
                for run_config in self.run_configs or []
            ],
            ask_user_confirmation=_reverse_optional_bool(self.auto_run),
        )


class GenerateAgentInputToolCall(MetaAgentToolCall):
    tool_name: str = "generate_agent_input"

    instructions: str | None = Field(
        default=None,
        description="The instructions on how to generate the agent input, this message will be passed to the input generation agent.",
    )

    def to_domain(self) -> GenerateAgentInputToolCallResult:
        return GenerateAgentInputToolCallResult(
            tool_name=self.tool_name,
            status=self.status,
            instructions=self.instructions,
            ask_user_confirmation=_reverse_optional_bool(self.auto_run),
        )


class UpdateVersionMessagesToolCall(MetaAgentToolCall):
    tool_name: str = "update_version_messages"

    improvement_instructions: str = Field(
        description="Instructions on how to improve the current agent version's messages.",
    )

    def to_domain(self) -> None:
        return None


class AddToolToolCall(MetaAgentToolCall):
    tool_name: str = "create_custom_tool"

    tool_name: str = Field(
        description="The name of the tool to add.",
    )

    tool_description: str = Field(
        description="The description of the tool to add.",
    )

    tool_parameters: dict[str, Any] = Field(
        description="The parameters of the tool to add.",
    )

    def to_domain(self) -> None:
        return None


class DirectUpdateVersionMessages(MetaAgentToolCall):
    tool_name: str = "update_version_messages_direct"

    messages: list[dict[str, Any]] = Field(
        description="The direct version messages to update the agent with.",
    )

    def to_domain(self) -> None:
        return None


MetaAgentToolCallType: TypeAlias = (
    ImprovePromptToolCall
    | EditSchemaToolCall
    | RunCurrentAgentOnModelsToolCall
    | GenerateAgentInputToolCall
    | UpdateVersionMessagesToolCall
    | AddToolToolCall
    | DirectUpdateVersionMessages
)


MetaAgentChatMessageKind: TypeAlias = Literal[
    "non_specific",
    "try_other_models_assistant_proposal",
    "try_other_models_user_confirmation",
    "try_other_models_user_postponement",
    "try_other_models_assistant_validation",
    "setup_input_variables_assistant_proposal",
    "setup_input_variables_user_confirmation",
    "setup_input_variables_user_postponement",
    "setup_input_variables_assistant_validation",
    "setup_structured_output_assistant_proposal",
    "setup_structured_output_user_confirmation",
    "setup_structured_output_user_postponement",
    "setup_structured_output_assistant_validation",
    "setup_deployment_assistant_proposal",
    "setup_deployment_user_confirmation",
    "setup_deployment_user_postponement",
    "setup_deployment_assistant_validation",
    "user_deployed_agent_in_playground",
    "run_deployed_agent_assistant_proposal",
    "run_deployed_agent_user_postponement",
    "run_deployed_agent_user_confirmation",
    "run_deployed_agent_assistant_validation",
]


class ProxyMetaAgentAgentPayload(NamedTuple):
    input: ProxyMetaAgentInput
    instructions: str
    message_kind: MetaAgentChatMessageKind


class MetaAgentChatMessage(BaseModel):
    # TODO: make this non nullable
    sent_at: datetime.datetime | None = Field(
        default=None,
        description="The date and time the message was sent",
    )
    role: Literal["USER", "PLAYGROUND", "ASSISTANT"] = Field(
        description="The role of the message sender, 'USER' is the actual human user browsing the playground, 'PLAYGROUND' are automated messages sent by the playground to the agent, and 'ASSISTANT' being the assistant generated by the agent",
    )
    content: str = Field(
        description="The content of the message",
        examples=[
            "Thank you for your help!",
            "What is the weather forecast for tomorrow?",
        ],
    )

    tool_call: MetaAgentToolCallType | None = Field(
        default=None,
        description="The tool call to run in the frontend to help the user improve its agent instructions.",
    )

    feedback_token: str | None = None

    switch_to_schema_id: int | None = None

    kind: MetaAgentChatMessageKind = Field(
        default="non_specific",
        description="The kind of message, used to determine the kind of tool call to show in the frontend.",
    )

    def to_domain(self) -> MetaAgentChatMessageDomain:
        return MetaAgentChatMessageDomain(
            role=self.role,
            content=self.content,
            tool_call=self.tool_call.to_domain() if self.tool_call else None,
            tool_call_status=self.tool_call.status if self.tool_call else None,
        )

    def to_proxy_domain(self) -> ProxyMetaAgentChatMessageDomain:
        return ProxyMetaAgentChatMessageDomain(
            role=self.role,
            content=self.content,
            tool_call=self.tool_call.model_dump() if self.tool_call else None,
            tool_call_status=self.tool_call.status if self.tool_call else None,
        )

    def to_chat_message(self) -> ChatMessage:
        role_map: dict[Literal["USER", "PLAYGROUND", "ASSISTANT"], Literal["USER", "ASSISTANT"]] = {
            "USER": "USER",
            "PLAYGROUND": "ASSISTANT",
            "ASSISTANT": "ASSISTANT",
        }

        return ChatMessage(
            role=role_map[self.role],
            content=self.content,
        )


class MetaAgentService:
    def __init__(
        self,
        storage: BackendStorage,
        event_router: EventRouter,
        runs_service: RunsService,
        versions_service: VersionsService,
        models_service: ModelsService,
        feedback_service: FeedbackService,
        reviews_service: ReviewsService,
    ):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.storage = storage
        self.event_router = event_router
        self.runs_service = runs_service
        self.models_service = models_service
        self.feedback_service = feedback_service
        self.versions_service = versions_service
        self.reviews_service = reviews_service

    async def fetch_agent_runs(self, task_tuple: TaskTuple, agent_run_ids: list[str]) -> list[AgentRun]:
        """Allow to concurrently fetch several concurrently and manage expections"""

        agent_runs_results = await asyncio.gather(
            *[self.runs_service.run_by_id(task_tuple, run_id) for run_id in agent_run_ids],
            return_exceptions=True,
        )
        valid_runs: list[AgentRun] = []
        for run_id, result in zip(agent_run_ids, agent_runs_results):
            if isinstance(result, BaseException):
                self._logger.warning("Meta agent run not found", extra={"run_id": run_id})
                continue  # Skip gracefully if anything went wrong with the run retrieval
            valid_runs.append(result)
        return valid_runs

    async def _build_model_list(
        self,
        instructions: str | None,
        current_agent: SerializableTaskVariant,
    ) -> list[PlaygroundStateDomain.PlaygroundModel]:
        models = await self.models_service.models_for_task(
            current_agent,
            instructions=instructions,
            requires_tools=None,
        )
        return [
            PlaygroundStateDomain.PlaygroundModel(
                id=model.id,
                name=model.name,
                quality_index=model.quality_index,
                context_window_tokens=model.context_window_tokens,
                is_not_supported_reason=model.is_not_supported_reason or "",
                estimate_cost_per_thousand_runs_usd=round(model.average_cost_per_run_usd * 1000, 3)
                if model.average_cost_per_run_usd
                else None,
                is_default=model.is_default,
                is_latest=model.is_latest,
                speed_index=model.speed_index,
            )
            for model in models
        ]

    def _extract_files_from_agent_input(
        self,
        agent_input: dict[str, Any] | None,
        input_schema: dict[str, Any],
    ) -> tuple[dict[str, Any], list[InputFile] | None]:
        """
        Extract files from agent input and return modified input and files list.

        Args:
            agent_input: The original agent input dictionary
            input_schema: The schema for the agent input

        Returns:
            A tuple containing:
                - Modified agent input with files removed
                - List of InputFile objects or None if no files were found
        """
        agent_input_copy = agent_input.copy() if agent_input else {}
        agent_input_files = None

        if agent_input_copy:
            # Extract files from agent_input using the input schema
            _, agent_input_copy, files = extract_files(input_schema, agent_input_copy)
            if files:
                # Convert FileWithKeyPath objects to PlaygroundState.InputFile objects
                agent_input_files = [
                    InputFile(
                        key_path=".".join(str(key) for key in file.key_path),
                        file=File(
                            content_type=file.content_type,
                            data=file.data,
                            url=file.url,
                        ),
                    )
                    for file in files
                ]

        return agent_input_copy, agent_input_files

    async def _extract_url_content_from_messages(self, messages: list[MetaAgentChatMessage]) -> list[URLContent]:
        # TODO: improve ?
        # For now, we are only extracting the URL content from the latest 'USER' message, for two reasons:
        # - Context size: We don't want to carry over the large HTML content on EVERY back and forth between the user and the meta-agent
        # - Latency: We currently have no caching mechanism for fetching the URL content, that would mean we would re-fetch the URL at every back and forth between the user and the meta-agent

        if not messages:
            return []

        message = messages[-1]
        if message.role != "USER":
            return []

        return await extract_and_fetch_urls(message.content)

    async def has_active_agent_runs(
        self,
        task_tuple: TaskTuple,
        task_schema_id: int | None,
    ) -> HasActiveRunAndDate:
        try:
            agent_run = await self.runs_service.latest_run(task_tuple, task_schema_id, is_success=None, is_active=True)
            return HasActiveRunAndDate(
                has_active_runs=True,
                latest_active_run_date=agent_run.created_at,
            )
        except ObjectNotFoundException:
            return HasActiveRunAndDate(
                has_active_runs=False,
                latest_active_run_date=None,
            )

    async def list_deployments(
        self,
        task_tuple: TaskTuple,
        agent_schema_id: int,
    ) -> list[MetaAgentInput.AgentLifecycleInfo.DeploymentInfo.Deployment]:
        versions = await self.versions_service.list_version_majors(task_tuple, agent_schema_id, self.models_service)

        deployments: list[MetaAgentInput.AgentLifecycleInfo.DeploymentInfo.Deployment] = []

        for version in versions:
            for minor in version.minors or []:
                deployments.extend(
                    [
                        MetaAgentInput.AgentLifecycleInfo.DeploymentInfo.Deployment(
                            environment=deployment.environment,
                            deployed_at=deployment.deployed_at,
                            deployed_by_email=deployment.deployed_by.user_email if deployment.deployed_by else None,
                            model_used=minor.properties.model,
                            last_active_at=minor.last_active_at,
                            run_count=minor.run_count,
                            notes=minor.notes,
                        )
                        for deployment in minor.deployments or []
                    ],
                )

        return deployments

    async def get_reviewed_input_count(
        self,
        task_tuple: TaskTuple,
        agent_schema_id: int,
    ) -> int:
        reviews = await self.reviews_service.list_reviewed_inputs(task_tuple, agent_schema_id)
        return len(reviews)

    async def fetch_meta_agent_context_for_testing(
        self,
        task_tuple: TaskTuple,
        agent_schema_id: int,
        user_email: str | None,
        playground_state: PlaygroundState,
    ) -> MetaAgentContext:
        """Public method that wraps _fetch_meta_agent_context for testing purposes."""
        return await self._fetch_meta_agent_context(
            task_tuple,
            agent_schema_id,
            user_email,
            playground_state,
        )

    async def _fetch_meta_agent_context(
        self,
        task_tuple: TaskTuple,
        agent_schema_id: int,
        user_email: str | None,
        playground_state: PlaygroundState,
    ) -> MetaAgentContext:
        """
        Fetch all context data needed for the meta agent input, handling exceptions.

        If any individual fetch fails, it returns None for that part of the context
        instead of failing the entire operation.
        """
        context_results = await asyncio.gather(
            safe_generate_company_description_from_email(user_email),
            list_agent_summaries(self.storage, limit=10),
            self.fetch_agent_runs(task_tuple, playground_state.agent_run_ids),
            self.feedback_service.list_feedback(
                task_tuple[1],
                run_id=None,
                limit=10,
                offset=0,
                map_fn=MetaAgentInput.AgentLifecycleInfo.FeedbackInfo.AgentFeedback.from_domain,
            ),
            self.has_active_agent_runs(task_tuple, agent_schema_id),
            self.get_reviewed_input_count(task_tuple, agent_schema_id),
            return_exceptions=True,
        )

        # Process each result - for each item, either use the value or log and return a default value
        if isinstance(context_results[0], BaseException):
            self._logger.warning("Failed to fetch company_description", exc_info=context_results[0])
            company_description = None
        else:
            company_description = context_results[0]

        if isinstance(context_results[1], BaseException):
            self._logger.warning("Failed to fetch existing_agents", exc_info=context_results[1])
            existing_agents = None
        else:
            existing_agents = [str(agent) for agent in context_results[1] or []]

        if isinstance(context_results[2], BaseException):
            self._logger.warning("Failed to fetch agent_runs", exc_info=context_results[2])
            agent_runs = None
        else:
            agent_runs = context_results[2]

        if isinstance(context_results[3], BaseException):
            self._logger.warning("Failed to fetch feedback_page", exc_info=context_results[3])
            feedback_page = None
        else:
            feedback_page = context_results[3]

        if isinstance(context_results[4], BaseException):
            self._logger.warning("Failed to fetch has_active_runs", exc_info=context_results[4])
            has_active_runs = None
        else:
            has_active_runs = context_results[4]

        if isinstance(context_results[5], BaseException):
            self._logger.warning("Failed to fetch reviewed_input_count", exc_info=context_results[5])
            reviewed_input_count = None
        else:
            reviewed_input_count = context_results[5]

        return MetaAgentContext(
            company_description=company_description,
            existing_agents=existing_agents,
            agent_runs=agent_runs,
            feedback_page=feedback_page,
            has_active_runs=has_active_runs,
            reviewed_input_count=reviewed_input_count,
        )

    async def _build_meta_agent_input(
        self,
        task_tuple: TaskTuple,
        agent_schema_id: int,
        user_email: str | None,
        messages: list[MetaAgentChatMessage],
        current_agent: SerializableTaskVariant,
        playground_state: PlaygroundState,
    ) -> tuple[MetaAgentInput, list[AgentRun]]:
        # Fetch context data with exception handling
        context = await self._fetch_meta_agent_context(
            task_tuple,
            agent_schema_id,
            user_email,
            playground_state,
        )

        # Extract files from agent_input
        agent_input_schema = current_agent.input_schema.json_schema.copy()
        agent_input_copy, agent_input_files = self._extract_files_from_agent_input(
            playground_state.agent_input,
            agent_input_schema,
        )

        return MetaAgentInput(
            current_datetime=datetime.datetime.now(tz=datetime.timezone.utc),
            messages=[message.to_domain() for message in messages],
            latest_messages_url_content=await self._extract_url_content_from_messages(messages),
            company_context=MetaAgentInput.CompanyContext(
                company_name=context.company_description.company_name if context.company_description else None,
                company_description=context.company_description.description if context.company_description else None,
                company_locations=context.company_description.locations if context.company_description else None,
                company_industries=context.company_description.industries if context.company_description else None,
                company_products=context.company_description.products if context.company_description else None,
                existing_agents_descriptions=context.existing_agents or [],
            ),
            workflowai_documentation_sections=[]
            if playground_state.is_proxy
            else await DocumentationService().get_relevant_doc_sections(
                chat_messages=[message.to_chat_message() for message in messages],
                agent_instructions=META_AGENT_INSTRUCTIONS or "",
            ),
            available_tools_description=internal_tools_description(
                include={ToolKind.WEB_BROWSER_TEXT, ToolKind.WEB_SEARCH_PERPLEXITY_SONAR_PRO},
            ),
            playground_state=PlaygroundStateDomain(
                current_agent=PlaygroundStateDomain.Agent(
                    name=current_agent.name,
                    schema_id=current_agent.task_schema_id,
                    description=current_agent.description,
                    input_schema=current_agent.input_schema.json_schema,
                    output_schema=current_agent.output_schema.json_schema,
                ),
                agent_input=agent_input_copy,
                agent_input_files=agent_input_files,
                agent_instructions=playground_state.agent_instructions,
                agent_temperature=playground_state.agent_temperature,
                available_models=await self._build_model_list(playground_state.agent_instructions, current_agent),
                selected_models=playground_state.selected_models.to_domain(),
                agent_runs=[
                    PlaygroundStateDomain.AgentRun(
                        id=agent_run.id,
                        model=agent_run.group.properties.model or "",
                        output=agent_run.task_output,
                        error=agent_run.error.model_dump() if agent_run.error else None,
                        cost_usd=agent_run.cost_usd,
                        duration_seconds=agent_run.duration_seconds,
                        user_evaluation=agent_run.user_review,
                        tool_calls=[
                            PlaygroundStateDomain.AgentRun.ToolCall(
                                name=tool_call.tool_name,
                                input=tool_call.tool_input_dict,
                            )
                            for llm_completion in agent_run.llm_completions or []
                            for tool_call in llm_completion.tool_calls or []
                        ],
                    )
                    for agent_run in context.agent_runs
                ]
                if context.agent_runs
                else None,
            ),
            agent_lifecycle_info=MetaAgentInput.AgentLifecycleInfo(
                deployment_info=MetaAgentInput.AgentLifecycleInfo.DeploymentInfo(
                    has_api_or_sdk_runs=context.has_active_runs.has_active_runs,
                    latest_api_or_sdk_run_date=context.has_active_runs.latest_active_run_date,
                    deployments=await self.list_deployments(task_tuple, agent_schema_id),
                )
                if context.has_active_runs
                else None,
                feedback_info=MetaAgentInput.AgentLifecycleInfo.FeedbackInfo(
                    user_feedback_count=context.feedback_page.count,
                    latest_user_feedbacks=context.feedback_page.items,
                )
                if context.feedback_page
                else None,
                internal_review_info=MetaAgentInput.AgentLifecycleInfo.InternalReviewInfo(
                    reviewed_input_count=context.reviewed_input_count,
                ),
            ),
        ), context.agent_runs or []

    def dispatch_new_user_messages_event(self, messages: list[MetaAgentChatMessage]):
        # Get all consecutive USER messages at the end of the conversation
        latest_user_messages: list[MetaAgentChatMessage] = []
        for message in reversed(messages):
            if message.role == "USER":
                latest_user_messages.insert(0, message)
            else:
                break

        if latest_user_messages:
            self.event_router(
                MetaAgentChatMessagesSent(messages=[message.to_domain() for message in latest_user_messages]),
            )
        else:
            self._logger.warning("No user message found in the list of messages")

    def dispatch_new_assistant_messages_event(self, messages: list[MetaAgentChatMessage]):
        self.event_router(MetaAgentChatMessagesSent(messages=[message.to_domain() for message in messages]))

    def _sanitize_agent_run_id(self, candidate_agent_run_id: str, valid_agent_runs: list[AgentRun]) -> str:
        if candidate_agent_run_id in [run.id for run in valid_agent_runs]:
            return candidate_agent_run_id

        self._logger.warning(
            "Invalid agent run id return by the meta-agent",
            extra={"candidate_agent_run_id": candidate_agent_run_id, "valid_agent_runs": valid_agent_runs},
        )

        if len(valid_agent_runs) == 0:
            return ""

        first_run_with_negative_output = next((run for run in valid_agent_runs if run.user_review == "negative"), None)
        if first_run_with_negative_output:
            return first_run_with_negative_output.id

        first_run_with_output = next((run for run in valid_agent_runs if run.task_output), None)
        if first_run_with_output:
            return first_run_with_output.id

        first_run = valid_agent_runs[0]
        self._logger.warning(
            "No valid agent run id found, returning the first one",
            extra={"first_run": first_run},
        )

        return first_run.id

    @classmethod
    def _resolve_auto_run(
        cls,
        tool_call_type: type[MetaAgentToolCallType],
        initial_auto_run: bool,
        messages: list[MetaAgentChatMessage],
    ) -> bool:
        if initial_auto_run is False:
            return False

        if tool_call_type is EditSchemaToolCall:
            return False

        # All other tool calls are auto-runnable, expect if the latest 'non-Playground' message is a tool call of the same type
        if (
            len(messages) > 1
            and messages[-1].role == "PLAYGROUND"
            and messages[-2].role == "ASSISTANT"
            and messages[-2].tool_call
            and type(messages[-2].tool_call) is tool_call_type
        ):
            return False

        return True

    def _extract_tool_call_from_meta_agent_output(
        self,
        meta_agent_output: MetaAgentOutput,
        agent_runs: list[AgentRun],
        messages: list[MetaAgentChatMessage],
    ) -> MetaAgentToolCallType | None:
        # If is mutually exclusive, because we want to only return one tool call at a time for now.
        if meta_agent_output.improve_instructions_tool_call:
            return ImprovePromptToolCall(
                run_id=self._sanitize_agent_run_id(
                    meta_agent_output.improve_instructions_tool_call.agent_run_id or "",
                    agent_runs,
                ),
                run_feedback_message=meta_agent_output.improve_instructions_tool_call.instruction_improvement_request_message,
                auto_run=self._resolve_auto_run(
                    tool_call_type=ImprovePromptToolCall,
                    initial_auto_run=_reverse_optional_bool(
                        meta_agent_output.improve_instructions_tool_call.ask_user_confirmation,
                    )
                    or False,
                    messages=messages,
                ),
            )

        # Schema description and examples tool call from the meta-agent is mapped to "Improve Prompt" feature in the frontend,
        # which can update the schema description and examples
        if meta_agent_output.edit_schema_description_and_examples_tool_call:
            return ImprovePromptToolCall(
                run_id=None,
                run_feedback_message=meta_agent_output.edit_schema_description_and_examples_tool_call.description_and_examples_edition_request_message
                or "",
                auto_run=self._resolve_auto_run(
                    tool_call_type=ImprovePromptToolCall,
                    initial_auto_run=_reverse_optional_bool(
                        meta_agent_output.edit_schema_description_and_examples_tool_call.ask_user_confirmation,
                    )
                    or False,
                    messages=messages,
                ),
            )

        if meta_agent_output.edit_schema_structure_tool_call:
            return EditSchemaToolCall(
                edition_request_message=meta_agent_output.edit_schema_structure_tool_call.edition_request_message,
                auto_run=self._resolve_auto_run(
                    tool_call_type=EditSchemaToolCall,
                    initial_auto_run=_reverse_optional_bool(
                        meta_agent_output.edit_schema_structure_tool_call.ask_user_confirmation,
                    )
                    or False,
                    messages=messages,
                ),
            )

        if meta_agent_output.run_current_agent_on_models_tool_call:
            return RunCurrentAgentOnModelsToolCall(
                run_configs=[
                    RunCurrentAgentOnModelsToolCall.RunConfig(
                        run_on_column=run_config.run_on_column,
                        model=run_config.model,
                    )
                    for run_config in meta_agent_output.run_current_agent_on_models_tool_call.run_configs or []
                ],
                auto_run=self._resolve_auto_run(
                    tool_call_type=RunCurrentAgentOnModelsToolCall,
                    initial_auto_run=_reverse_optional_bool(
                        meta_agent_output.run_current_agent_on_models_tool_call.ask_user_confirmation,
                    )
                    or False,
                    messages=messages,
                ),
            )

        if meta_agent_output.generate_agent_input_tool_call:
            return GenerateAgentInputToolCall(
                instructions=meta_agent_output.generate_agent_input_tool_call.instructions,
                auto_run=self._resolve_auto_run(
                    tool_call_type=GenerateAgentInputToolCall,
                    initial_auto_run=_reverse_optional_bool(
                        meta_agent_output.generate_agent_input_tool_call.ask_user_confirmation,
                    )
                    or False,
                    messages=messages,
                ),
            )

        return None

    async def _sanitize_tool_call_auto_run(
        self,
        tool_call: MetaAgentToolCallType,
        assistant_message_content: str,
    ) -> None:
        """The meta agent is VERY stubborn in asking user for confirmation before running a tool call,
        but at the same time returning 'ask_user_confirmation=False' in the tool call.
        Therefore, we'll use another layer of safety to make sure that when the meta agent asks for user confirmation in the message,
        the 'auto_run' flag is actually set to false."""
        if tool_call.auto_run is False:
            return

        # Only run check if the auto_run flag is set to 'True'
        try:
            agent_output = await meta_agent_user_confirmation_agent(
                MetaAgentUserConfirmationInput(assistant_message_content=assistant_message_content),
            )
            if agent_output.requires_user_confirmation is True:
                # The user confirmation agent has decided that a confirmation is needed, so we switch the auto_run to 'False'
                tool_call.auto_run = False

        except Exception as e:
            self._logger.exception("Error running meta agent user confirmation agent", exc_info=e)
            # do nothing

    async def stream_meta_agent_response(
        self,
        task_tuple: TaskTuple,
        agent_schema_id: int,
        user_email: str | None,
        messages: list[MetaAgentChatMessage],
        playground_state: PlaygroundState,
    ) -> AsyncIterator[list[MetaAgentChatMessage]]:
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        if len(messages) == 0:
            yield [MetaAgentChatMessage(role="ASSISTANT", content=FIRST_MESSAGE_CONTENT, sent_at=now)]
            return

        current_agent = await self.storage.task_variant_latest_by_schema_id(task_tuple[0], agent_schema_id)

        self.dispatch_new_user_messages_event(messages)

        meta_agent_input, agent_runs = await self._build_meta_agent_input(
            task_tuple,
            agent_schema_id,
            user_email,
            messages,
            current_agent,
            playground_state,
        )

        ret: list[MetaAgentChatMessage] = []
        chunk: "workflowai.Run[MetaAgentOutput] | None" = None
        async for chunk in meta_agent.stream(meta_agent_input, temperature=0.5):
            if chunk.output.content:
                ret = [
                    MetaAgentChatMessage(
                        role="ASSISTANT",
                        content=chunk.output.content,
                        feedback_token=chunk.feedback_token,
                        sent_at=now,
                    ),
                ]
                yield ret

        if chunk and (tool_call := self._extract_tool_call_from_meta_agent_output(chunk.output, agent_runs, messages)):
            assistant_message_content = chunk.output.content or ""
            await self._sanitize_tool_call_auto_run(tool_call, assistant_message_content)
            ret = [
                MetaAgentChatMessage(
                    role="ASSISTANT",
                    content=assistant_message_content,
                    tool_call=tool_call,
                    feedback_token=chunk.feedback_token,
                    sent_at=now,
                ),
            ]
            yield ret

        self.dispatch_new_assistant_messages_event(ret)

    # TODO: delete when we'll have factorized the two agents
    async def _proxy_build_model_list(
        self,
        instructions: str | None,
        current_agent: SerializableTaskVariant,
    ) -> list[ProxyPlaygroundStateDomain.PlaygroundModel]:
        models = await self.models_service.models_for_task(
            current_agent,
            instructions=instructions,
            requires_tools=None,
        )

        # Pre-calculate costs for ranking
        model_costs: list[tuple[Any, float]] = []
        for model in models:
            cost = (
                round(model.average_cost_per_run_usd * 1000, 3)
                if model.average_cost_per_run_usd is not None
                else float("inf")  # Models with no cost data get worst ranking
            )
            model_costs.append((model, cost))

        # Sort by quality (descending - higher quality gets better rank)
        models_by_quality = sorted(models, key=lambda m: m.quality_index, reverse=True)
        quality_rankings = {model.id: rank + 1 for rank, model in enumerate(models_by_quality)}

        # Sort by speed (descending - higher speed gets better rank)
        models_by_speed = sorted(models, key=lambda m: m.speed_index, reverse=True)
        speed_rankings = {model.id: rank + 1 for rank, model in enumerate(models_by_speed)}

        # Sort by cost (ascending - lower cost gets better rank)
        models_by_cost = sorted(model_costs, key=lambda x: x[1])
        cost_rankings = {model.id: rank + 1 for rank, (model, _) in enumerate(models_by_cost)}

        return [
            ProxyPlaygroundStateDomain.PlaygroundModel(
                id=model.id,
                name=model.name,
                quality_index=model.quality_index,
                quality_index_ranking=quality_rankings[model.id],
                speed_index=model.speed_index,
                speed_index_ranking=speed_rankings[model.id],
                context_window_tokens=model.context_window_tokens,
                is_supported_for_agent=not bool(model.is_not_supported_reason),
                is_not_supported_reason=model.is_not_supported_reason or "",
                estimate_cost_per_thousand_runs_usd=round(model.average_cost_per_run_usd * 1000, 3)
                if model.average_cost_per_run_usd is not None
                else None,
                cost_ranking=cost_rankings[model.id],
                is_default=model.is_default,
                is_latest=model.is_latest,
                supports_structured_output=model.supports_structured_output,
            )
            for model in models
        ]

    # TODO: delete when we'll have factorized the two agents
    async def list_proxy_deployments(
        self,
        task_tuple: TaskTuple,
        agent_schema_id: int,
    ) -> list[ProxyMetaAgentInput.AgentLifecycleInfo.DeploymentInfo.Deployment]:
        versions = await self.versions_service.list_version_majors(task_tuple, agent_schema_id, self.models_service)

        deployments: list[ProxyMetaAgentInput.AgentLifecycleInfo.DeploymentInfo.Deployment] = []

        for version in versions:
            for minor in version.minors or []:
                deployments.extend(
                    [
                        ProxyMetaAgentInput.AgentLifecycleInfo.DeploymentInfo.Deployment(
                            environment=deployment.environment,
                            deployed_at=deployment.deployed_at,
                            deployed_by_email=deployment.deployed_by.user_email if deployment.deployed_by else None,
                            model_used=minor.properties.model,
                            last_active_at=minor.last_active_at,
                            run_count=minor.run_count,
                            notes=minor.notes,
                        )
                        for deployment in minor.deployments or []
                    ],
                )

        return deployments

    async def _fetch_proxy_meta_agent_context(
        self,
        task_tuple: TaskTuple,
        agent_schema_id: int,
        user_email: str | None,
        playground_state: PlaygroundState,
    ) -> ProxyMetaAgentContext:
        """
        Fetch all context data needed for the meta agent input, handling exceptions.

        If any individual fetch fails, it returns None for that part of the context
        instead of failing the entire operation.
        """
        (
            company_description,
            existing_agents,
            agent_runs,
            feedback_page,
            has_active_runs,
            reviewed_input_count,
            playground_agent_runs,
        ) = await asyncio.gather(
            safe_generate_company_description_from_email(user_email),
            list_agent_summaries(self.storage, limit=10),
            self._fetch_latest_agent_runs(task_tuple, agent_schema_id),
            self.feedback_service.list_feedback(
                task_tuple[1],
                run_id=None,
                limit=10,
                offset=0,
                map_fn=ProxyMetaAgentInput.AgentLifecycleInfo.FeedbackInfo.AgentFeedback.from_domain,
            ),
            self.has_active_agent_runs(task_tuple, agent_schema_id),
            self.get_reviewed_input_count(task_tuple, agent_schema_id),
            self.fetch_agent_runs(task_tuple, playground_state.agent_run_ids),
            return_exceptions=True,
        )

        # Process each result - for each item, either use the value or log and return a default value
        if isinstance(company_description, BaseException):
            self._logger.warning("Failed to fetch company_description", exc_info=company_description)
            company_description = None
        else:
            company_description = cast(ExtractCompanyInfoFromDomainTaskOutput, company_description)

        if isinstance(existing_agents, BaseException):
            self._logger.warning("Failed to fetch existing_agents", exc_info=existing_agents)
            existing_agents = None
        else:
            existing_agents = [str(agent) for agent in existing_agents or []]  # type: ignore

        if isinstance(agent_runs, BaseException):
            self._logger.warning("Failed to fetch agent_runs", exc_info=agent_runs)
            agent_runs = None
        else:
            agent_runs = cast(list[AgentRun], agent_runs)

        if isinstance(feedback_page, BaseException):
            self._logger.warning("Failed to fetch feedback_page", exc_info=feedback_page)
            feedback_page = None
        else:
            feedback_page = cast(Page[ProxyMetaAgentInput.AgentLifecycleInfo.FeedbackInfo.AgentFeedback], feedback_page)

        if isinstance(has_active_runs, BaseException):
            self._logger.warning("Failed to fetch has_active_runs", exc_info=has_active_runs)
            has_active_runs = None
        else:
            has_active_runs = cast(HasActiveRunAndDate, has_active_runs)

        if isinstance(reviewed_input_count, BaseException):
            self._logger.warning("Failed to fetch reviewed_input_count", exc_info=reviewed_input_count)
            reviewed_input_count = None
        else:
            reviewed_input_count = cast(int, reviewed_input_count)

        if isinstance(playground_agent_runs, BaseException):
            self._logger.warning("Failed to fetch playground agent_runs", exc_info=playground_agent_runs)
            playground_agent_runs = None
        else:
            playground_agent_runs = cast(list[AgentRun], playground_agent_runs)

        return ProxyMetaAgentContext(
            company_description=company_description,
            existing_agents=existing_agents,
            agent_runs=agent_runs,
            feedback_page=feedback_page,
            has_active_runs=has_active_runs,
            reviewed_input_count=reviewed_input_count,
            playground_agent_runs=playground_agent_runs,
        )

    def _build_proxy_agent_runs(self, agent_run: AgentRun) -> ProxyAgentRun:
        return ProxyAgentRun(
            id=agent_run.id,
            model=agent_run.group.properties.model or "",
            input=str(agent_run.task_input),
            output=str(agent_run.task_output),  # Handle both dict output and str
            error=agent_run.error.model_dump() if agent_run.error else None,
            raw_response=agent_run.llm_completions[-1].response if agent_run.llm_completions else None,
            cost_usd=agent_run.cost_usd,
            duration_seconds=agent_run.duration_seconds,
            user_evaluation=agent_run.user_review,
            tool_calls=[
                ProxyAgentRun.ToolCall(
                    name=tool_call.tool_name,
                    input=tool_call.tool_input_dict,
                )
                for llm_completion in agent_run.llm_completions or []
                for tool_call in llm_completion.tool_calls or []
            ],
        )

    async def _pick_relevant_doc_sections(
        self,
        messages: list[MetaAgentChatMessage],
    ) -> list[DocumentationSection]:
        return await DocumentationService().get_relevant_doc_sections(
            chat_messages=[message.to_chat_message() for message in messages],
            agent_instructions=GENERIC_INSTRUCTIONS or "",
        )

    async def _build_proxy_meta_agent_input(
        self,
        task_tuple: TaskTuple,
        agent_schema_id: int,
        user_email: str | None,
        messages: list[MetaAgentChatMessage],
        current_agent: SerializableTaskVariant,
        playground_state: PlaygroundState,
        hosted_tool_update_mode: bool = False,
    ) -> tuple[ProxyMetaAgentInput, list[AgentRun]]:
        # Fetch context data with exception handling
        context = await self._fetch_proxy_meta_agent_context(
            task_tuple,
            agent_schema_id,
            user_email,
            playground_state,
        )

        # Extract files from agent_input
        agent_input_schema = current_agent.input_schema.json_schema.copy()
        agent_input_copy, agent_input_files = self._extract_files_from_agent_input(
            playground_state.agent_input,
            agent_input_schema,
        )

        agent_runs: list[ProxyAgentRun] | None = (
            [self._build_proxy_agent_runs(agent_run) for agent_run in context.agent_runs]
            if context.agent_runs
            else None
        )

        playground_agent_runs: list[ProxyAgentRun] | None = (
            [self._build_proxy_agent_runs(agent_run) for agent_run in context.playground_agent_runs]
            if context.playground_agent_runs
            else None
        )

        if hosted_tool_update_mode:
            # In the case when the use case is very well defined, we avoid dynamically picking a documentation section to save time—and manually pick the one to use.
            overidden_doc_sections = ["agents/tools"]
            relevant_doc_sections = await DocumentationService().get_documentation_by_path(
                paths=overidden_doc_sections,
            )
            if len(relevant_doc_sections) == 0:
                self._logger.error(
                    "Could not find overridden doc sections, reverting to dynamically picking relevant doc sections",
                    extra={"overidden_doc_sections": ", ".join(overidden_doc_sections)},
                )
                relevant_doc_sections = await self._pick_relevant_doc_sections(messages)
        else:
            relevant_doc_sections = await self._pick_relevant_doc_sections(messages)

        return ProxyMetaAgentInput(
            current_datetime=datetime.datetime.now(tz=datetime.timezone.utc),
            chat_messages=[message.to_proxy_domain() for message in messages],
            current_agent=ProxyMetaAgentInput.Agent(
                name=current_agent.name,
                slug=current_agent.task_id,
                schema_id=current_agent.task_schema_id,
                description=current_agent.description,
                input_schema=current_agent.input_schema.json_schema,
                output_schema=current_agent.output_schema.json_schema,
            ),
            latest_agent_run=agent_runs[0] if agent_runs and len(agent_runs) > 0 else None,
            previous_agent_runs=agent_runs[1:] if agent_runs and len(agent_runs) > 1 else None,
            latest_messages_url_content=await self._extract_url_content_from_messages(messages),
            company_context=ProxyMetaAgentInput.CompanyContext(
                company_name=context.company_description.company_name if context.company_description else None,
                company_description=context.company_description.description if context.company_description else None,
                company_locations=context.company_description.locations if context.company_description else None,
                company_industries=context.company_description.industries if context.company_description else None,
                company_products=context.company_description.products if context.company_description else None,
                existing_agents_descriptions=context.existing_agents or [],
            ),
            workflowai_documentation_sections=relevant_doc_sections,
            integration_documentation=[],  # Will be filled in later in 'stream_meta_agent_chat'
            available_hosted_tools_description=internal_tools_description(
                include={ToolKind.WEB_BROWSER_TEXT, ToolKind.WEB_SEARCH_PERPLEXITY_SONAR_PRO},
                formatting_func=get_tools_description_openai_format_str,
            ),
            playground_state=ProxyPlaygroundStateDomain(
                agent_input=agent_input_copy,
                agent_input_files=agent_input_files,
                agent_temperature=playground_state.agent_temperature,
                available_models=await self._proxy_build_model_list("", current_agent),  # TODO: add instructions
                selected_models=playground_state.selected_models.to_domain(),
                playground_agent_runs=playground_agent_runs,
                version_messages=playground_state.version_messages,
            ),
            agent_lifecycle_info=ProxyMetaAgentInput.AgentLifecycleInfo(
                deployment_info=ProxyMetaAgentInput.AgentLifecycleInfo.DeploymentInfo(
                    has_api_or_sdk_runs=context.has_active_runs.has_active_runs,
                    latest_api_or_sdk_run_date=context.has_active_runs.latest_active_run_date,
                    deployments=await self.list_proxy_deployments(task_tuple, agent_schema_id),
                )
                if context.has_active_runs
                else None,
                feedback_info=ProxyMetaAgentInput.AgentLifecycleInfo.FeedbackInfo(
                    user_feedback_count=context.feedback_page.count,
                    latest_user_feedbacks=context.feedback_page.items,
                )
                if context.feedback_page
                else None,
                internal_review_info=ProxyMetaAgentInput.AgentLifecycleInfo.InternalReviewInfo(
                    reviewed_input_count=context.reviewed_input_count,
                ),
            ),
        ), context.agent_runs or []

    async def _fetch_latest_agent_runs(
        self,
        task_tuple: TaskTuple,
        task_schema_id: int,
    ) -> list[AgentRun]:
        return [
            run
            async for run in self.storage.task_runs.list_latest_runs(
                task_uid=task_tuple[1],
                limit=10,
            )
            if run.task_schema_id == task_schema_id
        ]

    def _is_user_triggered(self, messages: list[MetaAgentChatMessage]) -> bool:
        if len(messages) == 0:
            return False

        latest_message = messages[-1]

        return latest_message.role == "USER"

    def _is_only_using_openai_models(self, agent_runs: list[AgentRun]) -> bool:
        for agent_run in agent_runs:
            if not agent_run.group.properties.model:
                continue
            try:
                model = Model(agent_run.group.properties.model)
            except ValueError:
                self._logger.warning("Failed to parse model", extra={"model": agent_run.group.properties.model})
                continue

            model_data = MODEL_DATAS[model]
            if isinstance(model_data, LatestModel):
                model = model_data.model
                model_data = MODEL_DATAS[model_data.model]

            if model not in AZURE_PROVIDER_DATA.keys() and model not in OPENAI_PROVIDER_DATA.keys():
                return False

        return True

    def _is_message_kind_already_sent(
        self,
        messages: list[MetaAgentChatMessage],
        message_kind: MetaAgentChatMessageKind,
    ) -> bool:
        for message in messages:
            if message.kind == message_kind:
                return True
        return False

    async def _resolve_integration_for_agent(
        self,
        agent: SerializableTaskVariant,
        agent_runs: list[AgentRun],
        task_tuple: TaskTuple,
        agent_schema_id: int,
    ) -> Integration:
        if integration := safe_get_integration_by_kind(agent.used_integration_kind):
            # If integration is registered for the agent, use it
            return integration

        if agent.task_schema_id > 1:
            schema_id_to_explore = list(range(1, agent.task_schema_id))[::-1]  # reverse order
            for schema_id in schema_id_to_explore:
                agent_to_check = await self.storage.task_variant_latest_by_schema_id(task_tuple[0], schema_id)
                if integration := safe_get_integration_by_kind(agent_to_check.used_integration_kind):
                    return integration

        # Else, pick the default integration for the programming language based on the user agent of the latest run
        user_agent = ""
        if len(agent_runs) and agent_runs[0].metadata:
            user_agent = agent_runs[0].metadata.get("user-agent", "")

        programming_language = get_programming_language_for_user_agent(user_agent)
        return default_integration_for_language(programming_language)

    async def _sanitize_output_string(self, output_string: str, integration: Integration) -> str:
        if integration.programming_language == ProgrammingLanguage.PYTHON:
            return _remove_typescript_comments(output_string)
        return output_string

    async def _get_proxy_agent_input_variables_proposal_paylaod(
        self,
        proxy_meta_agent_input: ProxyMetaAgentInput,
        agent_runs: list[AgentRun],
        integration: Integration,
    ) -> ProxyMetaAgentAgentPayload:
        # "Migrate to input variables" use case
        if integration.use_version_messages:
            input_variables_extractor_agent_run = await input_variables_extractor_agent(
                InputVariablesExtractorInput(
                    agent_inputs=[agent_run.task_input for agent_run in agent_runs],
                ),
            )
            proxy_meta_agent_input.suggested_messages_with_input_variables = [
                message.model_dump() for message in input_variables_extractor_agent_run.messages_with_input_variables
            ]
            proxy_meta_agent_input.suggested_input_variables_example = (
                input_variables_extractor_agent_run.input_variables_example
            )
            instructions = PROPOSE_INPUT_VARIABLES_INSTRUCTIONS
            message_kind = "setup_input_variables_assistant_proposal"
        else:
            instructions = PROPOSE_INPUT_VARIABLES_INSTRUCTIONS_NO_VERSION_MESSAGES
            message_kind = "setup_input_variables_assistant_proposal"

        return ProxyMetaAgentAgentPayload(
            input=proxy_meta_agent_input,
            instructions=instructions,
            message_kind=message_kind,
        )

    async def _get_structured_output_proposal_payload(
        self,
        proxy_meta_agent_input: ProxyMetaAgentInput,
        agent_runs: list[AgentRun],
        integration: Integration,
    ) -> ProxyMetaAgentAgentPayload:
        output_schema_extractor_run = await output_schema_extractor_agent(
            OutputSchemaExtractorInput(
                agent_runs=[
                    OutputSchemaExtractorInput.AgentRun(
                        raw_messages=[
                            llm_completion.messages or [] for llm_completion in agent_run.llm_completions or []
                        ],
                        input=str(agent_run.task_input),
                        output=str(agent_run.task_output),
                    )
                    for agent_run in agent_runs
                ],
                programming_language=integration.programming_language,
                structured_object_class=integration.output_class,
            ),
        )
        proxy_meta_agent_input.suggested_output_class_code = (
            output_schema_extractor_run.proposed_structured_object_class
        )
        proxy_meta_agent_input.suggested_instructions_parts_to_remove = (
            output_schema_extractor_run.instructions_parts_to_remove
        )

        return ProxyMetaAgentAgentPayload(
            input=proxy_meta_agent_input,
            instructions=PROPOSE_STRUCTURED_OUTPUT_INSTRUCTIONS,
            message_kind="setup_structured_output_assistant_proposal",
        )

    def get_agent_deployment(
        self,
        proxy_meta_agent_input: ProxyMetaAgentInput,
    ) -> ProxyMetaAgentInput.AgentLifecycleInfo.DeploymentInfo.Deployment | None:
        if (
            not proxy_meta_agent_input.agent_lifecycle_info
            or not proxy_meta_agent_input.agent_lifecycle_info.deployment_info
            or not proxy_meta_agent_input.agent_lifecycle_info.deployment_info.deployments
        ):
            return None
        return proxy_meta_agent_input.agent_lifecycle_info.deployment_info.deployments[0]

    def _is_any_run_using_deployment(self, agent_runs: list[AgentRun]) -> bool:
        return any(
            run.metadata.get(METADATA_KEY_DEPLOYMENT_ENVIRONMENT) if run.metadata else False for run in agent_runs
        )

    def detect_message_kind_in_raw_completion(self, raw_completion: str) -> tuple[MetaAgentChatMessageKind, str] | None:
        message_kinds: list[MetaAgentChatMessageKind] = [
            "setup_input_variables_assistant_proposal",
            "setup_structured_output_assistant_proposal",
            "try_other_models_assistant_proposal",
            "setup_deployment_assistant_proposal",
        ]

        for kind in message_kinds:
            if kind in raw_completion:
                raw_completion = raw_completion.replace(kind, "")
                return kind, raw_completion
        return None

    def _extract_tool_call_to_return(
        self,
        improvement_instructions: str | None,
        new_tool: ProxyMetaAgentOutput.NewTool | None,
        run_trigger_config: ProxyMetaAgentOutput.RunTriggerConfig | None,
        generate_input_request: GenerateAgentInputToolCallRequest | None,
        updated_version_messages: list[dict[str, Any]] | None = None,
    ) -> MetaAgentToolCallType | None:
        tool_call_to_return = None
        if improvement_instructions:
            tool_call_to_return = UpdateVersionMessagesToolCall(
                improvement_instructions=improvement_instructions,
            )

        if updated_version_messages:
            tool_call_to_return = DirectUpdateVersionMessages(
                messages=updated_version_messages,
            )

        if new_tool:
            tool_call_to_return = AddToolToolCall(
                tool_name=new_tool.name,
                tool_description=new_tool.description,
                tool_parameters=new_tool.parameters,
            )

        if run_trigger_config:
            run_configs = [
                RunCurrentAgentOnModelsToolCall.RunConfig(
                    run_on_column="column_1",
                    model=run_trigger_config.model_1,
                ),
            ]
            if run_trigger_config.model_2:
                run_configs.append(
                    RunCurrentAgentOnModelsToolCall.RunConfig(
                        run_on_column="column_2",
                        model=run_trigger_config.model_2,
                    ),
                )
            if run_trigger_config.model_3:
                run_configs.append(
                    RunCurrentAgentOnModelsToolCall.RunConfig(
                        run_on_column="column_3",
                        model=run_trigger_config.model_3,
                    ),
                )
            tool_call_to_return = RunCurrentAgentOnModelsToolCall(run_configs=run_configs)

        if generate_input_request:
            tool_call_to_return = GenerateAgentInputToolCall(
                instructions=generate_input_request.instructions,
            )

        return tool_call_to_return

    async def stream_proxy_meta_agent_response(  # noqa: C901
        self,
        task_tuple: TaskTuple,
        agent_schema_id: int,
        user_email: str | None,
        messages: list[MetaAgentChatMessage],
        playground_state: PlaygroundState,
        hosted_tool_update_mode: bool = False,
    ) -> AsyncIterator[list[MetaAgentChatMessage]]:
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        if len(messages) == 0:
            yield [MetaAgentChatMessage(role="ASSISTANT", content=FIRST_MESSAGE_CONTENT, sent_at=now)]
            return

        current_agent = await self.storage.task_variant_latest_by_schema_id(task_tuple[0], agent_schema_id)

        latest_agent = await self.storage.task_variants.get_latest_task_variant(task_tuple[0])

        if (
            latest_agent
            and latest_agent.task_schema_id > current_agent.task_schema_id
            and messages[0].sent_at
            and latest_agent.created_at > messages[0].sent_at
        ):
            # The user has created a new schema_id of the agent (happens when adding input variables and structured output)
            current_agent = latest_agent

        self.dispatch_new_user_messages_event(messages)

        proxy_meta_agent_input, agent_runs = await self._build_proxy_meta_agent_input(
            task_tuple,
            current_agent.task_schema_id,
            user_email,
            messages,
            current_agent,
            playground_state,
            hosted_tool_update_mode,
        )

        integration = await self._resolve_integration_for_agent(current_agent, agent_runs, task_tuple, agent_schema_id)

        # Fill the agent input with the right documentations
        proxy_meta_agent_input.integration_documentation = await DocumentationService().get_documentation_by_path(
            integration.documentation_filepaths,
        )
        proxy_meta_agent_input.current_agent.used_integration = integration

        # TODO: remove  messages[-1].content not in ["POLL", "poll"]
        is_user_triggered = self._is_user_triggered(messages) and messages[-1].content not in ["POLL", "poll"]
        is_using_instruction_variables = current_agent.input_schema.json_schema.get("properties", None) is not None
        is_using_structured_generation = not current_agent.output_schema.json_schema.get("format") == "message"
        agent_deployment = self.get_agent_deployment(proxy_meta_agent_input)
        has_tried_other_models = not self._is_only_using_openai_models(agent_runs)

        proxy_meta_agent_input.current_agent.is_input_variables_enabled = is_using_instruction_variables
        proxy_meta_agent_input.current_agent.is_structured_output_enabled = is_using_structured_generation

        tool_call: MetaAgentToolCallType | None = None
        fixed_messages: list[MetaAgentChatMessage] = []

        completion_client = integration.completion_client

        use_tools = False
        if messages[-1].kind == "user_deployed_agent_in_playground":
            if (
                agent_deployment
                and proxy_meta_agent_input.agent_lifecycle_info
                and proxy_meta_agent_input.agent_lifecycle_info.deployment_info
                and proxy_meta_agent_input.agent_lifecycle_info.deployment_info.deployments
                and len(proxy_meta_agent_input.agent_lifecycle_info.deployment_info.deployments) == 1
            ):
                environment = agent_deployment.environment or "production"
                yield [
                    MetaAgentChatMessage(
                        role="ASSISTANT",
                        content=f"Congratulations on deploying your agent! You can now make runs by using 'model={current_agent.task_id}/{current_agent.task_schema_id}/{environment}'.",
                        kind="run_deployed_agent_assistant_proposal",
                    ),
                ]
                return
            else:
                # This is not the first deployed version of the agent, we don't need to show the message
                yield []
                return

        # message_kind = "non_specific"
        if not is_user_triggered:  # Polling
            if (
                agent_runs
                and not has_tried_other_models
                and not self._is_message_kind_already_sent(messages, "try_other_models_assistant_proposal")
            ):
                # "Try non-OpenAI model" use case
                instructions = PROPOSE_NON_OPENAI_MODELS_INSTRUCTIONS
                message_kind = "try_other_models_assistant_proposal"
            elif (
                agent_runs
                and has_tried_other_models
                and not is_using_instruction_variables
                and not self._is_message_kind_already_sent(messages, "setup_input_variables_assistant_proposal")
            ):
                (
                    proxy_meta_agent_input,
                    instructions,
                    message_kind,
                ) = await self._get_proxy_agent_input_variables_proposal_paylaod(
                    proxy_meta_agent_input,
                    agent_runs,
                    integration,
                )
                if integration.use_version_messages:
                    tool_call = UpdateVersionMessagesToolCall(
                        improvement_instructions="Proposing to migrate to input variables. Utilize 'suggested_messages_with_input_variables' and 'suggested_input_variables_example' from the main agent input for new version messages.",
                    )
            elif (
                agent_runs
                and has_tried_other_models
                and is_using_instruction_variables  # We require the user to have used input variables before proposing structured output
                and not is_using_structured_generation
                and not self._is_message_kind_already_sent(messages, "setup_structured_output_assistant_proposal")
            ):
                (
                    proxy_meta_agent_input,
                    instructions,
                    message_kind,
                ) = await self._get_structured_output_proposal_payload(proxy_meta_agent_input, agent_runs, integration)
                completion_client = integration.completion_client_structured_output
            elif (
                agent_runs
                and has_tried_other_models
                and is_using_instruction_variables
                and is_using_structured_generation
                and not self._is_message_kind_already_sent(messages, "setup_deployment_assistant_proposal")
                and proxy_meta_agent_input.agent_lifecycle_info
                and proxy_meta_agent_input.agent_lifecycle_info.deployment_info
                and not proxy_meta_agent_input.agent_lifecycle_info.deployment_info.deployments
            ):
                yield [
                    MetaAgentChatMessage(
                        role="ASSISTANT",
                        content="Congratulations on get all that set! Do you want to deploy your agent now? This will allow you to manage your agent instructions from the WorkflowAI dashboard, and you won't need to deploy every time you update your agent's instructions.",
                        sent_at=now,
                        kind="setup_deployment_assistant_proposal",
                    ),
                ]
                return
            else:
                # This is a polling without required action, return.
                yield []
                return

        else:  # Message is user-triggered
            if messages[-1].kind == "run_deployed_agent_user_confirmation":
                if not self._is_any_run_using_deployment(agent_runs):
                    yield [
                        MetaAgentChatMessage(
                            role="ASSISTANT",
                            content="I can't find any run using your deployment, make sure you have set 'model={current_agent.task_id}/{current_agent.task_schema_id}/{environment}', and you have run the agent at least once after setting the deployment.",
                            kind="run_deployed_agent_user_confirmation",
                        ),
                    ]
                    return
                else:
                    yield [
                        MetaAgentChatMessage(
                            role="ASSISTANT",
                            content="Well done! I confirm that I've received a run using your deployment.",
                            kind="run_deployed_agent_assistant_validation",
                        ),
                    ]
                    return

            elif messages[-1].kind in [
                "try_other_models_user_postponement",
                "setup_input_variables_user_postponement",
                "setup_structured_output_user_postponement",
                "setup_deployment_user_postponement",
                "run_deployed_agent_user_postponement",
            ]:
                yield [
                    MetaAgentChatMessage(
                        role="ASSISTANT",
                        content="Ok. Anything else you need help with?",
                        kind="non_specific",
                    ),
                ]
                return
            elif messages[-1].kind == "try_other_models_user_confirmation":
                if not has_tried_other_models:
                    yield [
                        MetaAgentChatMessage(
                            role="ASSISTANT",
                            content="""I did not receive any run with non-OpenAI models.
Please double check:
- You have updated your model=... parametes as mentioned above.
- You did run the agent at least once after update.
                            """,
                            sent_at=now,
                            kind="try_other_models_assistant_proposal",
                        ),
                    ]
                    return
                else:
                    fixed_messages.append(
                        MetaAgentChatMessage(
                            role="ASSISTANT",
                            content="Congratulations on trying out a non-OpenAI model!",
                            sent_at=now,
                            kind="try_other_models_assistant_validation",
                        ),
                    )
                    yield fixed_messages
                    (
                        proxy_meta_agent_input,
                        instructions,
                        message_kind,
                    ) = await self._get_proxy_agent_input_variables_proposal_paylaod(
                        proxy_meta_agent_input,
                        agent_runs,
                        integration,
                    )
                    if integration.use_version_messages:
                        tool_call = UpdateVersionMessagesToolCall(
                            improvement_instructions="Proposing to migrate to input variables. Utilize 'suggested_messages_with_input_variables' and 'suggested_input_variables_example' from the main agent input for new version messages.",
                        )
            elif messages[-1].kind == "setup_input_variables_user_confirmation":
                if not is_using_instruction_variables:
                    yield [
                        MetaAgentChatMessage(
                            role="ASSISTANT",
                            content="""I did not receive any run with input variables, please try double check:
- You have included input variables in your agent messages, inside double curly braces '{'.
- You are passing your 'input' payload to the completion request. And the 'input' values match the input variables you defined in your 'messages'.
- You did run the agent at least once after update.
                            """,
                            sent_at=now,
                            kind="setup_input_variables_assistant_proposal",
                        ),
                    ]
                    return
                else:
                    # User confirmed input variables
                    fixed_messages.append(
                        MetaAgentChatMessage(
                            role="ASSISTANT",
                            content="Congratulations on setting up input variables! I confirm that your agent is now running with input variables.",
                            sent_at=now,
                            kind="setup_input_variables_assistant_validation",
                        ),
                    )
                    yield fixed_messages
                    (
                        proxy_meta_agent_input,
                        instructions,
                        message_kind,
                    ) = await self._get_structured_output_proposal_payload(
                        proxy_meta_agent_input,
                        agent_runs,
                        integration,
                    )
                    completion_client = integration.completion_client_structured_output

            elif messages[-1].kind == "setup_structured_output_user_confirmation":
                if not is_using_structured_generation:
                    yield [
                        MetaAgentChatMessage(
                            role="ASSISTANT",
                            content="""I did not receive any run with structured output, please try double check:
- You have included a response_format in your completion request.
- You did run the agent at least once after update.
                            """,
                            sent_at=now,
                            kind="setup_structured_output_assistant_proposal",
                        ),
                    ]
                    return
                else:
                    # User confirmed input variables
                    fixed_messages.extend(
                        [
                            MetaAgentChatMessage(
                                role="ASSISTANT",
                                content="Congratulations on setting up structured output! I confirm that your agent is now running with structured output.",
                                sent_at=now,
                                kind="setup_structured_output_assistant_validation",
                            ),
                        ],
                    )
                    yield fixed_messages
                    instructions = PROPOSE_DEPLOYMENT_INSTRUCTIONS
                    message_kind = "setup_deployment_assistant_proposal"
            elif messages[-1].kind == "setup_deployment_user_confirmation":
                if agent_deployment is None:
                    yield [
                        MetaAgentChatMessage(
                            role="ASSISTANT",
                            content="I can't find any deployment for your agent. Please double check https://docs.workflowai.com/deployments for more information.",
                            sent_at=now,
                            kind="setup_deployment_assistant_proposal",
                        ),
                    ]
                    return
                else:
                    if not self._is_any_run_using_deployment(agent_runs):
                        yield [
                            MetaAgentChatMessage(
                                role="ASSISTANT",
                                content=f"Congratulations on deploying your agent! You can now make runs by using 'model={current_agent.task_id}/{current_agent.task_schema_id}/{agent_deployment.environment}'.",
                                sent_at=now,
                                kind="setup_deployment_assistant_validation",
                            ),
                            MetaAgentChatMessage(
                                role="ASSISTANT",
                                content="Let me know when you will have run the agent",
                                sent_at=now,
                                kind="run_deployed_agent_assistant_proposal",
                            ),
                        ]
                        return
                    else:
                        yield [
                            MetaAgentChatMessage(
                                role="ASSISTANT",
                                content="Congratulations on deploying your agent! I confirm that I've received a run using your deployment.",
                                kind="run_deployed_agent_assistant_validation",
                            ),
                        ]
                        return
            elif hosted_tool_update_mode:
                use_tools = True
                instructions = HOSTED_TOOL_UPDATE_INSTRUCTIONS
                message_kind = "non_specific"
            else:
                # This is a another client message like 'I want to do ...'
                use_tools = True
                instructions = GENERIC_INSTRUCTIONS
                message_kind = "non_specific"

        ret: list[MetaAgentChatMessage] = []

        accumulator = ""
        improvement_instructions_chunk: str | None = None
        new_tool: ProxyMetaAgentOutput.NewTool | None = None
        run_trigger_config: ProxyMetaAgentOutput.RunTriggerConfig | None = None
        generate_input_request_chunk: GenerateAgentInputToolCallRequest | None = None
        updated_version_messages_chunk: list[dict[str, Any]] | None = None
        tool_call_to_return: MetaAgentToolCallType | None = None
        async for chunk in proxy_meta_agent(
            input=proxy_meta_agent_input,
            instructions=instructions,
            model_name_prefix=integration.model_name_prefix or "",
            completion_client=completion_client,
            is_using_version_messages=integration.use_version_messages,
            use_tool_calls=use_tools,
            agent_has_output_schema=is_using_structured_generation,
            is_using_input_variables=is_using_instruction_variables,
            is_agent_deployed=agent_deployment is not None,
            hosted_tool_update_mode=hosted_tool_update_mode,
        ):
            if chunk.assistant_answer:
                accumulator = await self._sanitize_output_string(accumulator + chunk.assistant_answer, integration)

                message_kind_detection = self.detect_message_kind_in_raw_completion(accumulator)
                if message_kind_detection:
                    message_kind, accumulator = message_kind_detection

                ret = fixed_messages + [
                    MetaAgentChatMessage(
                        role="ASSISTANT",
                        content=accumulator,
                        sent_at=now,
                        kind=message_kind,
                        tool_call=tool_call,
                        switch_to_schema_id=current_agent.task_schema_id,
                    ),
                ]
                yield ret

            if chunk.improvement_instructions:
                improvement_instructions_chunk = chunk.improvement_instructions
            if chunk.new_tool:
                new_tool = chunk.new_tool
            if chunk.run_trigger_config:
                run_trigger_config = chunk.run_trigger_config
            # Capture the schema edit requests from the chunk
            if chunk.generate_input_request:
                generate_input_request_chunk = chunk.generate_input_request
            if chunk.updated_version_messages:
                updated_version_messages_chunk = chunk.updated_version_messages

        tool_call_to_return = self._extract_tool_call_to_return(
            improvement_instructions_chunk,
            new_tool,
            run_trigger_config,
            generate_input_request_chunk,
            updated_version_messages_chunk,
        )

        if tool_call_to_return:
            ret = fixed_messages + [
                MetaAgentChatMessage(
                    role="ASSISTANT",
                    content=accumulator,
                    sent_at=now,
                    kind=message_kind,
                    tool_call=tool_call_to_return,
                    switch_to_schema_id=current_agent.task_schema_id,
                ),
            ]
            yield ret

        self.dispatch_new_assistant_messages_event(ret)
