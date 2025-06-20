from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request
from pydantic import Field
from starlette.exceptions import HTTPException

from api.dependencies.task_info import TaskTuple
from api.routers.mcp._mcp_models import (
    AgentResponse,
    AgentSortField,
    AIEngineerReponseWithUsefulLinks,
    ConciseLatestModelResponse,
    ConciseModelResponse,
    LegacyMCPToolReturn,
    MajorVersion,
    MCPToolReturn,
    ModelSortField,
    PaginatedMCPToolReturn,
    RunSearchResult,
    SortOrder,
)
from api.routers.mcp._mcp_service import MCPService
from api.services import file_storage, storage
from api.services.analytics import analytics_service
from api.services.event_handler import system_event_router, tenant_event_router
from api.services.feedback_svc import FeedbackService
from api.services.groups import GroupService
from api.services.internal_tasks.ai_engineer_service import AIEngineerService, AIGuidesEngineerAgentResponse
from api.services.internal_tasks.internal_tasks_service import InternalTasksService
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

    ai_engineer_service = AIEngineerService(
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
        ai_engineer_service=ai_engineer_service,
        runs_service=runs_service,
        versions_service=versions_service,
        models_service=models_service,
        task_deployments_service=task_deployments_service,
        user_email=user_identifier.user_email,
        tenant_slug=tenant.slug,
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

    # Get tenant storage to access tasks
    tenant_storage = storage.storage_for_tenant(
        tenant.tenant,
        tenant.uid,
        system_event_router(),
        storage.shared_encryption(),
    )
    try:
        task_info = await tenant_storage.tasks.get_task_info(task_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Task not found")

    return task_info.id_tuple


@_mcp.tool()
async def list_available_models(
    agent_id: Annotated[
        str | None,
        Field(
            description="The id of the user's agent, MUST be passed when searching for models in the context of a specific agent. Example: 'agent_id': 'email-filtering-agent' in metadata, or 'email-filtering-agent' in 'model=email-filtering-agent/gpt-4o-latest'.",
        ),
    ] = None,
    agent_schema_id: Annotated[
        int | None,
        Field(
            description="The schema ID of the user's agent version, if known from model=<agent_id>/#<agent_schema_id>/<deployment_environment> or model=#<agent_schema_id>/<deployment_environment> when the workflowAI agent is already deployed, if not provided, all models are returned",
        ),
    ] = None,
    agent_requires_tools: Annotated[
        bool,
        Field(
            description="Whether the agent requires tools to be used, if not provided, the agent is assumed to not require tools",
        ),
    ] = False,
    sort_by: Annotated[
        ModelSortField,
        Field(
            description="The field name to sort by, e.g., 'release_date', 'quality_index' (default), 'cost'",
        ),
    ] = "quality_index",
    order: Annotated[
        SortOrder,
        Field(
            description="The direction to sort: 'asc' for ascending, 'desc' for descending (default)",
        ),
    ] = "desc",
    page: Annotated[
        int,
        Field(description="The page number to return. Defaults to 1."),
    ] = 1,
) -> PaginatedMCPToolReturn[None, ConciseModelResponse | ConciseLatestModelResponse]:
    """<when_to_use>
    When you need to pick a model for the user's WorkflowAI agent, or any model-related goal.
    </when_to_use>
    <returns>
    Returns a list of all available AI models from WorkflowAI.
    </returns>"""
    service = await get_mcp_service()
    return await service.list_available_models(
        page=page,
        agent_id=agent_id,
        agent_schema_id=agent_schema_id,
        agent_requires_tools=agent_requires_tools,
        sort_by=sort_by,
        order=order,
    )


@_mcp.tool()
async def list_agents(
    agent_id: Annotated[
        str | None,
        Field(
            description="Filter on specific agent id. If omitted, all user's agents are returned. Example: 'agent_id': 'email-filtering-agent' in metadata, or 'email-filtering-agent' in 'model=email-filtering-agent/gpt-4o-latest'.",
        ),
    ] = None,
    with_schemas: Annotated[
        bool,
        Field(
            description="If true, the response will include the input and output schemas of the different schema ids of the agent. Useful to find on which schema id you are working on.",
        ),
    ] = False,
    stats_from_date: Annotated[
        str,
        Field(
            description="ISO date string to filter usage (runs and costs) stats from (e.g., '2024-01-01T00:00:00Z'). Defaults to 7 days ago if not provided.",
        ),
    ] = "",
    sort_by: Annotated[
        AgentSortField,
        Field(
            description="The field name to sort by, e.g., 'last_active_at' (default), 'total_cost_usd', 'run_count'",
        ),
    ] = "last_active_at",
    order: Annotated[
        SortOrder,
        Field(
            description="The direction to sort: 'asc' for ascending, 'desc' for descending (default)",
        ),
    ] = "desc",
    page: Annotated[
        int,
        Field(description="The page number to return. Defaults to 1."),
    ] = 1,
) -> PaginatedMCPToolReturn[None, AgentResponse]:
    """<when_to_use>
    When the user wants to see all agents they have created, along with their statistics (run counts and costs on the last 7 days).
    </when_to_use>
    <returns>
    Returns a list of all agents for the user along with their statistics (run counts and costs).
    </returns>"""
    service = await get_mcp_service()
    return await service.list_agents(
        agent_id=agent_id,
        stats_from_date=stats_from_date,
        with_schemas=with_schemas,
        page=page,
        sort_by=sort_by,
        order=order,
    )


@_mcp.tool()
async def fetch_run_details(
    agent_id: Annotated[
        str | None,
        Field(
            description="The id of the user's agent. Example: 'agent_id': 'email-filtering-agent' in metadata, or 'email-filtering-agent' in 'model=email-filtering-agent/gpt-4o-latest'.",
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
) -> LegacyMCPToolReturn:
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
    agent_id: Annotated[
        str,
        Field(
            description="The id of the user's agent. Example: 'agent_id': 'email-filtering-agent' in metadata, or 'email-filtering-agent' in 'model=email-filtering-agent/gpt-4o-latest'.",
        ),
    ],
    version_id: Annotated[
        str | None,
        Field(description="An optional version id, e-g 1.1. If not provided all versions are returned"),
    ] = None,
    page: Annotated[
        int,
        Field(description="The page number to return. Defaults to 1."),
    ] = 1,
) -> PaginatedMCPToolReturn[None, MajorVersion]:
    """<when_to_use>
    When the user wants to retrieve details of versions of a WorkflowAI agent, or when they want to compare a specific version of an agent.
    </when_to_use>
    <returns>
    Returns the details of one or more versions of a WorkflowAI agent.
    </returns>"""
    service = await get_mcp_service()
    task_tuple = await get_task_tuple_from_task_id(agent_id)

    if version_id:
        return await service.get_agent_version(task_tuple, version_id)

    return await service.list_agent_versions(task_tuple, page=page)


@_mcp.tool()
async def search_runs(
    agent_id: Annotated[
        str,
        Field(
            description="The id of the user's agent. Example: 'agent_id': 'email-filtering-agent' in metadata, or 'email-filtering-agent' in 'model=email-filtering-agent/gpt-4o-latest'.",
        ),
    ],
    field_queries: Annotated[
        list[dict[str, Any]],
        Field(
            description="List of field queries to search runs. Each query should have: field_name (string), operator (string), values (list of values), and optionally type (string like 'string', 'number', 'date', etc.)",
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
    page: Annotated[
        int,
        Field(description="The page number to return. Defaults to 1."),
    ] = 1,
) -> PaginatedMCPToolReturn[None, RunSearchResult]:
    """<when_to_use>
    When the user wants to search agent runs based on various criteria including metadata values, run properties (status, time, cost, latency), model parameters, input/output content, and reviews.
    </when_to_use>

    <searchable_fields>
    You can search across multiple types of fields:

    **Run Properties:**
    - "status": Run status (operators: is, is not | values: "success", "failure")
    - "time": Run creation time (operators: is before, is after | date values)
    - "price": Run cost in USD (operators: is, is not, greater than, less than, etc. | numeric values)
    - "latency": Run duration (operators: is, is not, greater than, less than, etc. | numeric values)

    **Model & Version:**
    - "model": Model used (operators: is, is not, contains, does not contain | string values)
    - "schema": Schema ID (operators: is, is not | numeric values)
    - "version": Version ID (operators: is, is not | string values)
    - "temperature": Temperature setting (operators: is, is not, greater than, less than, etc. | numeric values)
    - "source": Source of the run (operators: is, is not | string values)

    **Reviews:**
    - "review": User review status (operators: is | values: "positive", "negative", "unsure", "any")

    **Content Fields (nested search):**
    - "input.{key_path}": Search within input data (e.g., "input.message", "input.user.name")
    - "output.{key_path}": Search within output data (e.g., "output.result", "output.items[0].status")
    - "metadata.{key_path}": Search within metadata (e.g., "metadata.user_id", "metadata.environment")

    For nested fields, use dot notation for objects and brackets for arrays (e.g., "items[0].name")
    </searchable_fields>

    <operators_by_type>
    Different field types support different operators:

    **String fields:**
    - "is" - exact match
    - "is not" - not equal to
    - "contains" - string contains
    - "does not contain" - string does not contain
    - "is empty" - field has no value
    - "is not empty" - field has a value

    **Number fields:**
    - "is" - exact match
    - "is not" - not equal to
    - "greater than" - value > X
    - "greater than or equal to" - value >= X
    - "less than" - value < X
    - "less than or equal to" - value <= X
    - "is empty" - field has no value
    - "is not empty" - field has a value

    **Date fields:**
    - "is before" - date < X
    - "is after" - date > X

    **Boolean fields:**
    - "is" - exact match (true/false)
    - "is not" - not equal to
    </operators_by_type>

    <field_query_structure>
    Each field query should have this structure:
    {
        "field_name": "field_name",  // Required: the field to search
        "operator": "operator",       // Required: the search operator
        "values": [value1, value2],   // Required: list of values (usually one)
        "type": "string"             // Optional: field type hint
    }
    </field_query_structure>

    <examples>
    Example 1 - Search for failed runs with high cost:
    {
        "agent_id": "email-classifier",
        "field_queries": [
            {
                "field_name": "status",
                "operator": "is",
                "values": ["failure"]
                "type": "string"
            },
            {
                "field_name": "price",
                "operator": "greater than",
                "values": [0.10],
                "type": "number"
            }
        ]
    }

    Example 2 - Search for runs with specific metadata and positive reviews:
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
                "field_name": "review",
                "operator": "is",
                "values": ["positive"]
                "type": "string"
            }
        ]
    }

    Example 3 - Search for runs with specific input content and recent time:
    {
        "agent_id": "content-moderator",
        "field_queries": [
            {
                "field_name": "input.text",
                "operator": "contains",
                "values": ["urgent"],
                "type": "string"
            },
            {
                "field_name": "time",
                "operator": "is after",
                "values": ["2024-01-01T00:00:00Z"],
                "type": "date"
            }
        ]
    }

    Example 4 - Search for runs using specific models with low latency:
    {
        "agent_id": "task-analyzer",
        "field_queries": [
            {
                "field_name": "model",
                "operator": "contains",
                "values": ["gpt-4"]
                "type": "string"
            },
            {
                "field_name": "latency",
                "operator": "less than",
                "values": [5.0],
                "type": "number"
            }
        ]
    }

    Example 5 - Search within nested output structure:
    {
        "agent_id": "data-extractor",
        "field_queries": [
            {
                "field_name": "output.entities[0].type",
                "operator": "is",
                "values": ["person"],
                "type": "string"
            },
            {
                "field_name": "output.confidence",
                "operator": "greater than",
                "values": [0.95],
                "type": "number"
            }
        ]
    }
    </examples>

    <returns>
    Returns a paginated list of agent runs that match the search criteria, including run details.
    </returns>"""

    try:
        service = await get_mcp_service()

        task_tuple = await get_task_tuple_from_task_id(agent_id)

        return await service.search_runs(
            task_tuple=task_tuple,
            field_queries=field_queries,
            limit=limit,
            offset=offset,
            page=page,
        )
    except Exception as e:
        return PaginatedMCPToolReturn(
            success=False,
            error=f"Failed to search runs: {e}",
        )


@_mcp.tool()
async def ask_ai_engineer(
    message: Annotated[
        str,
        Field(description="Your message to the AI engineer about what help you need"),
    ],
    user_programming_language: Annotated[
        str,
        Field(
            description="The programming language and integration (if known) used by the user, e.g, Typescript, Python with OpenAI SDK, etc.",
        ),
    ],
    user_code_extract: Annotated[
        str,
        Field(
            description="The code you are working on to improve the user's agent, if any. Please DO NOT include API keys or other sensitive information.",
        ),
    ],
    agent_schema_id: Annotated[
        int | None,
        Field(
            description="The schema ID of the user's agent version, if known from model=<agent_id>/#<agent_schema_id>/<deployment_environment> or model=#<agent_schema_id>/<deployment_environment> when the workflowAI agent is already deployed",
        ),
    ] = None,
    agent_id: Annotated[
        str | None,
        Field(
            description="The id of the user's agent, MUST be passed when the user is asking a question in the context of a specific agent. Example: 'agent_id': 'email-filtering-agent' in metadata, or 'email-filtering-agent' in 'model=email-filtering-agent/gpt-4o-latest'. Can be ommited when the user is asking a general question about WorkflowAI or creating a new agent.",
        ),
    ] = None,
) -> MCPToolReturn[AIGuidesEngineerAgentResponse] | LegacyMCPToolReturn:
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
    agent_id: Annotated[
        str,
        Field(
            description="The id of the user's agent. Example: 'agent_id': 'email-filtering-agent' in metadata, or 'email-filtering-agent' in 'model=email-filtering-agent/gpt-4o-latest'.",
        ),
    ],
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
) -> LegacyMCPToolReturn:
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
    return _mcp.http_app(path="/")
