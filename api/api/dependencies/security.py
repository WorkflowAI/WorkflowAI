import logging
import re
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.dependencies.encryption import EncryptionDep
from api.services import storage
from api.services.analytics import analytics_service
from api.services.api_keys import APIKeyService
from api.services.event_handler import system_event_router
from api.services.security_service import SecurityService, UserClaims
from api.utils import set_tenant_slug
from core.domain.consts import WORKFLOWAI_APP_URL
from core.domain.errors import InvalidToken
from core.domain.tenant_data import (
    ProviderSettings,
    PublicOrganizationData,
    TenantData,
)
from core.domain.users import User
from core.storage import ObjectNotFoundException
from core.storage.backend_storage import SystemBackendStorage
from core.storage.organization_storage import OrganizationSystemStorage
from core.utils import no_op
from core.utils.encryption import Encryption
from core.utils.strings import obfuscate

from ..services.keys import KeyRing

logger = logging.getLogger(__name__)


async def key_ring_dependency() -> KeyRing:
    return SecurityService.key_ring


KeyRingDep = Annotated[KeyRing, Depends(key_ring_dependency)]


bearer = HTTPBearer(auto_error=False)

BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


# TODO: we should use the security service here instead of the key ring directly
async def user_auth_dependency(
    keys: KeyRingDep,
    credentials: BearerDep,
    request: Request,
) -> User | None:
    """This dependency is only responsible for parsing the JWT token and returning
    the user data. It is not responsible for finding the correct tenant."""
    if credentials is not None:
        if APIKeyService.is_api_key(credentials.credentials):
            return None

        claims = await keys.verify(credentials.credentials, returns=UserClaims)
        return claims.to_domain()

    if header := request.headers.get("Authorization"):
        raise InvalidToken(
            f"Invalid authorization header: {obfuscate(header, 5)}. "
            "A valid header with an API key looks like 'Bearer wai-****'. If you need a new API key, "
            f"Grab a fresh one (plus $5 in free LLM credits for new users) at {WORKFLOWAI_APP_URL}/keys 🚀",
        )

    return None


UserDep = Annotated[User | None, Depends(user_auth_dependency)]


def required_user_dependency(user: UserDep) -> User:
    if user is None:
        raise HTTPException(401, "Authentication is required")
    return user


RequiredUserDep = Annotated[User, Depends(required_user_dependency)]


# These paths are whitelisted for public tasks
_WHITELISTED_PATTERNS_FOR_AUTHENTICATED_USERS = (
    re.compile(r"^(/v1)?/[^/]+/agents/[^/]+/schemas/\d+/(run|input|versions|python)$"),
    re.compile(r"^/v1/[^/]+/agents/[^/]+/runs/search$"),
)


def _is_path_whitelisted(path: str) -> bool:
    return any(pattern.match(path) for pattern in _WHITELISTED_PATTERNS_FOR_AUTHENTICATED_USERS)


async def _is_different_tenant_allowed(
    request: Request,
    org: PublicOrganizationData,
    encryption: Encryption,
    is_authenticated: bool,
) -> bool:
    # Condition for allowing a tenant different from the token are:
    # - method is GET or (user is authenticated and path is whitelisted)
    # - agent_id is in the path
    # - the corresponding task is public
    if request.method != "GET" and (not is_authenticated or not _is_path_whitelisted(request.url.path)):
        return False

    if "agent_id" not in request.path_params:
        return False

    s = storage.storage_for_tenant(
        tenant=org.tenant,
        tenant_uid=org.uid,
        encryption=encryption,
        event_router=no_op.event_router,
    ).tasks
    agent_id = request.path_params["agent_id"]
    return await s.is_task_public(agent_id)


def system_storage(encryption: EncryptionDep) -> SystemBackendStorage:
    return storage.system_storage(encryption)


SystemStorageDep = Annotated[SystemBackendStorage, Depends(system_storage)]


def system_org_storage(storage: SystemStorageDep) -> OrganizationSystemStorage:
    return storage.organizations


OrgSystemStorageDep = Annotated[OrganizationSystemStorage, Depends(system_org_storage)]


def security_service_dependency(org_storage: OrgSystemStorageDep) -> SecurityService:
    return SecurityService(
        org_storage,
        system_event_router(),
        analytics_service(user_properties=None, organization_properties=None, task_properties=None),
    )


SecurityServiceDep = Annotated[SecurityService, Depends(security_service_dependency)]


async def user_organization(
    security_service: SecurityServiceDep,
    user: UserDep,
    credentials: BearerDep,
) -> TenantData | None:
    return await security_service.find_tenant(user, credentials.credentials if credentials else None)


UserOrganizationDep = Annotated[TenantData | None, Depends(user_organization)]


async def required_user_organization(user_org: UserOrganizationDep) -> TenantData:
    if not user_org:
        raise HTTPException(
            401,
            "Authorization header is missing. "
            "A valid authorization header with an API key looks like 'Bearer wai-****'. If you need a new API key, "
            f"Grab a fresh one (plus $5 in free LLM credits for new users) at {WORKFLOWAI_APP_URL}/keys 🚀",
        )
    return user_org


RequiredUserOrganizationDep = Annotated[TenantData, Depends(required_user_organization)]


async def non_anonymous_organization(user_org: RequiredUserOrganizationDep) -> TenantData:
    if user_org.is_anonymous:
        raise HTTPException(401, "Endpoint is only available for non-anonymous tenants")
    return user_org


async def url_public_organization(
    org_storage: OrgSystemStorageDep,
    request: Request,
    user_org: UserOrganizationDep,
) -> PublicOrganizationData | None:
    tenant_param = request.path_params.get("tenant")
    # "_" is a special tenant, in which we return the organization of the user
    if not tenant_param or tenant_param == "_":
        return user_org

    if user_org is not None:
        # if the user exists, then we try and bypass the db check
        # by checking whether the url tenant is either the old tenant or the new org slug
        # TODO: user.tenant will be the new org id once migrated so we can restrict the slug
        # to only be the org slug
        if user_org.tenant == tenant_param or user_org.slug == tenant_param:
            return user_org

    try:
        return await org_storage.get_public_organization(tenant_param)
    except ObjectNotFoundException:
        # TODO: raise a 404 if the tenant does not exist
        # Leaving it as a warning for now, to make sure we don't old clients using invalid URLs
        logger.warning("Requested URL tenant does not exist", extra={"tenant": tenant_param})
        return None


URLPublicOrganizationDep = Annotated[PublicOrganizationData | None, Depends(url_public_organization)]


async def _final_tenant_data_inner(
    user: User | None,
    user_org: TenantData | None,
    url_public_org: PublicOrganizationData | None,
    request: Request,
    encryption: EncryptionDep,
) -> PublicOrganizationData:
    # For all routes that do not have a tenant in the path, we use the tenant from the user
    # The user must be authenticated
    user_tenant = user_org.tenant if user_org else None
    url_tenant = url_public_org.tenant if url_public_org else None

    if not url_tenant:
        if user_org is None:
            raise HTTPException(401, "Authentication is required")
        return user_org

    if user_org is not None and user_tenant == url_tenant:
        return user_org

    if not url_public_org:  # mostly for typing
        raise HTTPException(404, "Tenant does not exist")

    different_tenant_allowed = await _is_different_tenant_allowed(
        request,
        url_public_org,
        encryption,
        is_authenticated=user is not None,
    )
    if not different_tenant_allowed and (user is None or user_tenant != url_tenant):
        raise HTTPException(404, "Task not found")

    return url_public_org


async def final_tenant_data(
    user: UserDep,
    user_org: UserOrganizationDep,
    url_public_org: URLPublicOrganizationDep,
    request: Request,
    encryption: EncryptionDep,
) -> PublicOrganizationData:
    data = await _final_tenant_data_inner(user, user_org, url_public_org, request, encryption)
    set_tenant_slug(request, data.slug)
    return data


FinalTenantDataDep = Annotated[PublicOrganizationData, Depends(final_tenant_data)]


async def tenant_dependency(org: FinalTenantDataDep) -> str:
    return org.tenant


TenantDep = Annotated[str, Depends(tenant_dependency)]


async def tenant_uid_dependency(org: FinalTenantDataDep) -> int:
    return org.uid


TenantUIDDep = Annotated[int, Depends(tenant_uid_dependency)]


def provider_settings_dependency(user_org: UserOrganizationDep) -> list[ProviderSettings] | None:
    if not user_org:
        return None
    return user_org.providers


ProviderSettingsDep = Annotated[list[ProviderSettings] | None, Depends(provider_settings_dependency)]
