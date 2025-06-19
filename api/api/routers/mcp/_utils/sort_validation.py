"""Sort field validation utilities for MCP service."""

from typing import cast, get_args

from api.api.routers.mcp._mcp_models import AgentSortField, ModelSortField, SortOrder


class SortValidationError(Exception):
    """Exception raised for invalid sort parameters."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def validate_agent_sort_params(sort_by: str, order: str) -> tuple[AgentSortField, SortOrder]:
    """Validate agent sorting parameters.

    Args:
        sort_by: The field name to sort by
        order: The sort direction

    Returns:
        A tuple of validated (sort_by, order) parameters

    Raises:
        SortValidationError: If parameters are invalid
    """
    # Get valid values from type annotations
    valid_sort_fields = get_args(AgentSortField)
    valid_orders = get_args(SortOrder)

    # Validate sort_by field
    if sort_by not in valid_sort_fields:
        raise SortValidationError(
            f"Invalid sort field '{sort_by}' for agents. Valid options are: {', '.join(valid_sort_fields)}",
        )

    # Validate order
    if order not in valid_orders:
        raise SortValidationError(
            f"Invalid sort order '{order}'. Valid options are: {', '.join(valid_orders)}",
        )

    # Safe to cast after validation
    return cast(AgentSortField, sort_by), cast(SortOrder, order)


def validate_model_sort_params(sort_by: str, order: str) -> tuple[ModelSortField, SortOrder]:
    """Validate model sorting parameters.

    Args:
        sort_by: The field name to sort by
        order: The sort direction

    Returns:
        A tuple of validated (sort_by, order) parameters

    Raises:
        SortValidationError: If parameters are invalid
    """
    # Get valid values from type annotations
    valid_sort_fields = get_args(ModelSortField)
    valid_orders = get_args(SortOrder)

    # Validate sort_by field
    if sort_by not in valid_sort_fields:
        raise SortValidationError(
            f"Invalid sort field '{sort_by}' for models. Valid options are: {', '.join(valid_sort_fields)}",
        )

    # Validate order
    if order not in valid_orders:
        raise SortValidationError(
            f"Invalid sort order '{order}'. Valid options are: {', '.join(valid_orders)}",
        )

    # Safe to cast after validation
    return cast(ModelSortField, sort_by), cast(SortOrder, order)


def get_valid_agent_sort_fields() -> list[str]:
    """Get list of valid agent sort fields."""
    return list(get_args(AgentSortField))


def get_valid_model_sort_fields() -> list[str]:
    """Get list of valid model sort fields."""
    return list(get_args(ModelSortField))


def get_valid_sort_orders() -> list[str]:
    """Get list of valid sort orders."""
    return list(get_args(SortOrder))
