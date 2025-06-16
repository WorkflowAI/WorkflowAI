from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel

from api.routers.mcp._mcp_models import (
    ConciseLatestModelResponse,
    ConciseModelResponse,
    MajorVersion,
    MCPToolReturn,
)
from api.services.internal_tasks.ai_engineer_service import AIEngineerChatMessage, AIEngineerReponse, AIEngineerService
from api.services.models import ModelsService
from api.services.runs.runs_service import RunsService
from api.services.runs_search import RunsSearchService
from api.services.task_deployments import TaskDeploymentsService
from api.services.versions import VersionsService
from core.domain.agent_run import AgentRunBase
from core.domain.consts import WORKFLOWAI_APP_URL
from core.domain.models.model_data import FinalModelData, LatestModel
from core.domain.models.model_datas_mapping import MODEL_DATAS
from core.domain.models.models import Model
from core.domain.search_query import FieldQuery, SearchOperator
from core.domain.task_info import TaskInfo
from core.domain.users import UserIdentifier
from core.domain.version_environment import VersionEnvironment
from core.storage import ObjectNotFoundException
from core.storage.backend_storage import BackendStorage
from core.utils.schemas import FieldType


class RunSearchResult(BaseModel):
    """Model for run search results"""

    id: str
    task_id: str
    task_schema_id: int
    status: str
    duration_seconds: float | None
    cost_usd: float | None
    created_at: str | None
    user_review: str | None
    ai_review: str | None
    error: dict[str, Any] | None


class UsefulLinks(BaseModel):
    class Link(BaseModel):
        title: str
        url: str
        description: str

    description: str = "A collection of useful link that the user can access in the browser, those link are NOT directly accessible without being authenticated in the browser"
    useful_links: list[Link]


class MCPService:
    def __init__(
        self,
        storage: BackendStorage,
        ai_engineer_service: AIEngineerService,
        runs_service: RunsService,
        versions_service: VersionsService,
        models_service: ModelsService,
        task_deployments_service: TaskDeploymentsService,
        user_email: str | None,
        tenant_slug: str | None,
    ):
        self.storage = storage
        self.ai_engineer_service = ai_engineer_service
        self.runs_service = runs_service
        self.versions_service = versions_service
        self.models_service = models_service
        self.task_deployments_service = task_deployments_service
        self.user_email = user_email
        self.tenant_slug = tenant_slug

    def _get_useful_links(self, agent_id: str | None, agent_schema_id: int | None) -> UsefulLinks:
        if agent_id is None:
            agent_id = "<example_agent_id>"

        tenant_slug = self.tenant_slug

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

    async def _enrich_tool_return(
        self,
        success: bool,
        data: dict[str, Any] = {},
        error: str | None = None,
        messages: list[str] | None = None,
        agent_id: str | None = None,
        agent_schema_id: int | None = None,
        add_useful_links: bool = True,
    ) -> MCPToolReturn:
        """Enrich the tool return with useful links and other data."""

        data = {"result": data}

        if add_useful_links:
            data["useful_links"] = self._get_useful_links(
                agent_id=agent_id,
                agent_schema_id=agent_schema_id,
            ).model_dump(exclude_none=True)

        return MCPToolReturn(
            success=success,
            data=data,
            error=error,
            messages=messages,
        )

    async def list_available_models(
        self,
        agent_id: str | None,
        agent_schema_id: int | None,
        agent_requires_tools: bool = False,
    ) -> MCPToolReturn:
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
                return await self._enrich_tool_return(
                    success=True,
                    data={
                        "compatible_models": [
                            ConciseModelResponse.from_model_for_task(m).model_dump(exclude_none=True)
                            for m in models
                            if m.is_not_supported_reason is None
                        ],
                    },
                    agent_id=agent_id,
                    agent_schema_id=agent_schema_id,
                )

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

        return await self._enrich_tool_return(
            success=True,
            data={
                "all_models": [m.model_dump(exclude_none=True) for m in _model_data_iterator()],
            },
        )

    def _extract_agent_id_and_run_id(self, run_url: str) -> tuple[str, str]:  # noqa: C901
        """Extract the agent ID and run ID from the run URL.

        Supports multiple URL formats:
        1. https://workflowai.com/workflowai/agents/classify-email-domain/runs/019763ae-ba9f-70a9-8d44-5a626c82e888
        2. http://localhost:3000/workflowai/agents/sentiment/2/runs?taskRunId=019763a5-12a7-73b7-9b0c-e6413d2da52f

        Args:
            run_url: The run URL to parse

        Returns:
            A tuple of (agent_id, run_id)

        Raises:
            ValueError: If the URL format is invalid or doesn't match the expected pattern
        """
        if not run_url:
            raise ValueError("run_url must be a non-empty string")

        # Parse query parameters first
        from urllib.parse import parse_qs, urlparse

        parsed_url = urlparse(run_url)
        query_params = parse_qs(parsed_url.query)

        # Remove trailing slash from path
        clean_path = parsed_url.path.rstrip("/")

        # Split by "/" and filter out empty parts
        parts = [part for part in clean_path.split("/") if part]

        # Find "agents" keyword and extract agent_id
        try:
            agents_index = None
            for i, part in enumerate(parts):
                if part == "agents":
                    agents_index = i
                    break

            if agents_index is None or agents_index + 1 >= len(parts):
                raise ValueError(f"Could not find 'agents/{{agent_id}}' pattern in URL: {run_url}")

            agent_id = parts[agents_index + 1]
            if not agent_id:
                raise ValueError(f"Agent ID is empty in URL: {run_url}")

            # Look for run ID in different places
            run_id = None

            # Method 1: Check for taskRunId in query parameters
            if "taskRunId" in query_params and query_params["taskRunId"]:
                run_id = query_params["taskRunId"][0]

            # Method 2: Check for standard pattern agents/agent_id/runs/run_id
            if not run_id:
                # Look for "runs" after agent_id (may have schema_id in between)
                runs_index = None
                for i in range(agents_index + 2, len(parts)):
                    if parts[i] == "runs" and i + 1 < len(parts):
                        runs_index = i
                        break

                if runs_index is not None:
                    run_id = parts[runs_index + 1]

            # Method 3: Check for pattern agents/agent_id/schema_id/runs (runs list page with taskRunId param)
            if not run_id:
                # Look for pattern where "runs" comes after agent_id (with optional schema_id)
                for i in range(agents_index + 2, len(parts)):
                    if parts[i] == "runs":
                        # This is probably a runs list page, check query params again
                        if "taskRunId" in query_params and query_params["taskRunId"]:
                            run_id = query_params["taskRunId"][0]
                        break

            if not run_id:
                raise ValueError(f"Could not find run ID in URL: {run_url}")

            return agent_id, run_id

        except (IndexError, ValueError) as e:
            raise ValueError(f"Invalid run URL format: {run_url}") from e

    async def fetch_run_details(
        self,
        agent_id: str | None,
        run_id: str | None,
        run_url: str | None,
    ) -> MCPToolReturn:
        """Fetch details of a specific agent run."""

        if run_url:
            try:
                agent_id, run_id = self._extract_agent_id_and_run_id(run_url)
                # find the task tuple from the agent id
            except ValueError:
                return await self._enrich_tool_return(
                    success=False,
                    error="Invalid run URL, must be in the format 'https://workflowai.com/workflowai/agents/agent-id/runs/run-id', or you must pass 'agent_id' and 'run_id'",
                    agent_id=agent_id,
                )

        if not agent_id:
            return await self._enrich_tool_return(
                success=False,
                error="Agent ID is required",
                agent_id=agent_id,
            )

        if not run_id:
            return await self._enrich_tool_return(
                success=False,
                error="Run ID is required",
                agent_id=agent_id,
            )

        task_info = await self.storage.tasks.get_task_info(agent_id)
        task_tuple = task_info.id_tuple
        if not task_tuple:
            return await self._enrich_tool_return(
                success=False,
                error=f"Agent {agent_id} not found",
            )

        try:
            run = await self.runs_service.run_by_id(task_tuple, run_id)

            # Convert the run to a serializable format
            run_data = {
                "id": run.id,
                "agent_id": run.task_id,
                "agent_schema_id": run.task_schema_id,
                "status": run.status,
                "agent_input": run.task_input,
                "agent_output": run.task_output,
                "duration_seconds": run.duration_seconds,
                "cost_usd": run.cost_usd,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "user_review": run.user_review,
                "ai_review": run.ai_review,
                "error": {
                    "code": run.error.code,
                    "message": run.error.message,
                    "details": run.error.details,
                }
                if run.error
                else None,
                "conversation_id": run.conversation_id,
            }

            return await self._enrich_tool_return(
                success=True,
                data=run_data,
                agent_id=agent_id,
            )

        except ObjectNotFoundException:
            return await self._enrich_tool_return(
                success=False,
                error=f"Run {run_id} not found",
                agent_id=agent_id,
            )
        except Exception as e:
            return await self._enrich_tool_return(
                success=False,
                error=f"Failed to fetch run details: {str(e)}",
                agent_id=agent_id,
            )

    async def list_agents(self, from_date: str = "") -> MCPToolReturn:
        """List all agents with their statistics."""
        try:
            # Parse from_date or use default
            parsed_from_date = None
            if from_date:
                try:
                    parsed_from_date = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
                except ValueError:
                    pass

            if not parsed_from_date:
                parsed_from_date = datetime.now() - timedelta(days=7)

            # Get agent stats
            stats_by_uid = {}
            async for stat in self.storage.task_runs.run_count_by_agent_uid(parsed_from_date):
                stats_by_uid[stat.agent_uid] = {
                    "run_count_last_7d": stat.run_count,
                    "total_cost_usd_last_7d": stat.total_cost_usd,
                }

            # Get all agents (tasks)
            from api.services import tasks

            agents = await tasks.list_tasks(self.storage)

            # Enrich agents with stats
            enriched_agents: list[dict[str, Any]] = []
            for agent in agents:
                agent_dict: dict[str, Any] = {
                    "id": agent.id,
                    "uid": agent.uid,
                    "name": agent.name,
                    "description": agent.description,
                    "is_public": agent.is_public,
                    "versions": [
                        {
                            "schema_id": v.schema_id,
                            "variant_id": v.variant_id,
                            "description": v.description,
                            "created_at": v.created_at.isoformat() if v.created_at else None,
                            "is_hidden": v.is_hidden,
                            "last_active_at": v.last_active_at.isoformat() if v.last_active_at else None,
                        }
                        for v in agent.versions
                    ],
                }

                # Add stats if available
                if agent.uid and agent.uid in stats_by_uid:
                    agent_dict["stats_last_7d"] = stats_by_uid[agent.uid]
                else:
                    agent_dict["stats_last_7d"] = {
                        "run_count_last_7d": 0,
                        "total_cost_usd_last_7d": 0.0,
                    }

                enriched_agents.append(agent_dict)

            return await self._enrich_tool_return(
                success=True,
                data={
                    "items": enriched_agents,
                    "count": len(enriched_agents),
                },
            )

        except Exception as e:
            return await self._enrich_tool_return(
                success=False,
                error=f"Failed to list agents with stats: {str(e)}",
            )

    async def get_agent_version(
        self,
        task_tuple: tuple[str, int],
        version_id: str,
    ) -> MCPToolReturn:
        """Get details of a specific agent version."""
        try:
            version_data = await self.versions_service.get_version(task_tuple, version_id, self.models_service)

            # Convert to the same format as the existing endpoint
            major_version = MajorVersion.from_version(*version_data)

            return await self._enrich_tool_return(
                success=True,
                data=major_version.model_dump(exclude_none=True),
                agent_id=task_tuple[0],
            )

        except ObjectNotFoundException:
            return await self._enrich_tool_return(
                success=False,
                error=f"Version {version_id} not found for agent {task_tuple[0]}",
                agent_id=task_tuple[0],
            )
        except Exception as e:
            return await self._enrich_tool_return(
                success=False,
                error=f"Failed to get agent version: {str(e)}",
                agent_id=task_tuple[0],
            )

    async def list_agent_versions(
        self,
        task_tuple: tuple[str, int],
        schema_id: int | None = None,
    ) -> MCPToolReturn:
        """List all versions of a specific agent."""
        try:
            versions = await self.versions_service.list_version_majors(task_tuple, schema_id, self.models_service)

            # Convert to the same format as the existing endpoint
            version_data = [MajorVersion.from_major(v).model_dump(exclude_none=True) for v in versions]

            return await self._enrich_tool_return(
                success=True,
                data={
                    "items": version_data,
                    "count": len(version_data),
                },
                agent_id=task_tuple[0],
                agent_schema_id=schema_id,
            )

        except Exception as e:
            return await self._enrich_tool_return(
                success=False,
                error=f"Failed to list agent versions: {str(e)}",
                agent_id=task_tuple[0],
                agent_schema_id=schema_id,
            )

    async def _get_agent_or_failed_tool_result(
        self,
        agent_id: str,
    ) -> tuple[TaskInfo | None, MCPToolReturn | None]:
        try:
            agent_info = await self.storage.tasks.get_task_info(agent_id)
        except ObjectNotFoundException:
            list_agent_tool_answer = await self.list_agents()

            return None, MCPToolReturn(
                success=False,
                error=f"Agent {agent_id} not found, please provide a valid agent id. Agent id can be found in either the model=... paramater (usually composed of '<agent_name>/<model_name>' or '<agent_name>/<agent_schema_id>/<deployment_environment>') or in the metadata of the agent run request. See 'data' for a list of existing agents for the user.",
                data=list_agent_tool_answer.data,
            )

        return agent_info, None

    async def ask_ai_engineer(
        self,
        agent_schema_id: int | None,
        agent_id: str | None,
        message: str,
        user_programming_language: str,
        user_code_extract: str,
    ) -> MCPToolReturn:
        """Ask the AI Engineer a question (legacy endpoint)."""

        user_message = message

        agent_info: TaskInfo | None = None
        if agent_id:
            agent_info, error_tool_result = await self._get_agent_or_failed_tool_result(agent_id)
            if error_tool_result:
                return error_tool_result
            if agent_info:
                agent_schema_id = agent_schema_id or agent_info.latest_schema_id or 1

        # TODO: switch to a streamable MCP tool
        last_chunk: AIEngineerReponse | None = None
        async for chunk in self.ai_engineer_service.stream_ai_engineer_agent_response(
            task_tuple=agent_info.id_tuple if agent_info else None,
            agent_schema_id=agent_schema_id,
            user_email=self.user_email,
            messages=[AIEngineerChatMessage(role="USER", content=user_message)],
            user_programming_language=user_programming_language,
            user_code_extract=user_code_extract,
        ):
            last_chunk = chunk

        if last_chunk is None:
            return await self._enrich_tool_return(
                success=False,
                error="No response from AI Engineer",
                agent_id=agent_id,
                agent_schema_id=agent_schema_id,
            )

        return await self._enrich_tool_return(
            success=True,
            data=last_chunk.model_dump(exclude_none=True),
            agent_id=agent_id,
            agent_schema_id=agent_schema_id,
        )

    async def deploy_agent_version(
        self,
        task_tuple: tuple[str, int],
        version_id: str,
        environment: str,
        deployed_by: UserIdentifier,
    ) -> MCPToolReturn:
        """Deploy a specific version of an agent to an environment."""
        try:
            try:
                env = VersionEnvironment(environment.lower())
            except ValueError:
                return MCPToolReturn(
                    success=False,
                    error=f"Invalid environment '{environment}'. Must be one of: dev, staging, production",
                )

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
                        "description": "If your prompt uses input variables (e.g., {email}, {context})",
                        "before": {
                            "model": f"{task_tuple[0]}/your-model-name",
                            "messages": [{"role": "user", "content": "Your prompt with {variable}"}],
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

            return await self._enrich_tool_return(
                success=True,
                data={
                    "version_id": deployment.version_id,
                    "task_schema_id": deployment.schema_id,
                    "environment": deployment.environment,
                    "deployed_at": deployment.deployed_at.isoformat() if deployment.deployed_at else None,
                    "message": f"Successfully deployed version {version_id} to {environment} environment",
                    "migration_guide": migration_guide,
                },
                agent_id=task_tuple[0],
                agent_schema_id=deployment.schema_id,
            )
        except Exception as e:
            return await self._enrich_tool_return(
                success=False,
                error=f"Failed to deploy version: {str(e)}",
                agent_id=task_tuple[0],
            )

    async def search_runs_by_metadata(  # noqa: C901
        self,
        task_tuple: tuple[str, int],
        field_queries: list[dict[str, Any]],
        limit: int,
        offset: int,
        include_full_data: bool = True,
    ) -> MCPToolReturn:
        """Search agent runs by metadata fields."""
        try:
            # Convert the field queries to the proper format
            parsed_field_queries: list[FieldQuery] = []
            for query_dict in field_queries:
                try:
                    # Validate required fields
                    if "field_name" not in query_dict:
                        return await self._enrich_tool_return(
                            success=False,
                            error="Missing required field 'field_name' in field query",
                            agent_id=task_tuple[0],
                        )

                    if "operator" not in query_dict:
                        return await self._enrich_tool_return(
                            success=False,
                            error="Missing required field 'operator' in field query",
                            agent_id=task_tuple[0],
                        )

                    if "values" not in query_dict:
                        return await self._enrich_tool_return(
                            success=False,
                            error="Missing required field 'values' in field query",
                            agent_id=task_tuple[0],
                        )

                    # Parse the operator
                    try:
                        operator = SearchOperator(query_dict["operator"])
                    except ValueError:
                        return await self._enrich_tool_return(
                            success=False,
                            error=f"Invalid operator: {query_dict['operator']}. Valid operators are: {', '.join([op.value for op in SearchOperator])}",
                            agent_id=task_tuple[0],
                        )

                    # Parse the field type if provided
                    field_type: FieldType | None = None
                    if "type" in query_dict and query_dict["type"]:
                        field_type = query_dict["type"]

                    parsed_field_queries.append(
                        FieldQuery(
                            field_name=query_dict["field_name"],
                            operator=operator,
                            values=query_dict["values"],
                            type=field_type,
                        ),
                    )
                except Exception as e:
                    return MCPToolReturn(
                        success=False,
                        error=f"Error parsing field query: {str(e)}",
                    )

            # Use the runs search service to perform the search

            search_service = RunsSearchService(self.storage)

            # Search for runs using the parsed field queries
            def run_mapper(run: AgentRunBase) -> RunSearchResult:
                return RunSearchResult(
                    id=run.id,
                    task_id=run.task_id,
                    task_schema_id=run.task_schema_id,
                    status=run.status,
                    duration_seconds=run.duration_seconds,
                    cost_usd=run.cost_usd,
                    created_at=run.created_at.isoformat() if run.created_at else None,
                    user_review=run.user_review,
                    ai_review=run.ai_review,
                    error={
                        "code": getattr(run.error, "code", ""),
                        "message": getattr(run.error, "message", ""),
                        "details": getattr(run.error, "details", None),
                    }
                    if run.error
                    else None,
                )

            page_result = await search_service.search_task_runs(
                task_uid=task_tuple,
                field_queries=parsed_field_queries,
                limit=limit,
                offset=offset,
                map=run_mapper,
            )

            # If requested, fetch full run details for each result
            # TODO: not optimal, we should fetch the full runs in the search service
            items = page_result.items
            if include_full_data:
                full_runs: list[dict[str, Any]] = []
                for run_summary in items:
                    try:
                        # Fetch the full AgentRun with task_input and task_output
                        full_run = await self.runs_service.run_by_id(task_tuple, run_summary.id)
                        full_run_data = {
                            **run_summary.model_dump(exclude_none=True),  # Convert RunSearchResult to dict
                            "task_input": full_run.task_input,
                            "task_output": full_run.task_output,
                            "task_input_preview": full_run.task_input_preview,
                            "task_output_preview": full_run.task_output_preview,
                        }
                        full_runs.append(full_run_data)
                    except Exception:
                        # If we can't fetch the full run, include what we have
                        full_runs.append(run_summary.model_dump(exclude_none=True))
                items = [
                    item.model_dump(exclude_none=True) if isinstance(item, BaseModel) else item for item in full_runs
                ]
            else:
                # Convert RunSearchResult objects to dicts
                items = [item.model_dump(exclude_none=True) for item in items]

            return await self._enrich_tool_return(
                success=True,
                data={
                    "items": items,
                    "count": page_result.count,
                    "limit": limit,
                    "offset": offset,
                },
                agent_id=task_tuple[0],
            )

        except Exception as e:
            return await self._enrich_tool_return(
                success=False,
                error=f"Failed to search runs by metadata: {str(e)}",
                agent_id=task_tuple[0],
            )

    async def send_feedback(self, feedback: str, context: str | None = None) -> MCPToolReturn:
        """Send MCP client feedback to processing agent and return acknowledgment"""
        try:
            import asyncio

            from core.agents.mcp_feedback_processing_agent import (
                MCPFeedbackProcessingInput,
            )

            # Create input for the agent
            agent_input = MCPFeedbackProcessingInput(
                feedback=feedback,
                context=context,
            )

            # Extract organization and user info from storage/tenant context
            # The storage already has tenant information from the authentication flow
            organization_name = getattr(self.storage, "tenant", None)
            user_email = None  # Could be extracted from user context if available

            # Fire-and-forget: start the agent processing but don't wait for results
            asyncio.create_task(self._process_feedback_async(agent_input, organization_name, user_email))

            return MCPToolReturn(
                success=True,
                result={
                    "message": "MCP client feedback received and sent for processing",
                    "feedback_length": len(feedback),
                    "has_context": context is not None,
                },
            )
        except Exception as e:
            return MCPToolReturn(
                success=False,
                error=f"Failed to send MCP client feedback for processing: {str(e)}",
            )

    async def _process_feedback_async(
        self,
        agent_input: Any,  # MCPFeedbackProcessingInput type
        organization_name: str | None,
        user_email: str | None,
    ):
        """Background task to process MCP client feedback with the agent"""
        try:
            from core.agents.mcp_feedback_processing_agent import mcp_feedback_processing_agent

            # Process feedback with the agent, including metadata for tracking
            async for response in mcp_feedback_processing_agent(
                agent_input,
                organization_name=organization_name,
                user_email=user_email,
            ):
                # Log the analysis or store it somewhere if needed
                # For now, just log that processing completed
                print(f"MCP client feedback processed for {organization_name}: {response.analysis.sentiment} sentiment")

        except Exception as e:
            # Log error but don't fail the MCP tool response
            print(f"Error processing MCP client feedback: {str(e)}")
