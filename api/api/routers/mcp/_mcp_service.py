import logging
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any, NamedTuple

from api.dependencies.services import _feedback_token_generator  # pyright: ignore[reportPrivateUsage]
from api.routers.mcp._mcp_errors import MCPError
from api.routers.mcp._mcp_models import (
    AgentListItem,
    AgentResponse,
    AgentSortField,
    ConciseLatestModelResponse,
    ConciseModelResponse,
    DeployAgentResponse,
    EmptyModel,
    MajorVersion,
    MCPRun,
    MCPToolReturn,
    ModelSortField,
    PaginatedMCPToolReturn,
    SearchResponse,
    SortOrder,
    UsefulLinks,
)
from api.routers.mcp._mcp_utils import extract_agent_id_and_run_id
from api.routers.mcp._utils.agent_sorting import sort_agents
from api.routers.mcp._utils.model_sorting import sort_models
from api.routers.openai_proxy._openai_proxy_handler import OpenAIProxyHandler
from api.routers.openai_proxy._openai_proxy_models import (
    OpenAIProxyChatCompletionRequest,
    OpenAIProxyChatCompletionResponse,
)
from api.services import tasks
from api.services.documentation_service import DocumentationService
from api.services.internal_tasks.ai_engineer_service import AIEngineerService
from api.services.models import ModelsService
from api.services.run import RunService
from api.services.runs.runs_service import RunsService
from api.services.runs_search import RunsSearchService
from api.services.task_deployments import TaskDeploymentsService
from api.services.versions import VersionsService
from core.agents.mcp_feedback_processing_agent import (
    mcp_feedback_processing_agent,
)
from core.domain.agent_run import AgentRun
from core.domain.consts import INPUT_KEY_MESSAGES, WORKFLOWAI_APP_URL
from core.domain.events import EventRouter
from core.domain.fields.chat_message import ChatMessage
from core.domain.message import Messages
from core.domain.models.model_data import FinalModelData, LatestModel
from core.domain.models.model_datas_mapping import MODEL_DATAS
from core.domain.models.models import Model
from core.domain.search_query import FieldQuery, SearchOperator
from core.domain.task_group import TaskGroup, TaskGroupQuery
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_info import TaskInfo
from core.domain.task_variant import SerializableTaskVariant
from core.domain.tenant_data import PublicOrganizationData
from core.domain.users import UserIdentifier
from core.domain.version_environment import VersionEnvironment
from core.storage import ObjectNotFoundException
from core.storage.backend_storage import BackendStorage
from core.utils.background import add_background_task
from core.utils.schemas import FieldType

_logger = logging.getLogger(__name__)


# Claude Code only support 25k tokens, for example.
# Overall it's a good practice to limit the tool return tokens to avoid overflowing the coding agents context.
MAX_TOOL_RETURN_TOKENS = 20000


class MCPService:
    def __init__(
        self,
        storage: BackendStorage,
        ai_engineer_service: AIEngineerService,
        runs_service: RunsService,
        run_service: RunService,
        versions_service: VersionsService,
        models_service: ModelsService,
        task_deployments_service: TaskDeploymentsService,
        user_email: str | None,
        tenant: PublicOrganizationData,
        event_router: EventRouter,
    ):
        self.storage = storage
        self.ai_engineer_service = ai_engineer_service
        self.runs_service = runs_service
        self.versions_service = versions_service
        self.models_service = models_service
        self.task_deployments_service = task_deployments_service
        self.user_email = user_email
        self.tenant = tenant
        self.run_service = run_service
        self.event_router = event_router

    def _get_useful_links(self, agent_id: str | None, agent_schema_id: int | None) -> UsefulLinks:
        if agent_id is None:
            agent_id = "<example_agent_id>"

        tenant_slug = self.tenant.slug

        return UsefulLinks(
            useful_links=[
                UsefulLinks.Link(
                    title="Agents list",
                    url=f"{WORKFLOWAI_APP_URL}/{tenant_slug}/agents",
                    description="View all agents in the user's organization, also allow to see the count of runs and cost of the last 7 days",
                ),
                UsefulLinks.Link(
                    title="API Keys management model",
                    url=f"{WORKFLOWAI_APP_URL}/keys",
                    description="View and create API keys for the user's organization",
                ),
                UsefulLinks.Link(
                    title="WorkflowAI playground",
                    url=f"{WORKFLOWAI_APP_URL}/{tenant_slug}/agents/{agent_id}/{agent_schema_id or 1}",
                    description="Main page of the WorkflowAI web app, allow to run agents on different models, update version messages, and more",
                ),
                UsefulLinks.Link(
                    title="Agent runs",
                    url=f"{WORKFLOWAI_APP_URL}/{tenant_slug}/agents/{agent_id}/{agent_schema_id or 1}/runs",
                    description="View runs for a specific agent",
                ),
                UsefulLinks.Link(
                    title="Agent versions",
                    url=f"{WORKFLOWAI_APP_URL}/{tenant_slug}/agents/{agent_id}/{agent_schema_id or 1}/versions",
                    description="View versions for a specific agent",
                ),
                UsefulLinks.Link(
                    title="Deployments",
                    url=f"{WORKFLOWAI_APP_URL}/{tenant_slug}/agents/{agent_id}/{agent_schema_id or 1}/deployments",
                    description="View deployments (deployed versions) for a specific agent",
                ),
                UsefulLinks.Link(
                    title="Agent side-by-side",
                    url=f"{WORKFLOWAI_APP_URL}/{tenant_slug}/agents/{agent_id}/{agent_schema_id or 1}/side-by-side",
                    description="View side-by-side comparison of two versions of an agent",
                ),
                UsefulLinks.Link(
                    title="Agent reviews",
                    url=f"{WORKFLOWAI_APP_URL}/{tenant_slug}/agents/{agent_id}/{agent_schema_id or 1}/reviews",
                    description="View reviews for a specific agent created by staff members in the organization",
                ),
                UsefulLinks.Link(
                    title="Agent benchmarks",
                    url=f"{WORKFLOWAI_APP_URL}/{tenant_slug}/agents/{agent_id}/{agent_schema_id or 1}/benchmarks",
                    description="View benchmarks for a specific agent, allow to compare different versions / models of an agent and compare their correctness, latency, and price",
                ),
                UsefulLinks.Link(
                    title="Agent feedback",
                    url=f"{WORKFLOWAI_APP_URL}/{tenant_slug}/agents/{agent_id}/{agent_schema_id or 1}/feedback",
                    description="View feedback for a specific agent created by end users (customers)",
                ),
                UsefulLinks.Link(
                    title="Agent cost",
                    url=f"{WORKFLOWAI_APP_URL}/{tenant_slug}/agents/{agent_id}/{agent_schema_id or 1}/cost",
                    description="View cost for a specific agent on different time frames (yesterday, last week, last month, last year, all time)",
                ),
                UsefulLinks.Link(
                    title="WorkflowAI offical documentation",
                    url="https://docs.workflowai.com",
                    description="Official documentation for WorkflowAI, including guides, API references, and more",
                ),
            ],
        )

    async def list_models(
        self,
        page: int,
        sort_by: ModelSortField,
        order: SortOrder,
        agent_id: str | None,
        agent_schema_id: int | None,
        agent_requires_tools: bool = False,
    ) -> PaginatedMCPToolReturn[None, ConciseModelResponse | ConciseLatestModelResponse]:
        if agent_id:
            if agent_schema_id is not None:
                agent = await self.storage.task_variant_latest_by_schema_id(agent_id, agent_schema_id)
            else:
                agent = await self.storage.task_variants.get_latest_task_variant(agent_id)

            if agent:
                models = await self.models_service.models_for_task(
                    agent,
                    instructions=None,
                    requires_tools=agent_requires_tools,
                )
                model_responses: list[ConciseModelResponse | ConciseLatestModelResponse] = [
                    ConciseModelResponse.from_model_for_task(m) for m in models if m.is_not_supported_reason is None
                ]
                sort_models(model_responses, sort_by, order)
                return PaginatedMCPToolReturn[None, ConciseModelResponse | ConciseLatestModelResponse](
                    success=True,
                    items=model_responses,
                ).paginate(max_tokens=MAX_TOOL_RETURN_TOKENS, page=page)

        def _model_data_iterator() -> Iterator[ConciseLatestModelResponse | ConciseModelResponse]:
            for model in Model:
                data = MODEL_DATAS[model]
                if isinstance(data, LatestModel):
                    points_to_model = MODEL_DATAS[data.model]
                    if isinstance(points_to_model, FinalModelData):
                        yield ConciseLatestModelResponse(
                            id=model.value,
                            currently_points_to=points_to_model.model.value,
                        )
                    continue
                elif isinstance(data, FinalModelData):
                    yield ConciseModelResponse.from_model_data(model.value, data)
                else:
                    # Skipping deprecated models
                    continue

        model_responses = list(_model_data_iterator())
        sort_models(model_responses, sort_by, order)

        return PaginatedMCPToolReturn[None, ConciseModelResponse | ConciseLatestModelResponse](
            success=True,
            items=model_responses,
        ).paginate(max_tokens=MAX_TOOL_RETURN_TOKENS, page=page)

    class RunVersionVariant(NamedTuple):
        run: AgentRun
        version: TaskGroup
        variant: SerializableTaskVariant | None
        task_info: TaskInfo

    async def _fetch_run_version_variant(self, agent_id: str, run_id: str):
        """Fetch a run and the retrieve the version"""
        task_info = await self.storage.tasks.get_task_info(agent_id)
        task_tuple = task_info.id_tuple
        if not task_tuple:
            raise MCPError(f"Agent {agent_id} not found")
        try:
            run = await self.runs_service.run_by_id(task_tuple, run_id)
        except ObjectNotFoundException:
            raise MCPError(f"Run {run_id} not found")

        # Retrieve variant to get output schema
        version = await self.storage.task_groups.get_task_group_by_id(task_tuple[0], run.group.id)

        if variant_id := version.properties.task_variant_id:
            variant = await self.storage.task_version_resource_by_id(task_tuple[0], variant_id)
        else:
            variant = None

        return self.RunVersionVariant(run, version, variant, task_info)

    async def fetch_run_details(
        self,
        agent_id: str | None,
        run_id: str | None,
        run_url: str | None,
    ) -> MCPRun:
        """Fetch details of a specific agent run."""

        if run_url:
            agent_id, run_id = extract_agent_id_and_run_id(run_url)

        if not agent_id:
            raise MCPError("Agent ID is required")

        if not run_id:
            raise MCPError("Run ID is required")

        data = await self._fetch_run_version_variant(agent_id, run_id)

        return MCPRun.from_domain(
            data.run,
            data.version,
            data.variant.output_schema.json_schema if data.variant else None,
            self.tenant.app_run_url(agent_id, run_id),
        )

    async def list_agents(
        self,
        page: int,
        sort_by: AgentSortField,
        order: SortOrder,
        stats_from_date: datetime | None = None,
    ) -> PaginatedMCPToolReturn[None, AgentListItem]:
        """List all agents with their statistics."""

        # Use default date (7 days ago)
        parsed_from_date = stats_from_date or datetime.now() - timedelta(days=7)

        # Get agents and their stats
        agents = await tasks.list_tasks(self.storage, with_schemas=False)
        stats_by_uid = {
            stat.agent_uid: stat
            async for stat in self.storage.task_runs.run_count_by_agent_uid(from_date=parsed_from_date)
        }

        agent_responses = [AgentListItem.from_domain(agent, stats_by_uid.get(agent.uid)) for agent in agents]

        sort_agents(agent_responses, sort_by, order)

        return PaginatedMCPToolReturn[None, AgentListItem](
            success=True,
            items=agent_responses,
        ).paginate(max_tokens=MAX_TOOL_RETURN_TOKENS, page=page)

    async def get_agent(
        self,
        agent_id: str,
        stats_from_date: datetime | None,
    ) -> MCPToolReturn[AgentResponse]:
        """Get detailed information for a specific agent."""

        parsed_from_date = stats_from_date or datetime.now() - timedelta(days=7)

        try:
            # Get single agent with detailed information
            agent = await tasks.get_task_by_id(self.storage, agent_id, with_schemas=True)
            stats = {
                stat.agent_uid: stat
                async for stat in self.storage.task_runs.run_count_by_agent_uid(
                    from_date=parsed_from_date,
                    agent_uids={agent.uid},
                )
            }

            detailed_response = AgentResponse.from_domain(agent, stats.get(agent.uid))

            return MCPToolReturn[AgentResponse](
                success=True,
                data=detailed_response,
            )

        except ObjectNotFoundException:
            return MCPToolReturn[AgentResponse](
                success=False,
                error=f"Agent {agent_id} not found",
            )

    async def get_agent_version(
        self,
        task_tuple: tuple[str, int],
        version_id: str,
    ) -> PaginatedMCPToolReturn[
        None,
        MajorVersion,
    ]:  # We return a paginated response for typing simplicity to align with list_agent_versions
        try:
            # TODO: use a Pydantic model for the version
            version_data = await self.versions_service.get_version(task_tuple, version_id, self.models_service)

            # Convert to the same format as the existing endpoint
            major_version = MajorVersion.from_version(*version_data)

            return PaginatedMCPToolReturn[None, MajorVersion](
                success=True,
                items=[major_version],
            ).paginate(max_tokens=MAX_TOOL_RETURN_TOKENS, page=1)

        except ObjectNotFoundException:
            return PaginatedMCPToolReturn[None, MajorVersion](
                success=False,
                error=f"Version {version_id} not found for agent {task_tuple[0]}",
            )
        except Exception as e:
            return PaginatedMCPToolReturn[None, MajorVersion](
                success=False,
                error=f"Failed to get agent version: {str(e)}",
            )

    async def list_agent_versions(
        self,
        task_tuple: tuple[str, int],
        page: int,
        schema_id: int | None = None,
    ) -> PaginatedMCPToolReturn[None, MajorVersion]:
        """List all versions of a specific agent."""
        try:
            versions = await self.versions_service.list_version_majors(task_tuple, schema_id, self.models_service)
            major_versions = [MajorVersion.from_major(v) for v in versions]

            return PaginatedMCPToolReturn[None, MajorVersion](
                success=True,
                items=major_versions,
            ).paginate(max_tokens=MAX_TOOL_RETURN_TOKENS, page=page)

        except Exception as e:
            return PaginatedMCPToolReturn[None, MajorVersion](
                success=False,
                error=f"Failed to list agent versions: {str(e)}",
            )

    async def _get_agent_or_failed_tool_result(self, agent_id: str) -> TaskInfo | None:
        try:
            agent_info = await self.storage.tasks.get_task_info(agent_id)
        except ObjectNotFoundException:
            list_agent_tool_answer = await self.list_agents(page=1, sort_by="last_active_at", order="desc")
            raise MCPError(
                f"Agent {agent_id} not found, please provide a valid agent id. Agent id can be found in either the model=... paramater (usually composed of '<agent_name>/<model_name>' or '<agent_name>/<agent_schema_id>/<deployment_environment>') or in the metadata of the agent run request. See 'data' for a list of existing agents for the user.",
                data={"user_agents": list_agent_tool_answer.items},
            )

        return agent_info

    async def deploy_agent_version(
        self,
        task_tuple: tuple[str, int],
        version_id: str,
        environment: str,
        deployed_by: UserIdentifier,
    ) -> DeployAgentResponse:
        """Deploy a specific version of an agent to an environment."""

        try:
            env = VersionEnvironment(environment.lower())
        except ValueError:
            raise MCPError(f"Invalid environment '{environment}'. Must be one of: dev, staging, production")

        deployment = await self.task_deployments_service.deploy_version(
            task_id=task_tuple,
            task_schema_id=None,
            version_id=version_id,
            environment=env,
            deployed_by=deployed_by,
        )

        # Build the model parameter for the migration guide
        model_param = f"{task_tuple[0]}/#{deployment.schema_id}/{environment}"

        # Create migration guide based on deployment documentation
        migration_guide: dict[str, Any] = {
            "model_parameter": model_param,
            "migration_instructions": {
                "overview": "Update your code to point to the deployed version instead of hardcoded prompts",
                "with_input_variables": {
                    "description": "If your prompt uses input variables (double curly braces)",
                    "before": {
                        "model": f"{task_tuple[0]}/your-model-name",
                        "messages": [{"role": "user", "content": "Your prompt with..."}],
                        "extra_body": {"input": {"variable": "value"}},
                    },
                    "after": {
                        "model": model_param,
                        "messages": [],  # Empty because prompt is stored in WorkflowAI
                        "extra_body": {"input": {"variable": "value"}},
                    },
                },
                "without_input_variables": {
                    "description": "If your prompt doesn't use input variables (e.g., chatbots with system messages)",
                    "before": {
                        "model": f"{task_tuple[0]}/your-model-name",
                        "messages": [
                            {"role": "system", "content": "Your system instructions"},
                            {"role": "user", "content": "user_message"},
                        ],
                    },
                    "after": {
                        "model": model_param,
                        "messages": [
                            {"role": "user", "content": "user_message"},
                        ],  # System message now comes from the deployment
                    },
                },
                "important_notes": [
                    "The messages parameter is always required, even if empty",
                    "Schema number defines the input/output contract",
                    f"This deployment uses schema #{deployment.schema_id}",
                    "Test thoroughly before deploying to production",
                ],
            },
        }

        return DeployAgentResponse(
            version_id=deployment.version_id,
            agent_schema_id=deployment.schema_id,
            environment=deployment.environment,
            deployed_at=deployment.deployed_at.isoformat() if deployment.deployed_at else "",
            migration_guide=migration_guide,
        )

    async def search_documentation(
        self,
        query: str | None = None,
        page: str | None = None,
    ) -> MCPToolReturn[SearchResponse]:
        """Search WorkflowAI documentation OR fetch a specific documentation page.

        Args:
            query: Search across all documentation to find relevant content snippets
            page: Direct access to specific documentation page

        Returns:
            LegacyMCPToolReturn with either search results or page content
        """
        if query and page:
            return MCPToolReturn(
                success=False,
                error="Use either 'query' OR 'page' parameter, not both",
            )

        if not query and not page:
            return MCPToolReturn(
                success=False,
                error="Provide either 'query' or 'page' parameter",
            )

        if query:
            return await self._search_documentation_by_query(query)

        if page:
            return await self._get_documentation_page(page)

        # This should never be reached due to the parameter validation above
        return MCPToolReturn(
            success=False,
            error="Invalid parameters provided",
        )

    async def _search_documentation_by_query(self, query: str) -> MCPToolReturn[SearchResponse]:
        """Search documentation using query and return snippets."""

        documentation_service = DocumentationService()
        relevant_sections = await documentation_service.get_relevant_doc_sections(
            chat_messages=[ChatMessage(role="USER", content=query)],
            agent_instructions="",
        )

        # Convert to SearchResult format with content snippets
        query_results = [
            SearchResponse.QueryResult(
                content_snippet=section.content,
                source_page=section.title.replace("content/", ""),
            )
            for section in relevant_sections
        ]

        if len(query_results) == 0:
            return MCPToolReturn(
                success=True,
                message=f"No relevant documentation sections found for query: {query}",
            )

        return MCPToolReturn(
            success=True,
            data=SearchResponse(query_results=query_results),
            message=f"Successfully found relevant documentation sections: {[section.title for section in relevant_sections]}",
        )

    async def _get_documentation_page(self, page: str) -> MCPToolReturn[SearchResponse]:
        """Get specific documentation page content."""

        documentation_service = DocumentationService()

        sections = await documentation_service.get_documentation_by_path([page])

        # Find the requested page
        if sections:
            return MCPToolReturn(
                success=True,
                data=SearchResponse(page_content=sections[0].content),
                message=f"Retrieved content for page: {page}",
            )

        # Page not found - list available pages for user reference
        all_sections = await documentation_service.get_all_doc_sections()
        available_pages = [section.title for section in all_sections]

        return MCPToolReturn(
            success=False,
            error=f"Page '{page}' not found. Available pages: {', '.join(available_pages)}",
        )

    async def _map_runs(self, task_tuple: tuple[str, int], runs: list[AgentRun]) -> list[MCPRun]:
        version_ids = {run.group.id for run in runs}

        variant_ids: set[str] = set()
        versions: dict[str, TaskGroup] = {}
        async for v in self.storage.task_groups.list_task_groups(
            TaskGroupQuery(
                task_id=task_tuple[0],
                ids=version_ids,
            ),
        ):
            versions[v.id] = v
            if v.properties.task_variant_id:
                variant_ids.add(v.properties.task_variant_id)

        schema_by_id: dict[int, dict[str, Any]] = {
            v.task_schema_id: v.output_schema.json_schema
            async for v in self.storage.task_variants.variants_iterator(task_tuple[0], variant_ids)
        }

        return [
            MCPRun.from_domain(
                run,
                versions.get(run.group.id),
                schema_by_id.get(run.task_schema_id),
                url=self.tenant.app_run_url(task_tuple[0], run.id),
            )
            for run in runs
        ]

    @classmethod
    def _process_run_fields(cls, field_queries: list[dict[str, Any]]) -> list[FieldQuery]:
        # TODO: we should be using the runs search service here

        # Convert the field queries to the proper format
        parsed_field_queries: list[FieldQuery] = []
        for idx, query_dict in enumerate(field_queries):
            # Validate required fields
            if "field_name" not in query_dict:
                raise MCPError(f"Missing required field 'field_name' in field query {idx}")

            if "operator" not in query_dict:
                raise MCPError(f"Missing required field 'operator' in field query {idx}")

            if "values" not in query_dict:
                raise MCPError(f"Missing required field 'values' in field query {idx}")

            # Parse the operator
            try:
                operator = SearchOperator(query_dict["operator"])
            except ValueError:
                raise MCPError(
                    f"Invalid operator: {query_dict['operator']}. Valid operators are: {', '.join([op.value for op in SearchOperator])}",
                )

            # Parse the field type if provided
            field_type: FieldType | None = None
            if "type" in query_dict and query_dict["type"]:
                field_type = query_dict["type"]

            field_query = FieldQuery(
                field_name=query_dict["field_name"],
                operator=operator,
                values=query_dict["values"],
                type=field_type,
            )
            parsed_field_queries.append(field_query)

        return parsed_field_queries

    async def search_runs(  # noqa: C901
        self,
        task_tuple: tuple[str, int],
        # TODO: this should be a plain string
        # See https://linear.app/workflowai/issue/WOR-4976/write-doc-about-how-to-search-runs
        field_queries: list[dict[str, Any]],
        limit: int,
        offset: int,
        page: int,
    ) -> PaginatedMCPToolReturn[None, MCPRun]:
        """Search agent runs by metadata fields."""

        # Use the runs search service to perform the search
        search_service = RunsSearchService(self.storage)
        parsed_field_queries = self._process_run_fields(field_queries)

        page_result = await search_service.search_task_runs(
            task_uid=task_tuple,
            field_queries=parsed_field_queries,
            limit=limit,
            offset=offset,
            map=lambda x: x,
            # tool_calls and llm_completions are not needed here
            # tool_calls contains the entirety of tool calls executed during the request
            # llm_completions contains each individual round trip with the LLM
            # TODO: ultimately we should only need the "messages" field
            # Using the full "llm_completions" here. It might be heavy but we really want
            # to have the full context of the run.
            exclude_fields={"tool_calls"},
        )

        return PaginatedMCPToolReturn[None, MCPRun](
            success=True,
            items=await self._map_runs(task_tuple, page_result.items),
        ).paginate(max_tokens=MAX_TOOL_RETURN_TOKENS, page=page)

    async def create_completion(
        self,
        # TODO: required for now, we should remove once we have a way to retrieve
        # a run by its ID without the agent_id
        agent_id: str,
        original_run_id: str | None,
        request: OpenAIProxyChatCompletionRequest,
        start_time: float,
    ) -> OpenAIProxyChatCompletionResponse:
        if original_run_id:
            run_data = await self._fetch_run_version_variant(agent_id, original_run_id)
        else:
            run_data = None

        # No matter what we are not streaming
        request.stream_options = None
        request.stream = False

        handler = OpenAIProxyHandler(
            group_service=self.run_service.group_service,
            storage=self.storage,
            run_service=self.run_service,
            event_router=self.event_router,
            feedback_generator=_feedback_token_generator,
        )
        prepared = await handler.prepare_run(request, self.tenant)
        if run_data:
            # We make sure we provide defaults for fields present in the run
            merged_properties = _merge_properties(
                prepared_properties=prepared.properties,
                run_properties=run_data.version.properties,
            )

            # TODO: we should likely raise if there is a difference in schema here
            # Not possible right now because prepared.variant will always be set
            # So we can't really detect "default variants"
            merged_variant = run_data.variant or prepared.variant

            merged_input = _merge_inputs(original_input=run_data.run.task_input, new_input=prepared.final_input)

            prepared = handler.PreparedRun(
                properties=merged_properties,
                variant=merged_variant,
                final_input=merged_input,
            )
        res = await handler.handle_prepared_run(prepared, request, None, start_time, self.tenant)
        if not isinstance(res, OpenAIProxyChatCompletionResponse):
            # That should never happen since we are not streaming
            raise ValueError("Unexpected response type")
        return res

    async def send_feedback(
        self,
        feedback: str,
        user_agent: str | None,
        context: str | None = None,
    ) -> MCPToolReturn[EmptyModel]:
        """Send MCP client feedback to processing agent and return acknowledgment"""

        # Fire-and-forget: start the agent processing but don't wait for results
        add_background_task(
            self._process_feedback(feedback, context, user_agent, self.tenant.slug, self.user_email),
        )

        return MCPToolReturn(
            success=True,
            message="MCP client feedback received and sent for processing",
            data=None,
        )

    async def _process_feedback(
        self,
        feedback: str,
        context: str | None,
        user_agent: str | None,
        organization_name: str | None,
        user_email: str | None,
    ):
        """Background task to process MCP client feedback with the agent"""
        try:
            # Process feedback with an agent, including metadata for tracking
            response = await mcp_feedback_processing_agent(
                feedback=feedback,
                context=context,
                user_agent=user_agent,
                organization_name=organization_name,
                user_email=user_email,
            )
            # Log the analysis or store it somewhere if needed
            # For now, just log that processing completed
            if response:
                _logger.info(
                    "MCP client feedback processed",
                    extra={
                        "organization_name": organization_name,
                        "sentiment": response.sentiment,
                        "summary": response.summary,
                        "key_themes": response.key_themes,
                        "confidence": response.confidence,
                        "user_agent": user_agent,
                    },
                )
            else:
                _logger.error(
                    "MCP client feedback processing agent returned no response",
                    extra={
                        "organization_name": organization_name,
                        "user_email": user_email,
                        "feedback": feedback,
                        "context": context,
                        "user_agent": user_agent,
                    },
                )

        except Exception as e:
            _logger.exception("Error processing MCP client feedback", exc_info=e)


def _merge_properties(
    prepared_properties: TaskGroupProperties,
    run_properties: TaskGroupProperties,
) -> TaskGroupProperties:
    return run_properties.model_copy(update=prepared_properties.model_dump(exclude_unset=True))


def _merge_inputs(
    original_input: dict[str, Any] | None,
    new_input: dict[str, Any] | None | Messages,
) -> dict[str, Any] | Messages:
    if not original_input:
        if not new_input:
            raise MCPError("Missing messages")
        return new_input or {}
    if not new_input:
        return original_input

    # Here we merge the messages and the rest separately
    if isinstance(new_input, Messages):
        merged = {}
        # TODO: remove, Same hack as in OpenAIProxyHandler
        if not new_input.messages:
            new_input_messages = None
        else:
            new_input_messages = new_input.model_dump(mode="json", exclude_none=True)[INPUT_KEY_MESSAGES]
    else:
        merged = {k: v for k, v in new_input.items() if k != INPUT_KEY_MESSAGES}
        new_input_messages = new_input.get(INPUT_KEY_MESSAGES)

    if not merged:
        # No actual input in the new input so we can fetch from the original input
        merged = {k: v for k, v in original_input.items() if k != INPUT_KEY_MESSAGES}

    # Then we set the messages in the same way
    merged[INPUT_KEY_MESSAGES] = (
        new_input_messages if new_input_messages is not None else original_input.get(INPUT_KEY_MESSAGES)
    )

    return merged
