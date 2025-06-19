"""Sort field validation utilities for runtime validation of sort parameters."""

from typing import get_args

from api.routers.mcp._mcp_models import AgentSortField, ModelSortField, SortOrder


class SortValidationError(ValueError):
    """Base exception for sort validation errors."""

    pass


class InvalidSortFieldError(SortValidationError):
    """Raised when an invalid sort field is provided for a specific entity type."""

    def __init__(self, entity_type: str, field: str, valid_fields: list[str]):
        self.entity_type = entity_type
        self.field = field
        self.valid_fields = valid_fields
        super().__init__(
            f"Invalid sort field '{field}' for {entity_type}. Valid fields are: {', '.join(valid_fields)}",
        )


class InvalidSortOrderError(SortValidationError):
    """Raised when an invalid sort order is provided."""

    def __init__(self, order: str, valid_orders: list[str]):
        self.order = order
        self.valid_orders = valid_orders
        super().__init__(
            f"Invalid sort order '{order}'. Valid orders are: {', '.join(valid_orders)}",
        )


def get_valid_agent_sort_fields() -> list[str]:
    """Get list of valid agent sort fields from the type annotation."""
    return list(get_args(AgentSortField))


def get_valid_model_sort_fields() -> list[str]:
    """Get list of valid model sort fields from the type annotation."""
    return list(get_args(ModelSortField))


def get_valid_sort_orders() -> list[str]:
    """Get list of valid sort orders from the type annotation."""
    return list(get_args(SortOrder))


def validate_agent_sort_field(sort_by: str) -> None:
    """Validate that a sort field is valid for agents.

    Args:
        sort_by: The sort field to validate

    Raises:
        InvalidSortFieldError: If the sort field is not valid for agents
    """
    valid_fields = get_valid_agent_sort_fields()
    if sort_by not in valid_fields:
        raise InvalidSortFieldError("agent", sort_by, valid_fields)


def validate_model_sort_field(sort_by: str) -> None:
    """Validate that a sort field is valid for models.

    Args:
        sort_by: The sort field to validate

    Raises:
        InvalidSortFieldError: If the sort field is not valid for models
    """
    valid_fields = get_valid_model_sort_fields()
    if sort_by not in valid_fields:
        raise InvalidSortFieldError("model", sort_by, valid_fields)


def validate_sort_order(order: str) -> None:
    """Validate that a sort order is valid.

    Args:
        order: The sort order to validate

    Raises:
        InvalidSortOrderError: If the sort order is not valid
    """
    valid_orders = get_valid_sort_orders()
    if order not in valid_orders:
        raise InvalidSortOrderError(order, valid_orders)


def validate_agent_sort_params(sort_by: str, order: str) -> None:
    """Validate both sort field and order for agents.

    Args:
        sort_by: The sort field to validate
        order: The sort order to validate

    Raises:
        InvalidSortFieldError: If the sort field is not valid for agents
        InvalidSortOrderError: If the sort order is not valid
    """
    validate_agent_sort_field(sort_by)
    validate_sort_order(order)


def validate_model_sort_params(sort_by: str, order: str) -> None:
    """Validate both sort field and order for models.

    Args:
        sort_by: The sort field to validate
        order: The sort order to validate

    Raises:
        InvalidSortFieldError: If the sort field is not valid for models
        InvalidSortOrderError: If the sort order is not valid
    """
    validate_model_sort_field(sort_by)
    validate_sort_order(order)
