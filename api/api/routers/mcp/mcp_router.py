from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from api.dependencies.services import MetaAgentServiceDep, ModelsServiceDep, RunsServiceDep, VersionsServiceDep
from api.dependencies.storage import StorageDep
from api.dependencies.task_info import TaskTupleDep
from api.services.mcp_service import MCPService, MCPToolReturn
from api.tags import RouteTags

router = APIRouter(prefix="/_mcp", tags=[RouteTags.MCP])
"""A specific router for MCP. This way we can maintain routes separately."""


def mcp_service_dependency(
    storage: StorageDep,
    meta_agent_service: MetaAgentServiceDep,
    runs_service: RunsServiceDep,
    versions_service: VersionsServiceDep,
    models_service: ModelsServiceDep,
) -> MCPService:
    return MCPService(
        storage=storage,
        meta_agent_service=meta_agent_service,
        runs_service=runs_service,
        versions_service=versions_service,
        models_service=models_service,
    )


MCPServiceDep = Annotated[MCPService, Depends(mcp_service_dependency)]


@router.get(
    "/agents/{task_id}/versions",
    operation_id="get_agent_versions",
    description="""
<when_to_use>
When the user wants to retrieve details of versions of a WorkflowAI agent, or when they want to compare a specific version of an agent.
</when_to_use>
<returns>
Returns the details of one or more versions of a WorkflowAI agent.
</returns>
""",
)
async def get_agent_versions(
    task_tuple: TaskTupleDep,
    mcp_service: MCPServiceDep,
    version_id: str | None = Query(
        description="An optional version id, e-g 1.1. If not provided all versions are returned",
        default=None,
    ),
) -> MCPToolReturn:
    if version_id:
        return await mcp_service.get_agent_version(task_tuple, version_id)

    return await mcp_service.list_agent_versions(task_tuple)


class AskAIEngineerRequest(BaseModel):
    agent_schema_id: int | None = Field(
        description="The schema ID of the user's agent version, if known from model=<agent_id>/<agent_schema_id>/<deployment_environment> when the workflowAI agent is already deployed",
        default=None,
    )
    agent_id: str | None = Field(
        description="The id of the user's agent, example: 'email-filtering-agent' in 'model=email-filtering-agent/gpt-4o-latest'.
        default=None,
    )
    message: str = Field()
    user_programming_language: str | None = Field(
        description="The programming language and integration (if known) used by the user, e.g, Typescript, Python with OpenAI SDK, etc.",
        default=None,
    )
    user_code_extract: str | None = Field(
        description="The code you are working on to improve the user's agent, if any. Please DO NOT include API keys or other sensitive information.",
        default=None,
    )


class AskAIEngineerResponse(BaseModel):
    response: str


@router.post("/ask-ai-engineer", operation_id="ask_ai_engineer", description="Ask the AI Engineer a question")
async def ask_ai_engineer(
    request: AskAIEngineerRequest,
    mcp_service: MCPServiceDep,
) -> MCPToolReturn:
    """
    <when_to_use>
    Most user request about WorkflowAI must be processed by starting a conversation with the AI engineer agent to get insight about the WorkflowAI platform and the user's agents.
    This tool is also useful when you're stuck and need guidance on how to proceed with the user's WorkflowAI-related task.
    </when_to_use>

    <returns>
    Returns a response from WorkflowAI's AI engineer (meta agent) to help improve your agent.
    </returns>
    Get a response from WorkflowAI's AI engineer (meta agent) to help improve your agent.
    """
    return await mcp_service.ask_ai_engineer(
        agent_schema_id=request.agent_schema_id,
        agent_id=request.agent_id,
        message=request.message,
        user_programming_language=request.user_programming_language,
        user_code_extract=request.user_code_extract,
    )


@router.get(
    "/models",
    operation_id="list_available_models",
    description="""
<when_to_use>
When you need to pick a model for the user's WorkflowAI agent, or any model-related goal.
</when_to_use>
<returns>
Returns a list of all available AI models from WorkflowAI.
TODO: explain what type of models information is returned, price, release_date (otherwise the LLM does not know until calling the tool since tool output are not part of the discovery done in the MCP protocol)
</returns>

TODO: ask examples from use-cases
""",
)
async def list_available_models(mcp_service: MCPServiceDep) -> MCPToolReturn:
    # remove the docstring (confused if the docstring is passed as the tool description, or the `description` parameter)
    return await mcp_service.list_available_models()


@router.get(
    "/runs-details",
    operation_id="fetch_run_details",
    description="""
<when_to_use>
When the user wants to investigate a specific run of a WorkflowAI agent, for debugging, improving the agent, fixing a problem on a specific use case, or any other reason.
You must either pass run_id + agent_id OR run_url.
</when_to_use>

TODO: give examples of use-cases
merge when_to_use with examples?

<example>
...
</example>


<returns>
Returns the details of a specific run of a WorkflowAI agent. (TODO: explain what type of information is returned)
</returns>
""",
)
async def fetch_run_details(
    mcp_service: MCPServiceDep,
    agent_id: str | None = Query(
        description="The id of the user's agent, example: 'email-filtering-agent'. Pass 'new' when the user wants to create a new agent.",
        default=None,
    ),
    run_id: str | None = Query(
        description="The id of the run to fetch details for",
        default=None,
    ),
    run_url: str | None = Query(
        description="The url of the run to fetch details for",
        default=None,
    ),
) -> MCPToolReturn:
    """Fetch details of a specific agent run."""
    return await mcp_service.fetch_run_details(agent_id, run_id, run_url)

# TODO: rename with list_agents
@router.get(
    "/agents-stats",
    operation_id="list_agents",
    description="""
<when_to_use>
When the user wants to see all agents they have created, along with their statistics (run counts and costs on the last 7 days).
</when_to_use>
<returns>
Returns a list of all agents for the user along with their statistics (run counts and costs).
</returns>
""",
)
async def list_agents(
    mcp_service: MCPServiceDep,
    from_date: str = Query(
        description="ISO date string to filter stats from (e.g., '2024-01-01T00:00:00Z'). Defaults to 7 days ago if not provided.",
        default="",
    ),
) -> MCPToolReturn:
    # """List all agents with their statistics."""
    # TODO: if the docstrings are not passed as the tool description, then we should remove the docstrings
    return await mcp_service.list_agents_with_stats(from_date)


@router.get(
    "/agents/{task_id}/versions",
    operation_id="list_agent_versions",
    description="""
<when_to_use>
When the user wants to see all versions of a specific agent, or when they want to compare different versions of an agent.
</when_to_use>
<returns>
Returns a list of all versions of a specific agent.
</returns>
""",
)
async def list_agent_versions(
    task_tuple: TaskTupleDep,
    mcp_service: MCPServiceDep,
    version_id: str | None = Query(
        description="Optional version ID to get a single version",
        default=None,
    ),
) -> MCPToolReturn:
    """List all versions of a specific agent."""
    if version_id:
        return await mcp_service.get_agent_version(task_tuple, version_id)

    return await mcp_service.list_agent_versions(task_tuple)
