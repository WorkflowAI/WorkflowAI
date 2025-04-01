import asyncio
import datetime
import json
import logging
from typing import Any, AsyncIterator, NamedTuple, TypeAlias

from pydantic import BaseModel, Field, model_validator
from typing_extensions import Literal
from workflowai import Run

from api.services.documentation_service import DocumentationService
from api.services.feedback_svc import FeedbackService
from api.services.internal_tasks._internal_tasks_utils import internal_tools_description
from api.services.models import ModelsService
from api.services.reviews import ReviewsService
from api.services.runs import RunsService
from api.services.slack_notifications import SlackNotificationDestination, get_user_and_org_str, send_slack_notification
from api.services.tasks import list_agent_summaries
from api.services.versions import VersionsService
from api.tasks.extract_company_info_from_domain_task import safe_generate_company_description_from_email
from api.tasks.meta_agent import (
    META_AGENT_INSTRUCTIONS,
    EditSchemaToolCallResult,
    GenerateAgentInputToolCallResult,
    ImprovePromptToolCallResult,
    MetaAgentInput,
    MetaAgentOutput,
    RunCurrentAgentOnModelsToolCallRequest,
    RunCurrentAgentOnModelsToolCallResult,
    meta_agent,
)
from api.tasks.meta_agent import (
    MetaAgentChatMessage as MetaAgentChatMessageDomain,
)
from api.tasks.meta_agent import (
    PlaygroundState as PlaygroundStateDomain,
)
from core.domain.events import EventRouter, MetaAgentChatMessagesSent
from core.domain.fields.file import File
from core.domain.task_run import SerializableTaskRun
from core.domain.task_variant import SerializableTaskVariant
from core.domain.url_content import URLContent
from core.runners.workflowai.utils import extract_files
from core.storage import ObjectNotFoundException, TaskTuple
from core.storage.backend_storage import BackendStorage
from core.tools import ToolKind
from core.utils.hash import compute_obj_hash
from core.utils.url_utils import extract_and_fetch_urls

FIRST_MESSAGE_CONTENT = "Hi, I'm WorkflowAI's agent. How can I help you?"


def _reverse_optional_bool(value: bool | None) -> bool | None:
    if value is None:
        return None
    return not value


class HasActiveRunAndDate(NamedTuple):
    has_active_runs: bool
    latest_active_run_date: datetime.datetime | None


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
            self.tool_call_id = f"{self.tool_name}_{compute_obj_hash(obj={**self.model_dump(), 'ts': datetime.datetime.now().isoformat()})}"
        return self


class PlaygroundState(BaseModel):
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

        def to_domain(self) -> PlaygroundStateDomain.SelectedModels:
            return PlaygroundStateDomain.SelectedModels(
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


MetaAgentToolCallType: TypeAlias = (
    ImprovePromptToolCall | EditSchemaToolCall | RunCurrentAgentOnModelsToolCall | GenerateAgentInputToolCall
)


class MetaAgentChatMessage(BaseModel):
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

    def to_domain(self) -> MetaAgentChatMessageDomain:
        return MetaAgentChatMessageDomain(
            role=self.role,
            content=self.content,
            tool_call=self.tool_call.to_domain() if self.tool_call else None,
            tool_call_status=self.tool_call.status if self.tool_call else None,
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

    async def fetch_agent_runs(self, task_tuple: TaskTuple, agent_run_ids: list[str]) -> list[SerializableTaskRun]:
        """Allow to concurrently fetch several concurrently and manage expections"""

        agent_runs_results = await asyncio.gather(
            *[self.runs_service.run_by_id(task_tuple, run_id) for run_id in agent_run_ids],
            return_exceptions=True,
        )
        valid_runs: list[SerializableTaskRun] = []
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
            )
            for model in models
        ]

    def _extract_files_from_agent_input(
        self,
        agent_input: dict[str, Any] | None,
        input_schema: dict[str, Any],
    ) -> tuple[dict[str, Any], list[PlaygroundStateDomain.InputFile] | None]:
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
                    PlaygroundStateDomain.InputFile(
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

    async def _build_meta_agent_input(
        self,
        task_tuple: TaskTuple,
        agent_schema_id: int,
        user_email: str | None,
        messages: list[MetaAgentChatMessage],
        current_agent: SerializableTaskVariant,
        playground_state: PlaygroundState,
    ) -> tuple[MetaAgentInput, list[SerializableTaskRun]]:
        (
            company_description,
            existing_agents,
            agent_runs,
            feedback_page,
            has_active_runs,
            reviewed_input_count,
        ) = await asyncio.gather(
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
        )
        existing_agents = [str(agent) for agent in existing_agents or []]

        # Extract files from agent_input
        agent_input_schema = current_agent.input_schema.json_schema.copy()
        agent_input_copy, agent_input_files = self._extract_files_from_agent_input(
            playground_state.agent_input,
            agent_input_schema,
        )

        return MetaAgentInput(
            current_datetime=datetime.datetime.now(),
            messages=[message.to_domain() for message in messages],
            latest_messages_url_content=await self._extract_url_content_from_messages(messages),
            company_context=MetaAgentInput.CompanyContext(
                company_name=company_description.company_name if company_description else None,
                company_description=company_description.description if company_description else None,
                company_locations=company_description.locations if company_description else None,
                company_industries=company_description.industries if company_description else None,
                company_products=company_description.products if company_description else None,
                existing_agents_descriptions=existing_agents or [],
            ),
            workflowai_documentation_sections=await DocumentationService().get_relevant_doc_sections(
                chat_messages=[message.to_domain() for message in messages],
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
                    for agent_run in agent_runs or []
                ],
            ),
            agent_lifecycle_info=MetaAgentInput.AgentLifecycleInfo(
                deployment_info=MetaAgentInput.AgentLifecycleInfo.DeploymentInfo(
                    has_api_or_sdk_runs=has_active_runs.has_active_runs,
                    latest_api_or_sdk_run_date=has_active_runs.latest_active_run_date,
                    deployments=await self.list_deployments(task_tuple, agent_schema_id),
                )
                if has_active_runs
                else None,
                feedback_info=MetaAgentInput.AgentLifecycleInfo.FeedbackInfo(
                    user_feedback_count=feedback_page.count,
                    latest_user_feedbacks=feedback_page.items,
                )
                if feedback_page
                else None,
                internal_review_info=MetaAgentInput.AgentLifecycleInfo.InternalReviewInfo(
                    reviewed_input_count=reviewed_input_count,
                ),
            ),
        ), agent_runs

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

    def _sanitize_agent_run_id(self, candidate_agent_run_id: str, valid_agent_runs: list[SerializableTaskRun]) -> str:
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
        agent_runs: list[SerializableTaskRun],
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

        if meta_agent_output.edit_schema_tool_call:
            return EditSchemaToolCall(
                edition_request_message=meta_agent_output.edit_schema_tool_call.edition_request_message,
                auto_run=self._resolve_auto_run(
                    tool_call_type=EditSchemaToolCall,
                    initial_auto_run=_reverse_optional_bool(
                        meta_agent_output.edit_schema_tool_call.ask_user_confirmation,
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

    async def stream_meta_agent_response(
        self,
        task_tuple: TaskTuple,
        agent_schema_id: int,
        user_email: str | None,
        messages: list[MetaAgentChatMessage],
        playground_state: PlaygroundState,
    ) -> AsyncIterator[list[MetaAgentChatMessage]]:
        if len(messages) == 0:
            yield [MetaAgentChatMessage(role="ASSISTANT", content=FIRST_MESSAGE_CONTENT)]
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
        chunk: Run[MetaAgentOutput] | None = None
        async for chunk in meta_agent.stream(meta_agent_input, temperature=0.5):
            if chunk.output.content:
                ret = [
                    MetaAgentChatMessage(
                        role="ASSISTANT",
                        content=chunk.output.content,
                        feedback_token=chunk.feedback_token,
                    ),
                ]
                yield ret

        if chunk and (tool_call := self._extract_tool_call_from_meta_agent_output(chunk.output, agent_runs, messages)):
            ret = [
                MetaAgentChatMessage(
                    role="ASSISTANT",
                    content=chunk.output.content or "",
                    tool_call=tool_call,
                    feedback_token=chunk.feedback_token,
                ),
            ]
            yield ret

        self.dispatch_new_assistant_messages_event(ret)

    async def notify_meta_agent_messages_sent(self, event: MetaAgentChatMessagesSent):
        user_and_org_str = get_user_and_org_str(event=event)

        for message in event.messages:
            if message.role == "USER":
                message_str = f"{user_and_org_str} sent a message to the meta-agent:\n\n```{message.content}```"
            else:
                message_str = f"Meta-agent sent a message to {user_and_org_str}:\n\n```{message.content}```"

                if message.tool_call:
                    message_str += f"\n\n```Tool call: {json.dumps(message.tool_call.model_dump(), indent=2)}```"

            await send_slack_notification(
                message=message_str,
                user_email=event.user_properties.user_email if event.user_properties else None,
                destination=SlackNotificationDestination.CUSTOMER_JOURNEY,
            )
