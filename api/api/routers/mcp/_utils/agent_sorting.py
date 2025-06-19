"""Agent sorting utilities for MCP service."""

from api.routers.mcp._mcp_models import AgentResponse, AgentSortField, SortOrder
from api.routers.mcp._utils.sort_validation import validate_agent_sort_params


def sort_agents(
    agents: list[AgentResponse],
    sort_by: AgentSortField,
    order: SortOrder,
) -> list[AgentResponse]:
    """Sort agents based on the specified field and order with stable secondary sorting by agent_id.

    Args:
        agents: List of agent responses to sort
        sort_by: Field to sort by
            - "last_active_at": Sort by maximum last_active_at across all schemas
            - "total_cost_usd": Sort by total_cost_usd
            - "run_count": Sort by run_count
        order: Sort direction
            - "asc": Ascending order (lowest to highest)
            - "desc": Descending order (highest to lowest)

    Returns:
        Sorted list of agents (modifies in place and returns the list)

    Raises:
        InvalidSortFieldError: If the sort field is not valid for agents
        InvalidSortOrderError: If the sort order is not valid
    """
    # Runtime validation of sort parameters
    validate_agent_sort_params(sort_by, order)

    reverse_sort = order == "desc"

    if sort_by == "last_active_at":

        def get_max_last_active_at(agent: AgentResponse) -> tuple[str, str]:
            """Get the maximum last_active_at across all schemas, handling None values.
            Returns a tuple of (max_last_active_at, agent_id) for stable sorting."""
            active_dates = [schema.last_active_at for schema in agent.schemas if schema.last_active_at is not None]
            if not active_dates:
                # Use a very old date for agents with no active dates
                # Using "0000" as a prefix ensures these sort appropriately relative to real dates
                max_date = "0000-00-00T00:00:00"
            else:
                max_date = max(active_dates)

            # Return tuple with agent_id as secondary sort key for stable ordering
            return (max_date, agent.agent_id)

        agents.sort(key=get_max_last_active_at, reverse=reverse_sort)
    elif sort_by == "total_cost_usd":
        agents.sort(key=lambda x: (x.total_cost_usd, x.agent_id), reverse=reverse_sort)
    elif sort_by == "run_count":
        agents.sort(key=lambda x: (x.run_count, x.agent_id), reverse=reverse_sort)

    return agents
