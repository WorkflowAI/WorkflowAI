import logging

from api.jobs.common import (
    InternalTasksServiceDep,
    StorageDep,
    UserPropertiesDep,
    VersionsServiceDep,
)
from api.jobs.utils.jobs_utils import get_task_str_for_slack
from api.services.internal_tasks.moderation_service import ModerationService
from api.services.slack_notifications import get_user_and_org_str
from core.domain.events import TaskGroupCreated

from ..broker import broker

logger = logging.getLogger(__name__)


@broker.task(retry_on_error=True)
async def run_task_version_moderation(
    event: TaskGroupCreated,
    storage: StorageDep,
    internal_tasks: InternalTasksServiceDep,
):
    if not ModerationService.is_moderation_activated():
        return

    group = await storage.task_groups.get_task_group_by_id(
        task_id=event.task_id,
        id=event.id,
    )

    variant_id = group.properties.task_variant_id
    if not variant_id:
        logger.warning(
            "Task variant not found",
            extra={"agent_id": event.task_id, "group_id": event.id},
        )
        return

    task_variant = await storage.task_version_resource_by_id(
        task_id=event.task_id,
        version_id=variant_id,
    )

    await internal_tasks.moderation.run_task_version_moderation_process(
        user_and_org_str=get_user_and_org_str(event=event),
        tenant=event.tenant,
        task_id=event.task_id,
        task_str=get_task_str_for_slack(event=event, task_id=event.task_id, task_schema_id=event.task_schema_id),
        iteration=group.iteration,
        task_name=task_variant.name,
        instructions=group.properties.instructions if group.properties.instructions else "",
        input_schema=task_variant.input_schema.json_schema,
        output_schema=task_variant.output_schema.json_schema,
        chat_messages=task_variant.creation_chat_messages,
    )


@broker.task(retry_on_error=True)
async def autosave_version(
    event: TaskGroupCreated,
    versions_service: VersionsServiceDep,
    user_properties: UserPropertiesDep,
):
    if event.disable_autosave:
        return

    await versions_service.autosave_version(
        task_id=event.task_id,
        grp_id=event.id,
        source=user_properties.client_source if user_properties else None,
    )


JOBS = [run_task_version_moderation, autosave_version]
