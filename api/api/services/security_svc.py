import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from fastapi import HTTPException

from core.domain.analytics_events.analytics_events import (
    AnalyticsEvent,
    FullAnalyticsEvent,
    OrganizationCreatedProperties,
    OrganizationProperties,
)
from core.domain.errors import DuplicateValueError
from core.domain.events import EventRouter, SendAnalyticsEvent
from core.domain.tenant_data import TenantData
from core.domain.users import User
from core.storage import ObjectNotFoundException
from core.storage.organization_storage import OrganizationSystemStorage
from core.utils.background import add_background_task
from core.utils.coroutines import capture_errors
from core.utils.hash import secure_hash
from core.utils.ids import id_uint32
from core.utils.models.dumps import safe_dump_pydantic_model

_logger = logging.getLogger(__name__)


class SecurityService:
    # Can't use the analytics service here since it depends on data provided by this service
    def __init__(self, org_storage: OrganizationSystemStorage, event_router: EventRouter):
        self._org_storage = org_storage
        self._event_router = event_router

    def _send_created_org(self, org: TenantData):
        self._event_router(
            SendAnalyticsEvent(
                event=FullAnalyticsEvent(
                    event=AnalyticsEvent(event_properties=OrganizationCreatedProperties()),
                    organization_properties=OrganizationProperties.build(org),
                    # TODO: set user properties here ?
                    user_properties=None,
                    task_properties=None,
                ),
            ),
        )

    async def _create_organization(
        self,
        org_id: str | None,
        org_slug: str | None,
        user_id: str | None,
        anon_id: str | None,
        on_duplicate: Callable[[], Awaitable[TenantData]],
    ):
        """Create an organization and return the tenant data"""

        if all(not x for x in (org_id, org_slug, user_id, anon_id)):
            raise ValueError(
                "At least one of org_id, org_slug, user_id, anon_id must be provided",
            )

        uid = id_uint32()

        data = TenantData(
            tenant=f"orguid_{uid}",
            uid=uid,
            slug=org_slug or "",
            org_id=org_id or None,
            owner_id=user_id or None,
            anonymous_user_id=anon_id,
        )

        credits = 0.2 if data.is_anonymous else 5
        data.added_credits_usd = credits
        data.current_credits_usd = credits

        try:
            org = await self._org_storage.create_organization(data)
            with capture_errors(_logger, "Error sending created org event"):
                self._send_created_org(org)
            return org
        except DuplicateValueError:
            # This can happen in race conditions
            pass

        try:
            return await on_duplicate()
        except ObjectNotFoundException:
            _logger.exception(
                "Race condition let to org not found when creating organization",
                extra={"org_id": org_id, "org_slug": org_slug, "user_id": user_id, "anon_id": anon_id},
            )
            raise HTTPException(401, "Organization not found")

    async def _migrate_tenant_to_organization(
        self,
        org_id: str,
        org_slug: str | None,
        user_id: str | None,
        anon_id: str | None,
    ) -> TenantData | None:
        """Migrate an existing tenant to an organization by adding the and org_id, org_slug
        to an existing record"""
        if not user_id and not anon_id:
            return None

        try:
            return await self._org_storage.migrate_tenant_to_organization(
                org_id=org_id,
                org_slug=org_slug,
                owner_id=user_id,
                anon_id=anon_id,
            )
        except ObjectNotFoundException:
            return None

    async def _find_tenant_for_org_id(
        self,
        org_id: str,
        org_slug: str | None,
        user_id: str | None,
        anon_id: str | None,
    ) -> TenantData:
        try:
            return await self._org_storage.find_tenant_for_org_id(org_id)
        except ObjectNotFoundException:
            pass

        # Organization was not found, but we know the org is valid since we trust the token
        # First, we try migrating a potentially existing tenant
        if migrated := await self._migrate_tenant_to_organization(org_id, org_slug, user_id, anon_id):
            return migrated

        # Otherwise we create a new organization
        return await self._create_organization(
            org_id=org_id,
            org_slug=org_slug,
            user_id=user_id,
            anon_id=anon_id,
            on_duplicate=lambda: self._org_storage.find_tenant_for_org_id(org_id),
        )

    async def _migrate_tenant_to_user(
        self,
        user_id: str,
        org_slug: str | None,
        anon_id: str | None,
    ) -> TenantData | None:
        """Migrate an existing anonymous user to a user type tenant"""
        if not anon_id:
            return None
        try:
            return await self._org_storage.migrate_tenant_to_user(user_id, org_slug, anon_id)
        except ObjectNotFoundException:
            return None

    async def _find_tenant_for_owner_id(self, owner_id: str, org_slug: str | None, anon_id: str | None) -> TenantData:
        """Find, migrate or create a tenant for a user_id. This should be called
        if there is a user_id but no org_id"""
        try:
            return await self._org_storage.find_tenant_for_owner_id(owner_id)
        except ObjectNotFoundException:
            pass

        if migrated := await self._migrate_tenant_to_user(owner_id, org_slug, anon_id):
            return migrated

        return await self._create_organization(
            org_id=None,
            org_slug=org_slug,
            user_id=owner_id,
            anon_id=anon_id,
            on_duplicate=lambda: self._org_storage.find_tenant_for_owner_id(owner_id),
        )

    async def _find_tenant_for_api_key(self, credentials: str):
        try:
            # We split the find and the update, the find is on the critical path
            res = await self._org_storage.find_tenant_for_api_key(secure_hash(credentials))
            add_background_task(
                self._org_storage.update_api_key_last_used_at(secure_hash(credentials), datetime.now(timezone.utc)),
            )
            return res
        except ObjectNotFoundException:
            pass

    async def _find_anonymous_tenant(self, unknown_user_id: str) -> TenantData:
        try:
            return await self._org_storage.find_anonymous_tenant(unknown_user_id)
        except ObjectNotFoundException:
            pass

        return await self._create_organization(
            org_id=None,
            org_slug=None,
            user_id=None,
            anon_id=unknown_user_id,
            on_duplicate=lambda: self._org_storage.find_anonymous_tenant(unknown_user_id),
        )

    async def find_tenant(self, user: User | None, credentials: str | None) -> TenantData | None:
        # TODO: we should check if the tenantdata.slug matches the user slug here
        # And update in the background if needed
        if not user:
            if not credentials:
                return None
            return await self._find_tenant_for_api_key(credentials)

        if user.org_id:
            return await self._find_tenant_for_org_id(
                user.org_id,
                org_slug=user.slug,
                user_id=user.user_id,
                anon_id=user.unknown_user_id,
            )
        if user.user_id:
            return await self._find_tenant_for_owner_id(
                owner_id=user.user_id,
                org_slug=user.slug,
                anon_id=user.unknown_user_id,
            )
        if user.unknown_user_id:
            return await self._find_anonymous_tenant(unknown_user_id=user.unknown_user_id)

        # TODO[org]: remove, we should just throw a 401 here
        if user.tenant:
            _logger.warning(
                "Deprecated tenant was used",
                extra={"user": safe_dump_pydantic_model(user)},
            )

            # Before the tenant was the domain
            try:
                return await self._org_storage.find_tenant_for_deprecated_user(domain=user.tenant)
            except ObjectNotFoundException:
                _logger.error(
                    "Organization not found for deprecated token",
                    extra={"user": safe_dump_pydantic_model(user)},
                )
                raise HTTPException(401, "Organization not found for deprecated token")

        # this would be very bad and mean that someone generated an invalid token
        # that has a valid signature
        _logger.error(
            "Very bad: API was called with an invalid token",
            extra={"user": safe_dump_pydantic_model(user)},
        )
        raise HTTPException(401, "Organization not found")
