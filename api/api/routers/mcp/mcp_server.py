import datetime
import logging
import time
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware

from api.dependencies.task_info import TaskTuple
from api.routers.mcp._mcp_dependencies import get_mcp_service
from api.routers.mcp._mcp_errors import MCPError, mcp_wrap
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
)
from api.routers.mcp._mcp_observability_middleware import MCPObservabilityMiddleware
from api.routers.mcp._mcp_serializer import tool_serializer
from api.routers.openai_proxy._openai_proxy_models import (
    OpenAIProxyChatCompletionRequest,
    OpenAIProxyChatCompletionResponse,
)
from api.services.documentation_service import DocumentationService
from api.services.tools_service import ToolsService
from core.domain.tool import Tool
from core.domain.users import UserIdentifier
from core.storage.backend_storage import BackendStorage
from core.utils.schema_formatter import format_schema_as_yaml_description

logger = logging.getLogger(__name__)

_mcp = FastMCP("WorkflowAI 🚀", tool_serializer=tool_serializer)  # pyright: ignore [reportUnknownVariableType]


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
    To select a model for a WorkflowAI agent or explore available models.
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
To list all WorkflowAI agents along with their basic statistics (run counts and costs).
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
    To retrieve detailed information about a specific WorkflowAI agent, including full input/output schemas, versions, name, description, and statistics.
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
    To investigate a specific run of a WorkflowAI agent for debugging, improvement, or troubleshooting. This is particularly useful for:
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
    - agent_input: Input data if any that was provided to the agent (only when using input variables)
    - messages: The exchanged messages, including the returned assistant message

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
    return await mcp_wrap(service.fetch_run_details(agent_id, run_id, run_url))


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
    To retrieve version details of a WorkflowAI agent or compare specific agent versions.

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
    To search agent runs based on various criteria including metadata values, run properties (status, time, cost, latency), model parameters, input/output content, and reviews.
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
    - "version": Version ID (e.g., "2.1") or deployment environment (e.g., "dev", "staging", "production") (operators: is, is not | string values)
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

    service = await get_mcp_service()

    task_tuple = await get_task_tuple_from_task_id(service.storage, agent_id)

    return await service.search_runs(
        task_tuple=task_tuple,
        field_queries=field_queries,
        limit=limit,
        offset=offset,
        page=page,
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
) -> MCPToolReturn[DeployAgentResponse]:
    """<when_to_use>
    To deploy a specific version of a WorkflowAI agent to an environment (dev, staging, or production).

    The version ID can be obtained by:
    1. Requesting the desired version to deploy
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

    return await mcp_wrap(
        service.deploy_agent_version(
            task_tuple=task_tuple,
            version_id=version_id,
            environment=environment,
            deployed_by=user_identifier,
        ),
        message=lambda x: f"Successfully deployed version {x.version_id} to {x.environment} environment",
    )


def _get_user_agent_from_request() -> str | None:
    request = get_http_request()
    return request.headers.get("user-agent")


@_mcp.tool()
async def send_feedback(
    feedback: str = Field(description="Feedback about the MCP client's experience using the MCP server"),
    context: str | None = Field(
        default=None,
        description="Optional context about the MCP operations that generated this feedback",
    ),
) -> MCPToolReturn[EmptyModel]:
    """<when_to_use>
    When an MCP client wants to provide feedback about its experience using the MCP server.
    This tool is designed for automated feedback collection from MCP clients after they complete operations,
    not for end-user feedback. The feedback helps improve MCP server functionality and user experience.

    You can use this tool when you are running into issues with achieving your goal, or when you are not sure how to use the MCP server. Use this tool between your other tool calls.
    </when_to_use>
    <returns>
    Returns acknowledgment that the feedback was received and sent for processing.
    The actual analysis is handled asynchronously by the feedback processing agent.
    </returns>"""
    service = await get_mcp_service()
    return await service.send_feedback(feedback=feedback, context=context, user_agent=_get_user_agent_from_request())


class CreateApiKeyResponse(BaseModel):
    api_key: str


@_mcp.tool()
async def create_api_key() -> MCPToolReturn[CreateApiKeyResponse]:
    """<when_to_use>
    To retrieve the API key for WorkflowAI. This is a temporary tool that returns the API key that was used to authenticate the current request.
    </when_to_use>
    <returns>
    Returns the API key that was used to authenticate the current MCP request.
    </returns>"""
    request = get_http_request()

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return MCPToolReturn(
            success=False,
            error="No Authorization header found or invalid format",
        )

    # Extract the API key from "Bearer <key>"
    api_key = auth_header.split(" ")[1]

    return MCPToolReturn(
        success=True,
        data=CreateApiKeyResponse(api_key=api_key),
        message="API key retrieved successfully",
    )


class HostedToolItem(BaseModel):
    """A tool hosted by WorkflowAI.
    To use a WorkflowAI hosted tool:
    - either refer to the tool name (e.g., '@search-google') in the first system message of
    the completion request
    - pass a tool with a corresponding name and no arguments in the `tools` argument of the completion request
    """

    name: str = Field(description="The tool handle/name (e.g., '@search-google')")
    description: str = Field(description="Description of what the tool does")

    @classmethod
    def from_tool(cls, tool: Tool):
        return cls(name=tool.name, description=tool.description or "")


@_mcp.tool()
async def list_hosted_tools() -> PaginatedMCPToolReturn[None, HostedToolItem]:
    """
    Read the documentation about hosted tools using the `search_documentation` tool.

    <when_to_use>
    To view all available hosted tools in WorkflowAI, including web search, browser tools, and other built-in capabilities.
    </when_to_use>

    <returns>
    Returns a list of all hosted tools available in WorkflowAI, including their names, descriptions.
    </returns>"""

    return PaginatedMCPToolReturn(
        success=True,
        items=[HostedToolItem.from_tool(tool) for tool in ToolsService.hosted_tools()],
    )


def _get_description_search_documentation_tool() -> str:
    """Generate dynamic description for search_documentation tool."""
    documentation_service = DocumentationService()

    available_pages = documentation_service.get_available_pages_descriptions()

    return f"""Search WorkflowAI documentation OR fetch a specific documentation page.

     <how_to_use>
     Enable MCP clients to explore WorkflowAI documentation through a dual-mode search tool:
     1. Search mode ('query' parameter): Search across all documentation to find relevant documentation sections. Use search mode when you need to find information but don't know which specific page contains it.
     2. Direct navigation mode ('page' parameter): Fetch the complete content of a specific documentation page (see <available_pages> below for available pages). Use direct navigation mode when you want to read the full content of a specific page.

    We recommend combining search and direct navigation, and making multiple searches and direct navigations to get the most relevant knowledge.
    </how_to_use>

     <available_pages>
     The following documentation pages are available for direct access:

     {available_pages}
     </available_pages>

     <returns>
     - If using query: Returns a list of SearchResult objects with relevant documentation sections and source page references that you can use to navigate to the relevant page.
     - If using page: Returns the complete content of the specified documentation page as a string
     - Error message if both or neither parameters are provided, or if the requested page is not found
     </returns>"""


# TODO: generate the tool description dynamically
@_mcp.tool(description=_get_description_search_documentation_tool())
async def search_documentation(
    query: str | None = Field(
        default=None,
        description="Search across all WorkflowAI documentation. Use query when you need to find specific information across multiple pages or you don't know which specific page contains the information you need.",
    ),
    page: str | None = Field(
        default=None,
        description="Use page when you know which specific page contains the information you need.",
    ),
) -> MCPToolReturn[SearchResponse]:
    service = await get_mcp_service()
    try:
        return await service.search_documentation(query=query, page=page)
    except MCPError as e:
        return MCPToolReturn(
            success=False,
            error=str(e),
        )


@_mcp.tool()
async def create_completion(
    # TODO: we should not need the agent id here
    agent_id: str = Field(
        description="The id of the user's agent. Example: 'agent_id': 'email-filtering-agent' in metadata, or 'email-filtering-agent' in 'model=email-filtering-agent/gpt-4o-latest'.",
    ),
    # TODO: we should likely split the completion request object
    request: OpenAIProxyChatCompletionRequest = Field(
        description="A partial completion request. The model is always required. If original_run_id is not provided, messages is required",
    ),
    original_run_id: str | None = Field(
        default=None,
        description="A run ID to repeat. Parameters provided in the request will override the "
        "parameters in the original completion request",
    ),
) -> MCPToolReturn[OpenAIProxyChatCompletionResponse]:
    """Create a completion for an agent.

    <when_to_use>
    Use create_completion to:
    - Test or compare different AI models without local setup
    - Create a completion for a WorkflowAI agent (new or existing)
    - Quickly prototype prompts, structured outputs, or templates
    - Debug agent behavior by testing specific inputs
    - Compare model performance (speed, cost, quality)
    - Retry an existing run with different parameters (requires 'original_run_id' to be provided)

    Supports all OpenAI API features including structured outputs (Pydantic models),
    prompt templates with Jinja2, input variables, and tool calling.

    When retrying a run, the model must be provided in the request. All other parameters are optional. The request
    parameter is identical to the OpenAI completion request.
    </when_to_use>

    <returns>
    Returns a completion response from the agent. The object is identical to the OpenAI completion response, including:
    - The AI model's response (text or structured output)
    - Usage statistics (tokens, cost, duration)
    - Run metadata (run ID, URL, feedback token)
    - Model information (provider, actual model used)
    </returns>"""

    start_time = time.time()

    service = await get_mcp_service()
    return await mcp_wrap(service.create_completion(agent_id, original_run_id, request, start_time=start_time))


def mcp_http_app():
    custom_middleware = [
        Middleware(MCPObservabilityMiddleware),
    ]
    return _mcp.http_app(path="/", stateless_http=True, middleware=custom_middleware)
