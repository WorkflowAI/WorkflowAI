from fastmcp.server.dependencies import get_http_request
from starlette.exceptions import HTTPException

from api.routers.mcp._mcp_service import MCPService
from api.services import file_storage, storage
from api.services.analytics import analytics_service
from api.services.event_handler import system_event_router, tenant_event_router
from api.services.feedback_svc import FeedbackService
from api.services.groups import GroupService
from api.services.internal_tasks.ai_engineer_service import AIEngineerService
from api.services.internal_tasks.internal_tasks_service import InternalTasksService
from api.services.models import ModelsService
from api.services.providers_service import shared_provider_factory
from api.services.reviews import ReviewsService
from api.services.run import RunService
from api.services.runs.runs_service import RunsService
from api.services.security_service import SecurityService
from api.services.task_deployments import TaskDeploymentsService
from api.services.versions import VersionsService
from core.domain.analytics_events.analytics_events import OrganizationProperties, SourceType, UserProperties
from core.domain.users import UserIdentifier


async def get_mcp_service() -> MCPService:
    request = get_http_request()

    _system_storage = storage.system_storage(storage.shared_encryption())
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    security_service = SecurityService(
        _system_storage.organizations,
        system_event_router(),
        analytics_service(user_properties=None, organization_properties=None, task_properties=None),
    )
    tenant = await security_service.tenant_from_credentials(auth_header.split(" ")[1])
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    org_properties = OrganizationProperties.build(tenant)
    # TODO: user analytics
    user_properties: UserProperties | None = None
    event_router = tenant_event_router(tenant.tenant, tenant.uid, user_properties, org_properties, None)
    _storage = storage.storage_for_tenant(tenant.tenant, tenant.uid, event_router, storage.shared_encryption())
    analytics = analytics_service(
        user_properties=user_properties,
        organization_properties=org_properties,
        task_properties=None,
    )
    models_service = ModelsService(storage=_storage)
    runs_service = RunsService(
        storage=_storage,
        provider_factory=shared_provider_factory(),
        event_router=event_router,
        analytics_service=analytics,
        file_storage=file_storage.shared_file_storage,
    )
    feedback_service = FeedbackService(storage=_storage.feedback)
    versions_service = VersionsService(storage=_storage, event_router=event_router)
    internal_tasks = InternalTasksService(event_router=event_router, storage=_storage)
    reviews_service = ReviewsService(
        backend_storage=_storage,
        internal_tasks=internal_tasks,
        event_router=event_router,
    )

    # Create GroupService and RunService for TaskDeploymentsService
    user_identifier = UserIdentifier(user_id=None, user_email=None)  # System user for MCP operations
    group_service = GroupService(
        storage=_storage,
        event_router=event_router,
        analytics_service=analytics,
        user=user_identifier,
    )
    run_service = RunService(
        storage=_storage,
        event_router=event_router,
        analytics_service=analytics,
        group_service=group_service,
        user=user_identifier,
    )
    task_deployments_service = TaskDeploymentsService(
        storage=_storage,
        run_service=run_service,
        group_service=group_service,
        analytics_service=analytics,
    )

    ai_engineer_service = AIEngineerService(
        storage=_storage,
        event_router=event_router,
        runs_service=runs_service,
        models_service=models_service,
        feedback_service=feedback_service,
        versions_service=versions_service,
        reviews_service=reviews_service,
    )

    user_properties = UserProperties(
        user_id=None,
        client_source=SourceType.MCP,
        client_version=None,
        client_language=None,
    )

    organization_properties = OrganizationProperties.build(tenant)

    event_router = tenant_event_router(
        tenant=tenant.slug,
        tenant_uid=tenant.uid,
        user_properties=user_properties,
        organization_properties=organization_properties,
        task_properties=None,
    )

    return MCPService(
        storage=_storage,
        ai_engineer_service=ai_engineer_service,
        runs_service=runs_service,
        versions_service=versions_service,
        models_service=models_service,
        task_deployments_service=task_deployments_service,
        user_email=user_identifier.user_email,
        tenant=tenant,
        event_router=event_router,
        analytics_service=analytics,
    )
