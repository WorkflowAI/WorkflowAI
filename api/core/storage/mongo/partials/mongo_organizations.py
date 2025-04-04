from datetime import datetime, timezone
from typing import Any, List, Literal, override

from pymongo.errors import DuplicateKeyError

from core.domain.api_key import APIKey
from core.domain.errors import DuplicateValueError
from core.domain.tenant_data import (
    ProviderSettings,
    PublicOrganizationData,
    TenantData,
)
from core.domain.users import UserIdentifier
from core.providers.base.config import ProviderConfig
from core.storage import ObjectNotFoundException, TenantTuple
from core.storage.mongo.models.organization_document import (
    APIKeyDocument,
    OrganizationDocument,
    PaymentFailureSchema,
    ProviderSettingsSchema,
)
from core.storage.mongo.mongo_types import AsyncCollection
from core.storage.mongo.partials.base_partial_storage import PartialStorage
from core.storage.mongo.utils import dump_model
from core.storage.organization_storage import OrganizationStorage
from core.utils.encryption import Encryption
from core.utils.fields import datetime_factory


class MongoOrganizationStorage(PartialStorage[OrganizationDocument], OrganizationStorage):
    def __init__(self, tenant: TenantTuple, collection: AsyncCollection, encryption: Encryption):
        super().__init__(tenant, collection, OrganizationDocument)
        self.encryption = encryption

    @classmethod
    def _projection(cls, dict: dict[str, Any] | None) -> dict[str, Any]:
        if dict is None:
            return {"api_keys.hashed_key": 0}
        if "api_keys.hashed_key" not in dict:
            return {"api_keys.hashed_key": 0, **dict}
        return dict

    @override
    async def update_customer_id(self, stripe_customer_id: str | None) -> None:
        await self._update_one(
            {"stripe_customer_id": {"$exists": False}},
            {"$set": {"stripe_customer_id": stripe_customer_id}},
        )

    @override
    async def get_organization(self) -> TenantData:
        doc = await self._find_one({}, projection=self._projection(None))
        return doc.to_domain(self.encryption)

    async def get_public_org(self, filter: dict[str, Any]):
        doc = await self._collection.find_one(
            filter,
            projection={"tenant": 1, "slug": 1, "display_name": 1, "uid": 1, "org_id": 1, "owner_id": 1},
        )
        if doc is None:
            raise ObjectNotFoundException("Organization  not found", code="organization_not_found")

        return OrganizationDocument.model_validate(doc).to_domain_public()

    @override
    async def get_public_organization(self, slug: str) -> PublicOrganizationData:
        # We should move the domain to "previous_slugs" once all data have been migrated
        # and fetch from there
        if "." in slug:
            # Domain were previously used as slugs
            filter = {"domain": slug}
        else:
            # New slugs are URL safe and do not contain dots
            filter = {"slug": slug}

        return await self.get_public_org(filter)

    @override
    async def public_organization_by_tenant(self, tenant: str) -> PublicOrganizationData:
        return await self.get_public_org({"tenant": tenant})

    @override
    async def update_slug(
        self,
        org_id: str,
        slug: str | None,
        display_name: str | None,
    ):
        update: dict[str, Any] = {}
        if slug:
            update["slug"] = slug
        if display_name:
            update["display_name"] = display_name

        if not update:
            # Noop
            return

        with self._wrap_errors():
            await self._collection.update_one(
                {"org_id": org_id},
                {"$set": update},
            )

    async def _find_tenant(self, filter: dict[str, Any], projection: dict[str, Any] | None = None) -> TenantData:
        doc = await self._collection.find_one(filter, projection=projection)
        if doc is None:
            raise ObjectNotFoundException("Organization  not found", code="organization_not_found")
        return OrganizationDocument.model_validate(doc).to_domain(self.encryption)

    async def _update_tenant(self, tenant: str, filter: dict[str, Any], update: dict[str, Any]):
        with self._wrap_errors():
            res = await self._collection.update_one(
                {"tenant": tenant, **filter},
                update,
            )
        if res.matched_count != 1:
            raise ObjectNotFoundException("Organization  not found", code="organization_not_found")

    async def _find_one_and_update_tenant(self, filter: dict[str, Any], update: dict[str, Any]) -> TenantData:
        doc = await self._collection.find_one_and_update(
            filter,
            update,
            projection=self._projection(None),
            return_document=True,
        )
        if doc is None:
            raise ObjectNotFoundException("Organization  not found", code="organization_not_found")
        return OrganizationDocument.model_validate(doc).to_domain(self.encryption)

    @override
    async def find_tenant_for_org_id(self, org_id: str) -> TenantData:
        return await self._find_tenant({"org_id": org_id})

    @override
    async def find_tenant_for_deprecated_user(self, domain: str) -> TenantData:
        return await self._find_tenant({"domain": domain})

    @classmethod
    def _owner_id_filter(cls, owner_id: str):
        return {"owner_id": owner_id, "org_id": {"$exists": False}}

    @override
    async def find_tenant_for_owner_id(self, owner_id: str) -> TenantData:
        return await self._find_tenant(self._owner_id_filter(owner_id))

    @override
    async def add_provider_config(self, config: ProviderConfig) -> ProviderSettings:
        schema = ProviderSettingsSchema.from_domain(config, self.encryption)

        await self._update_one(
            {},
            {"$push": {"providers": dump_model(schema)}},
        )

        return schema.to_domain(self.encryption)

    @override
    async def delete_provider_config(self, config_id: str) -> None:
        updated = await self._update_one(
            {},
            {"$pull": {"providers": {"id": config_id}}},
        )
        if updated.modified_count != 1:
            raise ObjectNotFoundException(f"Config {config_id} not found", code="config_not_found")

    @override
    async def add_credits_to_tenant(self, tenant: str, credits: float) -> None:
        # Add credits and unset the payment failure status
        await self._collection.update_one(
            {"tenant": tenant},
            {
                "$inc": {"current_credits_usd": credits, "added_credits_usd": credits},
                "$unset": {"payment_failure": "", "low_credits_email_sent": ""},
            },
        )

    @override
    async def decrement_credits(self, tenant: str, credits: float) -> TenantData:
        res = await self._collection.find_one_and_update(
            {"tenant": tenant},
            {"$inc": {"current_credits_usd": -credits}},
            projection={
                "uid": 1,
                "tenant": 1,
                "current_credits_usd": 1,
                "automatic_payment_enabled": 1,
                "automatic_payment_threshold": 1,
                "automatic_payment_balance_to_maintain": 1,
                "locked_for_payment": 1,
                "payment_failure": 1,
                "low_credits_email_sent": 1,
            },
            return_document=True,
        )
        return OrganizationDocument.model_validate(res).to_domain(self.encryption)

    @override
    async def create_organization(self, org_settings: TenantData) -> TenantData:
        # Set no_tasks_yet to True for new organizations to enable first-task credit bonus
        doc = OrganizationDocument.from_domain(org_settings, no_tasks_yet=True)
        # Using the collection directly to avoid the tenant being set to the current one
        # As this function is used from the system storage (aka with self._tenant == "__system__")
        with self._wrap_errors():
            res = await self._collection.insert_one(dump_model(doc))
        doc.id = res.inserted_id
        return doc.to_domain(self.encryption)

    @override
    async def add_5_credits_for_first_task(self) -> None:
        await self._update_one(
            {"no_tasks_yet": True, "anonymous": {"$ne": True}},
            {
                "$inc": {"current_credits_usd": 5, "added_credits_usd": 5},
                "$unset": {"no_tasks_yet": ""},
            },
        )

    @override
    async def delete_organization(self, org_id: str):
        current_date = datetime.now(tz=None).isoformat(timespec="seconds")
        with self._wrap_errors():
            await self._collection.update_one(
                {"org_id": org_id},
                [
                    {"$set": {"deleted": True, "slug": {"$concat": [f"__deleted__.{current_date}.", "$slug"]}}},
                ],
            )

    @override
    async def create_api_key_for_organization(
        self,
        name: str,
        hashed_key: str,
        partial_key: str,
        created_by: UserIdentifier,
    ) -> APIKey:
        doc = APIKeyDocument(
            name=name,
            hashed_key=hashed_key,
            partial_key=partial_key,
            created_at=datetime.now(timezone.utc),
            last_used_at=None,
            created_by=created_by,
        )
        try:
            await self._update_one(
                {
                    # Relying on unique index to prevent duplicates across organizations
                },
                {"$push": {"api_keys": dump_model(doc)}},
                upsert=False,
            )
        except DuplicateKeyError:
            # $nor raises an error if the document does not exist, i.e. api_key hashed_key already exists
            raise DuplicateValueError("API key already exists")
        return doc.to_domain()

    @override
    async def get_api_keys_for_organization(self) -> List[APIKey]:
        # can't just send api_keys: 1 here because it will raise a path collision
        fields = {k: 0 for k in OrganizationDocument.model_fields.keys() if k != "api_keys"}
        doc = await self._find_one({}, projection=self._projection(fields))
        return [api_key.to_domain() for api_key in doc.api_keys] if doc.api_keys else []

    @override
    async def delete_api_key_for_organization(self, key_id: str) -> bool:
        result = await self._update_one(
            {"api_keys.id": key_id},
            {"$pull": {"api_keys": {"id": key_id}}},
        )
        return result.modified_count > 0

    @override
    async def find_tenant_for_api_key(self, hashed_key: str) -> TenantData:
        return await self._find_tenant({"api_keys.hashed_key": hashed_key})

    @override
    async def update_api_key_last_used_at(self, hashed_key: str, now: datetime):
        await self._collection.update_one(
            # $elemMatch required for positional $ operator
            # We have to use a not gt instead of lt to handle the case where the last_used_at is None
            {"api_keys": {"$elemMatch": {"hashed_key": hashed_key, "last_used_at": {"$not": {"$gt": now}}}}},
            {"$set": {"api_keys.$.last_used_at": now}},
        )

    @override
    async def attempt_lock_for_payment(self, tenant: str) -> TenantData | None:
        try:
            return await self._find_one_and_update_tenant(
                {"tenant": tenant, "locked_for_payment": {"$ne": True}},
                {"$set": {"locked_for_payment": True}},
            )
        except ObjectNotFoundException:
            return None

    def _last_payment_failed_at_set(self, is_failed: bool, update: dict[str, Any]):
        if is_failed:
            update["$set"] = {"last_payment_failed_at": datetime.now(timezone.utc)}
        else:
            if "$unset" in update:
                update["$unset"]["last_payment_failed_at"] = ""
            else:
                update["$unset"] = {"last_payment_failed_at": ""}

    @override
    async def update_automatic_payment(
        self,
        opt_in: bool,
        threshold: float | None,
        balance_to_maintain: float | None,
    ) -> None:
        await self._update_one(
            {},
            {
                "$set": {
                    "automatic_payment_enabled": opt_in,
                    "automatic_payment_threshold": threshold if opt_in else None,
                    "automatic_payment_balance_to_maintain": balance_to_maintain if opt_in else None,
                },
            },
        )

    @classmethod
    def _anonymous_user_id_filter(cls, unknown_user_id: str):
        return {"anonymous_user_id": unknown_user_id, "org_id": {"$exists": False}, "owner_id": {"$exists": False}}

    @override
    async def find_anonymous_tenant(self, anon_id: str) -> TenantData:
        # We only return anonymous tenants that do not have an org_id
        # Otherwise you could use this function to find a tenant that should not be anonymous
        return await self._find_tenant(self._anonymous_user_id_filter(anon_id))

    @override
    async def migrate_tenant_to_organization(
        self,
        org_id: str,
        org_slug: str | None,
        owner_id: str | None,
        anon_id: str | None,
    ) -> TenantData:
        or_filters: list[dict[str, Any]] = []
        if owner_id:
            or_filters.append(self._owner_id_filter(owner_id))
        if anon_id:
            or_filters.append(self._anonymous_user_id_filter(anon_id))
        if not or_filters:
            raise ValueError("No owner_id or anon_id provided")
        filter = {"$or": or_filters} if len(or_filters) > 1 else or_filters[0]

        update = {"org_id": org_id, "slug": org_slug}
        if owner_id:
            update["owner_id"] = owner_id

        return await self._find_one_and_update_tenant(
            filter,
            {"$set": update},
        )

    @override
    async def migrate_tenant_to_user(self, owner_id: str, org_slug: str | None, anon_id: str) -> TenantData:
        update = {"owner_id": owner_id}
        if org_slug:
            update["slug"] = org_slug
        return await self._find_one_and_update_tenant(
            self._anonymous_user_id_filter(anon_id),
            {"$set": update},
        )

    @override
    async def feedback_slack_hook_for_tenant(self, tenant_uid: int) -> str | None:
        doc = await self._collection.find_one({"uid": tenant_uid}, projection={"feedback_slack_hook": 1})
        if not doc:
            raise ObjectNotFoundException("Organization not found", code="organization_not_found")
        return doc.get("feedback_slack_hook")

    @override
    async def unlock_payment_for_failure(
        self,
        tenant: str,
        now: datetime,
        code: Literal["internal", "payment_failed"],
        failure_reason: str,
    ):
        obj = PaymentFailureSchema(failure_code=code, failure_reason=failure_reason, failure_date=now)
        await self._update_tenant(
            tenant,
            {"locked_for_payment": True},
            {"$unset": {"locked_for_payment": ""}, "$set": {"payment_failure": dump_model(obj)}},
        )

    @override
    async def unlock_payment_for_success(self, tenant: str, amount: float) -> None:
        await self._update_tenant(
            tenant,
            {"locked_for_payment": True},
            {"$unset": {"locked_for_payment": "", "payment_failure": ""}, "$inc": {"current_credits_usd": amount}},
        )

    @override
    async def add_low_credits_email_sent(self, tenant: str, threshold: float) -> None:
        threshold_cts = int(round(threshold * 100))
        await self._update_tenant(
            tenant,
            {},
            {
                "$push": {
                    "low_credits_email_sent": dump_model(
                        OrganizationDocument.LowCreditsEmailSent(
                            threshold_cts=threshold_cts,
                            sent_at=datetime_factory(),
                        ),
                    ),
                },
            },
        )

    @override
    async def check_unlocked_payment_failure(self, tenant: str) -> TenantData.PaymentFailure | None:
        doc = await self._find_tenant(
            {"tenant": tenant, "locked_for_payment": {"$ne": True}},
            projection={"payment_failure": 1},
        )
        return doc.payment_failure
