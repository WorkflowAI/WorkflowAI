"""Agent sorting utilities for MCP service."""

import datetime

from api.routers.mcp._mcp_models import AgentResponse, AgentSortField, SortOrder


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
    """
    reverse_sort = order == "desc"

    if sort_by == "last_active_at":

        def get_sort_key(agent: AgentResponse) -> tuple[float, str]:
            """Get the sort key for last_active_at sorting with stable ordering."""
            active_dates = [schema.last_active_at for schema in agent.schemas if schema.last_active_at is not None]
            if not active_dates:
                # Use a very old timestamp for agents with no active dates
                max_timestamp = 0.0
            else:
                max_date = max(active_dates)
                # Convert ISO string to timestamp for proper numerical sorting
                max_timestamp = datetime.datetime.fromisoformat(max_date.replace("Z", "+00:00")).timestamp()

            return (max_timestamp, agent.agent_id)

        agents.sort(key=get_sort_key, reverse=reverse_sort)
    elif sort_by == "total_cost_usd":
        agents.sort(key=lambda x: (x.total_cost_usd, x.agent_id), reverse=reverse_sort)
    elif sort_by == "run_count":
        agents.sort(key=lambda x: (x.run_count, x.agent_id), reverse=reverse_sort)

    return agents
