import asyncio
import logging
from datetime import datetime
from typing import Any, Concatenate, Coroutine, Generic, NamedTuple, Sequence, TypeVar

from taskiq import AsyncTaskiqDecoratedTask

from core.domain.analytics_events.analytics_events import OrganizationProperties, TaskProperties, UserProperties
from core.domain.events import (
    AgentInstructionsGeneratedEvent,
    AIReviewCompletedEvent,
    AIReviewerBuildStartedEvent,
    AIReviewerUpdatedEvent,
    AIReviewStartedEvent,
    Event,
    EventRouter,
    FeaturesByDomainGenerationStarted,
    FeedbackCreatedEvent,
    MetaAgentChatMessagesSent,
    ProxyAgentCreatedEvent,
    RecomputeReviewBenchmarkEvent,
    RunCreatedEvent,
    SendAnalyticsEvent,
    StoreTaskRunEvent,
    TaskChatStartedEvent,
    TaskGroupCreated,
    TaskGroupSaved,
    TaskSchemaCreatedEvent,
    TaskSchemaGeneratedEvent,
    TenantCreatedEvent,
    TenantMigratedEvent,
    TriggerRunEvaluationEvent,
    TriggerTaskRunEvent,
    UserReviewAddedEvent,
    WithDelay,
)

_logger = logging.getLogger(__name__)


T = TypeVar("T", bound=Event)


class _JobListing(NamedTuple, Generic[T]):
    event: type[T]
    jobs: Sequence[AsyncTaskiqDecoratedTask[Concatenate[T, ...], Coroutine[Any, Any, None]] | WithDelay[T]]  # Run ASAP


def _jobs():
    # Importing here to avoid circular dependency
    from api.jobs import (
        agent_created_via_proxy_jobs,
        ai_review_completed_jobs,
        ai_review_started_jobs,
        ai_reviewer_build_started_jobs,
        ai_reviewer_updated_jobs,
        analytics_jobs,
        chat_started_jobs,
        features_by_domain_generation_started_jobs,
        feedback_created_jobs,
        meta_agent_chat_messages_sent_jobs,
        recompute_review_benchmark_jobs,
        run_created_jobs,
        store_run_jobs,
        task_group_created_jobs,
        task_group_saved_jobs,
        task_instructions_generated_jobs,
        task_schema_created_jobs,
        task_schema_generated_jobs,
        tenant_created_jobs,
        tenant_migrated_jobs,
        trigger_run_evaluation_jobs,
        trigger_task_run_jobs,
        user_review_added_jobs,
    )

    # We use an array to have correct typing
    return [
        _JobListing(RunCreatedEvent, run_created_jobs.JOBS),
        _JobListing(
            TaskSchemaCreatedEvent,
            task_schema_created_jobs.JOBS,
        ),
        _JobListing(
            TriggerTaskRunEvent,
            [
                trigger_task_run_jobs.trigger_run,
            ],
        ),
        # TODO: remove once we no longer use the event (post 2025-06-03 release)
        _JobListing(SendAnalyticsEvent, analytics_jobs.jobs),
        _JobListing(TaskChatStartedEvent, chat_started_jobs.JOBS),
        _JobListing(TaskSchemaGeneratedEvent, task_schema_generated_jobs.JOBS),
        _JobListing(TaskGroupCreated, task_group_created_jobs.JOBS),
        _JobListing(StoreTaskRunEvent, store_run_jobs.JOBS),
        _JobListing(UserReviewAddedEvent, user_review_added_jobs.JOBS),
        _JobListing(AIReviewerUpdatedEvent, ai_reviewer_updated_jobs.JOBS),
        _JobListing(RecomputeReviewBenchmarkEvent, recompute_review_benchmark_jobs.JOBS),
        _JobListing(AIReviewStartedEvent, ai_review_started_jobs.JOBS),
        _JobListing(AIReviewCompletedEvent, ai_review_completed_jobs.JOBS),
        _JobListing(AIReviewerBuildStartedEvent, ai_reviewer_build_started_jobs.JOBS),
        _JobListing(TaskGroupSaved, task_group_saved_jobs.JOBS),
        _JobListing(TriggerRunEvaluationEvent, trigger_run_evaluation_jobs.JOBS),
        _JobListing(AgentInstructionsGeneratedEvent, task_instructions_generated_jobs.JOBS),
        _JobListing(MetaAgentChatMessagesSent, meta_agent_chat_messages_sent_jobs.JOBS),
        _JobListing(FeedbackCreatedEvent, feedback_created_jobs.JOBS),
        _JobListing(FeaturesByDomainGenerationStarted, features_by_domain_generation_started_jobs.JOBS),
        _JobListing(TenantCreatedEvent, tenant_created_jobs.JOBS),
        _JobListing(TenantMigratedEvent, tenant_migrated_jobs.JOBS),
        _JobListing(ProxyAgentCreatedEvent, agent_created_via_proxy_jobs.JOBS),
    ]


class _EventRouter:
    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[None]] = set()
        self._handlers: dict[type[Event], _JobListing[Event]] = {job.event: job for job in _jobs()}  # pyright: ignore [reportAttributeAccessIssue]

    @classmethod
    async def _send_job(
        cls,
        job: AsyncTaskiqDecoratedTask[[T], Coroutine[Any, Any, None]],
        event: T,
        retry_after: datetime | None = None,
    ):
        try:
            if retry_after:
                from api.broker import schedule_job

                await schedule_job(job, retry_after, event)
                return

            await job.kiq(event)
        except Exception as e:
            # We retry once, see https://github.com/redis/redis-py/issues/2491
            # We added the hiredis parser so this should not happen
            _logger.warning("Error sending job, retrying", exc_info=e)
            try:
                await job.kiq(event)
            except Exception:
                _logger.exception("Error sending job")

    def _schedule_task(
        self,
        job: AsyncTaskiqDecoratedTask[[Event], Coroutine[Any, Any, None]],
        event: Event,
        schedule_time: datetime | None,
    ):
        t = asyncio.create_task(self._send_job(job, event, schedule_time))
        self._tasks.add(t)
        t.add_done_callback(self._tasks.remove)

    def __call__(self, event: Event, retry_after: datetime | None = None) -> None:
        try:
            listing = self._handlers[type(event)]
            now = datetime.now()
            for job in listing.jobs:
                if isinstance(job, WithDelay):
                    self._schedule_task(job.job, event, now + job.delay)
                else:
                    self._schedule_task(job, event, retry_after)

        except KeyError as e:
            _logger.exception("Missing event handler", exc_info=e)
            return
        except Exception as e:
            # This one should never happen
            _logger.exception("Error handling event", exc_info=e)


_event_router = _EventRouter()


def system_event_router() -> EventRouter:
    return _event_router


class _TenantEventRouter:
    def __init__(
        self,
        tenant: str,
        tenant_uid: int,
        user_properties: UserProperties | None,
        organization_properties: OrganizationProperties | None,
        task_properties: TaskProperties | None,
    ) -> None:
        self.tenant = tenant
        self.tenant_uid = tenant_uid
        self.user_properties = user_properties
        self.organization_properties = organization_properties
        self.task_properties = task_properties

    def __call__(self, event: Event, retry_after: datetime | None = None) -> None:
        event.tenant = self.tenant
        event.tenant_uid = self.tenant_uid
        event.user_properties = self.user_properties
        event.organization_properties = self.organization_properties
        event.task_properties = self.task_properties
        _event_router(event, retry_after)


def tenant_event_router(
    tenant: str,
    tenant_uid: int,
    user_properties: UserProperties | None,
    organization_properties: OrganizationProperties | None,
    task_properties: TaskProperties | None,
) -> EventRouter:
    return _TenantEventRouter(tenant, tenant_uid, user_properties, organization_properties, task_properties)
