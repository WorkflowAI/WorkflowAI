import logging
from dataclasses import dataclass

from starlette.requests import Request

from api.services import storage
from api.services.analytics import analytics_service
from api.services.event_handler import system_event_router
from api.services.security_service import SecurityService
from core.domain.analytics_events.analytics_events import OrganizationProperties

logger = logging.getLogger(__name__)


@dataclass
class AuthResult:
    """Result of auth extraction containing tenant and organization info"""
    tenant_slug: str
    organization_name: str | None
    user_email: str | None
    # Add more fields as needed for future use
    tenant_uid: str


async def extract_auth_info_from_request(request: Request) -> AuthResult | None:
    """
    Extract authentication information from request headers.
    
    Returns AuthResult if authentication is successful, None if it fails.
    This function handles auth errors gracefully and logs them rather than raising exceptions.
    """
    try:
        # Extract auth header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning(
                "Missing or invalid Authorization header in MCP request",
                extra={
                    "has_auth_header": auth_header is not None,
                    "auth_header_format": auth_header[:20] + "..." if auth_header else None,
                },
            )
            return None

        # Set up auth services
        _system_storage = storage.system_storage(storage.shared_encryption())
        security_service = SecurityService(
            _system_storage.organizations,
            system_event_router(),
            analytics_service(user_properties=None, organization_properties=None, task_properties=None),
        )

        # Extract and validate token
        token = auth_header.split(" ")[1]
        tenant = await security_service.tenant_from_credentials(token)
        if not tenant:
            logger.warning(
                "Invalid bearer token in MCP request",
                extra={
                    "token_length": len(token),
                    "token_prefix": token[:8] + "..." if len(token) > 8 else token,
                },
            )
            return None

        # Build organization properties to extract name
        org_properties = OrganizationProperties.build(tenant)
        
        # Extract organization name from properties
        # Note: OrganizationProperties might have different fields - adjust as needed
        organization_name = getattr(org_properties, 'name', None) or tenant.slug

        # TODO: Add user email extraction if/when user info becomes available
        user_email = None  # Currently not available in tenant info

        return AuthResult(
            tenant_slug=tenant.slug,
            tenant_uid=tenant.uid,
            organization_name=organization_name,
            user_email=user_email,
        )

    except Exception as e:
        logger.error(
            "Error extracting auth info from MCP request",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        return None