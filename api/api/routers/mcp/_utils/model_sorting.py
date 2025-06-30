"""Model sorting utilities for MCP service."""

import logging

from api.routers.mcp._mcp_models import ConciseLatestModelResponse, ConciseModelResponse, ModelSortField, SortOrder

logger = logging.getLogger(__name__)


def sort_models(
    models: list[ConciseModelResponse | ConciseLatestModelResponse],
    sort_by: ModelSortField,
    order: SortOrder,
) -> list[ConciseModelResponse | ConciseLatestModelResponse]:
    """Sort models based on the specified field and order with stable secondary sorting by model id.

    Args:
        models: List of model responses to sort
        sort_by: Field to sort by
            - "release_date": Sort by release_date
            - "quality_index": Sort by quality_index
            - "cost": Sort by combined input+output cost
        order: Sort direction
            - "asc": Ascending order (lowest to highest)
            - "desc": Descending order (highest to lowest)

    Returns:
        Sorted list of models (modifies in place and returns the list)
    """
    # Separate latest models from concrete models for sorting
    latest_models = [m for m in models if isinstance(m, ConciseLatestModelResponse)]
    concrete_models = [m for m in models if isinstance(m, ConciseModelResponse)]

    reverse_sort = order == "desc"

    if sort_by == "release_date":
        # Sort by release date, with model id as secondary key for stable ordering
        concrete_models.sort(key=lambda x: (x.release_date, x.id), reverse=reverse_sort)
    elif sort_by == "quality_index":
        # Sort by quality index, with model id as secondary key
        concrete_models.sort(key=lambda x: (x.quality_index, x.id), reverse=reverse_sort)
    elif sort_by == "cost":
        # Sort by combined cost, with model id as secondary key
        concrete_models.sort(
            key=lambda x: (x.cost_per_input_token_usd + x.cost_per_output_token_usd, x.id),
            reverse=reverse_sort,
        )

    # Sort latest models by their id for stable ordering
    latest_models.sort(key=lambda x: x.id)

    # Insert latest models just above the models they point to
    result: list[ConciseModelResponse | ConciseLatestModelResponse] = []
    concrete_models_set = {model.id for model in concrete_models}

    for concrete_model in concrete_models:
        # Find any latest models that point to this concrete model
        pointing_latest_models = [latest for latest in latest_models if latest.currently_points_to == concrete_model.id]

        # Add the latest models first (they appear just above the model they point to)
        result.extend(pointing_latest_models)
        # Then add the concrete model
        result.append(concrete_model)

    # Add any latest models that don't point to concrete models in our list (orphaned latest models)
    orphaned_latest_models = [
        latest for latest in latest_models if latest.currently_points_to not in concrete_models_set
    ]
    if len(orphaned_latest_models) > 0:
        logger.warning(
            "Found orphaned latest models",
            extra={"orphaned_latest_models": orphaned_latest_models},
        )
        result.extend(orphaned_latest_models)

    # Replace the original list contents
    models.clear()
    models.extend(result)

    return models
