import random
from datetime import datetime, timezone

from api.broker import broker
from api.jobs.common import (
    InternalTasksServiceDep,
    PaymentSystemServiceDep,
    ReviewsServiceDep,
    StorageDep,
)
from api.jobs.utils.jobs_utils import get_task_run_str
from api.services.slack_notifications import get_user_and_org_str
from core.domain.events import RunCreatedEvent
from core.domain.task_group_update import TaskGroupUpdate
from core.storage.models import TaskUpdate


def _is_run_external(event: RunCreatedEvent) -> bool:
    return event.run.author_tenant is not None and event.run.author_tenant != event.tenant


@broker.task(retry_on_error=False)
async def evaluate_run_review(event: RunCreatedEvent, reviews_service: ReviewsServiceDep):
    if _is_run_external(event):
        return

    await reviews_service.evaluate_runs_by_hash_if_needed(
        task_id=event.run.task_id,
        task_schema_id=event.run.task_schema_id,
        task_input_hash=event.run.task_input_hash,
        task_output_hash=event.run.task_output_hash,
        run_id=event.run.id,
        version_id=event.run.group.id,
        iteration=event.run.group.iteration,
        run_failed=event.run.status == "failure",
    )


@broker.task(retry_on_error=False)
async def decrement_credits(event: RunCreatedEvent, payment_service: PaymentSystemServiceDep):
    if cost := event.run.credits_used:
        await payment_service.decrement_credits(
            event.run.author_tenant or event.tenant,
            cost,
        )


@broker.task(retry_on_error=False)
async def increment_run_count(event: RunCreatedEvent, storage: StorageDep):
    await storage.task_groups.increment_run_count(
        event.run.task_id,
        event.run.task_schema_id,
        event.run.group.iteration,
        increment=1,
    )


@broker.task(retry_on_error=False)
async def update_task_group_last_active_at(event: RunCreatedEvent, storage: StorageDep):
    if not event.run.is_active:
        return

    await storage.task_groups.update_task_group(
        task_id=event.run.task_id,
        task_schema_id=event.run.task_schema_id,
        iteration=event.run.group.iteration,
        update=TaskGroupUpdate(last_active_at=datetime.now(timezone.utc)),
    )


@broker.task(retry_on_error=False)
async def update_task_schema_last_active_at(event: RunCreatedEvent, storage: StorageDep):
    if not event.run.is_active:
        return

    await storage.tasks.update_task(
        task_id=event.run.task_id,
        update=TaskUpdate(schema_last_active_at=(event.run.task_schema_id, datetime.now(timezone.utc))),
    )


def _should_run_task_run_moderation() -> bool:
    return random.random() < 0.01


@broker.task(retry_on_error=False)
async def run_task_run_moderation(
    event: RunCreatedEvent,
    internal_service: InternalTasksServiceDep,
):
    if not _should_run_task_run_moderation():
        return

    await internal_service.moderation.run_task_run_moderation_process(
        tenant=event.tenant,
        task_id=event.run.task_id,
        user_and_org_str=get_user_and_org_str(event),
        task_run_str=get_task_run_str(
            event=event,
            task_id=event.run.task_id,
            task_schema_id=event.run.task_schema_id,
            task_run_id=event.run.id,
        ),
        task_run_input=event.run.task_input,
    )


JOBS = [
    decrement_credits,
    increment_run_count,
    evaluate_run_review,
    update_task_group_last_active_at,
    update_task_schema_last_active_at,
    run_task_run_moderation,
]
