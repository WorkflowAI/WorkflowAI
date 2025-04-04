import os
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException, Request

from core.domain.tenant_data import PublicOrganizationData, TenantData
from core.domain.users import User
from core.utils import no_op

from .security import (
    UserClaims,
    _default_key_ring,  # pyright: ignore [reportPrivateUsage]
    final_tenant_data,
    url_public_organization,
)


class TestDefaultKeyRing:
    @pytest.fixture(scope="function", autouse=True)
    def patch_jwks_url(self):
        with patch.dict(os.environ, {"WORKFLOWAI_JWKS_URL": "https://hello"}, clear=True):
            yield

    def test_not_present(self):
        assert "WORKFLOWAI_JWK" not in os.environ, "sanity"

        kr = _default_key_ring()
        assert kr.key_cache == {}

    def test_present_not_valid(self):
        assert "WORKFLOWAI_JWK" not in os.environ, "sanity"
        # Sending invalid value in WORKFLOWAI_JWK
        os.environ["WORKFLOWAI_JWK"] = "hello"

        kr = _default_key_ring()
        assert kr.key_cache == {}

    def test_present_valid(self):
        os.environ["WORKFLOWAI_JWK"] = (
            "eyJrdHkiOiJFQyIsIngiOiJLVUpZYzd2V0R4Um55NW5BdC1VNGI4MHRoQ1ZuaERUTDBzUmZBRjR2cDdVIiwieSI6IjM0dWx1VDgyT0RFRFJXVU9KNExrZzFpanljclhqMWc1MmZRblpqeFc5cTAiLCJjcnYiOiJQLTI1NiIsImlkIjoiMSJ9Cg=="
        )
        kr = _default_key_ring()
        assert len(kr.key_cache) == 1


@pytest.fixture(scope="function")
def mock_request():
    # Mocks a POST request with tenant t1
    req = Mock(spec=Request)
    req.path_params = {"tenant": "org_1_slug"}
    # POST means auth for public tasks will not be considered by default
    req.method = "POST"
    return req


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
        tenant="hello.com",
        org_id="org_1",
        slug="org_1_slug",
    )


@pytest.fixture(scope="function")
def anon_user():
    return UserClaims(unknownUserId="1234", exp=1234).to_domain()


class TestFinalTenantDataDependency:
    @pytest.fixture(scope="function")
    def patched_storage_for_tenant(self, mock_encryption: Mock, mock_storage: Mock):
        with patch("api.services.storage.storage_for_tenant", return_value=mock_storage) as mock:
            yield mock

    async def test_no_tenant_in_path_old_user(
        self,
        mock_request: Mock,
        old_user: User,
        user_org: TenantData,
        mock_encryption: Mock,
        patched_storage_for_tenant: Mock,
    ):
        # no tenant in path + old user token
        mock_request.path_params = None
        actual = await final_tenant_data(old_user, user_org, None, mock_request, mock_encryption)

        assert actual.tenant == "t1"
        patched_storage_for_tenant.assert_not_called()

    async def test_no_tenant_in_path_new_user(
        self,
        mock_request: Mock,
        new_user: User,
        user_org: TenantData,
        patched_storage_for_tenant: Mock,
        mock_encryption: Mock,
    ):
        # no tenant in path + new user token
        mock_request.path_params = None
        user_org.tenant = "t1"

        actual = await final_tenant_data(new_user, user_org, None, mock_request, mock_encryption)
        assert actual.tenant == "t1"
        patched_storage_for_tenant.assert_not_called()

    async def test_tenant_in_path_old_user_same_tenant(
        self,
        mock_request: Mock,
        old_user: User,
        user_org: TenantData,
        mock_encryption: Mock,
        patched_storage_for_tenant: Mock,
    ):
        # If the tenant in the path matches the user old tenant field, we don't check the db
        user_org.tenant = "hello1"

        actual = await final_tenant_data(
            old_user,
            user_org,
            PublicOrganizationData(tenant="hello1"),
            mock_request,
            mock_encryption,
        )
        assert actual.tenant == "hello1"

        patched_storage_for_tenant.assert_not_called()

    async def test_tenant_in_path_new_user_same_tenant(
        self,
        mock_request: Mock,
        new_user: User,
        user_org: TenantData,
        mock_storage: Mock,
        mock_encryption: Mock,
        patched_storage_for_tenant: Mock,
    ):
        # If the tenant in the path matches the user org slug field, we don't check the db
        mock_request.path_params = {"tenant": "org_1_slug"}
        # If the tenant in the path matches the user old tenant field, we don't check the db
        user_org.tenant = "hello1"

        actual = await final_tenant_data(
            new_user,
            user_org,
            PublicOrganizationData(tenant="hello1"),
            mock_request,
            mock_encryption,
        )
        assert actual.tenant == "hello1"

        patched_storage_for_tenant.assert_not_called()

    async def test_mismatching_tenants_for_post_request(
        self,
        mock_request: Mock,
        new_user: User,
        user_org: TenantData,
        mock_encryption: Mock,
        patched_storage_for_tenant: Mock,
    ):
        # Check that we return a 404 for a post request where the url tenant and the user tenant don't match
        mock_request.path_params = {"tenant": "org_2_slug", "task_id": "task_1"}
        mock_request.url.path = "/test/agents/task_1/schemas/1"
        user_org.tenant = "hello1"
        public_org = PublicOrganizationData(tenant="hello2")

        with pytest.raises(HTTPException) as e:
            await final_tenant_data(new_user, user_org, public_org, mock_request, mock_encryption)

        assert e.value.status_code == 404

        patched_storage_for_tenant.assert_not_called()

    async def test_mismatching_tenants_for_public_task(
        self,
        mock_request: Mock,
        new_user: User,
        user_org: TenantData,
        mock_storage: Mock,
        mock_encryption: Mock,
        patched_storage_for_tenant: Mock,
    ):
        mock_request.method = "GET"
        mock_request.path_params = {"tenant": "org_2_slug", "task_id": "task_1"}
        mock_request.url.path = "/test/agents/task_1/schemas/1"
        user_org.tenant = "hello1"

        mock_storage.tasks.is_task_public.return_value = True
        public_org = PublicOrganizationData(tenant="hello2", uid=1)

        # We return the tenant from the url
        actual = await final_tenant_data(new_user, user_org, public_org, mock_request, mock_encryption)
        assert actual.tenant == "hello2"

        patched_storage_for_tenant.assert_called_once_with(
            tenant="hello2",
            tenant_uid=1,
            encryption=mock_encryption,
            event_router=no_op.event_router,
        )
        mock_storage.tasks.is_task_public.assert_called_once_with("task_1")


class TestURLPublicOrganization:
    async def test_special_tenant(self, mock_request: Mock, user_org: TenantData, mock_storage: Mock):
        mock_request.path_params = {"tenant": "_"}

        assert await url_public_organization(mock_storage.organizations, mock_request, user_org) == user_org

    async def test_no_tenant(self, mock_request: Mock, user_org: TenantData, mock_storage: Mock):
        mock_request.path_params = {}

        assert await url_public_organization(mock_storage.organizations, mock_request, user_org) == user_org
