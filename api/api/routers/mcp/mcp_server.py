from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request
from pydantic import Field
from starlette.exceptions import HTTPException

from api.dependencies.task_info import TaskTuple
from api.routers.mcp._mcp_models import MCPToolReturn
from api.routers.mcp._mcp_service import MCPService
from api.services import file_storage, storage
from api.services.analytics import analytics_service
from api.services.event_handler import system_event_router, tenant_event_router
from api.services.feedback_svc import FeedbackService
from api.services.groups import GroupService
from api.services.internal_tasks.internal_tasks_service import InternalTasksService
from api.services.internal_tasks.meta_agent_service import MetaAgentService
from api.services.models import ModelsService
from api.services.providers_service import shared_provider_factory
from api.services.reviews import ReviewsService
from api.services.run import RunService
from api.services.runs.runs_service import RunsService
from api.services.security_service import SecurityService
from api.services.task_deployments import TaskDeploymentsService
from api.services.versions import VersionsService
from core.domain.analytics_events.analytics_events import OrganizationProperties, UserProperties
from core.domain.users import UserIdentifier

_mcp = FastMCP("WorkflowAI 🚀", stateless_http=True)  # pyright: ignore [reportUnknownVariableType]


# TODO: test auth
async def get_mcp_service() -> MCPService:
    request = get_http_request()

    _system_storage = storage.system_storage(storage.shared_encryption())
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    security_service = SecurityService(
        _system_storage.organizations,
        system_event_router(),
        analytics_service(user_properties=None, organization_properties=None, task_properties=None),
    )
    tenant = await security_service.find_tenant(None, auth_header.split(" ")[1])
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    org_properties = OrganizationProperties.build(tenant)
    # TODO: user analytics
    user_properties: UserProperties | None = None
    event_router = tenant_event_router(tenant.tenant, tenant.uid, user_properties, org_properties, None)
    _storage = storage.storage_for_tenant(tenant.tenant, tenant.uid, event_router, storage.shared_encryption())
    analytics = analytics_service(
        user_properties=user_properties,
        organization_properties=org_properties,
        task_properties=None,
    )
    models_service = ModelsService(storage=_storage)
    runs_service = RunsService(
        storage=_storage,
        provider_factory=shared_provider_factory(),
        event_router=event_router,
        analytics_service=analytics,
        file_storage=file_storage.shared_file_storage,
    )
    feedback_service = FeedbackService(storage=_storage.feedback)
    versions_service = VersionsService(storage=_storage, event_router=event_router)
    internal_tasks = InternalTasksService(event_router=event_router, storage=_storage)
    reviews_service = ReviewsService(
        backend_storage=_storage,
        internal_tasks=internal_tasks,
        event_router=event_router,
    )

    # Create GroupService and RunService for TaskDeploymentsService
    user_identifier = UserIdentifier(user_id=None, user_email=None)  # System user for MCP operations
    group_service = GroupService(
        storage=_storage,
        event_router=event_router,
        analytics_service=analytics,
        user=user_identifier,
    )
    run_service = RunService(
        storage=_storage,
        event_router=event_router,
        analytics_service=analytics,
        group_service=group_service,
        user=user_identifier,
    )
    task_deployments_service = TaskDeploymentsService(
        storage=_storage,
        run_service=run_service,
        group_service=group_service,
        analytics_service=analytics,
    )

    meta_agent_service = MetaAgentService(
        storage=_storage,
        event_router=event_router,
        runs_service=runs_service,
        models_service=models_service,
        feedback_service=feedback_service,
        versions_service=versions_service,
        reviews_service=reviews_service,
    )

    return MCPService(
        storage=_storage,
        meta_agent_service=meta_agent_service,
        runs_service=runs_service,
        versions_service=versions_service,
        models_service=models_service,
        task_deployments_service=task_deployments_service,
    )


async def get_task_tuple_from_task_id(task_id: str) -> TaskTuple:
    """Helper function to create TaskTuple from task_id for MCP tools that need it"""
    request = get_http_request()
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    _system_storage = storage.system_storage(storage.shared_encryption())
    security_service = SecurityService(
        _system_storage.organizations,
        system_event_router(),
        analytics_service(user_properties=None, organization_properties=None, task_properties=None),
    )
    tenant = await security_service.find_tenant(None, auth_header.split(" ")[1])
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    return (task_id, tenant.uid)


@_mcp.tool()
async def list_available_models() -> MCPToolReturn:
    """<when_to_use>
    When you need to pick a model for the user's WorkflowAI agent, or any model-related goal.
    </when_to_use>
    <returns>
    Returns a list of all available AI models from WorkflowAI.
    </returns>"""
    service = await get_mcp_service()
    return await service.list_available_models()


@_mcp.tool()
async def list_agents(
    from_date: Annotated[
        str,
        Field(
            description="ISO date string to filter stats from (e.g., '2024-01-01T00:00:00Z'). Defaults to 7 days ago if not provided.",
        ),
    ],
) -> MCPToolReturn:
    """<when_to_use>
    When the user wants to see all agents they have created, along with their statistics (run counts and costs on the last 7 days).
    </when_to_use>
    <returns>
    Returns a list of all agents for the user along with their statistics (run counts and costs).
    </returns>"""
    service = await get_mcp_service()
    return await service.list_agents(from_date)


@_mcp.tool()
async def fetch_run_details(
    agent_id: Annotated[
        str | None,
        Field(
            description="The id of the user's agent, example: 'email-filtering-agent'. Pass 'new' when the user wants to create a new agent.",
        ),
    ] = None,
    run_id: Annotated[
        str | None,
        Field(description="The id of the run to fetch details for"),
    ] = None,
    run_url: Annotated[
        str | None,
        Field(description="The url of the run to fetch details for"),
    ] = None,
) -> MCPToolReturn:
    """<when_to_use>
    When the user wants to investigate a specific run of a WorkflowAI agent, for debugging, improving the agent, fixing a problem on a specific use case, or any other reason. This is particularly useful for:
    - Debugging failed runs by examining error details and input/output data
    - Analyzing successful runs to understand agent behavior and performance
    - Reviewing cost and duration metrics for optimization
    - Examining user and AI reviews for quality assessment
    - Troubleshooting specific use cases by examining exact inputs and outputs

    You must either pass run_id + agent_id OR run_url. The run_url approach is convenient when you have a direct link to the run from the WorkflowAI dashboard.
    </when_to_use>
    <returns>
    Returns comprehensive details of a specific WorkflowAI agent run, including:

    **Core Run Information:**
    - id: Unique identifier for this specific run
    - agent_id: The ID of the agent that was executed
    - agent_schema_id: The schema/version ID of the agent used for this run
    - status: Current status of the run (e.g., "completed", "failed", "running")
    - conversation_id: Links this run to a broader conversation context if applicable

    **Input/Output Data:**
    - agent_input: Complete input data provided to the agent for this run
    - agent_output: Complete output/response generated by the agent

    **Performance Metrics:**
    - duration_seconds: Execution time in seconds
    - cost_usd: Cost of this run in USD (based on model usage, tokens, etc.)
    - created_at: ISO timestamp of when the run was created/started

    **Quality Assessment:**
    - user_review: Any review or feedback provided by the user for this run
    - ai_review: Automated review or assessment generated by the AI system

    **Error Information:**
    - error: If the run failed, contains error code, message, and detailed information for debugging

    This data structure provides everything needed for debugging, performance analysis, cost tracking, and understanding the complete execution context of your WorkflowAI agent.
    </returns>"""
    service = await get_mcp_service()
    return await service.fetch_run_details(agent_id, run_id, run_url)


@_mcp.tool()
async def get_agent_versions(
    task_id: Annotated[str, Field(description="The task ID of the agent")],
    version_id: Annotated[
        str | None,
        Field(description="An optional version id, e-g 1.1. If not provided all versions are returned"),
    ] = None,
) -> MCPToolReturn:
    """<when_to_use>
    When the user wants to retrieve details of versions of a WorkflowAI agent, or when they want to compare a specific version of an agent.
    </when_to_use>
    <returns>
    Returns the details of one or more versions of a WorkflowAI agent.
    </returns>"""
    service = await get_mcp_service()
    task_tuple = await get_task_tuple_from_task_id(task_id)

    if version_id:
        return await service.get_agent_version(task_tuple, version_id)

    return await service.list_agent_versions(task_tuple)


# @_mcp.tool() WIP
async def search_runs_by_metadata(
    agent_id: Annotated[
        str,
        Field(description="The agent ID of the agent to search runs for"),
    ],
    field_queries: Annotated[
        list[dict[str, Any]],
        Field(
            description="List of metadata field queries. Each query should have: field_name (string starting with 'metadata.'), operator (string like 'is', 'contains', etc.), values (list of values), and optionally type (string like 'string', 'number', etc.)",
        ),
    ],
    limit: Annotated[
        int,
        Field(description="Maximum number of results to return"),
    ] = 20,
    offset: Annotated[
        int,
        Field(description="Number of results to skip"),
    ] = 0,
) -> MCPToolReturn:
    """<when_to_use>
    When the user wants to search agent runs based on metadata values, such as filtering runs by custom metadata fields they've added to their WorkflowAI agent calls.
    </when_to_use>

    <how_to_query_metadata>
    To search by metadata, you need to construct field queries with the following structure:

    1. field_name: Must start with "metadata." followed by the metadata field name
       - Example: "metadata.user_id", "metadata.session_id", "metadata.environment"

    2. operator: One of these search operators:
       - "is" - exact match
       - "is not" - not equal to
       - "contains" - string contains (for text fields)
       - "does not contain" - string does not contain
       - "greater than" - numeric comparison
       - "less than" - numeric comparison
       - "is empty" - field has no value
       - "is not empty" - field has a value

    3. values: List of values to search for (usually just one value)

    4. type: Optional field type ("string", "number", "boolean", "date")
    </how_to_query_metadata>

    <examples>
    Example 1 - Search for runs with specific user_id:
    {
        "agent_id": "email-classifier",
        "field_queries": [
            {
                "field_name": "metadata.user_id",
                "operator": "is",
                "values": ["user123"],
                "type": "string"
            }
        ]
    }

    Example 2 - Search for runs in production environment with high priority:
    {
        "agent_id": "data-processor",
        "field_queries": [
            {
                "field_name": "metadata.environment",
                "operator": "is",
                "values": ["production"],
                "type": "string"
            },
            {
                "field_name": "metadata.priority",
                "operator": "greater than",
                "values": [5],
                "type": "number"
            }
        ]
    }

    Example 3 - Search for runs that contain specific text in a notes field:
    {
        "agent_id": "content-moderator",
        "field_queries": [
            {
                "field_name": "metadata.notes",
                "operator": "contains",
                "values": ["urgent"]
            }
        ]
    }

    Example 4 - Search for runs where a field is empty:
    {
        "agent_id": "task-analyzer",
        "field_queries": [
            {
                "field_name": "metadata.reviewer",
                "operator": "is empty",
                "values": []
            }
        ]
    }
    </examples>

    <returns>
    Returns a paginated list of agent runs that match the metadata search criteria, including run details like:
    - Full task input and output data (task_input, task_output)
    - Input/output previews (task_input_preview, task_output_preview)
    - Run status, duration, cost, and timestamps
    - User and AI reviews
    - Error details if the run failed
    </returns>"""
    service = await get_mcp_service()
    task_tuple = await get_task_tuple_from_task_id(agent_id)
    return await service.search_runs_by_metadata(
        task_tuple=task_tuple,
        field_queries=field_queries,
        limit=limit,
        offset=offset,
    )


@_mcp.tool()
async def ask_ai_engineer(
    agent_id: Annotated[
        str,
        Field(
            description="The id of the user's agent, MUST be passed when the user is asking a question in the context of a specific agent. Example: 'email-filtering-agent' in 'model=email-filtering-agent/gpt-4o-latest'. Pass 'new' when the user wants to create a new agent.",
        ),
    ],
    message: Annotated[
        str,
        Field(description="Your message to the AI engineer about what help you need"),
    ] = "I need help improving my agent",
    agent_schema_id: Annotated[
        int | None,
        Field(
            description="The schema ID of the user's agent version, if known from model=<agent_id>/<agent_schema_id>/<deployment_environment> when the workflowAI agent is already deployed",
        ),
    ] = None,
    user_programming_language: Annotated[
        str | None,
        Field(
            description="The programming language and integration (if known) used by the user, e.g, Typescript, Python with OpenAI SDK, etc.",
        ),
    ] = None,
    user_code_extract: Annotated[
        str | None,
        Field(
            description="The code you are working on to improve the user's agent, if any. Please DO NOT include API keys or other sensitive information.",
        ),
    ] = None,
) -> MCPToolReturn:
    """
    <when_to_use>
    Most user request about WorkflowAI must be processed by starting a conversation with the AI engineer agent to get insight about the WorkflowAI platform and the user's agents.
    </when_to_use>

    <returns>
    Returns a response from WorkflowAI's AI engineer (meta agent) to help improve your agent.
    </returns>
    Get a response from WorkflowAI's AI engineer (meta agent) to help improve your agent.
    """
    service = await get_mcp_service()
    return await service.ask_ai_engineer(
        agent_schema_id=agent_schema_id,
        agent_id=agent_id,
        message=message,
        user_programming_language=user_programming_language,
        user_code_extract=user_code_extract,
    )


@_mcp.tool()
async def deploy_agent_version(
    agent_id: Annotated[str, Field(description="The id of the agent to deploy, e.g., 'email-filtering-agent'")],
    version_id: Annotated[
        str,
        Field(
            description="The version ID to deploy (e.g., '1.0', '2.1', or a hash). This can be obtained from the agent versions list or from the version_id metadata in chat completion responses.",
        ),
    ],
    environment: Annotated[
        Literal["dev", "staging", "production"],
        Field(description="The deployment environment. Must be one of: 'dev', 'staging', or 'production'"),
    ],
) -> MCPToolReturn:
    """<when_to_use>
    When the user wants to deploy a specific version of their WorkflowAI agent to an environment (dev, staging, or production).

    The version ID can be obtained by:
    1. Asking the user which version they want to deploy
    2. Using the get_agent_versions tool to list available versions
    3. Checking the response payload from a chat completion endpoint which contains version_id metadata
    </when_to_use>

    <returns>
    Returns deployment confirmation with:
    - version_id: The deployed version ID
    - task_schema_id: The schema ID of the deployed version
    - environment: The deployment environment
    - deployed_at: The deployment timestamp
    - message: Success message
    - migration_guide: Detailed instructions on how to update your code to use the deployed version, including:
      - model_parameter: The exact model parameter to use in your code
      - migration_instructions: Step-by-step examples for both scenarios (with and without input variables)
      - important_notes: Key considerations for the migration
    </returns>"""
    service = await get_mcp_service()
    task_tuple = await get_task_tuple_from_task_id(agent_id)

    # Get user identifier for deployment tracking
    # Since we already validated the token in get_mcp_service, we can create a basic user identifier
    user_identifier = UserIdentifier(user_id=None, user_email=None)  # System user for MCP deployments

    return await service.deploy_agent_version(
        task_tuple=task_tuple,
        version_id=version_id,
        environment=environment,
        deployed_by=user_identifier,
    )


def mcp_http_app():
    return _mcp.http_app(path="/sse")
