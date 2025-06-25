from fastapi import APIRouter, Depends, HTTPException

from api.dependencies.security import URLPublicOrganizationDep, key_ring_dependency, tenant_dependency
from api.routers import (
    clerk_webhooks,
    features,
    feedback_v1,
    helpscout_webhooks,
    integrations_router,
    slack_webhooks,
    stripe_webhooks,
)
from api.routers.agents import meta_agent, new_tool_agent
from api.routers.tools_v1 import tools_v1_router
from api.tags import RouteTags
from core.domain.tenant_data import PublicOrganizationData

main_router = APIRouter()
main_router.include_router(clerk_webhooks.router)
main_router.include_router(stripe_webhooks.router)
main_router.include_router(feedback_v1.feedback_router)
main_router.include_router(slack_webhooks.router)
main_router.include_router(helpscout_webhooks.router)
main_router.include_router(tools_v1_router.router)


# Route for public organization data
@main_router.get("/organizations/{tenant}", description="Get the public organization settings", include_in_schema=False)
async def get_public_organization_settings(
    public_org: URLPublicOrganizationDep,
) -> PublicOrganizationData:
    if not public_org:
        raise HTTPException(404, "Not found")
    return public_org


# Non v1 routes
def _tenant_router():
    from api.routers import (
        api_keys,
        examples_by_id,
        organizations,
        payments,
        reviews,
        runs_by_id,
        stats,
        task_groups,
        task_schemas,
        tasks,
        tools_router,
        transcriptions,
        upload,
    )

    tenant_router = APIRouter(prefix="/{tenant}")
    tenant_router.include_router(stats.router, tags=[RouteTags.MONITORING])
    tenant_router.include_router(api_keys.router, tags=[RouteTags.API_KEYS])
    tenant_router.include_router(task_groups.router, tags=[RouteTags.AGENT_GROUPS])
    tenant_router.include_router(task_schemas.router, tags=[RouteTags.AGENT_SCHEMAS])
    tenant_router.include_router(tasks.router, tags=[RouteTags.AGENTS])
    # TODO: remove once the client has been updated
    tenant_router.include_router(organizations.router, deprecated=True, include_in_schema=False)
    tenant_router.include_router(transcriptions.router, tags=[RouteTags.TRANSCRIPTIONS])
    tenant_router.include_router(examples_by_id.router, tags=[RouteTags.EXAMPLES])
    tenant_router.include_router(runs_by_id.router, tags=[RouteTags.RUNS])
    tenant_router.include_router(upload.router, tags=[RouteTags.UPLOAD])
    tenant_router.include_router(reviews.router, tags=[RouteTags.REVIEWS])
    # TODO: remove once the client has been updated
    tenant_router.include_router(payments.router, deprecated=True, include_in_schema=False)
    tenant_router.include_router(meta_agent.router, tags=[RouteTags.PROMPT_ENGINEER_AGENT])
    tenant_router.include_router(new_tool_agent.router, tags=[RouteTags.NEW_TOOL_AGENT])
    tenant_router.include_router(tools_router.router, tags=[RouteTags.TOOLS])
    return tenant_router


def _authenticated_router():
    from api.routers import agents_v1, organizations, payments, runs_v1, task_schemas_v1, versions_v1

    authenticated_router = APIRouter(
        dependencies=[
            Depends(tenant_dependency),
            Depends(key_ring_dependency),
        ],
    )
    authenticated_router.include_router(task_schemas_v1.router, tags=[RouteTags.AGENT_SCHEMAS])
    authenticated_router.include_router(versions_v1.router)
    authenticated_router.include_router(runs_v1.router)
    authenticated_router.include_router(agents_v1.router)
    authenticated_router.include_router(payments.router)
    authenticated_router.include_router(_tenant_router())
    authenticated_router.include_router(organizations.router)
    authenticated_router.include_router(features.router, tags=[RouteTags.FEATURES])
    authenticated_router.include_router(feedback_v1.router)
    authenticated_router.include_router(integrations_router.router, tags=[RouteTags.INTEGRATIONS])

    return authenticated_router


main_router.include_router(_authenticated_router())
