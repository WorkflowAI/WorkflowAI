from datetime import datetime
from typing import List, Literal, Protocol

from core.domain.api_key import APIKey
from core.domain.tenant_data import (
    ProviderSettings,
    PublicOrganizationData,
    TenantData,
)
from core.domain.users import UserIdentifier
from core.providers.base.config import ProviderConfig


class PublicOrganizationStorage(Protocol):
    async def get_public_organization(self, slug: str) -> PublicOrganizationData: ...
    async def public_organization_by_tenant(self, tenant: str) -> PublicOrganizationData: ...


class OrganizationSystemStorage(PublicOrganizationStorage, Protocol):
    async def find_tenant_for_api_key(self, hashed_key: str) -> TenantData: ...

    async def update_api_key_last_used_at(self, hashed_key: str, now: datetime): ...

    async def update_slug(self, org_id: str, slug: str | None, display_name: str | None): ...

    async def create_organization(self, org_settings: TenantData) -> TenantData: ...

    async def delete_organization(self, org_id: str) -> None: ...

    async def find_tenant_for_deprecated_user(self, domain: str) -> TenantData: ...

    async def find_tenant_for_org_id(self, org_id: str) -> TenantData: ...

    async def find_tenant_for_owner_id(self, owner_id: str) -> TenantData: ...

    async def find_anonymous_tenant(self, anon_id: str) -> TenantData: ...

    async def feedback_slack_hook_for_tenant(self, tenant_uid: int) -> str | None: ...

    async def add_credits_to_tenant(self, tenant: str, credits: float) -> None: ...

    async def decrement_credits(self, tenant: str, credits: float) -> TenantData: ...

    async def migrate_tenant_to_organization(
        self,
        org_id: str,
        org_slug: str | None,
        owner_id: str | None,
        anon_id: str | None,
    ) -> TenantData:
        """Migrate an existing anon or user tenant to an organization tenant"""
        ...

    async def migrate_tenant_to_user(self, owner_id: str, org_slug: str | None, anon_id: str) -> TenantData:
        """Migrate an existing anonymous user to a user type tenant"""
        ...

    async def attempt_lock_for_payment(self, tenant: str) -> TenantData | None: ...

    async def unlock_payment_for_failure(
        self,
        tenant: str,
        now: datetime,
        code: Literal["internal", "payment_failed"],
        failure_reason: str,
    ): ...

    async def unlock_payment_for_success(self, tenant: str, amount: float): ...

    async def add_low_credits_email_sent(self, tenant: str, threshold: float): ...

    # Returns either a payment failure or None
    # or raise an error if the organization is locked
    async def check_unlocked_payment_failure(self, tenant: str) -> TenantData.PaymentFailure | None: ...


class OrganizationStorage(OrganizationSystemStorage, Protocol):
    @property
    def tenant(self) -> str: ...

    async def get_organization(self) -> TenantData: ...

    async def update_customer_id(self, stripe_customer_id: str | None) -> None: ...

    async def add_provider_config(self, config: ProviderConfig) -> ProviderSettings: ...

    async def delete_provider_config(self, config_id: str) -> None: ...

    async def add_5_credits_for_first_task(self) -> None: ...

    async def create_api_key_for_organization(
        self,
        name: str,
        hashed_key: str,
        partial_key: str,
        created_by: UserIdentifier,
    ) -> APIKey: ...

    async def get_api_keys_for_organization(self) -> List[APIKey]: ...

    async def delete_api_key_for_organization(self, key_id: str) -> bool: ...

    async def update_automatic_payment(
        self,
        opt_in: bool,
        threshold: float | None,
        balance_to_maintain: float | None,
    ) -> None: ...
