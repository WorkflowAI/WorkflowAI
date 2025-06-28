import logging
from typing import Annotated

from fastapi import Depends, Request

from api.dependencies.security import URLPublicOrganizationDep, UserDep, UserOrganizationDep
from core.domain.analytics_events.analytics_events import (
    OrganizationProperties,
    SourceType,
    TaskProperties,
    UserProperties,
)

_logger = logging.getLogger(__name__)


def analytics_user_properties(user: UserDep, request: Request) -> UserProperties:
    try:
        if request.url.path == "/v1/chat/completions":
            source = SourceType.PROXY
        else:
            source = SourceType(request.headers.get("x-workflowai-source", "api"))
    except ValueError:
        _logger.warning("Invalid source type", extra={"source": request.headers.get("x-workflowai-source")})
        source = SourceType.API

    return UserProperties(
        user_id=user.user_id if user else None,
        user_email=user.sub if user else None,
        client_source=source,
        client_version=request.headers.get("x-workflowai-version"),
        client_language=request.headers.get("x-workflowai-language"),
    )


UserPropertiesDep = Annotated[UserProperties, Depends(analytics_user_properties)]


def analytics_organization_properties(user_org: UserOrganizationDep) -> OrganizationProperties:
    if not user_org:
        return OrganizationProperties(tenant="unknown_user")
    return OrganizationProperties.build(user_org)


AnalyticsOrganizationPropertiesDep = Annotated[OrganizationProperties, Depends(analytics_organization_properties)]


async def analytics_task_properties(
    request: Request,
    url_public_org: URLPublicOrganizationDep,
    user_org: UserOrganizationDep,
) -> TaskProperties | None:
    agent_id = request.path_params.get("agent_id")
    if not agent_id:
        return None

    try:
        raw_schema_id = request.path_params["task_schema_id"]
        schema_id = int(raw_schema_id)
    except (ValueError, TypeError, KeyError):
        schema_id = None

    return TaskProperties.build(agent_id, schema_id, url_public_org or user_org)


AnalyticsTaskPropertiesDep = Annotated[TaskProperties | None, Depends(analytics_task_properties)]
