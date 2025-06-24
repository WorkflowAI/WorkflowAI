import datetime
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request
from pydantic import Field
from starlette.exceptions import HTTPException

from api.dependencies.task_info import TaskTuple
from api.routers.mcp._mcp_models import (
    AgentListItem,
    AgentResponse,
    AgentSortField,
    ConciseLatestModelResponse,
    ConciseModelResponse,
    LegacyMCPToolReturn,
    MajorVersion,
    MCPRun,
    MCPToolReturn,
    ModelSortField,
    PaginatedMCPToolReturn,
    SortOrder,
)
from api.routers.mcp._mcp_service import MCPService
from api.services import file_storage, storage
from api.services.analytics import analytics_service
from api.services.event_handler import system_event_router, tenant_event_router
from api.services.feedback_svc import FeedbackService
from api.services.groups import GroupService
from api.services.internal_tasks.ai_engineer_service import AIEngineerService
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
from core.storage.backend_storage import BackendStorage
from core.utils.schema_formatter import format_schema_as_yaml_description

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
    tenant = await security_service.tenant_from_credentials(auth_header.split(" ")[1])
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


async def get_task_tuple_from_task_id(storage: BackendStorage, agent_id: str) -> TaskTuple:
    """Helper function to create TaskTuple from task_id for MCP tools that need it"""
    task_info = await storage.tasks.get_task_info(agent_id)
    if not task_info:
        raise HTTPException(status_code=404, detail=f"Task {agent_id} not found")
    return task_info.id_tuple


@_mcp.tool()
async def list_models(
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
    return await service.list_models(
        page=page,
        agent_id=agent_id,
        agent_schema_id=agent_schema_id,
        agent_requires_tools=agent_requires_tools,
        sort_by=sort_by,
        order=order,
    )


def description_for_list_agents() -> str:
    """Generate dynamic description for list_agents tool based on Pydantic models"""
    # Get the YAML-like description for AgentListItem
    agent_item_description = format_schema_as_yaml_description(AgentListItem)

    return f"""<when_to_use>
When the user wants to see all agents they have created, along with their basic statistics (run counts and costs).
</when_to_use>
<returns>
Returns a list of agents with the following structure:

{agent_item_description}
</returns>"""


@_mcp.tool(description=description_for_list_agents())
async def list_agents(
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
) -> PaginatedMCPToolReturn[None, AgentListItem]:
    service = await get_mcp_service()
    return await service.list_agents(
        page=page,
        sort_by=sort_by,
        order=order,
    )


@_mcp.tool()
async def get_agent(
    agent_id: Annotated[
        str,
        Field(
            description="The id of the user's agent. Example: 'agent_id': 'email-filtering-agent' in metadata, or 'email-filtering-agent' in 'model=email-filtering-agent/gpt-4o-latest'.",
        ),
    ],
    stats_from_date: Annotated[
        datetime.datetime | None,
        Field(
            description="ISO date string to filter usage (runs and costs) stats from (e.g., '2024-01-01T00:00:00Z'). Defaults to 7 days ago if not provided.",
        ),
    ] = None,
) -> MCPToolReturn[AgentResponse]:
    """<when_to_use>
    When the user wants to get detailed information about a specific agent, including full input/output schemas, versions, name, description, and statistics.
    </when_to_use>
    <returns>
    Returns detailed information for a specific agent including:
    - Full input and output JSON schemas for each schema version
    - Agent name and description
    - Complete schema information (created_at, is_hidden, last_active_at)
    - Run statistics (run count and total cost)
    - Agent metadata (is_public status)
    </returns>"""
    service = await get_mcp_service()
    return await service.get_agent(
        agent_id=agent_id,
        stats_from_date=stats_from_date,
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
) -> MCPToolReturn[MCPRun]:
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

    Example:
    - when debugging a failed run, you can use this tool to get the parameters of the agent that was used.
    </when_to_use>
    <returns>
    Returns the details of one or more versions of a WorkflowAI agent.
    </returns>"""
    # TODO: remind the agent what an AgentVersion is ?
    service = await get_mcp_service()
    task_tuple = await get_task_tuple_from_task_id(service.storage, agent_id)

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
) -> PaginatedMCPToolReturn[None, MCPRun]:
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

        task_tuple = await get_task_tuple_from_task_id(service.storage, agent_id)

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
    task_tuple = await get_task_tuple_from_task_id(service.storage, agent_id)

    # Get user identifier for deployment tracking
    # Since we already validated the token in get_mcp_service, we can create a basic user identifier
    user_identifier = UserIdentifier(user_id=None, user_email=None)  # System user for MCP deployments

    return await service.deploy_agent_version(
        task_tuple=task_tuple,
        version_id=version_id,
        environment=environment,
        deployed_by=user_identifier,
    )


@_mcp.tool()
async def create_api_key() -> LegacyMCPToolReturn:
    """<when_to_use>
    When the user wants to get their API key for WorkflowAI. This is a temporary tool that returns the API key that was used to authenticate the current request.
    </when_to_use>
    <returns>
    Returns the API key that was used to authenticate the current MCP request.
    </returns>"""
    request = get_http_request()

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return LegacyMCPToolReturn(
            success=False,
            error="No Authorization header found or invalid format",
        )

    # Extract the API key from "Bearer <key>"
    api_key = auth_header.split(" ")[1]

    return LegacyMCPToolReturn(
        success=True,
        data={"api_key": api_key},
        messages=["API key retrieved successfully"],
    )


@_mcp.tool()
async def search_documentation(
    query: str | None = Field(
        default=None,
        description="Search across all WorkflowAI documentation. Use this when you need to find specific information across multiple pages.",
    ),
    page: str | None = Field(
        default=None,
        description="Direct access to specific documentation page. Available pages are dynamically determined from the docsv2 directory structure.",
    ),
) -> LegacyMCPToolReturn:
    """Search WorkflowAI documentation OR fetch a specific documentation page.

     <when_to_use>
     Enable MCP clients to explore WorkflowAI documentation without web access through a dual-mode search tool:
     1. Search mode ('query' parameter): Search across all documentation to find relevant documentation sections. Use search mode when you need to find information but don't know which specific page contains it.
     2. Direct navigation mode ('page' parameter): Fetch the complete content of a specific documentation page (see <available_pages> below for available pages). Use direct navigation mode when you want to read the full content of a specific page. Example: 'page': 'reference/authentication'
    </when_to_use>

     <available_pages>
     The following documentation pages are available for direct access:

     **Getting Started:**
     - 'index.mdx' - Introduction to the WorkflowAI documentation. Provides information on what WorkflowAI is and how to get started with building, deploying, and improving AI agents.
     - 'why-workflowai.mdx' - An explanation of the WorkflowAI platform. Covers its commitment to open standards, provider flexibility, and developer and agent experience.
     - 'self-hosting.mdx' - Guide for deploying and managing WorkflowAI in your own environment. Provides step-by-step instructions for self-hosting to have control over data and infrastructure.
     - 'pricing.mdx' - Documentation on the pay-as-you-go pricing model. Explains the price-match guarantee, what you pay for, and answers common questions about billing and costs.
     - 'organizations.mdx' - Documentation on team collaboration using organizations. Covers creating, joining, and switching between organizations, as well as managing members and join settings.
     - 'glossary.mdx' - A glossary of key terms and concepts used throughout the WorkflowAI documentation. Provides definitions for important terminology.
     - 'ask-ai.mdx' - Documentation for the 'Ask AI' assistant. Explains how to ask questions, use commands, and get guidance on using the platform.
     - 'changelog.mdx' - A chronological record of updates, improvements, and new model integrations to the WorkflowAI platform.
     - 'compliance.mdx' - Information on security and compliance. Covers SOC2 compliance, data handling policies, and provides answers to frequently asked questions about data privacy.

     **Use Cases:**
     - 'use-cases/chatbot.mdx' - Use case guide for building a conversational AI chatbot. Covers basic setup, conversation management, streaming, error handling, and deployment.
     - 'use-cases/new_agent.mdx' - Comprehensive framework for building AI agents from scratch. Covers requirements analysis, agent types, model selection, prompt design, evaluation methods, and best practices.
     - 'use-cases/migrating_existing_agent.mdx' - Step-by-step guide for migrating existing AI agents to the WorkflowAI platform. Covers understanding your current agent, data requirements, and migration best practices.
     - 'use-cases/improving_and_debugging_existing_agent.mdx' - Guide for troubleshooting and optimizing existing AI agents. Covers common errors like max_tokens_exceeded, debugging with metadata, and performance optimization strategies.
     - 'use-cases/classifier.mdx' - Use case guide for building AI classifiers. Covers techniques for text categorization, sentiment analysis, and more, from basic to advanced implementations.
     - 'use-cases/image-input.mdx' - Use case guide for using images as input for AI agents. Covers processing and analyzing images to extract information, answer questions, and perform vision-based tasks.
     - 'use-cases/pdf-input.mdx' - Use case guide for processing and extracting information from PDF documents. Covers techniques for using PDF files as input for summarization, data extraction, and question-answering tasks.
     - 'use-cases/image-generation.mdx' - Use case guide for generating and editing images. Covers best practices for prompting, customizing image outputs, and using the WorkflowAI SDK for image generation tasks.
     - 'use-cases/mcp.mdx' - A collection of use-case scenarios for AI agents that interact with the WorkflowAI platform. Outlines the required capabilities for agents to perform tasks like optimization, debugging, and deployment.

     **API Reference:**
     - 'reference/api-errors.mdx' - Reference for API error codes and meanings from chat completion endpoints and SDKs.
     - 'reference/api-responses.mdx' - Response formats documentation (detailed content available in file)
     - 'reference/authentication.mdx' - Explains API authentication using bearer tokens. Covers API key management, security best practices, and the authentication process.
     - 'reference/prompt-templating.mdx' - Prompt engineering documentation (detailed content available in file)
     - 'reference/supported-models.mdx' - Available models documentation (detailed content available in file)
     - 'reference/supported-parameters.mdx' - API parameters documentation (detailed content available in file)

     **Quickstarts:**
     - 'quickstarts.mdx' - Provides quickstart guides for getting started with WorkflowAI. Includes instructions for creating agents without code and integrating with popular SDKs.
     - 'quickstarts/instructor-python.mdx' - Instructor Python integration guide (detailed content available in file)
     - 'quickstarts/no-code.mdx' - No-code solutions guide (detailed content available in file)
     - 'quickstarts/openai-agents.mdx' - OpenAI Agents integration guide (detailed content available in file)
     - 'quickstarts/openai-javascript-typescript.mdx' - OpenAI JS/TS SDK integration guide (detailed content available in file)
     - 'quickstarts/openai-python.mdx' - OpenAI Python SDK integration guide (detailed content available in file)
     - 'quickstarts/pydanticai.mdx' - PydanticAI integration guide (detailed content available in file)
     - 'quickstarts/vercelai.mdx' - Vercel AI SDK integration guide (detailed content available in file)

     **Playground:**
     - 'playground.mdx' - Overview of the WorkflowAI Playground. Lists its features for comparing models, optimizing prompts, and team collaboration.
     - 'playground/additional-features.mdx' - Advanced playground features documentation (detailed content available in file)
     - 'playground/ai-assistant.mdx' - AI Assistant in playground documentation (detailed content available in file)
     - 'playground/compare-models.mdx' - Model comparison tools documentation (detailed content available in file)
     - 'playground/data-generation.mdx' - Data generation tools documentation (detailed content available in file)
     - 'playground/diff-mode.mdx' - Diff mode feature documentation (detailed content available in file)
     - 'playground/price-and-latency.mdx' - Performance metrics documentation (detailed content available in file)
     - 'playground/sharing-playgrounds.mdx' - Sharing functionality documentation (detailed content available in file)
     - 'playground/versioning.mdx' - Version management documentation (detailed content available in file)

     **Observability:**
     - 'observability.mdx' - Overview of observability tools for AI applications. Explains how to automatically monitor, analyze, and optimize agent performance.
     - 'observability/conversations.mdx' - Conversation tracking documentation (detailed content available in file)
     - 'observability/costs.mdx' - Cost monitoring documentation (detailed content available in file)
     - 'observability/insights.mdx' - Analytics insights documentation (detailed content available in file)
     - 'observability/reports.mdx' - Reporting features documentation (detailed content available in file)
     - 'observability/runs.mdx' - Run monitoring documentation (detailed content available in file)
     - 'observability/search.mdx' - Search functionality documentation (detailed content available in file)
     - 'observability/versions.mdx' - Version tracking documentation (detailed content available in file)

     **Inference:**
     - 'inference.mdx' - Overview of the WorkflowAI inference API. Lists key features, including OpenAI compatibility, multi-provider support, structured outputs, and caching.
     - 'inference/caching.mdx' - Caching strategies documentation (detailed content available in file)
     - 'inference/cost.mdx' - Cost optimization documentation (detailed content available in file)
     - 'inference/models.mdx' - Model selection documentation (detailed content available in file)
     - 'inference/reasoning.mdx' - Reasoning capabilities documentation (detailed content available in file)
     - 'inference/reliability.mdx' - Reliability features documentation (detailed content available in file)
     - 'inference/streaming.mdx' - Streaming responses documentation (detailed content available in file)
     - 'inference/structured-outputs.mdx' - Structured data documentation (detailed content available in file)

     **Deployments:**
     - 'deployments.mdx' - Documentation on using deployments to manage and update AI agents. Covers separating prompts from code, managing environments, and versioning with schemas.

     **Evaluations:**
     - 'evaluations.mdx' - Overview of the evaluations feature for systematic testing of AI applications. Covers prompt evaluation, model comparison, regression testing, and best practices.
     - 'evaluations/benchmarks.mdx' - Benchmarking documentation (detailed content available in file)
     - 'evaluations/reviews.mdx' - Review system documentation (detailed content available in file)
     - 'evaluations/side-by-side.mdx' - Comparison tools documentation (detailed content available in file)
     - 'evaluations/user-feedback.mdx' - Feedback collection documentation (detailed content available in file)

     **Agents:**
     - 'agents.mdx' - Overview of AI agents in WorkflowAI. Covers what agents are and their purpose in the platform for automating tasks.
     - 'agents/mcp.mdx' - Model Control Protocol for agents documentation (detailed content available in file)
     - 'agents/memory.mdx' - Explains how to manage conversational memory using `reply_to_run_id`. This feature maintains chat history for stateful, multi-turn interactions.
     - 'agents/tools.mdx' - Documentation for using tools with AI agents. Covers hosted tools like web search and defining custom tools for specific use cases.

     **AI Engineer:**
     - 'ai-engineer.mdx' - Setup guide for the AI Engineer. Walks through the necessary installation and configuration steps.

     **Components:**
     - 'components.mdx' - Overview of the reusable UI component library. Lists available components like buttons, forms, and cards.
     </available_pages>

     <returns>
     - If using query: Returns a list of SearchResult objects with relevant documentation sections and source page references
     - If using page: Returns the complete content of the specified documentation page as a string
     - Error message if both or neither parameters are provided, or if the requested page is not found
     </returns>"""

    service = await get_mcp_service()
    return await service.search_documentation(query=query, page=page)


def mcp_http_app():
    return _mcp.http_app(path="/")
