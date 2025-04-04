import json
import logging
from datetime import datetime
from typing import Optional, Self

from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from typing_extensions import override

from core.domain.api_key import APIKey
from core.domain.models import Provider
from core.domain.tenant_data import (
    ProviderConfig,
    ProviderSettings,
    PublicOrganizationData,
    TenantData,
)
from core.domain.users import UserIdentifier
from core.storage.mongo.models.base_document import BaseDocumentWithID
from core.utils.encryption import Encryption
from core.utils.fields import datetime_factory, datetime_zero, id_factory
from core.utils.ids import id_uint32

_logger = logging.getLogger(__name__)


class DecryptableProviderSettings(ProviderSettings):
    secrets: str

    _encryption: Encryption | None = None

    @override
    def decrypt(self) -> ProviderConfig:
        if not self._encryption:
            raise ValueError("Encryption is not set")

        decrypted = self._encryption.decrypt(self.secrets)
        as_dict = json.loads(decrypted)
        return TypeAdapter[ProviderConfig](ProviderConfig).validate_python(
            {
                **as_dict,
                "provider": self.provider,
            },
        )


class ProviderSettingsSchema(BaseModel):
    id: str = Field(default_factory=id_factory)
    created_at: datetime = Field(default_factory=datetime_factory)
    provider: Provider
    secrets: str
    preserve_credits: bool | None = None

    @classmethod
    def from_domain(cls, domain: ProviderConfig, encryption: Encryption) -> Self:
        dumped = domain.model_dump_json(exclude={"provider"})
        return cls(
            provider=domain.provider,
            secrets=encryption.encrypt(dumped),
        )

    def to_domain(self, encryption: Encryption | None) -> DecryptableProviderSettings:
        out = DecryptableProviderSettings(
            id=self.id,
            created_at=self.created_at,
            provider=self.provider,
            secrets=self.secrets,
            preserve_credits=self.preserve_credits or None,
        )
        out._encryption = encryption  # pyright: ignore [reportPrivateUsage]
        return out


class APIKeyDocument(BaseModel):
    id: str = Field(default_factory=id_factory)
    name: str = ""
    hashed_key: str = ""
    partial_key: str = ""
    created_at: datetime = Field(default_factory=datetime_factory)
    last_used_at: Optional[datetime] = None
    created_by: UserIdentifier = Field(default_factory=UserIdentifier)

    def to_domain(self) -> APIKey:
        return APIKey(
            id=self.id,
            name=self.name,
            partial_key=self.partial_key,
            created_at=self.created_at,
            last_used_at=self.last_used_at,
            created_by=self.created_by,
        )


class PaymentFailureSchema(BaseModel):
    failure_date: datetime | None = None
    failure_reason: str | None = None
    failure_code: str | None = None

    def to_domain(self) -> TenantData.PaymentFailure | None:
        try:
            return TenantData.PaymentFailure(
                failure_date=self.failure_date or datetime_zero(),
                failure_reason=self.failure_reason or "",
                failure_code=self.failure_code or "internal",  # pyright: ignore [reportArgumentType]
            )
        except ValidationError:
            _logger.exception("Invalid payment failure", extra={"failure": self.model_dump()})
            return None


class OrganizationDocument(BaseDocumentWithID):
    uid: int = Field(default_factory=id_uint32)
    anonymous_user_id: str | None = None
    # Organization slug to be used in URLs
    slug: str | None = None
    # Old tenant field before migrating to clerk orgs
    # We should remove once we are fully migrated
    domain: str | None = None
    providers: list[ProviderSettingsSchema] | None = None
    display_name: str | None = None
    # org as set by clerk, once all data has been migrated org_id == tenant so we should remove the org_id field
    org_id: str | None = None
    # Owner ID retrieved from clerk
    owner_id: str | None = None

    # The total number of credits and organization has added
    added_credits_usd: float = 0.0
    # The current number of credits the organization has
    current_credits_usd: float = 0.0
    no_tasks_yet: bool | None = None
    anonymous: bool | None = None
    api_keys: list[APIKeyDocument] | None = None
    stripe_customer_id: str | None = None
    locked_for_payment: bool | None = None

    automatic_payment_enabled: bool = Field(default=False, title="Automatic payment enabled")
    automatic_payment_threshold: float | None = Field(default=None, title="Automatic payment threshold")
    automatic_payment_balance_to_maintain: float | None = Field(
        default=None,
        title="Automatic payment balance to maintain",
    )

    # For now the field is filled manually
    feedback_slack_hook: str | None = None

    payment_failure: PaymentFailureSchema | None = None

    class LowCreditsEmailSent(BaseModel):
        threshold_cts: int
        sent_at: datetime

    low_credits_email_sent: list[LowCreditsEmailSent] | None = None

    @classmethod
    def from_domain(cls, org_settings: TenantData, no_tasks_yet: bool | None = None) -> Self:
        return cls(
            uid=org_settings.uid or id_uint32(),
            tenant=org_settings.tenant,
            domain=org_settings.tenant or None,
            slug=org_settings.slug or None,
            display_name=org_settings.name or None,
            providers=None,
            added_credits_usd=org_settings.added_credits_usd,
            current_credits_usd=org_settings.current_credits_usd,
            org_id=org_settings.org_id or None,
            no_tasks_yet=no_tasks_yet or None,
            api_keys=None,
            stripe_customer_id=org_settings.stripe_customer_id or None,
            locked_for_payment=org_settings.locked_for_payment or None,
            automatic_payment_enabled=org_settings.automatic_payment_enabled,
            automatic_payment_threshold=org_settings.automatic_payment_threshold or None,
            automatic_payment_balance_to_maintain=org_settings.automatic_payment_balance_to_maintain or None,
            anonymous=org_settings.anonymous,
            anonymous_user_id=org_settings.anonymous_user_id or None,
            owner_id=org_settings.owner_id or None,
            feedback_slack_hook=org_settings.feedback_slack_hook or None,
            low_credits_email_sent=[
                cls.LowCreditsEmailSent(
                    threshold_cts=threshold_cts,
                    sent_at=sent_at,
                )
                for threshold_cts, sent_at in org_settings.low_credits_email_sent_by_threshold.items()
            ]
            if org_settings.low_credits_email_sent_by_threshold
            else None,
        )

    def to_domain(self, encryption: Encryption | None) -> TenantData:
        return TenantData(
            uid=self.uid,
            slug=self.slug or "",
            name=self.display_name or "",
            tenant=self.tenant or "",
            providers=[s.to_domain(encryption) for s in self.providers] if self.providers else [],
            added_credits_usd=self.added_credits_usd,
            current_credits_usd=self.current_credits_usd,
            org_id=self.org_id,
            stripe_customer_id=self.stripe_customer_id,
            locked_for_payment=self.locked_for_payment,
            automatic_payment_enabled=self.automatic_payment_enabled,
            automatic_payment_threshold=self.automatic_payment_threshold,
            automatic_payment_balance_to_maintain=self.automatic_payment_balance_to_maintain,
            anonymous=self.anonymous,
            anonymous_user_id=self.anonymous_user_id or None,
            owner_id=self.owner_id or None,
            feedback_slack_hook=self.feedback_slack_hook or None,
            payment_failure=self.payment_failure.to_domain() if self.payment_failure else None,
            low_credits_email_sent_by_threshold={
                threshold_cts: sent_at
                for threshold_cts, sent_at in (
                    (email.threshold_cts, email.sent_at) for email in self.low_credits_email_sent
                )
            }
            if self.low_credits_email_sent
            else None,
        )

    def to_domain_public(self) -> PublicOrganizationData:
        return PublicOrganizationData(
            uid=self.uid,
            slug=self.slug or "",
            name=self.display_name or "",
            tenant=self.tenant or "",
            org_id=self.org_id,
            owner_id=self.owner_id,
        )
