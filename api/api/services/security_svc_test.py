from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from api.dependencies.security import UserClaims
from api.services.security_svc import SecurityService
from core.domain.events import EventRouter
from core.domain.tenant_data import TenantData
from core.domain.users import User
from core.storage import ObjectNotFoundException
from core.storage.organization_storage import OrganizationSystemStorage


@pytest.fixture(scope="function")
def mock_org_storage():
    return Mock(spec=OrganizationSystemStorage)


@pytest.fixture(scope="function")
def security_svc(mock_org_storage: Mock, mock_event_router: EventRouter):
    return SecurityService(mock_org_storage, mock_event_router)


@pytest.fixture(scope="function")
def anon_user():
    return UserClaims(unknownUserId="1234", exp=1234).to_domain()


@pytest.fixture(scope="function")
def old_user():
    # Mocks a user with tenant t1 that has the old format
    return User(
        sub="hello@hello.com",
        tenant="hello.com",
    )


@pytest.fixture(scope="function")
def user_org():
    return TenantData(tenant="t1")


@pytest.fixture(scope="function")
def new_user():
    # Mocks a user with tenant t1 that has the old format
    return User(
        sub="hello@hello.com",
        tenant=None,
        org_id="org_1",
        slug="org_1_slug",
        user_id="user_1",
        unknown_user_id="anon_1",
    )


class TestUserOrganization:
    async def test_with_api_key(
        self,
        mock_org_storage: Mock,
        security_svc: SecurityService,
    ):
        org_settings = TenantData(
            tenant="test_tenant",
            slug="test_slug",
            org_id="test_org_id",
            added_credits_usd=5,
            current_credits_usd=5,
        )
        mock_org_storage.find_tenant_for_api_key.return_value = org_settings

        result = await security_svc.find_tenant(None, "wai-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

        mock_org_storage.find_tenant_for_api_key.assert_called_once_with(
            "87d3cf28a4ff2a959dff462edff2a40e8bcad5d3a01a6cf2698eac369058075e",
        )
        assert result == org_settings

    async def test_with_invalid_api_key(
        self,
        mock_org_storage: Mock,
        security_svc: SecurityService,
    ):
        mock_org_storage.find_tenant_for_api_key.side_effect = ObjectNotFoundException()

        result = await security_svc.find_tenant(None, "sk-12345678")
        mock_org_storage.find_tenant_for_api_key.assert_called_once_with(
            "db722c9c5c5fbe334dd0e95a7406d76fcde6396e9d3495edf174ad689fda5dc2",
        )

        assert result is None

    async def test_with_user(
        self,
        mock_org_storage: Mock,
        new_user: User,
        security_svc: SecurityService,
    ):
        org_settings = TenantData(
            tenant="1",
            slug=new_user.slug or "",
            org_id=new_user.org_id,
            added_credits_usd=5,
            current_credits_usd=5,
        )
        mock_org_storage.find_tenant_for_org_id.return_value = org_settings

        result = await security_svc.find_tenant(new_user, None)

        mock_org_storage.find_tenant_for_org_id.assert_called_once_with(new_user.org_id)
        assert result == org_settings

    @patch("api.services.security_svc.id_uint32", return_value=1)
    async def test_with_user_org_not_found_creates_new_no_migration(
        self,
        mock_id_uint32: Mock,
        mock_org_storage: Mock,
        new_user: User,
        security_svc: SecurityService,
    ):
        """Test the case where the org_id is not found, and the migration fails"""
        mock_org_storage.find_tenant_for_org_id.side_effect = ObjectNotFoundException()
        mock_org_storage.migrate_tenant_to_organization.side_effect = ObjectNotFoundException()
        expected_org = TenantData(
            uid=1,
            tenant="orguid_1",
            slug=new_user.slug or "",
            org_id=new_user.org_id,
            added_credits_usd=5,
            current_credits_usd=5,
            anonymous=None,
            owner_id=new_user.user_id,
            anonymous_user_id=new_user.unknown_user_id,
        )
        mock_org_storage.create_organization.return_value = expected_org

        result = await security_svc.find_tenant(new_user, None)

        mock_org_storage.find_tenant_for_org_id.assert_called_once_with(new_user.org_id)
        mock_org_storage.create_organization.assert_called_once_with(expected_org)
        mock_org_storage.migrate_tenant_to_organization.assert_called_once_with(
            org_id=new_user.org_id,
            org_slug=new_user.slug,
            owner_id=new_user.user_id,
            anon_id="anon_1",
        )
        assert result == expected_org
        mock_id_uint32.assert_called_once()

    @patch("api.services.security_svc.id_uint32", return_value=1)
    async def test_with_user_org_not_found_creates_new_anonymous(
        self,
        mock_id_uint32: Mock,
        mock_org_storage: Mock,
        anon_user: User,
        security_svc: SecurityService,
    ):
        mock_org_storage.find_anonymous_tenant.side_effect = ObjectNotFoundException()
        expected_org = TenantData(
            tenant="orguid_1",
            added_credits_usd=0.2,
            current_credits_usd=0.2,
            anonymous=True,
            anonymous_user_id="1234",
            uid=1,
        )
        mock_org_storage.find_tenant_for_org_id.assert_not_called()
        mock_org_storage.create_organization.return_value = expected_org

        result = await security_svc.find_tenant(anon_user, None)

        mock_org_storage.find_anonymous_tenant.assert_called_once_with("1234")
        mock_org_storage.create_organization.assert_called_once_with(expected_org)
        assert result == expected_org
        mock_id_uint32.assert_called_once()

    async def test_with_anonymous_user_id_already_exists(
        self,
        mock_org_storage: Mock,
        anon_user: User,
        security_svc: SecurityService,
    ):
        org = TenantData(
            tenant="1234",
            anonymous_user_id="1234",
            added_credits_usd=0.2,
            current_credits_usd=0.2,
        )
        mock_org_storage.find_anonymous_tenant.return_value = org

        result = await security_svc.find_tenant(anon_user, None)

        mock_org_storage.find_anonymous_tenant.assert_called_once_with("1234")
        mock_org_storage.create_organization.assert_not_called()
        assert result == org

    # TODO[org]: remove
    async def test_with_deprecated_user_token(
        self,
        mock_org_storage: Mock,
        old_user: User,
        security_svc: SecurityService,
    ):
        mock_org_storage.find_tenant_for_deprecated_user.return_value = TenantData(
            tenant=old_user.tenant or "",
            slug=old_user.slug or "",
            org_id=old_user.org_id,
        )
        expected_org = TenantData(
            tenant=old_user.tenant or "",
            slug=old_user.slug or "",
            org_id=old_user.org_id,
        )
        result = await security_svc.find_tenant(old_user, None)
        assert result == expected_org

        mock_org_storage.find_tenant_for_deprecated_user.assert_called_once_with(
            domain=old_user.tenant,
        )

    # TODO[org]: remove
    async def test_with_deprecated_user_token_not_found(
        self,
        mock_org_storage: Mock,
        old_user: User,
        security_svc: SecurityService,
    ):
        # Check that we do not autocreate an org if the user token is deprecated
        mock_org_storage.find_tenant_for_deprecated_user.side_effect = ObjectNotFoundException()

        with pytest.raises(HTTPException) as e:
            await security_svc.find_tenant(old_user, None)

        assert e.value.status_code == 401
        assert e.value.detail == "Organization not found for deprecated token"

    async def test_no_user_no_api_key(self, mock_org_storage: Mock, security_svc: SecurityService):
        result = await security_svc.find_tenant(None, None)

        mock_org_storage.find_tenant_for_org_id.assert_not_called()
        mock_org_storage.find_tenant_for_api_key.assert_not_called()
        assert result is None

    async def test_find_tenant_with_org_id_migration_success(
        self,
        mock_org_storage: Mock,
        new_user: User,
        security_svc: SecurityService,
    ):
        """Test successful migration when finding tenant with org_id"""
        expected_org = TenantData(
            tenant="t1",
            slug=new_user.slug or "",
            org_id=new_user.org_id,
            added_credits_usd=5,
            current_credits_usd=5,
            owner_id=new_user.user_id,
            anonymous_user_id=new_user.unknown_user_id,
        )
        mock_org_storage.find_tenant_for_org_id.side_effect = ObjectNotFoundException()
        mock_org_storage.migrate_tenant_to_organization.return_value = expected_org

        result = await security_svc.find_tenant(new_user, None)

        mock_org_storage.find_tenant_for_org_id.assert_called_once_with(new_user.org_id)
        mock_org_storage.migrate_tenant_to_organization.assert_called_once_with(
            org_id=new_user.org_id,
            org_slug=new_user.slug,
            owner_id=new_user.user_id,
            anon_id=new_user.unknown_user_id,
        )
        assert result == expected_org

    async def test_find_tenant_with_org_id_migration_failure(
        self,
        mock_org_storage: Mock,
        new_user: User,
        security_svc: SecurityService,
    ):
        """Test migration failure when finding tenant with org_id"""
        mock_org_storage.find_tenant_for_org_id.side_effect = ObjectNotFoundException()
        mock_org_storage.migrate_tenant_to_organization.side_effect = ObjectNotFoundException()
        expected_org = TenantData(
            tenant="orguid_1",
            slug=new_user.slug or "",
            org_id=new_user.org_id,
            added_credits_usd=5,
            current_credits_usd=5,
            owner_id=new_user.user_id,
            anonymous_user_id=new_user.unknown_user_id,
        )
        mock_org_storage.create_organization.return_value = expected_org

        result = await security_svc.find_tenant(new_user, None)

        mock_org_storage.find_tenant_for_org_id.assert_called_once_with(new_user.org_id)
        mock_org_storage.migrate_tenant_to_organization.assert_called_once_with(
            org_id=new_user.org_id,
            org_slug=new_user.slug,
            owner_id=new_user.user_id,
            anon_id=new_user.unknown_user_id,
        )
        mock_org_storage.create_organization.assert_called_once()
        assert result == expected_org

    async def test_find_tenant_with_user_id_migration_success(
        self,
        mock_org_storage: Mock,
        new_user: User,
        security_svc: SecurityService,
    ):
        """Test successful migration when finding tenant with user_id"""
        # Create a user without org_id but with user_id
        user_without_org = User(
            sub=new_user.sub,
            tenant=None,
            org_id=None,
            slug="hello",
            user_id=new_user.user_id,
            unknown_user_id=new_user.unknown_user_id,
        )
        expected_org = TenantData(
            tenant="t1",
            slug="",
            org_id=None,
            added_credits_usd=5,
            current_credits_usd=5,
            owner_id=user_without_org.user_id,
            anonymous_user_id=user_without_org.unknown_user_id,
        )
        mock_org_storage.find_tenant_for_owner_id.side_effect = ObjectNotFoundException()
        mock_org_storage.migrate_tenant_to_user.return_value = expected_org

        result = await security_svc.find_tenant(user_without_org, None)

        mock_org_storage.find_tenant_for_owner_id.assert_called_once_with(user_without_org.user_id)
        mock_org_storage.migrate_tenant_to_user.assert_called_once_with(
            user_without_org.user_id,
            "hello",
            user_without_org.unknown_user_id,
        )
        assert result == expected_org

    @patch("api.services.security_svc.id_uint32", return_value=1)
    async def test_find_tenant_with_user_id_migration_failure(
        self,
        mock_id_uint32: Mock,
        mock_org_storage: Mock,
        new_user: User,
        security_svc: SecurityService,
    ):
        """Test migration failure when finding tenant with user_id"""
        # Create a user without org_id but with user_id
        new_user.org_id = None
        new_user.slug = "@hello"

        mock_org_storage.find_tenant_for_owner_id.side_effect = ObjectNotFoundException()
        mock_org_storage.migrate_tenant_to_user.side_effect = ObjectNotFoundException()
        expected_org = TenantData(
            uid=1,
            tenant="orguid_1",
            slug="@hello",
            org_id=None,
            added_credits_usd=5,
            current_credits_usd=5,
            owner_id=new_user.user_id,
            anonymous_user_id=new_user.unknown_user_id,
        )
        mock_org_storage.create_organization.return_value = expected_org

        result = await security_svc.find_tenant(new_user, None)

        mock_org_storage.find_tenant_for_owner_id.assert_called_once_with(new_user.user_id)
        mock_org_storage.migrate_tenant_to_user.assert_called_once_with(
            new_user.user_id,
            "@hello",
            new_user.unknown_user_id,
        )
        mock_org_storage.create_organization.assert_called_once_with(expected_org)
        assert result == expected_org
