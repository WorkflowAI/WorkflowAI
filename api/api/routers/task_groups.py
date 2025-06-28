import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.dependencies.group import TaskGroupDep
from api.dependencies.path_params import AgentID, GroupID, TaskSchemaID
from api.dependencies.security import UserDep, UserOrganizationDep
from api.dependencies.services import GroupServiceDep, ModelsServiceDep
from api.dependencies.storage import StorageDep, TaskGroupStorageDep
from api.dependencies.task_info import TaskTupleDep
from api.errors import prettify_errors
from api.tags import RouteTags
from core.domain.models import Model, Provider
from core.domain.page import Page
from core.domain.task_group import TaskGroup, TaskGroupQuery, TaskGroupWithCost
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_group_update import TaskGroupUpdate
from core.domain.users import UserIdentifier
from core.domain.version_reference import VersionReference
from core.storage import ObjectNotFoundException
from core.utils.tags import compute_tags

router = APIRouter(prefix="/agents/{agent_id}/schemas/{task_schema_id}/groups")

_logger = logging.getLogger(__name__)


@router.get("", description="List all groups for an agent schema.", response_model_exclude_none=True)
async def list_groups(
    task_id: TaskTupleDep,
    task_schema_id: TaskSchemaID,
    storage: StorageDep,
    models_service: ModelsServiceDep,
) -> Page[TaskGroupWithCost]:
    query = TaskGroupQuery(task_id=task_id[0], task_schema_id=task_schema_id)

    # Fetch all groups for the given task and schema
    groups = [group async for group in storage.task_groups.list_task_groups(query)]

    # Extract model and provider information from groups
    models_providers: set[tuple[Model, Provider]] = set()
    for group in groups:
        if group.properties.model and group.properties.provider:
            try:
                model = Model(group.properties.model)
                provider = Provider(group.properties.provider)
                models_providers.add((model, provider))
            except ValueError:
                _logger.warning(
                    "Invalid model or provider in list groups",
                    extra={"model": group.properties.model, "provider": group.properties.provider},
                )
                continue

    # Get cost estimates for all model-provider combinations
    cost_estimates = await models_service.get_cost_estimates(
        task_id=task_id,
        task_schema_id=task_schema_id,
        models_providers=models_providers,
    )

    def _build_task_group_with_cost(group: TaskGroup) -> TaskGroupWithCost:
        try:
            model = Model(group.properties.model)
            provider = Provider(group.properties.provider)
        except ValueError:
            return TaskGroupWithCost(**group.model_dump())

        return TaskGroupWithCost(
            cost_estimate_usd=cost_estimates.get((model, provider)),
            **group.model_dump(),
        )

    # Create TaskGroupWithCost objects, including cost estimates where available
    task_groups_with_cost = [_build_task_group_with_cost(group) for group in groups]

    # Return a Page object containing the TaskGroupWithCost items
    return Page(items=task_groups_with_cost, count=len(task_groups_with_cost))


class CreateTaskGroupRequest(BaseModel):
    id: Optional[str] = Field(
        default=None,
        description="The id of the group. If not provided a uuid will be generated.",
    )
    properties: TaskGroupProperties = Field(..., description="The properties used for executing runs.")
    tags: Optional[list[str]] = Field(
        default=None,
        description="A list of tags associated with the group. If not provided, tags are computed from the properties "
        "by creating strings from each key value pair <key>=<value>.",
    )

    use_external_runner: bool = Field(
        default=False,
        description="Set to true to store the group as is, without any runner validation.\n"
        "Note that it means that the group will not be usable as is by internal runners.",
    )


@router.post("", description="Create an agent group for the agent", response_model_exclude_none=True)
async def create_group(
    agent_id: AgentID,
    task_schema_id: TaskSchemaID,
    request: CreateTaskGroupRequest,
    groups_service: GroupServiceDep,
    storage: StorageDep,
    user: UserDep,
    user_org: UserOrganizationDep,
) -> TaskGroup:
    if request.use_external_runner:
        try:
            await storage.task_variant_latest_by_schema_id(agent_id, task_schema_id)
        except ObjectNotFoundException:
            raise HTTPException(404, detail="Task not found")

        tags = compute_tags(request.properties.model_dump(exclude_none=True)) if request.tags is None else request.tags
        properties = request.properties
    else:
        version_ref = VersionReference(properties=request.properties)
        with prettify_errors(user_org, agent_id, task_schema_id, version_ref):
            runner, _ = await groups_service.sanitize_groups_for_internal_runner(
                task_id=agent_id,
                task_schema_id=task_schema_id,
                reference=version_ref,
                detect_chain_of_thought=True,
                # detect_structured_generation=True,
            )
        properties = runner.properties
        tags = runner.group_tags() if request.tags is None else request.tags

    return await storage.get_or_create_task_group(
        agent_id,
        task_schema_id,
        properties,
        tags,
        is_external=request.use_external_runner,
        id=request.id,
        user=UserIdentifier(user_email=user.sub, user_id=user.user_id) if user else None,
    )


@router.get(
    "/{group_id}",
    description="Retrieve an agent group",
    tags=[RouteTags.AGENT_GROUPS],
    response_model_exclude_none=True,
)
async def group_by_id(group: TaskGroupDep) -> TaskGroup:
    return group


@router.patch("/{group_id}", description="Update an agent group", tags=[RouteTags.AGENT_GROUPS])
async def patch_group_by_id(
    agent_id: AgentID,
    task_schema_id: TaskSchemaID,
    group_id: GroupID,
    request: TaskGroupUpdate,
    task_group_storage: TaskGroupStorageDep,
    user: UserDep,
) -> TaskGroup:
    # Endpoint: PATCH /tasks/{agent_id}/schemas/{task_schema_id}/groups/{group_id}
    return await task_group_storage.update_task_group(
        task_id=agent_id,
        task_schema_id=task_schema_id,
        iteration=group_id,
        update=request,
        user=UserIdentifier(user_email=user.sub, user_id=user.user_id) if user else None,
    )
