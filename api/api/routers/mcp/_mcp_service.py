from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel

from api._standard_model_response import StandardModelResponse
from api.routers.mcp._mcp_models import MajorVersion, MCPToolReturn
from api.services.documentation_service import DocumentationService
from api.services.internal_tasks.meta_agent_service import MetaAgentChatMessage, PlaygroundState
from api.services.internal_tasks.meta_agent_service import MetaAgentService as MetaAgentServiceType
from api.services.models import ModelsService
from api.services.runs.runs_service import RunsService
from api.services.runs_search import RunsSearchService
from api.services.versions import VersionsService
from core.domain.agent_run import AgentRunBase
from core.domain.fields.chat_message import ChatMessage
from core.domain.models.model_data import FinalModelData, LatestModel
from core.domain.models.model_datas_mapping import MODEL_DATAS
from core.domain.models.models import Model
from core.domain.search_query import FieldQuery, SearchOperator
from core.domain.users import UserIdentifier
from core.domain.version_environment import VersionEnvironment
from core.storage import ObjectNotFoundException
from core.storage.backend_storage import BackendStorage
from core.utils.schemas import FieldType
from core.utils.url_utils import IGNORE_URL_END_TAG, IGNORE_URL_START_TAG


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


class MCPService:
    def __init__(
        self,
        storage: BackendStorage,
        meta_agent_service: MetaAgentServiceType,
        runs_service: RunsService,
        versions_service: VersionsService,
        models_service: ModelsService,
        task_deployments_service: Any,  # TaskDeploymentsService
    ):
        self.storage = storage
        self.meta_agent_service = meta_agent_service
        self.runs_service = runs_service
        self.versions_service = versions_service
        self.models_service = models_service
        self.task_deployments_service = task_deployments_service

    async def list_models(self) -> MCPToolReturn:
        def _model_data_iterator() -> Iterator[StandardModelResponse.ModelItem]:
            for model in Model:
                data = MODEL_DATAS[model]
                if isinstance(data, LatestModel):
                    yield StandardModelResponse.ModelItem.from_model_data(model.value, MODEL_DATAS[data.model])  # pyright: ignore [reportArgumentType]
                elif isinstance(data, FinalModelData):
                    yield StandardModelResponse.ModelItem.from_model_data(model.value, data)
                else:
                    # Skipping deprecated models
                    continue

        return MCPToolReturn(
            success=True,
            data=StandardModelResponse(data=list(_model_data_iterator())).model_dump(),
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
                return MCPToolReturn(
                    success=False,
                    error="Invalid run URL, must be in the format 'https://workflowai.com/workflowai/agents/agent-id/runs/run-id', or you must pass 'agent_id' and 'run_id'",
                )

        if not agent_id:
            return MCPToolReturn(
                success=False,
                error="Agent ID is required",
            )

        if not run_id:
            return MCPToolReturn(
                success=False,
                error="Run ID is required",
            )

        task_info = await self.storage.tasks.get_task_info(agent_id)
        task_tuple = task_info.id_tuple
        if not task_tuple:
            return MCPToolReturn(
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

            return MCPToolReturn(
                success=True,
                data=run_data,
            )

        except ObjectNotFoundException:
            return MCPToolReturn(
                success=False,
                error=f"Run {run_id} not found",
            )
        except Exception as e:
            return MCPToolReturn(
                success=False,
                error=f"Failed to fetch run details: {str(e)}",
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

            return MCPToolReturn(
                success=True,
                data={
                    "items": enriched_agents,
                    "count": len(enriched_agents),
                },
            )

        except Exception as e:
            return MCPToolReturn(
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

            return MCPToolReturn(
                success=True,
                data=major_version.model_dump(),
            )

        except ObjectNotFoundException:
            return MCPToolReturn(
                success=False,
                error=f"Version {version_id} not found for agent {task_tuple[0]}",
            )
        except Exception as e:
            return MCPToolReturn(
                success=False,
                error=f"Failed to get agent version: {str(e)}",
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
            version_data = [MajorVersion.from_major(v).model_dump() for v in versions]

            return MCPToolReturn(
                success=True,
                data={
                    "items": version_data,
                    "count": len(version_data),
                },
            )

        except Exception as e:
            return MCPToolReturn(
                success=False,
                error=f"Failed to list agent versions: {str(e)}",
            )

    async def ask_ai_engineer(
        self,
        agent_schema_id: int | None,
        agent_id: str | None,
        message: str,
        user_programming_language: str | None,
        user_code_extract: str | None,
    ) -> MCPToolReturn:
        """Ask the AI Engineer a question (legacy endpoint)."""

        user_message = message

        if user_programming_language:
            user_message += f"""
            The user is using the following programming language and integration:
            {user_programming_language}
            """

        if user_code_extract:
            user_message += f"""
            Here is a code extract from the user's code:
            {IGNORE_URL_START_TAG}{user_code_extract}{IGNORE_URL_END_TAG}
            """
            # We add URL fetching ignore tags to avoid fetching URLs in the code extract

        # Add guidance about using input variables and agent prefix in metadata
        user_message += """
        
        IMPORTANT GUIDANCE FOR THE AI ENGINEER:
        1. ALWAYS encourage the use of input variables in prompts when generating code examples. Instead of hardcoded values in prompts, show how to use {variable_name} syntax and pass data via the 'input' parameter.
        2. When generating completion code, ALWAYS include the agent prefix in the metadata field as the preferred way to identify the agent.
        3. Show examples with both approaches: with input variables (preferred) and without input variables when appropriate.
        4. Emphasize that input variables make agents more flexible and reusable.
        
        Example of GOOD code generation:
        ```python
        completion = client.beta.chat.completions.parse(
            model="agent-name/gpt-4o",
            messages=[],  # Empty because prompt is stored in WorkflowAI
            response_format=ResponseFormat,
            extra_body={
                "input": {"text": user_input, "context": additional_context},
                "metadata": {"agent_prefix": "agent-name", "user_id": "user123"}
            }
        )
        ```
        
        Example of code to AVOID (hardcoded prompts):
        ```python
        completion = client.beta.chat.completions.parse(
            model="agent-name/gpt-4o",
            messages=[
                {"role": "system", "content": "Fixed system prompt"},
                {"role": "user", "content": f"Hardcoded prompt with {variable}"}
            ]
        )
        ```
        """

        if not agent_id or agent_id == "new":
            # Find the relevant section in the documentation
            relevant_docs = await DocumentationService().get_relevant_doc_sections(
                chat_messages=[ChatMessage(role="USER", content=user_message)],
                agent_instructions="",
            )
            return MCPToolReturn(
                success=True,
                data=f"""Here are some relevant documentation from WorkflowAI for your request:
                {"\n".join([f"- {doc.title}: {doc.content}" for doc in relevant_docs])}
                
                **Key Recommendations:**
                - Use input variables in your prompts with {{variable_name}} syntax for flexibility
                - Always include agent prefix in metadata for proper identification  
                - Test different models to find the best balance of quality, speed, and cost
                - Consider using the playground to prototype your agents before implementing them in code
                """,
            )

        task_info = await self.storage.tasks.get_task_info(agent_id)
        # TODO: figure out the right schema id to use here
        schema_id = agent_schema_id or task_info.latest_schema_id or 1

        last_messages: list[MetaAgentChatMessage] = []
        async for messages in self.meta_agent_service.stream_proxy_meta_agent_response(
            task_tuple=task_info.id_tuple,
            agent_schema_id=schema_id,
            user_email=None,  # TODO:
            messages=[MetaAgentChatMessage(role="USER", content=user_message)],
            playground_state=PlaygroundState(
                is_proxy=True,
                selected_models=PlaygroundState.SelectedModels(column_1=None, column_2=None, column_3=None),
                agent_run_ids=[],
            ),
        ):
            last_messages = messages

        # Add additional guidance to the AI engineer's response
        ai_response = "\n\n".join([message.content for message in last_messages])

        # Append next steps and best practices
        ai_response += """

**Next Steps:**
1. Consider using the playground to test your changes interactively
2. Use input variables in your prompts for better flexibility 
3. Add agent prefix to metadata for proper tracking
4. Test with different models to optimize performance and cost

**Best Practices:**
- Always use input variables instead of hardcoded values in prompts
- Include meaningful metadata with agent_prefix for identification
- Test thoroughly before deploying to production
- Use structured output formats when possible for better reliability
"""

        return MCPToolReturn(
            success=True,
            data=ai_response,
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

            return MCPToolReturn(
                success=True,
                data={
                    "version_id": deployment.version_id,
                    "task_schema_id": deployment.schema_id,
                    "environment": deployment.environment,
                    "deployed_at": deployment.deployed_at.isoformat() if deployment.deployed_at else None,
                    "message": f"Successfully deployed version {version_id} to {environment} environment",
                    "migration_guide": migration_guide,
                },
            )
        except Exception as e:
            return MCPToolReturn(
                success=False,
                error=f"Failed to deploy version: {str(e)}",
            )

    async def open_playground(self, agent_id: str | None = None, with_comparison: bool = False) -> MCPToolReturn:
        """Open the WorkflowAI playground with optional agent context."""
        try:
            # Base playground URL - we'll need to determine the correct domain based on environment
            # For now using a placeholder that would be configured per environment
            base_url = "https://workflowai.com"  # This should be configurable per environment

            if agent_id and agent_id != "new":
                # Try to get task info to validate the agent exists
                try:
                    task_info = await self.storage.tasks.get_task_info(agent_id)
                    if with_comparison:
                        playground_url = f"{base_url}/workflowai/agents/{agent_id}/playground?mode=comparison"
                    else:
                        playground_url = f"{base_url}/workflowai/agents/{agent_id}/playground"

                    agent_context = f"Opening playground for agent '{agent_id}' ({task_info.name})"
                except Exception:
                    # Agent doesn't exist, but we can still open the playground
                    if with_comparison:
                        playground_url = f"{base_url}/workflowai/playground?mode=comparison"
                    else:
                        playground_url = f"{base_url}/workflowai/playground"
                    agent_context = f"Agent '{agent_id}' not found, opening general playground"
            else:
                # Open general playground
                if with_comparison:
                    playground_url = f"{base_url}/workflowai/playground?mode=comparison"
                else:
                    playground_url = f"{base_url}/workflowai/playground"
                agent_context = "Opening general playground"

            next_steps = [
                "1. Click the link above to open the WorkflowAI playground in your browser",
                "2. Experiment with different prompts and models",
            ]

            if with_comparison:
                next_steps.extend(
                    [
                        "3. Use the comparison mode to test multiple models side-by-side",
                        "4. Compare performance, cost, and quality across different models",
                    ],
                )

            if agent_id and agent_id != "new":
                next_steps.extend(
                    [
                        "5. Make any needed changes to your agent in the playground",
                        "6. Test your changes with sample inputs",
                        "7. Save your changes as a new version when ready",
                    ],
                )
            else:
                next_steps.extend(
                    [
                        "5. Create a new agent or import an existing one",
                        "6. Test different model configurations",
                        "7. Save your work as a new agent when ready",
                    ],
                )

            return MCPToolReturn(
                success=True,
                data={
                    "playground_url": playground_url,
                    "message": agent_context,
                    "comparison_mode": with_comparison,
                    "next_steps": next_steps,
                    "tips": [
                        "Use the playground to rapidly prototype and test your agents",
                        "Try different models to find the best balance of quality, speed, and cost",
                        "Use input variables in your prompts to make them more flexible",
                        "Save different versions to track your improvements over time",
                    ],
                },
            )

        except Exception as e:
            return MCPToolReturn(
                success=False,
                error=f"Failed to open playground: {str(e)}",
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
                        return MCPToolReturn(
                            success=False,
                            error="Missing required field 'field_name' in field query",
                        )

                    if "operator" not in query_dict:
                        return MCPToolReturn(
                            success=False,
                            error="Missing required field 'operator' in field query",
                        )

                    if "values" not in query_dict:
                        return MCPToolReturn(
                            success=False,
                            error="Missing required field 'values' in field query",
                        )

                    # Parse the operator
                    try:
                        operator = SearchOperator(query_dict["operator"])
                    except ValueError:
                        return MCPToolReturn(
                            success=False,
                            error=f"Invalid operator: {query_dict['operator']}. Valid operators are: {', '.join([op.value for op in SearchOperator])}",
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
                            **run_summary.model_dump(),  # Convert RunSearchResult to dict
                            "task_input": full_run.task_input,
                            "task_output": full_run.task_output,
                            "task_input_preview": full_run.task_input_preview,
                            "task_output_preview": full_run.task_output_preview,
                        }
                        full_runs.append(full_run_data)
                    except Exception:
                        # If we can't fetch the full run, include what we have
                        full_runs.append(run_summary.model_dump())
                items = [item.model_dump() if isinstance(item, BaseModel) else item for item in full_runs]
            else:
                # Convert RunSearchResult objects to dicts
                items = [item.model_dump() for item in items]

            return MCPToolReturn(
                success=True,
                data={
                    "items": items,
                    "count": page_result.count,
                    "limit": limit,
                    "offset": offset,
                },
            )

        except Exception as e:
            return MCPToolReturn(
                success=False,
                error=f"Failed to search runs by metadata: {str(e)}",
            )
