# pyright: reportPrivateUsage=false

import hashlib
import secrets
from datetime import datetime, timezone

import pytest
from freezegun.api import FrozenDateTimeFactory
from pymongo.errors import DuplicateKeyError

from core.domain.api_key import APIKey
from core.domain.errors import DuplicateValueError
from core.domain.models import Provider
from core.domain.tenant_data import TenantData
from core.domain.users import UserIdentifier
from core.providers.openai.openai_provider import OpenAIConfig
from core.storage import ObjectNotFoundException
from core.storage.mongo.conftest import TENANT
from core.storage.mongo.models.organization_document import (
    APIKeyDocument,
    DecryptableProviderSettings,
    OrganizationDocument,
    PaymentFailureSchema,
    ProviderSettingsSchema,
)
from core.storage.mongo.mongo_storage import MongoStorage
from core.storage.mongo.mongo_types import AsyncCollection
from core.storage.mongo.partials.mongo_organizations import MongoOrganizationStorage
from core.storage.mongo.utils import dump_model
from core.utils import no_op
from core.utils.encryption import Encryption


@pytest.fixture(scope="function")
def organization_storage(storage: MongoStorage) -> MongoOrganizationStorage:
    return storage.organizations


@pytest.fixture(scope="function")
def other_organization_storage(mongo_test_uri: str, mock_encryption: Encryption) -> MongoOrganizationStorage:
    return MongoStorage(
        tenant="tenant_2",
        connection_string=mongo_test_uri,
        encryption=mock_encryption,
        event_router=no_op.event_router,
    ).organizations


@pytest.fixture(scope="function")
async def inserted_tenant(organization_storage: MongoOrganizationStorage, org_col: AsyncCollection):
    org_settings = OrganizationDocument(tenant=TENANT)
    await org_col.insert_one(dump_model(org_settings))
    return org_settings.tenant


class TestGetOrganizationSettings:
    def _org_settings(self, tenant: str = TENANT) -> OrganizationDocument:
        return OrganizationDocument(
            tenant=tenant,
            slug="",
            providers=[ProviderSettingsSchema(provider=Provider.OPEN_AI, secrets="hello")],
        )

    async def test_found(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        org_settings = self._org_settings()
        await org_col.insert_one(dump_model(org_settings))

        settings = await organization_storage.get_organization()
        assert len(settings.providers) == 1

    async def test_not_found(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        org_settings = self._org_settings(tenant="t2")
        await org_col.insert_one(dump_model(org_settings))

        with pytest.raises(ObjectNotFoundException):
            await organization_storage.get_organization()

    async def test_settings_unique(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        org_settings = self._org_settings()
        await org_col.insert_one(dump_model(org_settings))

        with pytest.raises(DuplicateKeyError):
            await org_col.insert_one(dump_model(self._org_settings()))

    async def test_include(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        org_settings = self._org_settings()
        org_settings.slug = "test-slug"
        await org_col.insert_one(dump_model(org_settings))

        org = await organization_storage.get_organization(include={"slug"})
        assert org.slug == "test-slug"
        assert org.uid == 0


class TestAddProviderConfig:
    async def test_create_and_add(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
        mock_encryption: Encryption,
    ) -> None:
        # First, insert the organization document to ensure it exists
        org_settings = OrganizationDocument(tenant=TENANT, slug="", providers=[])
        await org_col.insert_one(dump_model(org_settings))

        await organization_storage.add_provider_config(OpenAIConfig(api_key="h"))

        settings = await org_col.find_one({"tenant": TENANT})
        doc = OrganizationDocument.model_validate(settings)
        assert doc.providers and len(doc.providers) == 1

        await organization_storage.add_provider_config(OpenAIConfig(api_key="h"))

        settings = await org_col.find_one({"tenant": TENANT})
        doc = OrganizationDocument.model_validate(settings)
        assert doc.providers and len(doc.providers) == 2
        assert doc.providers[0].preserve_credits is False
        assert doc.providers[1].preserve_credits is False

        org_settings = await organization_storage.get_organization()
        for provider in org_settings.providers:
            assert isinstance(provider, DecryptableProviderSettings)
            decrypted = provider.decrypt()
            assert isinstance(decrypted, OpenAIConfig)
            assert decrypted.api_key == "h"

    async def test_add_preserve_credits(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
        mock_encryption: Encryption,
    ) -> None:
        # First, insert the organization document to ensure it exists
        org_settings = OrganizationDocument(tenant=TENANT, slug="", providers=[])
        await org_col.insert_one(dump_model(org_settings))

        await organization_storage.add_provider_config(OpenAIConfig(api_key="h"), preserve_credits=True)

        settings = await org_col.find_one({"tenant": TENANT})
        doc = OrganizationDocument.model_validate(settings)
        assert doc.providers and len(doc.providers) == 1
        assert doc.providers[0].preserve_credits is True


class TestDeleteProviderConfig:
    async def test_delete(self, organization_storage: MongoOrganizationStorage, org_col: AsyncCollection) -> None:
        # First, insert the organization document to ensure it exists
        org_settings = OrganizationDocument(tenant=TENANT, slug="", providers=[])
        await org_col.insert_one(dump_model(org_settings))

        settings = await organization_storage.add_provider_config(OpenAIConfig(api_key="h"))
        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert len(doc["providers"]) == 1, "sanity"

        await organization_storage.delete_provider_config(settings.id)

        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert len(doc["providers"]) == 0, "sanity"

        with pytest.raises(ObjectNotFoundException):
            await organization_storage.delete_provider_config(settings.id)


class TestUpdateSlug:
    async def test_update(self, organization_storage: MongoOrganizationStorage, org_col: AsyncCollection) -> None:
        # First, insert the organization document to ensure it exists
        org_settings = OrganizationDocument(tenant=TENANT, org_id="o1", slug="", providers=[])
        await org_col.insert_one(dump_model(org_settings))

        # Now proceed with updating the slug
        await organization_storage.update_slug("o1", "slug", "a")

        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert doc["slug"] == "slug"

        await organization_storage.update_slug("o1", "slug2", "b")

        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert doc["slug"] == "slug2"

    async def test_unique(
        self,
        organization_storage: MongoOrganizationStorage,
        other_organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Ensure both organizations exist before updating the slug
        org_settings_1 = OrganizationDocument(tenant=TENANT, org_id="o1", slug="unique_slug_1", providers=[], uid=1)
        org_settings_2 = OrganizationDocument(tenant="tenant_2", org_id="o2", slug="unique_slug_2", providers=[], uid=2)

        # Insert both organizations with unique slugs
        await org_col.insert_one(dump_model(org_settings_1))
        await org_col.insert_one(dump_model(org_settings_2))

        # Update slug for the first organization
        await organization_storage.update_slug("o1", "slug", "b")

        # This should be a no-op (updating with the same slug and org_id)
        await organization_storage.update_slug("o1", "slug", "b")

        # Now try updating the slug in another organization, which should raise a DuplicateValueError
        with pytest.raises(DuplicateValueError):
            await other_organization_storage.update_slug("o2", "slug", "b")


class TestGetPublicOrganization:
    async def test_success(
        self,
        organization_storage: MongoOrganizationStorage,
        other_organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert two organizations for two tenants
        org_settings_1 = OrganizationDocument(
            tenant=TENANT,
            slug="initial_slug",
            org_id="o1",
            providers=[],
            uid=1,
            owner_id="owner1",
        )
        org_settings_2 = OrganizationDocument(
            tenant="tenant_2",
            slug="initial_slug_2",
            org_id="o2",
            providers=[],
            uid=2,
        )

        await org_col.insert_one(dump_model(org_settings_1))
        await org_col.insert_one(dump_model(org_settings_2))

        # Update slug for the first organization
        await organization_storage.update_slug("o1", "slug", "b")

        # Fetch the updated slug from the first tenant
        org = await organization_storage.get_public_organization("slug")
        assert org.tenant == TENANT
        assert org.uid == 1
        assert org.owner_id == "owner1"
        assert org.org_id == "o1"

        # Fetch the same slug for the second tenant (it should not collide, returning the correct tenant)
        org = await other_organization_storage.get_public_organization("initial_slug_2")
        assert org.tenant == "tenant_2"
        assert org.uid == 2

    async def test_not_found(self, organization_storage: MongoOrganizationStorage, org_col: AsyncCollection) -> None:
        # Insert an organization to ensure it exists
        org_settings = OrganizationDocument(tenant=TENANT, slug="initial_slug", providers=[])
        await org_col.insert_one(dump_model(org_settings))

        # Update the slug for the organization
        await organization_storage.update_slug("o1", "slug", "b")

        # Try to fetch a non-existent slug, expecting an ObjectNotFoundException
        with pytest.raises(ObjectNotFoundException):
            await organization_storage.get_public_organization("slug1")


class TestFindTenantForOrgId:
    @pytest.fixture(scope="function", autouse=True)
    async def inserted_orgs(self, organization_storage: MongoOrganizationStorage, org_col: AsyncCollection):
        orgs = [
            {
                "tenant": "t2",
                "domain": "workflowai.com",
                "slug": "slug1",
                "org_id": "o2",
                "uid": 1,
            },
            {
                "tenant": "t3",
                "domain": "workflowai.dev",
                "slug": "slug2",
                "org_id": "o3",
                "uid": 2,
            },
            {
                "tenant": "t4",
                "domain": "workflowai.org",
                "slug": "slug3",
                "org_id": "o4",
                "uid": 3,
            },
            {"tenant": "t5", "org_id": "o5", "uid": 4},
        ]
        await org_col.insert_many(orgs)
        return [OrganizationDocument.model_validate(org) for org in orgs]

    async def test_success(
        self,
        organization_storage: MongoOrganizationStorage,
    ) -> None:
        new_org_id = await organization_storage.find_tenant_for_org_id("o2")
        assert new_org_id.tenant == "t2"

    async def test_not_found(
        self,
        organization_storage: MongoOrganizationStorage,
    ) -> None:
        with pytest.raises(ObjectNotFoundException):
            # Using a domain here to make sure
            await organization_storage.find_tenant_for_org_id(org_id="workflowai.com")

    async def test_deprecated_user(
        self,
        organization_storage: MongoOrganizationStorage,
    ) -> None:
        org = await organization_storage.find_tenant_for_deprecated_user(domain="workflowai.com")
        assert org.tenant == "t2"

    async def test_deprecated_user_not_found(
        self,
        organization_storage: MongoOrganizationStorage,
    ) -> None:
        with pytest.raises(ObjectNotFoundException):
            await organization_storage.find_tenant_for_deprecated_user(domain="blabla")


class TestFindTenantForOwnerId:
    async def test_find_tenant_for_owner_id_success(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert a user-owned tenant without org_id
        owner_id = "owner123"
        await org_col.insert_one(
            dump_model(
                OrganizationDocument(
                    tenant="t6",
                    owner_id=owner_id,
                ),
            ),
        )

        # Find the tenant by owner_id
        tenant = await organization_storage.find_tenant_for_owner_id(owner_id)
        assert tenant.tenant == "t6"
        assert tenant.owner_id == owner_id
        assert tenant.org_id is None

    async def test_find_tenant_for_owner_id_not_found(
        self,
        organization_storage: MongoOrganizationStorage,
    ) -> None:
        # Try to find a tenant with non-existent owner_id
        with pytest.raises(ObjectNotFoundException):
            await organization_storage.find_tenant_for_owner_id("nonexistent_owner")

    async def test_find_tenant_for_owner_id_with_org_id_not_found(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert a tenant with both owner_id and org_id
        owner_id = "owner123"
        await org_col.insert_one(
            dump_model(
                OrganizationDocument(
                    tenant="t6",
                    owner_id=owner_id,
                    org_id="org123",  # Having org_id should prevent finding by owner_id
                ),
            ),
        )

        # Try to find the tenant by owner_id - should fail because org_id exists
        with pytest.raises(ObjectNotFoundException):
            await organization_storage.find_tenant_for_owner_id(owner_id)

    async def test_find_tenant_for_owner_id_unique(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert two tenants with the same owner_id but one with org_id
        owner_id = "owner123"
        await org_col.insert_one(dump_model(OrganizationDocument(tenant="t6", owner_id=owner_id, uid=1)))

        # Try to insert another tenant with the same owner_id
        with pytest.raises(DuplicateKeyError):
            await org_col.insert_one(dump_model(OrganizationDocument(tenant="t7", owner_id=owner_id, uid=2)))

        # But should be able to insert one with org_id
        await org_col.insert_one(
            dump_model(OrganizationDocument(tenant="t7", owner_id=owner_id, org_id="org123", uid=3)),
        )

        # But should be able to insert one with a different org_id
        await org_col.insert_one(
            dump_model(OrganizationDocument(tenant="t8", owner_id=owner_id, org_id="org456", uid=4)),
        )

        # But should be able to insert one with a same org_id
        with pytest.raises(DuplicateKeyError):
            await org_col.insert_one(
                dump_model(OrganizationDocument(tenant="t9", owner_id=owner_id, org_id="org456", uid=5)),
            )


class TestIncrementCredits:
    async def test_existing_org(self, organization_storage: MongoOrganizationStorage, org_col: AsyncCollection) -> None:
        await org_col.insert_one(
            dump_model(OrganizationDocument(tenant=TENANT, current_credits_usd=10, added_credits_usd=20)),
        )
        await organization_storage.add_credits_to_tenant(TENANT, 10)

        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert doc["current_credits_usd"] == 20
        assert doc["added_credits_usd"] == 30

        org = await organization_storage.get_organization()
        assert org.current_credits_usd == 20
        assert org.added_credits_usd == 30

    async def test_org_with_credits_missing(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Credit fields will not be present
        raw = dump_model(OrganizationDocument(tenant=TENANT, current_credits_usd=10, added_credits_usd=20))
        del raw["current_credits_usd"]
        del raw["added_credits_usd"]
        await org_col.insert_one(raw)

        doc = await org_col.find_one({"tenant": TENANT})
        assert doc
        assert "current_credits_usd" not in doc
        assert "added_credits_usd" not in doc

        await organization_storage.add_credits_to_tenant(TENANT, 10)

        doc = await organization_storage.get_organization()
        assert doc.current_credits_usd == 10
        assert doc.added_credits_usd == 10

    async def test_clears_payment_failure_and_low_credits_email(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert org with payment failure and low credits email sent
        now = datetime.now(timezone.utc).replace(microsecond=0)
        await org_col.insert_one(
            dump_model(
                OrganizationDocument(
                    tenant=TENANT,
                    current_credits_usd=10,
                    added_credits_usd=20,
                    payment_failure=PaymentFailureSchema(
                        failure_code="payment_failed",
                        failure_reason="Test failure",
                        failure_date=now,
                    ),
                    low_credits_email_sent=[
                        OrganizationDocument.LowCreditsEmailSent(
                            threshold_cts=100,
                            sent_at=now,
                        ),
                    ],
                ),
            ),
        )

        # Add credits and verify flags are cleared
        await organization_storage.add_credits_to_tenant(TENANT, 10)

        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert doc["current_credits_usd"] == 20
        assert doc["added_credits_usd"] == 30
        assert "payment_failure" not in doc
        assert "low_credits_email_sent" not in doc

        org = await organization_storage.get_organization()
        assert org.current_credits_usd == 20
        assert org.added_credits_usd == 30
        assert org.payment_failure is None


class TestDecrementCredits:
    async def test_existing_org(self, organization_storage: MongoOrganizationStorage, org_col: AsyncCollection) -> None:
        await org_col.insert_one(
            dump_model(OrganizationDocument(tenant=TENANT, current_credits_usd=5, added_credits_usd=20)),
        )
        await organization_storage.decrement_credits(TENANT, 10)

        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert doc["current_credits_usd"] == -5
        assert doc["added_credits_usd"] == 20

        org = await organization_storage.get_organization()
        assert org.current_credits_usd == -5
        assert org.added_credits_usd == 20

    async def test_org_with_credits_missing(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Credit fields will not be present
        raw = dump_model(OrganizationDocument(tenant=TENANT, current_credits_usd=10, added_credits_usd=20))
        del raw["current_credits_usd"]
        del raw["added_credits_usd"]
        await org_col.insert_one(raw)

        doc = await org_col.find_one({"tenant": TENANT})
        assert doc
        assert "current_credits_usd" not in doc
        assert "added_credits_usd" not in doc

        await organization_storage.decrement_credits(TENANT, 10)

        doc = await organization_storage.get_organization()
        assert doc.current_credits_usd == -10
        assert doc.added_credits_usd == 0


class TestCreateOrganization:
    async def test_create_organization(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Create a new organization
        new_org_settings = TenantData(
            tenant="new_tenant",
            slug="new_slug",
            org_id="new_org_id",
            added_credits_usd=5.0,
            current_credits_usd=5.0,
        )
        created_org = await organization_storage.create_organization(new_org_settings)

        # Fetch the created organization document
        doc = await org_col.find_one({"tenant": "new_tenant"})
        assert doc is not None
        assert doc["tenant"] == "new_tenant"
        assert doc["slug"] == "new_slug"
        assert doc["added_credits_usd"] == 5.0
        assert doc["current_credits_usd"] == 5.0
        assert doc["org_id"] == "new_org_id"
        assert doc["no_tasks_yet"] is True
        assert doc["uid"]

        # Validate the created organization settings
        assert created_org.tenant == "new_tenant"
        assert created_org.slug == "new_slug"
        assert created_org.added_credits_usd == 5.0
        assert created_org.current_credits_usd == 5.0
        assert created_org.org_id == "new_org_id"
        assert created_org.uid == doc["uid"]


class TestAdd5CreditsForFirstTask:
    async def test_add_5_credits_for_first_task(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert an organization document with no tasks yet
        org_settings = OrganizationDocument(tenant=TENANT, slug="", providers=[], no_tasks_yet=True)
        await org_col.insert_one(dump_model(org_settings))

        # Add 5 credits for the first task
        await organization_storage.add_5_credits_for_first_task()

        # Fetch the updated organization document
        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert doc["current_credits_usd"] == 5
        assert doc["added_credits_usd"] == 5
        assert "no_tasks_yet" not in doc

        # Attempt to add 5 credits again, expecting an ObjectNotFoundException
        with pytest.raises(ObjectNotFoundException):
            await organization_storage.add_5_credits_for_first_task()


class TestDeleteOrganization:
    async def test_delete_organization(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
        frozen_time: FrozenDateTimeFactory,
    ) -> None:
        await org_col.insert_one(dump_model(OrganizationDocument(tenant="t1", slug="slug1", org_id="o1", uid=1)))

        # Check that it's not possible to insert another organization with the same slug
        same_slug_org = OrganizationDocument(tenant="t2", slug="slug1", org_id="o2", uid=2)
        with pytest.raises(DuplicateKeyError):
            await org_col.insert_one(dump_model(same_slug_org))

        # Delete the organization
        await organization_storage.delete_organization("o1")

        # Check that we can insert another organization with the same slug
        await org_col.insert_one(dump_model(same_slug_org))

        doc = await org_col.find_one({"org_id": "o1"})
        assert doc
        assert doc["slug"] == "__deleted__.2024-08-12T00:00:00.slug1"
        assert doc["deleted"] is True

        frozen_time.tick()

        # Check that we can delete an organization with the same slug again
        await organization_storage.delete_organization("o2")


class TestCreateAPIKeyForOrganization:
    async def test_api_keys(self, organization_storage: MongoOrganizationStorage, org_col: AsyncCollection) -> None:
        org_settings = OrganizationDocument(tenant=TENANT, slug="simple_slug", providers=[], no_tasks_yet=True)
        await org_col.insert_one(dump_model(org_settings))

        name = "test key"
        hashed_key = "hashed123"
        partial_key = "sk-123****"
        created_by = UserIdentifier(user_id="user1", user_email="test@example.com")

        doc = await organization_storage.create_api_key_for_organization(
            name=name,
            hashed_key=hashed_key,
            partial_key=partial_key,
            created_by=created_by,
        )

        assert isinstance(doc, APIKey)
        assert doc.name == name
        assert doc.partial_key == partial_key
        assert doc.created_by == created_by
        assert doc.last_used_at is None
        assert isinstance(doc.created_at, datetime)

    async def test_duplicate_key_different_org(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        await organization_storage.create_organization(
            TenantData(
                tenant=TENANT,
                slug="simple_slug",
                org_id="o1",
                added_credits_usd=5.0,
                current_credits_usd=5.0,
            ),
        )
        await organization_storage.create_organization(
            TenantData(
                tenant="tenant2",
                slug="tenant2_slug",
                org_id="o2",
                added_credits_usd=5.0,
                current_credits_usd=5.0,
            ),
        )
        name = "test key"
        hashed_key = "hashed123"
        partial_key = "sk-123****"
        created_by = UserIdentifier(user_id="user1", user_email="test@example.com")
        await organization_storage._find_one_and_update_without_tenant(  # pyright: ignore
            {"tenant": "tenant2"},
            {
                "$push": {
                    "api_keys": dump_model(
                        APIKeyDocument(
                            name=name,
                            hashed_key=hashed_key,
                            partial_key=partial_key,
                            created_by=created_by,
                            created_at=datetime.now(timezone.utc),
                        ),
                    ),
                },
            },
        )

        with pytest.raises(DuplicateValueError):
            await organization_storage.create_api_key_for_organization(
                name=name,
                hashed_key=hashed_key,
                partial_key=partial_key,
                created_by=created_by,
            )


class TestGetAPIKeysForOrganization:
    async def test_get_api_keys_for_organization(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        await org_col.insert_one(
            dump_model(
                OrganizationDocument(
                    tenant=TENANT,
                    slug="simple_slug",
                    providers=[],
                    no_tasks_yet=True,
                    api_keys=[
                        APIKeyDocument(
                            name="test key",
                            hashed_key="hashed123",
                            partial_key="sk-123****",
                            created_by=UserIdentifier(user_id="user1", user_email="test@example.com"),
                            created_at=datetime.now(timezone.utc),
                        ),
                        APIKeyDocument(
                            name="test key 2",
                            hashed_key="hashed456",
                            partial_key="sk-456****",
                            created_by=UserIdentifier(user_id="user1", user_email="test@example.com"),
                            created_at=datetime.now(timezone.utc),
                        ),
                    ],
                ),
            ),
        )

        keys = await organization_storage.get_api_keys_for_organization()
        assert len(keys) == 2
        assert all(isinstance(key, APIKey) for key in keys)
        assert all(key.name in ["test key", "test key 2"] for key in keys)  # type: ignore

    async def test_get_api_keys_for_multiple_orgs(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        await org_col.insert_one(
            dump_model(
                OrganizationDocument(
                    tenant=TENANT,
                    slug="simple_slug",
                    providers=[],
                    no_tasks_yet=True,
                    uid=1,
                    api_keys=[
                        APIKeyDocument(
                            name="test key 4",
                            hashed_key="hashed123",
                            partial_key="sk-123****",
                            created_by=UserIdentifier(user_id="user1", user_email="test@example.com"),
                            created_at=datetime.now(timezone.utc),
                        ),
                        APIKeyDocument(
                            name="test key 5",
                            hashed_key="hashed456",
                            partial_key="sk-456****",
                            created_by=UserIdentifier(user_id="user1", user_email="test@example.com"),
                            created_at=datetime.now(timezone.utc),
                        ),
                    ],
                ),
            ),
        )

        await org_col.insert_one(
            dump_model(
                OrganizationDocument(
                    tenant="tenant2",
                    slug="tenant2_slug",
                    providers=[],
                    no_tasks_yet=True,
                    uid=2,
                    api_keys=[
                        APIKeyDocument(
                            name="test key 6",
                            hashed_key="hashed789",
                            partial_key="sk-789****",
                            created_by=UserIdentifier(user_id="user1", user_email="test@example.com"),
                            created_at=datetime.now(timezone.utc),
                        ),
                        APIKeyDocument(
                            name="test key 7",
                            hashed_key="hashed1011",
                            partial_key="sk-1011****",
                            created_by=UserIdentifier(user_id="user1", user_email="test@example.com"),
                            created_at=datetime.now(timezone.utc),
                        ),
                    ],
                ),
            ),
        )

        keys = await organization_storage.get_api_keys_for_organization()
        assert len(keys) == 2
        assert all(isinstance(key, APIKey) for key in keys)
        assert all(key.name in ["test key 4", "test key 5"] for key in keys)  # type: ignore


class TestDeleteAPIKeyForOrganization:
    async def test_delete_api_key_for_organization(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        await org_col.insert_one(
            dump_model(OrganizationDocument(tenant=TENANT, slug="simple_slug", providers=[], no_tasks_yet=True)),
        )
        name = "test key"
        hashed_key = "hashed123"
        partial_key = "sk-123****"
        created_by = UserIdentifier(user_id="user1", user_email="test@example.com")

        doc = await organization_storage.create_api_key_for_organization(
            name=name,
            hashed_key=hashed_key,
            partial_key=partial_key,
            created_by=created_by,
        )
        # Delete the key
        result = await organization_storage.delete_api_key_for_organization(key_id=str(doc.id))
        assert result is True

        # Verify key is deleted
        keys = await organization_storage.get_api_keys_for_organization()
        assert not any(key.id == doc.id for key in keys)

    async def test_delete_last_api_key_duplicate(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        """Test that reproduces the MongoDB index issue when deleting the last API key on 2 tenants

        With the old index ({"api_keys": {"$exists": True}}), having 2 different tenants delete all their API keys
        will create a duplicate key error because the index would still match the document even with an
        empty api_keys array.
        """

        # Create organizations for both tenants
        await org_col.insert_one(
            dump_model(OrganizationDocument(tenant=TENANT, uid=organization_storage._tenant_uid, slug="1")),
        )
        await org_col.insert_one(dump_model(OrganizationDocument(tenant="t2", uid=2, slug="2")))

        # Manually instantiate storage for tenant 2
        tenant2_storage = MongoOrganizationStorage(
            tenant=("t2", 2),
            collection=org_col,
            encryption=organization_storage.encryption,
        )

        # Create API key for tenant 1 and tenant 2
        tenant1_key = await organization_storage.create_api_key_for_organization(
            name="tenant1 key",
            hashed_key="hashed123",
            partial_key="sk-123****",
            created_by=UserIdentifier(user_id="user1", user_email="test@example.com"),
        )

        tenant2_key = await tenant2_storage.create_api_key_for_organization(
            name="tenant2 key",
            hashed_key="hashed456",
            partial_key="sk-456****",
            created_by=UserIdentifier(user_id="user2", user_email="test2@example.com"),
        )

        # Delete the API key for tenant 1
        result = await organization_storage.delete_api_key_for_organization(key_id=str(tenant1_key.id))
        assert result is True

        # Delete the API key for tenant 2
        result = await tenant2_storage.delete_api_key_for_organization(key_id=str(tenant2_key.id))
        assert result is True

        # Verify no keys remain for either tenant
        tenant1_keys = await organization_storage.get_api_keys_for_organization()
        tenant2_keys = await tenant2_storage.get_api_keys_for_organization()
        assert len(tenant1_keys) == 0
        assert len(tenant2_keys) == 0


class TestFindTenantForAPIKey:
    async def test_validate_key(self, organization_storage: MongoOrganizationStorage, org_col: AsyncCollection) -> None:
        org_settings = OrganizationDocument(tenant=TENANT, slug="simple_slug", providers=[], no_tasks_yet=True)
        await org_col.insert_one(dump_model(org_settings))
        # Create a key to validate
        name = "test key 3"
        created_by = UserIdentifier(user_id="user1", user_email="test@example.com")

        random_key = secrets.token_urlsafe(32)
        key = f"wai-{random_key}"
        hashed_key = hashlib.sha256(key.encode()).hexdigest()
        partial_key = f"{key[:9]}****"

        await organization_storage.create_api_key_for_organization(
            name=name,
            hashed_key=hashed_key,
            partial_key=partial_key,
            created_by=created_by,
        )

        # Validate the key
        authenticated_org = await organization_storage.find_tenant_for_api_key(hashed_key=hashed_key)
        assert authenticated_org is not None
        assert authenticated_org.tenant == TENANT

    async def test_find_tenant_for_api_key_not_found(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert an organization without any API keys
        await org_col.insert_one(
            dump_model(OrganizationDocument(tenant=TENANT, slug="simple_slug", providers=[], no_tasks_yet=True)),
        )

        # Try to find tenant with a non-existent API key
        with pytest.raises(ObjectNotFoundException):
            await organization_storage.find_tenant_for_api_key(hashed_key="non_existent_key")


class TestUpdateAPIKeyLastUsedAt:
    @pytest.fixture
    def base_doc(self):
        return OrganizationDocument(
            tenant=TENANT,
            api_keys=[
                APIKeyDocument(
                    name="test key",
                    hashed_key="hashed123",
                    partial_key="sk-123****",
                    created_by=UserIdentifier(),
                ),
            ],
        )

    async def test_first_time(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
        base_doc: OrganizationDocument,
    ):
        """Check that we can update the api key last update at when the last used at is None"""
        # Create an org with a single api key that has never been used
        assert base_doc.api_keys and base_doc.api_keys[0].last_used_at is None, "sanity"
        await org_col.insert_one(dump_model(base_doc))

        # Update the last_used_at timestamp
        now = datetime.now(timezone.utc).replace(microsecond=0)
        await organization_storage.update_api_key_last_used_at(hashed_key="hashed123", now=now)

        # Verify the update
        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        api_key = next(key for key in doc["api_keys"] if key["hashed_key"] == "hashed123")
        assert api_key["last_used_at"] == now

    async def test_no_update_if_newer(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
        base_doc: OrganizationDocument,
    ) -> None:
        assert base_doc.api_keys
        future_time = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        base_doc.api_keys[0].last_used_at = future_time
        await org_col.insert_one(dump_model(base_doc))

        # Try to update with an older timestamp
        past_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        await organization_storage.update_api_key_last_used_at(hashed_key="hashed123", now=past_time)

        # Verify the timestamp wasn't updated
        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        api_key = next(key for key in doc["api_keys"] if key["hashed_key"] == "hashed123")
        assert api_key["last_used_at"] == future_time

    async def test_update_api_key_last_used_at_multiple_keys(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
        base_doc: OrganizationDocument,
    ) -> None:
        assert base_doc.api_keys
        base_doc.api_keys.append(
            APIKeyDocument(
                name="test key 2",
                hashed_key="hashed456",
                partial_key="sk-456****",
                created_by=UserIdentifier(),
            ),
        )
        await org_col.insert_one(dump_model(base_doc))

        # Update the last_used_at timestamp for the first key
        now = datetime.now(timezone.utc).replace(microsecond=0)
        await organization_storage.update_api_key_last_used_at(hashed_key="hashed123", now=now)

        # Verify only the first key was updated
        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert doc["api_keys"][0]["last_used_at"] == now
        assert doc["api_keys"][1].get("last_used_at") is None


class TestUpdateCustomerId:
    async def test_update_customer_id(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        await org_col.insert_one(
            dump_model(OrganizationDocument(tenant=TENANT, slug="simple_slug", providers=[], no_tasks_yet=True)),
        )
        await organization_storage.update_customer_id("cus_123")

        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert doc["stripe_customer_id"] == "cus_123"

    async def test_update_customer_id_with_existing_customer(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        await org_col.insert_one(
            dump_model(
                OrganizationDocument(
                    tenant=TENANT,
                    slug="simple_slug",
                    providers=[],
                    no_tasks_yet=True,
                    stripe_customer_id="cus_123",
                ),
            ),
        )

        with pytest.raises(ObjectNotFoundException):
            await organization_storage.update_customer_id("cus_456")

        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert doc["stripe_customer_id"] == "cus_123"


class TestAutomaticPayment:
    async def test_opt_in_automatic_payment(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ):
        await org_col.insert_one(
            dump_model(OrganizationDocument(tenant=TENANT, slug="simple_slug", providers=[], no_tasks_yet=True)),
        )

        await organization_storage.update_automatic_payment(opt_in=True, threshold=10, balance_to_maintain=100)

        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert doc["automatic_payment_enabled"] is True
        assert doc["automatic_payment_threshold"] == 10
        assert doc["automatic_payment_balance_to_maintain"] == 100

    async def test_opt_out_automatic_payment(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ):
        await org_col.insert_one(
            dump_model(OrganizationDocument(tenant=TENANT, slug="simple_slug", providers=[], no_tasks_yet=True)),
        )

        await organization_storage.update_automatic_payment(opt_in=False, threshold=None, balance_to_maintain=None)

        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert doc["automatic_payment_enabled"] is False
        assert doc["automatic_payment_threshold"] is None
        assert doc["automatic_payment_balance_to_maintain"] is None


class TestFindAnonymousTenant:
    async def test_find_anonymous_tenant_success(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert an anonymous organization without org_id
        await org_col.insert_one(dump_model(OrganizationDocument(tenant="user123", anonymous_user_id="user123")))

        # Find the anonymous tenant
        org = await organization_storage.find_anonymous_tenant("user123")
        assert org.tenant == "user123"
        assert org.org_id is None

    async def test_find_anonymous_tenant_not_found(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        with pytest.raises(ObjectNotFoundException):
            await organization_storage.find_anonymous_tenant("nonexistent_user")

    async def test_find_anonymous_tenant_with_org_id_not_found(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert an organization with org_id that should not be returned
        await org_col.insert_one(
            dump_model(
                OrganizationDocument(
                    tenant="user123",
                    slug="not_anonymous_slug",
                    anonymous_user_id="user123",
                    org_id="org123",
                ),
            ),
        )

        with pytest.raises(ObjectNotFoundException):
            await organization_storage.find_anonymous_tenant("user123")

    async def test_anonymous_user_id_unique(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert multiple anonymous organizations
        await org_col.insert_one(dump_model(OrganizationDocument(tenant="user123", anonymous_user_id="user123")))
        with pytest.raises(DuplicateKeyError):
            await org_col.insert_one(dump_model(OrganizationDocument(tenant="user123", anonymous_user_id="user123")))


class TestMigrateTenantToUser:
    async def test_success(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert an anonymous tenant
        anon_id = "user123"
        await org_col.insert_one(
            dump_model(
                OrganizationDocument(
                    tenant=TENANT,
                    anonymous_user_id=anon_id,
                ),
            ),
        )

        # Migrate the tenant to a user
        owner_id = "owner123"
        migrated_org = await organization_storage.migrate_tenant_to_user(
            owner_id=owner_id,
            org_slug="bla",
            anon_id=anon_id,
        )

        # Verify the migration
        assert migrated_org.tenant == TENANT
        assert migrated_org.owner_id == owner_id
        assert migrated_org.anonymous_user_id == anon_id
        assert migrated_org.org_id is None

        # Verify in database
        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert doc["owner_id"] == owner_id
        assert doc["previous_anonymous_user_id"] == anon_id
        assert "anonymous_user_id" not in doc
        assert doc["slug"] == "bla"
        assert "org_id" not in doc

    async def test_not_found_when_has_owner_id(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert an anonymous tenant that already has an owner_id
        anon_id = "user123"
        existing_owner_id = "existing_owner"
        await org_col.insert_one(
            dump_model(
                OrganizationDocument(
                    tenant=TENANT,
                    anonymous_user_id=anon_id,
                    owner_id=existing_owner_id,
                ),
            ),
        )

        # Attempt to migrate should raise ObjectNotFoundException
        with pytest.raises(ObjectNotFoundException):
            await organization_storage.migrate_tenant_to_user(
                owner_id="new_owner",
                org_slug=None,
                anon_id=anon_id,
            )

        # Verify the document wasn't modified
        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert doc["owner_id"] == existing_owner_id
        assert doc["anonymous_user_id"] == anon_id

    async def test_not_found_when_has_org_id(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert an anonymous tenant that already has an org_id
        anon_id = "user123"
        org_id = "org123"
        await org_col.insert_one(
            dump_model(
                OrganizationDocument(
                    tenant=TENANT,
                    anonymous_user_id=anon_id,
                    org_id=org_id,
                ),
            ),
        )

        # Attempt to migrate should raise ObjectNotFoundException
        with pytest.raises(ObjectNotFoundException):
            await organization_storage.migrate_tenant_to_user(
                owner_id="new_owner",
                org_slug=None,
                anon_id=anon_id,
            )

        # Verify the document wasn't modified
        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert doc["org_id"] == org_id
        assert doc["anonymous_user_id"] == anon_id
        assert "owner_id" not in doc

    async def test_unique_anonymous_user_id(
        self,
        organization_storage: MongoOrganizationStorage,
    ) -> None:
        # Insert two anonymous organizations with the same anonymous_user_id
        anon_id = "user123"
        await organization_storage.create_organization(
            TenantData(
                tenant="1",
                anonymous_user_id=anon_id,
            ),
        )

        # I should not be able to insert another organization with the same anonymous_user_id
        with pytest.raises(DuplicateValueError):
            await organization_storage.create_organization(
                TenantData(
                    tenant="2",
                    anonymous_user_id=anon_id,
                ),
            )

        # But if I migrate to a user
        await organization_storage.migrate_tenant_to_user(
            owner_id="owner123",
            org_slug="bla",
            anon_id=anon_id,
        )

        # I should be able to insert another organization with the same anonymous_user_id
        await organization_storage.create_organization(
            TenantData(
                tenant="3",
                anonymous_user_id=anon_id,
            ),
        )


class TestMigrateTenantToOrganization:
    async def test_migrate_from_anonymous(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert an anonymous tenant
        anon_id = "user123"
        await org_col.insert_one(
            dump_model(
                OrganizationDocument(
                    tenant=TENANT,
                    anonymous_user_id=anon_id,
                ),
            ),
        )

        # Migrate the tenant to an organization
        migrated_org = await organization_storage.migrate_tenant_to_organization(
            org_id="org123",
            org_slug="my-org",
            owner_id="owner123",
            anon_id=anon_id,
        )

        # Verify the migration
        assert migrated_org.tenant == TENANT
        assert migrated_org.org_id == "org123"
        assert migrated_org.slug == "my-org"
        assert migrated_org.owner_id == "owner123"
        assert migrated_org.anonymous_user_id == anon_id

        # Verify in database
        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert doc["org_id"] == "org123"
        assert doc["slug"] == "my-org"
        assert doc["owner_id"] == "owner123"
        assert doc["previous_anonymous_user_id"] == anon_id
        assert "anonymous_user_id" not in doc

    async def test_migrate_from_user(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert a user-owned tenant
        owner_id = "owner123"
        await org_col.insert_one(
            dump_model(
                OrganizationDocument(
                    tenant=TENANT,
                    owner_id=owner_id,
                ),
            ),
        )

        # Migrate the tenant to an organization
        org_id = "org123"
        org_slug = "my-org"
        migrated_org = await organization_storage.migrate_tenant_to_organization(
            org_id=org_id,
            org_slug=org_slug,
            owner_id=owner_id,
            anon_id=None,
        )

        # Verify the migration
        assert migrated_org.tenant == TENANT
        assert migrated_org.org_id == org_id
        assert migrated_org.slug == org_slug
        assert migrated_org.owner_id == owner_id
        assert migrated_org.anonymous_user_id is None

        # Verify in database
        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert doc["org_id"] == org_id
        assert doc["slug"] == org_slug
        assert doc["owner_id"] == owner_id
        assert "anonymous_user_id" not in doc

    async def test_not_found_when_already_has_org_id(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert a tenant that already has an org_id
        owner_id = "owner123"
        existing_org_id = "existing_org"
        await org_col.insert_one(
            dump_model(
                OrganizationDocument(
                    tenant=TENANT,
                    owner_id=owner_id,
                    org_id=existing_org_id,
                ),
            ),
        )

        # Attempt to migrate should raise ObjectNotFoundException
        with pytest.raises(ObjectNotFoundException):
            await organization_storage.migrate_tenant_to_organization(
                org_id="new_org",
                org_slug="new-slug",
                owner_id=owner_id,
                anon_id=None,
            )

        # Verify the document wasn't modified
        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert doc["org_id"] == existing_org_id
        assert doc["owner_id"] == owner_id

    async def test_not_found_when_no_matching_tenant(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert a tenant with different owner_id and anon_id
        await org_col.insert_one(
            dump_model(
                OrganizationDocument(
                    tenant=TENANT,
                    owner_id="other_owner",
                    anonymous_user_id="other_anon",
                ),
            ),
        )

        # Attempt to migrate should raise ObjectNotFoundException
        with pytest.raises(ObjectNotFoundException):
            await organization_storage.migrate_tenant_to_organization(
                org_id="new_org",
                org_slug="new-slug",
                owner_id="owner123",
                anon_id="user123",
            )

        # Verify the document wasn't modified
        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert doc["owner_id"] == "other_owner"
        assert doc["anonymous_user_id"] == "other_anon"
        assert "org_id" not in doc

    async def test_raises_value_error_when_no_identifiers(
        self,
        organization_storage: MongoOrganizationStorage,
    ) -> None:
        # Attempt to migrate without owner_id or anon_id should raise ValueError
        with pytest.raises(ValueError, match="No owner_id or anon_id provided"):
            await organization_storage.migrate_tenant_to_organization(
                org_id="new_org",
                org_slug="new-slug",
                owner_id=None,
                anon_id=None,
            )

    async def test_unique_anonymous_user_id(
        self,
        organization_storage: MongoOrganizationStorage,
    ) -> None:
        # Insert two anonymous organizations with the same anonymous_user_id
        anon_id = "user123"
        await organization_storage.create_organization(
            TenantData(
                tenant="1",
                anonymous_user_id=anon_id,
            ),
        )

        # I should not be able to insert another organization with the same anonymous_user_id
        with pytest.raises(DuplicateValueError):
            await organization_storage.create_organization(
                TenantData(
                    tenant="2",
                    anonymous_user_id=anon_id,
                ),
            )

        # But if I migrate to a user
        await organization_storage.migrate_tenant_to_organization(
            org_id="org123",
            org_slug="bla",
            owner_id=None,
            anon_id=anon_id,
        )

        # I should be able to insert another organization with the same anonymous_user_id
        await organization_storage.create_organization(
            TenantData(
                tenant="3",
                anonymous_user_id=anon_id,
            ),
        )


class TestFeedbackSlackHookForTenant:
    async def test_get_feedback_slack_hook_success(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert an organization with a slack hook
        slack_hook = "https://hooks.slack.com/services/123/456/789"
        await org_col.insert_one(
            dump_model(
                OrganizationDocument(
                    tenant=TENANT,
                    uid=1,
                    feedback_slack_hook=slack_hook,
                ),
            ),
        )

        # Get the slack hook
        result = await organization_storage.feedback_slack_hook_for_tenant(tenant_uid=1)
        assert result == slack_hook

    async def test_get_feedback_slack_hook_not_found(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert an organization without a slack hook
        await org_col.insert_one(
            dump_model(
                OrganizationDocument(
                    tenant=TENANT,
                    uid=1,
                ),
            ),
        )

        # Get the slack hook
        result = await organization_storage.feedback_slack_hook_for_tenant(tenant_uid=1)
        assert result is None

    async def test_get_feedback_slack_hook_org_not_found(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Try to get slack hook for non-existent organization
        with pytest.raises(ObjectNotFoundException):
            await organization_storage.feedback_slack_hook_for_tenant(tenant_uid=999)


class TestAttemptLockForPayment:
    async def test_attempt_lock_for_payment_success(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert a tenant with different owner_id and anon_id
        await org_col.insert_one(dump_model(OrganizationDocument(tenant=TENANT)))

        # Attempt lock for payment
        res = await organization_storage.attempt_lock_for_payment(tenant=TENANT)
        assert res is not None
        assert res.tenant == TENANT

        # Verify the document was locked
        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert doc["locked_for_payment"] is True

        # Now lock it again it should return None
        res = await organization_storage.attempt_lock_for_payment(tenant=TENANT)
        assert res is None


class TestUnlockPaymentForSuccess:
    @pytest.fixture(autouse=True)
    async def lock_inserted_tenant(self, organization_storage: MongoOrganizationStorage, inserted_tenant: str):
        lock = await organization_storage.attempt_lock_for_payment(inserted_tenant)
        assert lock, "sanity check, could not lock org"

    async def test_unlock_payment_for_success(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
        inserted_tenant: str,
    ) -> None:
        # Add initial credits
        await org_col.update_one(
            {"tenant": inserted_tenant},
            {"$set": {"current_credits_usd": 10}},
        )

        # Unlock payment for success with a payment amount
        await organization_storage.unlock_payment_for_success(tenant=inserted_tenant, amount=50)

        # Verify the document was unlocked and credits were updated
        doc = await org_col.find_one({"tenant": inserted_tenant})
        assert doc is not None
        assert "locked_for_payment" not in doc
        assert doc["current_credits_usd"] == 60  # 10 + 50

        # Check that we can still get the tenant
        tenant = await organization_storage.get_organization()
        assert tenant is not None
        assert tenant.locked_for_payment is None
        assert tenant.current_credits_usd == 60

        # And that we can lock it again
        lock = await organization_storage.attempt_lock_for_payment(inserted_tenant)
        assert lock is not None
        assert lock.tenant == inserted_tenant
        assert lock.locked_for_payment is True
        assert lock.current_credits_usd == 60

    async def test_unlock_payment_for_success_no_credits(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
        inserted_tenant: str,
    ) -> None:
        # Unlock payment for success with a payment amount (no initial credits)
        await organization_storage.unlock_payment_for_success(tenant=inserted_tenant, amount=50)

        # Verify the document was unlocked and credits were set
        doc = await org_col.find_one({"tenant": inserted_tenant})
        assert doc is not None
        assert "locked_for_payment" not in doc
        assert doc["current_credits_usd"] == 50

        # Check that we can still get the tenant
        tenant = await organization_storage.get_organization()
        assert tenant is not None
        assert tenant.locked_for_payment is None
        assert tenant.current_credits_usd == 50

        # And that we can lock it again
        lock = await organization_storage.attempt_lock_for_payment(inserted_tenant)
        assert lock is not None
        assert lock.tenant == inserted_tenant
        assert lock.locked_for_payment is True
        assert lock.current_credits_usd == 50

    async def test_unlock_payment_for_success_after_failure(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
        inserted_tenant: str,
    ) -> None:
        # First unlock with a failure
        await organization_storage.unlock_payment_for_failure(
            tenant=inserted_tenant,
            now=datetime.now(timezone.utc).replace(microsecond=0),
            code="internal",
            failure_reason="Test internal error",
        )

        # Now unlock with a success
        lock = await organization_storage.attempt_lock_for_payment(inserted_tenant)
        assert lock is not None, "sanity check, could not lock org"

        await organization_storage.unlock_payment_for_success(tenant=inserted_tenant, amount=50)

        # Verify the document was unlocked and credits were updated
        doc = await org_col.find_one({"tenant": inserted_tenant})
        assert doc is not None
        assert "locked_for_payment" not in doc
        assert "payment_failure" not in doc
        assert doc["current_credits_usd"] == 50


class TestUnlockPaymentForFailure:
    @pytest.fixture(autouse=True)
    async def lock_inserted_tenant(self, organization_storage: MongoOrganizationStorage, inserted_tenant: str):
        lock = await organization_storage.attempt_lock_for_payment(inserted_tenant)
        assert lock, "sanity check, could not lock org"

    async def test_unlock_payment_for_failure_internal(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
        inserted_tenant: str,
    ) -> None:
        # Get current time
        now = datetime.now(timezone.utc).replace(microsecond=0)

        # Unlock payment for failure with internal error
        await organization_storage.unlock_payment_for_failure(
            tenant=inserted_tenant,
            now=now,
            code="internal",
            failure_reason="Test internal error",
        )

        # Verify the document was unlocked and error was recorded
        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert "locked_for_payment" not in doc
        assert doc["payment_failure"] == {
            "failure_code": "internal",
            "failure_reason": "Test internal error",
            "failure_date": now,
        }

        # Check that we can still get the tenant
        tenant = await organization_storage.get_organization()
        assert tenant is not None
        assert tenant.locked_for_payment is None
        assert tenant.payment_failure is not None
        assert tenant.payment_failure.failure_code == "internal"
        assert tenant.payment_failure.failure_reason == "Test internal error"
        assert tenant.payment_failure.failure_date == now

        # And that we can still lock and get the same info
        lock = await organization_storage.attempt_lock_for_payment(inserted_tenant)
        assert lock is not None
        assert lock.tenant == inserted_tenant
        assert lock.locked_for_payment is True
        assert lock.payment_failure is not None
        assert lock.payment_failure.failure_code == "internal"
        assert lock.payment_failure.failure_reason == "Test internal error"
        assert lock.payment_failure.failure_date == now

    async def test_unlock_payment_for_failure_payment_failed(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Get current time
        now = datetime.now(timezone.utc).replace(microsecond=0)

        # Unlock payment for failure with payment_failed error
        await organization_storage.unlock_payment_for_failure(
            tenant=TENANT,
            now=now,
            code="payment_failed",
            failure_reason="Test payment failed error",
        )

        # Verify the document was unlocked and error was recorded
        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert "locked_for_payment" not in doc
        assert doc["payment_failure"] == {
            "failure_code": "payment_failed",
            "failure_reason": "Test payment failed error",
            "failure_date": now,
        }

        # Check that we can still get the tenant
        tenant = await organization_storage.get_organization()
        assert tenant is not None
        assert tenant.locked_for_payment is None
        assert tenant.payment_failure is not None


class TestAddLowCreditsEmailSent:
    @pytest.fixture(autouse=True)
    async def setup_tenant(self, organization_storage: MongoOrganizationStorage, org_col: AsyncCollection):
        # Insert a tenant with initial credits
        await org_col.insert_one(
            dump_model(
                OrganizationDocument(
                    tenant=TENANT,
                    current_credits_usd=10,
                    added_credits_usd=20,
                ),
            ),
        )

    async def test_add_low_credits_email_sent(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Add a low credits email sent record
        threshold_usd = 1.0
        await organization_storage.add_low_credits_email_sent(TENANT, threshold_usd)

        # Verify the record was added
        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert "low_credits_email_sent" in doc
        assert len(doc["low_credits_email_sent"]) == 1
        assert doc["low_credits_email_sent"][0]["threshold_cts"] == 100
        assert isinstance(doc["low_credits_email_sent"][0]["sent_at"], datetime)

        # Verify we can get the tenant and see the record
        tenant = await organization_storage.get_organization()
        assert tenant.low_credits_email_sent_by_threshold is not None
        assert len(tenant.low_credits_email_sent_by_threshold) == 1
        assert 100 in tenant.low_credits_email_sent_by_threshold
        assert isinstance(tenant.low_credits_email_sent_by_threshold[100], datetime)

        # If I try again I will get an object not found exception
        with pytest.raises(ObjectNotFoundException):
            await organization_storage.add_low_credits_email_sent(TENANT, threshold_usd)

    async def test_add_multiple_low_credits_email_sent(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Add multiple low credits email sent records
        thresholds = [1.0, 0.5, 0.25]
        for threshold in thresholds:
            await organization_storage.add_low_credits_email_sent(TENANT, threshold)

        # Verify all records were added
        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert "low_credits_email_sent" in doc
        assert len(doc["low_credits_email_sent"]) == 3

        # Verify we can get the tenant and see all records
        tenant = await organization_storage.get_organization()
        assert tenant.low_credits_email_sent_by_threshold is not None
        assert len(tenant.low_credits_email_sent_by_threshold) == 3
        assert sorted(tenant.low_credits_email_sent_by_threshold.keys()) == sorted(
            [int(round(t * 100)) for t in thresholds],
        )
        assert all(isinstance(t, datetime) for t in tenant.low_credits_email_sent_by_threshold.values())

    async def test_clear_low_credits_email_sent_after_adding_credits(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Add a low credits email sent record
        threshold_cts = 100
        await organization_storage.add_low_credits_email_sent(TENANT, threshold_cts)

        # Verify the record was added
        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert "low_credits_email_sent" in doc
        assert len(doc["low_credits_email_sent"]) == 1

        # Add credits to the tenant
        await organization_storage.add_credits_to_tenant(TENANT, 50)

        # Verify the low credits email sent record was cleared
        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert "low_credits_email_sent" not in doc

        # Verify we can get the tenant and see no records
        tenant = await organization_storage.get_organization()
        assert tenant.low_credits_email_sent_by_threshold is None


class TestCheckUnlockedPaymentFailure:
    async def test_no_payment_failure(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert an organization without any payment failure
        await org_col.insert_one(
            dump_model(
                OrganizationDocument(
                    tenant=TENANT,
                    current_credits_usd=10,
                    added_credits_usd=20,
                ),
            ),
        )

        # Check for payment failure
        failure = await organization_storage.check_unlocked_payment_failure(TENANT)
        assert failure is None

    async def test_with_payment_failure(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert an organization with a payment failure
        now = datetime.now(timezone.utc).replace(microsecond=0)
        await org_col.insert_one(
            dump_model(
                OrganizationDocument(
                    tenant=TENANT,
                    current_credits_usd=10,
                    added_credits_usd=20,
                    payment_failure=PaymentFailureSchema(
                        failure_code="payment_failed",
                        failure_reason="Test failure",
                        failure_date=now,
                    ),
                ),
            ),
        )

        # Check for payment failure
        failure = await organization_storage.check_unlocked_payment_failure(TENANT)
        assert failure is not None
        assert failure.failure_code == "payment_failed"
        assert failure.failure_reason == "Test failure"
        assert failure.failure_date == now

    async def test_locked_organization(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert a locked organization with a payment failure
        now = datetime.now(timezone.utc).replace(microsecond=0)
        await org_col.insert_one(
            dump_model(
                OrganizationDocument(
                    tenant=TENANT,
                    current_credits_usd=10,
                    added_credits_usd=20,
                    locked_for_payment=True,
                    payment_failure=PaymentFailureSchema(
                        failure_code="payment_failed",
                        failure_reason="Test failure",
                        failure_date=now,
                    ),
                ),
            ),
        )

        # Check for payment failure - should return None since organization is locked
        with pytest.raises(ObjectNotFoundException):
            await organization_storage.check_unlocked_payment_failure(TENANT)


class TestPublicOrganizationByTenant:
    async def test_success(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert an organization with public data
        org_settings = OrganizationDocument(
            tenant=TENANT,
            slug="test_slug",
            uid=1,
            org_id="o1",
            owner_id="owner1",
        )
        await org_col.insert_one(dump_model(org_settings))

        # Get the public organization data
        org = await organization_storage.public_organization_by_tenant(TENANT)

        # Verify the returned data
        assert org.tenant == TENANT
        assert org.slug == "test_slug"
        assert org.uid == 1
        assert org.org_id == "o1"
        assert org.owner_id == "owner1"

    async def test_not_found(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert an organization for a different tenant
        org_settings = OrganizationDocument(
            tenant="other_tenant",
            slug="other_slug",
            uid=2,
            org_id="o2",
            owner_id="owner2",
        )
        await org_col.insert_one(dump_model(org_settings))

        # Try to get public organization data for non-existent tenant
        with pytest.raises(ObjectNotFoundException):
            await organization_storage.public_organization_by_tenant(TENANT)

    async def test_anonymous_organization(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert an organization with minimal required data
        org_settings = OrganizationDocument(
            tenant=TENANT,
            uid=3,
        )
        await org_col.insert_one(dump_model(org_settings))

        # Get the public organization data
        org = await organization_storage.public_organization_by_tenant(TENANT)

        # Verify the returned data
        assert org.tenant == TENANT
        assert org.uid == 3
        assert org.org_id is None
        assert org.owner_id is None
        assert org.is_anonymous is True


class TestClearPaymentFailure:
    async def test_clear_payment_failure_success(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert an organization with a payment failure
        now = datetime.now(timezone.utc).replace(microsecond=0)
        await org_col.insert_many(
            [
                dump_model(d)
                for d in [
                    OrganizationDocument(
                        uid=1,
                        tenant=TENANT,
                        current_credits_usd=10,
                        added_credits_usd=20,
                        payment_failure=PaymentFailureSchema(
                            failure_code="payment_failed",
                            failure_reason="Test failure",
                            failure_date=now,
                        ),
                    ),
                    OrganizationDocument(
                        tenant="other_tenant",
                        uid=2,
                        current_credits_usd=10,
                        added_credits_usd=20,
                        payment_failure=PaymentFailureSchema(
                            failure_code="payment_failed1",
                            failure_reason="Test failure 1",
                            failure_date=now,
                        ),
                    ),
                ]
            ],
        )

        # Clear the payment failure
        await organization_storage.clear_payment_failure()

        # Verify the payment failure was cleared
        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert "payment_failure" not in doc

        # Verify we can get the tenant and see no payment failure
        tenant = await organization_storage.get_organization()
        assert tenant.payment_failure is None

        # Verify the other tenant's payment failure was not cleared
        doc = await org_col.find_one({"tenant": "other_tenant"})
        assert doc is not None
        assert "payment_failure" in doc

    async def test_clear_payment_failure_no_failure(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert an organization without any payment failure
        await org_col.insert_one(
            dump_model(
                OrganizationDocument(
                    tenant=TENANT,
                    current_credits_usd=10,
                    added_credits_usd=20,
                ),
            ),
        )

        # Clear the payment failure (should be a no-op)
        await organization_storage.clear_payment_failure()

        # Verify the document remains unchanged
        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert "payment_failure" not in doc

        # Verify we can get the tenant and see no payment failure
        tenant = await organization_storage.get_organization()
        assert tenant.payment_failure is None


class TestSetSlackChannelId:
    async def test_set_slack_channel_id_success(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert an organization without a slack channel ID
        await org_col.insert_one(
            dump_model(
                OrganizationDocument(
                    tenant=TENANT,
                    slug="simple_slug",
                    providers=[],
                    no_tasks_yet=True,
                ),
            ),
        )

        # Set the slack channel ID
        channel_id = "C1234567890"
        await organization_storage.set_slack_channel_id(channel_id)

        # Verify the slack channel ID was set
        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert doc["slack_channel_id"] == channel_id

        # Verify we can get the tenant and see the slack channel ID
        tenant = await organization_storage.get_organization()
        assert tenant.slack_channel_id == channel_id

    async def test_set_slack_channel_id_organization_not_found(
        self,
        organization_storage: MongoOrganizationStorage,
    ) -> None:
        # Try to set slack channel ID for non-existent organization
        with pytest.raises(ObjectNotFoundException):
            await organization_storage.set_slack_channel_id("C1234567890")

    async def test_set_slack_channel_raises_if_already_set(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ) -> None:
        # Insert an organization with a slack channel ID
        await org_col.insert_one(
            dump_model(
                OrganizationDocument(
                    tenant=TENANT,
                    slug="simple_slug",
                ),
            ),
        )

        await organization_storage.set_slack_channel_id("C1234567890")
        # Try to set the slack channel ID again
        with pytest.raises(ObjectNotFoundException):
            await organization_storage.set_slack_channel_id("C1234567890")

    async def test_set_slack_channel_id_none(
        self,
        organization_storage: MongoOrganizationStorage,
        org_col: AsyncCollection,
    ):
        # Insert an organization with a slack channel ID
        await org_col.insert_one(
            dump_model(
                OrganizationDocument(
                    tenant=TENANT,
                    slug="simple_slug",
                ),
            ),
        )
        # I can set the channel id to an empty string
        await organization_storage.set_slack_channel_id("")
        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert doc["slack_channel_id"] == ""

        # now I can't set it again
        with pytest.raises(ObjectNotFoundException):
            await organization_storage.set_slack_channel_id("hello")

        # But i can reset it by using None
        await organization_storage.set_slack_channel_id(None)

        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert "slack_channel_id" not in doc

        # Which allows me to set it again
        await organization_storage.set_slack_channel_id("hello")
        doc = await org_col.find_one({"tenant": TENANT})
        assert doc is not None
        assert doc["slack_channel_id"] == "hello"
