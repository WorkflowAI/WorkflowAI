import asyncio
import datetime
import logging
from typing import Any, AsyncIterator, NamedTuple, TypeAlias, cast

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
from core.agents.ai_engineer_agent import (
    AI_ENGINEER_INSTRUCTIONS,
    AIEngineerAgentInput,
    AIEngineerAgentOutput,
    CurrentAgentContext,
    EditSchemaDescriptionAndExamplesToolCallRequest,
    EditSchemaStructureToolCallRequest,
    UserContext,
    ai_engineer_agent,
)
from core.agents.ai_engineer_agent import (
    AgentRun as AIEngineerAgentRun,
)
from core.agents.ai_engineer_agent import (
    AIEngineerAgentChatMessage as AIEngineerAgentChatMessageDomain,
)
from core.agents.extract_company_info_from_domain_task import (
    ExtractCompanyInfoFromDomainTaskOutput,
    safe_generate_company_description_from_email,
)
from core.agents.meta_agent import MetaAgentChatMessage
from core.domain.agent_run import AgentRun
from core.domain.documentation_section import DocumentationSection
from core.domain.events import EventRouter, MetaAgentChatMessagesSent
from core.domain.fields.chat_message import ChatMessage
from core.domain.integration.integration_domain import (
    ProgrammingLanguage,
)
from core.domain.page import Page
from core.domain.task_typology import TaskTypology
from core.domain.task_variant import SerializableTaskVariant
from core.storage import TaskTuple
from core.storage.backend_storage import BackendStorage
from core.tools import ToolKind
from core.utils.hash import compute_obj_hash
from core.utils.tool_utils.tool_utils import get_tools_description_openai_format_str


class AIEngineerAgentContext(NamedTuple):
    company_description: ExtractCompanyInfoFromDomainTaskOutput | None
    existing_agents: list[str] | None
    agent_runs: list[AgentRun] | None
    feedback_page: Page[CurrentAgentContext.AgentLifecycleInfo.FeedbackInfo.AgentFeedback] | None
    reviewed_input_count: int | None


def get_programming_language_for_user_agent(user_agent: str) -> ProgrammingLanguage:
    user_agent = user_agent.lower()
    if "python" in user_agent:
        return ProgrammingLanguage.PYTHON
    if any(kw in user_agent for kw in ("javascript", "js", "typescript", "ts")):
        return ProgrammingLanguage.TYPESCRIPT
    return ProgrammingLanguage.PYTHON


class AIEngineerToolCall(BaseModel):
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


class ImprovePromptToolCall(AIEngineerToolCall):
    tool_name: str = "improve_agent_instructions"

    run_id: str | None = Field(
        default=None,
        description="The id of the run to improve",
    )
    run_feedback_message: str = Field(
        description="The feedback on the run (what is wrong with the output of the run, what is the expected output, etc.).",
    )


class EditSchemaToolCall(AIEngineerToolCall):
    tool_name: str = "edit_agent_schema"

    edition_request_message: str | None = Field(
        default=None,
        description="The message to edit the agent schema with.",
    )


class RunCurrentAgentOnModelsToolCall(AIEngineerToolCall):
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


class GenerateAgentInputToolCall(AIEngineerToolCall):
    tool_name: str = "generate_agent_input"

    instructions: str | None = Field(
        default=None,
        description="The instructions on how to generate the agent input, this message will be passed to the input generation agent.",
    )


class UpdateVersionMessagesToolCall(AIEngineerToolCall):
    tool_name: str = "update_version_messages"

    improvement_instructions: str = Field(
        description="Instructions on how to improve the current agent version's messages.",
    )

    def to_domain(self) -> None:
        return None


class AddToolToolCall(AIEngineerToolCall):
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


AIEngineerToolCallType: TypeAlias = (
    ImprovePromptToolCall
    | EditSchemaToolCall
    | RunCurrentAgentOnModelsToolCall
    | GenerateAgentInputToolCall
    | UpdateVersionMessagesToolCall
    | AddToolToolCall
)


class AIEngineerChatMessage(BaseModel):
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

    tool_call: AIEngineerToolCallType | None = Field(
        default=None,
        description="The tool call to run in the frontend to help the user improve its agent instructions.",
    )

    feedback_token: str | None = None

    def to_domain(self) -> AIEngineerAgentChatMessageDomain:
        return AIEngineerAgentChatMessageDomain(
            role=self.role,
            content=self.content,
            tool_call=self.tool_call.model_dump() if self.tool_call else None,
            tool_call_status=self.tool_call.status if self.tool_call else None,
        )

    def to_meta_agent_chat_message(self) -> MetaAgentChatMessage:
        return MetaAgentChatMessage(
            role=self.role,
            content=self.content,
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


class AIEngineerReponse(BaseModel):
    messages: list[AIEngineerChatMessage]

    class UsefulContext(BaseModel):
        relevant_doc_sections: list[DocumentationSection]
        latest_runs: list[AgentRun]
        deployments: list[CurrentAgentContext.AgentLifecycleInfo.DeploymentInfo.Deployment]

    useful_context: UsefulContext


class AIEngineerService:
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

    async def get_reviewed_input_count(
        self,
        task_tuple: TaskTuple | None,
        agent_schema_id: int | None,
    ) -> int | None:
        if task_tuple is None or agent_schema_id is None:
            return None

        reviews = await self.reviews_service.list_reviewed_inputs(task_tuple, agent_schema_id)
        return len(reviews)

    def dispatch_new_user_messages_event(self, messages: list[AIEngineerChatMessage]):
        # Get all consecutive USER messages at the end of the conversation
        latest_user_messages: list[AIEngineerChatMessage] = []
        for message in reversed(messages):
            if message.role == "USER":
                latest_user_messages.insert(0, message)
            else:
                break

        if latest_user_messages:
            self.event_router(
                MetaAgentChatMessagesSent(
                    messages=[message.to_meta_agent_chat_message() for message in latest_user_messages],
                ),
            )
        else:
            self._logger.warning("No user message found in the list of messages")

    def dispatch_new_assistant_messages_event(self, messages: list[AIEngineerChatMessage]):
        self.event_router(
            MetaAgentChatMessagesSent(messages=[message.to_meta_agent_chat_message() for message in messages]),
        )

    async def _build_model_list(
        self,
        instructions: str | None,
        current_agent: SerializableTaskVariant | None,
    ) -> list[AIEngineerAgentInput.Model]:
        if current_agent:
            models = await self.models_service.models_for_task(
                current_agent,
                instructions=instructions,
                requires_tools=None,
            )
        else:
            models = await self.models_service.model_for_task_typology(
                # TODO: plug more info about the task typology here,when we know about it
                TaskTypology(),
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
            AIEngineerAgentInput.Model(
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

    async def list_agent_deployments(
        self,
        task_tuple: TaskTuple,
        agent_schema_id: int | None,
    ) -> list[CurrentAgentContext.AgentLifecycleInfo.DeploymentInfo.Deployment]:
        versions = await self.versions_service.list_version_majors(task_tuple, agent_schema_id, self.models_service)

        deployments: list[CurrentAgentContext.AgentLifecycleInfo.DeploymentInfo.Deployment] = []

        for version in versions:
            for minor in version.minors or []:
                deployments.extend(
                    [
                        CurrentAgentContext.AgentLifecycleInfo.DeploymentInfo.Deployment(
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

    async def _list_feedback(
        self,
        task_tuple: TaskTuple | None,
        agent_schema_id: int | None,
    ) -> Page[CurrentAgentContext.AgentLifecycleInfo.FeedbackInfo.AgentFeedback] | None:
        if task_tuple is None or agent_schema_id is None:
            return None

        return await self.feedback_service.list_feedback(
            task_tuple[1],
            run_id=None,
            limit=10,
            offset=0,
            map_fn=CurrentAgentContext.AgentLifecycleInfo.FeedbackInfo.AgentFeedback.from_domain,
        )

    async def _fetch_ai_engineer_agent_context(
        self,
        task_tuple: TaskTuple | None,
        agent_schema_id: int | None,
        user_email: str | None,
    ) -> AIEngineerAgentContext:
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
            reviewed_input_count,
        ) = await asyncio.gather(
            safe_generate_company_description_from_email(user_email),
            list_agent_summaries(self.storage, limit=10),
            self._fetch_latest_agent_runs(task_tuple, agent_schema_id),
            self._list_feedback(task_tuple, agent_schema_id),
            self.get_reviewed_input_count(task_tuple, agent_schema_id),
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

        if isinstance(feedback_page, BaseException):
            self._logger.warning("Failed to fetch feedback_page", exc_info=feedback_page)
            feedback_page = None

        if isinstance(reviewed_input_count, BaseException):
            self._logger.warning("Failed to fetch reviewed_input_count", exc_info=reviewed_input_count)
            reviewed_input_count = None

        return AIEngineerAgentContext(
            company_description=company_description,
            existing_agents=existing_agents,
            agent_runs=agent_runs,
            feedback_page=feedback_page,
            reviewed_input_count=reviewed_input_count,
        )

    async def _build_ai_engineer_agent_input(
        self,
        task_tuple: TaskTuple | None,
        current_agent: SerializableTaskVariant | None,
        user_email: str | None,
        messages: list[AIEngineerChatMessage],
        user_programming_language: str | None,
        user_code_extract: str | None,
    ) -> tuple[AIEngineerAgentInput, list[AgentRun]]:
        # Fetch context data with exception handling
        context = await self._fetch_ai_engineer_agent_context(
            task_tuple,
            current_agent.task_schema_id if current_agent else None,
            user_email,
        )

        # Convert domain AgentRuns to AI Engineer AgentRuns
        ai_engineer_agent_runs: list[AIEngineerAgentRun] | None = None
        if context.agent_runs:
            ai_engineer_agent_runs = [
                AIEngineerAgentRun(
                    id=agent_run.id,
                    model=agent_run.group.properties.model or "",
                    input=str(agent_run.task_input),
                    output=str(agent_run.task_output),
                    error=agent_run.error.model_dump() if agent_run.error else None,
                    raw_response=agent_run.llm_completions[-1].response if agent_run.llm_completions else None,
                    cost_usd=agent_run.cost_usd,
                    duration_seconds=agent_run.duration_seconds,
                    user_evaluation=agent_run.user_review,
                    tool_calls=[
                        AIEngineerAgentRun.ToolCall(
                            name=tool_call.tool_name,
                            input=tool_call.tool_input_dict,
                        )
                        for llm_completion in agent_run.llm_completions or []
                        for tool_call in llm_completion.tool_calls or []
                    ],
                )
                for agent_run in context.agent_runs
            ]

        if current_agent and task_tuple:
            deployments = await self.list_agent_deployments(task_tuple, current_agent.task_schema_id)
        else:
            deployments = None

        return AIEngineerAgentInput(
            current_datetime=datetime.datetime.now(tz=datetime.timezone.utc),
            chat_messages=[message.to_domain() for message in messages],
            user_programming_language=user_programming_language,
            user_code_extract=user_code_extract,
            current_agent_context=CurrentAgentContext(
                current_agent=CurrentAgentContext.Agent(
                    name=current_agent.name,
                    slug=current_agent.task_id,
                    schema_id=current_agent.task_schema_id,
                    description=current_agent.description,
                    input_schema=current_agent.input_schema.json_schema,
                    output_schema=current_agent.output_schema.json_schema,
                    is_input_variables_enabled=current_agent.input_schema.json_schema.get("properties", None)
                    is not None,
                    is_structured_output_enabled=not current_agent.output_schema.json_schema.get("format") == "message",
                    is_deployed=deployments is not None,
                ),
                latest_agent_run=ai_engineer_agent_runs[0]
                if ai_engineer_agent_runs and len(ai_engineer_agent_runs) > 0
                else None,
                previous_agent_runs=ai_engineer_agent_runs[1:]
                if ai_engineer_agent_runs and len(ai_engineer_agent_runs) > 1
                else None,
                agent_lifecycle_info=CurrentAgentContext.AgentLifecycleInfo(
                    deployment_info=CurrentAgentContext.AgentLifecycleInfo.DeploymentInfo(
                        deployments=deployments,
                    ),
                    feedback_info=CurrentAgentContext.AgentLifecycleInfo.FeedbackInfo(
                        user_feedback_count=context.feedback_page.count,
                        latest_user_feedbacks=context.feedback_page.items,
                    )
                    if context.feedback_page
                    else None,
                    internal_review_info=CurrentAgentContext.AgentLifecycleInfo.InternalReviewInfo(
                        reviewed_input_count=context.reviewed_input_count,
                    ),
                ),
            )
            if current_agent and task_tuple
            else None,
            user_context=UserContext(
                company_context=UserContext.CompanyContext(
                    company_name=context.company_description.company_name if context.company_description else None,
                    company_description=context.company_description.description
                    if context.company_description
                    else None,
                    company_locations=context.company_description.locations if context.company_description else None,
                    company_industries=context.company_description.industries if context.company_description else None,
                    company_products=context.company_description.products if context.company_description else None,
                    existing_agents_descriptions=context.existing_agents or [],
                ),
            ),
            workflowai_documentation_sections=await DocumentationService().get_relevant_doc_sections(
                chat_messages=[message.to_chat_message() for message in messages],
                agent_instructions="",
            ),
            available_hosted_tools_description=internal_tools_description(
                include={ToolKind.WEB_BROWSER_TEXT, ToolKind.WEB_SEARCH_PERPLEXITY_SONAR_PRO},
                formatting_func=get_tools_description_openai_format_str,
            ),
            available_models=[
                AIEngineerAgentInput.Model(
                    id=model.id,
                    name=model.name,
                    is_supported_for_agent=model.is_supported_for_agent,
                    is_not_supported_reason=model.is_not_supported_reason,
                    is_default=model.is_default,
                    is_latest=model.is_latest,
                    quality_index=model.quality_index,
                    quality_index_ranking=model.quality_index_ranking,
                    speed_index=model.speed_index,
                    speed_index_ranking=model.speed_index_ranking,
                    context_window_tokens=model.context_window_tokens,
                    supports_structured_output=model.supports_structured_output,
                    estimate_cost_per_thousand_runs_usd=model.estimate_cost_per_thousand_runs_usd,
                    cost_ranking=model.cost_ranking,
                )
                for model in await self._build_model_list("", current_agent)
            ],
        ), context.agent_runs or []

    async def _fetch_latest_agent_runs(
        self,
        task_tuple: TaskTuple | None,
        task_schema_id: int | None,
    ) -> list[AgentRun]:
        if task_tuple is None:
            return []

        return [
            run
            async for run in self.storage.task_runs.list_latest_runs(
                task_uid=task_tuple[1],
                limit=10,
            )
            if task_schema_id is None or run.task_schema_id == task_schema_id
        ]

    def _extract_tool_call_to_return(
        self,
        improvement_instructions: str | None,
        new_tool: AIEngineerAgentOutput.NewTool | None,
        edit_schema_structure_request: EditSchemaStructureToolCallRequest | None,
        edit_schema_description_and_examples_request: EditSchemaDescriptionAndExamplesToolCallRequest | None,
    ) -> AIEngineerToolCallType | None:
        tool_call_to_return = None
        if improvement_instructions:
            tool_call_to_return = UpdateVersionMessagesToolCall(
                improvement_instructions=improvement_instructions,
            )

        if new_tool:
            tool_call_to_return = AddToolToolCall(
                tool_name=new_tool.name,
                tool_description=new_tool.description,
                tool_parameters=new_tool.parameters,
            )

        if edit_schema_structure_request:
            tool_call_to_return = EditSchemaToolCall(
                edition_request_message=edit_schema_structure_request.edition_request_message,
            )

        if edit_schema_description_and_examples_request:
            tool_call_to_return = EditSchemaToolCall(
                edition_request_message=edit_schema_description_and_examples_request.description_and_examples_edition_request_message,
            )

        return tool_call_to_return

    async def stream_ai_engineer_agent_response(
        self,
        task_tuple: TaskTuple | None,
        agent_schema_id: int | None,
        user_email: str | None,
        user_programming_language: str | None,
        user_code_extract: str | None,
        messages: list[AIEngineerChatMessage],
    ) -> AsyncIterator[AIEngineerReponse]:
        now = datetime.datetime.now(tz=datetime.timezone.utc)

        current_agent: SerializableTaskVariant | None = None
        if task_tuple is not None and agent_schema_id is not None:
            current_agent = await self.storage.task_variant_latest_by_schema_id(task_tuple[0], agent_schema_id)
        elif task_tuple is not None and agent_schema_id is None:
            current_agent = await self.storage.task_variants.get_latest_task_variant(task_tuple[0])

        ai_engineer_input, agent_runs = await self._build_ai_engineer_agent_input(
            task_tuple,
            current_agent,
            user_email,
            messages,
            user_programming_language,
            user_code_extract,
        )

        tool_call: AIEngineerToolCallType | None = None
        fixed_messages: list[AIEngineerChatMessage] = []

        ret: list[AIEngineerChatMessage] = []

        accumulator: str = ""
        improvement_instructions_chunk: str | None = None
        new_tool: AIEngineerAgentOutput.NewTool | None = None
        edit_schema_structure_request_chunk: EditSchemaStructureToolCallRequest | None = None
        edit_schema_description_and_examples_request_chunk: EditSchemaDescriptionAndExamplesToolCallRequest | None = (
            None
        )
        tool_call_to_return: AIEngineerToolCallType | None = None
        async for chunk in ai_engineer_agent(
            input=ai_engineer_input,
            instructions=AI_ENGINEER_INSTRUCTIONS,
        ):
            if chunk.assistant_answer:
                accumulator += chunk.assistant_answer

                ret = fixed_messages + [
                    AIEngineerChatMessage(
                        role="ASSISTANT",
                        content=accumulator,
                        sent_at=now,
                        tool_call=tool_call,
                    ),
                ]
                yield AIEngineerReponse(
                    messages=ret,
                    useful_context=AIEngineerReponse.UsefulContext(
                        relevant_doc_sections=ai_engineer_input.workflowai_documentation_sections,
                        latest_runs=agent_runs,
                        deployments=ai_engineer_input.current_agent_context.agent_lifecycle_info.deployment_info.deployments
                        if ai_engineer_input.current_agent_context
                        and ai_engineer_input.current_agent_context.agent_lifecycle_info
                        and ai_engineer_input.current_agent_context.agent_lifecycle_info.deployment_info
                        and ai_engineer_input.current_agent_context.agent_lifecycle_info.deployment_info.deployments
                        else [],
                    ),
                )

            if chunk.improvement_instructions:
                improvement_instructions_chunk = chunk.improvement_instructions
            if chunk.new_tool:
                new_tool = chunk.new_tool
            edit_schema_structure_request_chunk = chunk.edit_schema_structure_request
            edit_schema_description_and_examples_request_chunk = chunk.edit_schema_description_and_examples_request

        tool_call_to_return = self._extract_tool_call_to_return(
            improvement_instructions_chunk,
            new_tool,
            edit_schema_structure_request_chunk,
            edit_schema_description_and_examples_request_chunk,
        )

        if tool_call_to_return:
            ret = fixed_messages + [
                AIEngineerChatMessage(
                    role="ASSISTANT",
                    content=accumulator,
                    sent_at=now,
                    tool_call=tool_call_to_return,
                ),
            ]
            yield AIEngineerReponse(
                messages=ret,
                useful_context=AIEngineerReponse.UsefulContext(
                    relevant_doc_sections=ai_engineer_input.workflowai_documentation_sections,
                    latest_runs=agent_runs,
                    deployments=ai_engineer_input.current_agent_context.agent_lifecycle_info.deployment_info.deployments
                    if ai_engineer_input.current_agent_context
                    and ai_engineer_input.current_agent_context.agent_lifecycle_info
                    and ai_engineer_input.current_agent_context.agent_lifecycle_info.deployment_info
                    and ai_engineer_input.current_agent_context.agent_lifecycle_info.deployment_info.deployments
                    else [],
                ),
            )
