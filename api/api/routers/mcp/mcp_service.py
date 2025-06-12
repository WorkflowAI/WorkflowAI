from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel

from api.main import StandardModelResponse
from api.routers.mcp._mcp_models import MajorVersion
from api.services.documentation_service import DocumentationService
from api.services.internal_tasks.meta_agent_service import MetaAgentChatMessage, PlaygroundState
from api.services.internal_tasks.meta_agent_service import MetaAgentService as MetaAgentServiceType
from api.services.models import ModelsService
from api.services.runs.runs_service import RunsService
from api.services.versions import VersionsService
from core.domain.fields.chat_message import ChatMessage
from core.domain.models.model_data import FinalModelData, LatestModel
from core.domain.models.model_datas_mapping import MODEL_DATAS
from core.domain.models.models import Model
from core.storage import ObjectNotFoundException
from core.storage.backend_storage import BackendStorage
from core.utils.url_utils import IGNORE_URL_END_TAG, IGNORE_URL_START_TAG


class MCPToolReturn(BaseModel):
    """Standardized return format for MCP tools"""

    success: bool
    data: Any | None = None
    error: str | None = None
    messages: list[str] | None = None


class MCPService:
    def __init__(
        self,
        storage: BackendStorage,
        meta_agent_service: MetaAgentServiceType,
        runs_service: RunsService,
        versions_service: VersionsService,
        models_service: ModelsService,
    ):
        self.storage = storage
        self.meta_agent_service = meta_agent_service
        self.runs_service = runs_service
        self.versions_service = versions_service
        self.models_service = models_service

    async def list_available_models(self) -> MCPToolReturn:
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
                "task_id": run.task_id,
                "task_schema_id": run.task_schema_id,
                "status": run.status,
                "task_input": run.task_input,
                "task_output": run.task_output,
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

    async def list_agents_with_stats(self, from_date: str = "") -> MCPToolReturn:
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
        user_programming_language: str,
        user_code_extract: str | None,
    ) -> MCPToolReturn:
        """Ask the AI Engineer a question (legacy endpoint)."""

        user_message = f"""
        {message}

        The user is using the following programming language and integration:
        {user_programming_language}
        """

        if user_code_extract:
            user_message += f"""
            Here is a code extract from the user's code:
            {IGNORE_URL_START_TAG}{user_code_extract}{IGNORE_URL_END_TAG}
            """
            # We add URL fetching ignore tags to avoid fetching URLs in the code extract

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

        return MCPToolReturn(
            success=True,
            data="\n\n".join([message.content for message in last_messages]),
        )
