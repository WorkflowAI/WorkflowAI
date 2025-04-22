import logging

from api.jobs.common import CustomerServiceDep, InternalTasksServiceDep, StorageDep
from api.jobs.utils.jobs_utils import get_task_str_for_slack
from api.services.internal_tasks.moderation_service import ModerationService
from api.services.slack_notifications import get_user_and_org_str
from core.domain.events import TaskSchemaCreatedEvent
from core.storage import ObjectNotFoundException

from ..broker import broker

logger = logging.getLogger(__name__)


@broker.task(retry_on_error=True, max_retries=1)
async def send_task_update_slack_notification(event: TaskSchemaCreatedEvent, customer_service: CustomerServiceDep):
    await customer_service.send_task_update(event=event)


@broker.task(retry_on_error=True)
async def add_credits_for_first_task(event: TaskSchemaCreatedEvent, storage: StorageDep):
    try:
        await storage.organizations.add_5_credits_for_first_task()
    except ObjectNotFoundException:
        logger.info("Organization not found, skipping credit addition")


@broker.task(retry_on_error=True)
async def run_task_schema_moderation(
    event: TaskSchemaCreatedEvent,
    storage: StorageDep,
    internal_service: InternalTasksServiceDep,
):
    if not ModerationService.is_moderation_activated():
        return

    task_variant = await storage.task_variants.get_latest_task_variant(
        task_id=event.task_id,
        schema_id=event.task_schema_id,
    )

    if not task_variant:
        logger.warning(
            "Task variant not found",
            extra={
                "task_id": event.task_id,
                "task_schema_id": event.task_schema_id,
            },
        )
        return

    await internal_service.moderation.run_task_version_moderation_process(
        tenant=event.tenant,
        task_id=event.task_id,
        chat_messages=task_variant.creation_chat_messages,
        user_and_org_str=get_user_and_org_str(event=event),
        task_str=get_task_str_for_slack(event=event, task_id=event.task_id, task_schema_id=event.task_schema_id),
        iteration=None,
        task_name=event.task_id,
        instructions=None,  # TODO: Instructions are not available at this point
        input_schema=task_variant.input_schema.json_schema,
        output_schema=task_variant.output_schema.json_schema,
    )


JOBS = [
    send_task_update_slack_notification,
    add_credits_for_first_task,
    run_task_schema_moderation,
]
