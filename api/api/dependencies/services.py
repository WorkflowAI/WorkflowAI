from collections.abc import Callable
from typing import Annotated

from fastapi import Depends

from api.dependencies.analytics import (
    AnalyticsOrganizationPropertiesDep,
    AnalyticsTaskPropertiesDep,
    UserPropertiesDep,
)
from api.dependencies.event_router import EventRouterDep
from api.dependencies.provider_factory import ProviderFactoryDep
from api.dependencies.security import RequiredUserDep, SystemStorageDep, TenantUIDDep, UserDep
from api.dependencies.storage import (
    OrganizationStorageDep,
    StorageDep,
    TranscriptionStorageDep,
)
from api.dependencies.task_info import TaskTupleDep
from api.services import file_storage
from api.services.analytics import AnalyticsService, analytics_service
from api.services.api_keys import APIKeyService
from api.services.feedback_svc import FeedbackService, FeedbackTokenGenerator
from api.services.groups import GroupService
from api.services.internal_tasks.agent_creation_service import AgentCreationService
from api.services.internal_tasks.integration_service import IntegrationService
from api.services.internal_tasks.internal_tasks_service import InternalTasksService
from api.services.internal_tasks.meta_agent_service import MetaAgentService
from api.services.models import ModelsService
from api.services.payments_service import PaymentService, PaymentSystemService
from api.services.reviews import ReviewsService
from api.services.run import RunService
from api.services.runs.runs_service import RunsService
from api.services.runs_search import RunsSearchService
from api.services.task_deployments import TaskDeploymentsService
from api.services.tools_service import ToolsService
from api.services.transcriptions import TranscriptionService
from api.services.versions import VersionsService
from core.domain.users import UserIdentifier
from core.services.emails import shared_email_service
from core.services.emails.email_service import EmailService
from core.services.users import shared_user_service
from core.services.users.user_service import UserService
from core.storage.file_storage import FileStorage


async def analytics_service_dependency(
    organization_properties: AnalyticsOrganizationPropertiesDep,
    user_properties: UserPropertiesDep,
    task_properties: AnalyticsTaskPropertiesDep,
) -> AnalyticsService:
    return analytics_service(
        user_properties=user_properties,
        organization_properties=organization_properties,
        task_properties=task_properties,
    )


AnalyticsServiceDep = Annotated[AnalyticsService, Depends(analytics_service_dependency)]


def file_storage_dependency() -> FileStorage:
    return file_storage.shared_file_storage


FileStorageDep = Annotated[FileStorage, Depends(file_storage_dependency)]


def group_service(
    storage: StorageDep,
    event_router: EventRouterDep,
    analytics_service: AnalyticsServiceDep,
    user: UserDep,
) -> GroupService:
    return GroupService(
        storage=storage,
        event_router=event_router,
        analytics_service=analytics_service,
        user=UserIdentifier(
            user_id=user.user_id if user else None,
            user_email=user.sub if user else None,
        ),
    )


GroupServiceDep = Annotated[GroupService, Depends(group_service)]


def run_service(
    storage: StorageDep,
    event_router: EventRouterDep,
    analytics_service: AnalyticsServiceDep,
    group_service: GroupServiceDep,
    user: UserDep,
) -> RunService:
    return RunService(
        storage=storage,
        event_router=event_router,
        analytics_service=analytics_service,
        group_service=group_service,
        user=UserIdentifier(
            user_id=user.user_id if user else None,
            user_email=user.sub if user else None,
        ),
    )


RunServiceDep = Annotated[RunService, Depends(run_service)]


def internal_tasks(
    event_router: EventRouterDep,
    storage: StorageDep,
) -> InternalTasksService:
    return InternalTasksService(
        storage=storage,
        event_router=event_router,
    )


InternalTasksServiceDep = Annotated[InternalTasksService, Depends(internal_tasks)]


def agent_creation_service(
    storage: StorageDep,
    event_router: EventRouterDep,
) -> AgentCreationService:
    return AgentCreationService(storage=storage, event_router=event_router)


AgentCreationServiceDep = Annotated[AgentCreationService, Depends(agent_creation_service)]


def runs_service(
    storage: StorageDep,
    provider_factory: ProviderFactoryDep,
    event_router: EventRouterDep,
    analytics_service: AnalyticsServiceDep,
    file_storage: FileStorageDep,
) -> RunsService:
    return RunsService(
        storage=storage,
        provider_factory=provider_factory,
        event_router=event_router,
        analytics_service=analytics_service,
        file_storage=file_storage,
    )


RunsServiceDep = Annotated[RunsService, Depends(runs_service)]


def transcription_service(
    transcription_storage: TranscriptionStorageDep,
) -> TranscriptionService:
    return TranscriptionService(storage=transcription_storage)


TranscriptionServiceDep = Annotated[TranscriptionService, Depends(transcription_service)]


def api_key_service(
    organization_storage: OrganizationStorageDep,
) -> APIKeyService:
    return APIKeyService(storage=organization_storage)


APIKeyServiceDep = Annotated[APIKeyService, Depends(api_key_service)]


def reviews_service(
    backend_storage: StorageDep,
    internal_tasks: InternalTasksServiceDep,
    event_router: EventRouterDep,
) -> ReviewsService:
    return ReviewsService(
        backend_storage=backend_storage,
        internal_tasks=internal_tasks,
        event_router=event_router,
    )


ReviewsServiceDep = Annotated[ReviewsService, Depends(reviews_service)]


def task_deployments_service(
    storage: StorageDep,
    run_service: RunServiceDep,
    group_service: GroupServiceDep,
    analytics_service: AnalyticsServiceDep,
) -> TaskDeploymentsService:
    return TaskDeploymentsService(
        storage=storage,
        run_service=run_service,
        group_service=group_service,
        analytics_service=analytics_service,
    )


TaskDeploymentsServiceDep = Annotated[TaskDeploymentsService, Depends(task_deployments_service)]


def models_service(storage: StorageDep):
    return ModelsService(storage=storage)


ModelsServiceDep = Annotated[ModelsService, Depends(models_service)]


def versions_service(storage: StorageDep, event_router: EventRouterDep):
    return VersionsService(storage=storage, event_router=event_router)


VersionsServiceDep = Annotated[VersionsService, Depends(versions_service)]


def payment_service(storage: StorageDep) -> PaymentService:
    return PaymentService(org_storage=storage.organizations)


PaymentServiceDep = Annotated[PaymentService, Depends(payment_service)]


def runs_search_service(
    storage: StorageDep,
) -> RunsSearchService:
    return RunsSearchService(storage=storage)


RunsSearchServiceDep = Annotated[RunsSearchService, Depends(runs_search_service)]

_feedback_token_generator = FeedbackTokenGenerator.default_generator()


def feedback_token_generator() -> FeedbackTokenGenerator:
    return _feedback_token_generator


FeedbackTokenGeneratorDep = Annotated[FeedbackTokenGenerator, Depends(feedback_token_generator)]


def run_feedback_generator(
    feedback_generator: FeedbackTokenGeneratorDep,
    task_tuple: TaskTupleDep,
    tenant_uid: TenantUIDDep,
) -> Callable[[str], str]:
    """Returns a function that generates a feedback token for a given run based on the route dependencies"""

    def generate_token(run_id: str) -> str:
        return feedback_generator.generate_token(tenant_uid, task_tuple[1], run_id)

    return generate_token


RunFeedbackGeneratorDep = Annotated[Callable[[str], str], Depends(run_feedback_generator)]


def user_service_dep() -> UserService:
    return shared_user_service.shared_user_service


UserServiceDep = Annotated[UserService, Depends(user_service_dep)]


def email_service_dep(storage: SystemStorageDep, user_service: UserServiceDep) -> EmailService:
    return shared_email_service.email_service_builder(storage.organizations, user_service)


EmailServiceDep = Annotated[EmailService, Depends(email_service_dep)]


def payment_system_service(
    storage: SystemStorageDep,
    email_service: EmailServiceDep,
) -> PaymentSystemService:
    return PaymentSystemService(storage.organizations, email_service)


PaymentSystemServiceDep = Annotated[PaymentSystemService, Depends(payment_system_service)]


def tools_service(storage: StorageDep) -> ToolsService:
    return ToolsService(storage)


ToolsServiceDep = Annotated[ToolsService, Depends(tools_service)]


def integration_service_dependency(
    storage: StorageDep,
    event_router: EventRouterDep,
    runs_service: RunsServiceDep,
    api_keys_service: APIKeyServiceDep,
    user: RequiredUserDep,
):
    return IntegrationService(
        storage=storage,
        event_router=event_router,
        runs_service=runs_service,
        api_keys_service=api_keys_service,
        user=user,
    )


IntegrationAgentServiceDep = Annotated[IntegrationService, Depends(integration_service_dependency)]


def feedback_service_dependency(storage: StorageDep):
    return FeedbackService(storage.feedback)


FeedbackServiceDep = Annotated[FeedbackService, Depends(feedback_service_dependency)]


def meta_agent_service_dependency(
    storage: StorageDep,
    event_router: EventRouterDep,
    runs_service: RunsServiceDep,
    models_service: ModelsServiceDep,
    feedback_service: FeedbackServiceDep,
    versions_service: VersionsServiceDep,
    reviews_service: ReviewsServiceDep,
):
    return MetaAgentService(
        storage=storage,
        event_router=event_router,
        runs_service=runs_service,
        models_service=models_service,
        feedback_service=feedback_service,
        versions_service=versions_service,
        reviews_service=reviews_service,
    )


MetaAgentServiceDep = Annotated[MetaAgentService, Depends(meta_agent_service_dependency)]
