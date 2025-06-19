"""Agent sorting utilities for MCP service."""

from api.routers.mcp._mcp_models import AgentResponse, AgentSortField, SortOrder


class InvalidSortFieldError(ValueError):
    """Raised when an invalid sort field is provided for agent sorting."""

    def __init__(self, sort_by: str, valid_fields: list[str]):
        self.sort_by = sort_by
        self.valid_fields = valid_fields
        super().__init__(
            f"Invalid sort field '{sort_by}' for agents. Valid fields are: {', '.join(valid_fields)}",
        )


def validate_agent_sort_field(sort_by: str) -> None:
    """Validate that the sort field is valid for agent entities.

    Args:
        sort_by: The field name to validate

    Raises:
        InvalidSortFieldError: If the sort field is not valid for agents
    """
    valid_fields = ["last_active_at", "total_cost_usd", "run_count"]
    if sort_by not in valid_fields:
        raise InvalidSortFieldError(sort_by, valid_fields)


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
    """
    # Validate sort field at runtime
    validate_agent_sort_field(sort_by)

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
