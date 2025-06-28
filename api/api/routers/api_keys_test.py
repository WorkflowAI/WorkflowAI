from datetime import datetime
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from core.domain.api_key import APIKey
from core.domain.users import UserIdentifier


@pytest.fixture(scope="function")
def mock_api_keys_service(test_app: FastAPI) -> Mock:
    from api.dependencies.services import APIKeyService, api_key_service

    mock = Mock(spec=APIKeyService)
    test_app.dependency_overrides[api_key_service] = lambda: mock
    return mock


class TestNoAnonymousOrganization:
    async def test_create_api_key(
        self,
        test_api_client: AsyncClient,
        mock_user_org_dep: Mock,
        mock_api_keys_service: Mock,
    ):
        # Anonymous organization
        mock_user_org_dep.return_value.org_id = None
        mock_user_org_dep.return_value.owner_id = None
        assert mock_user_org_dep.return_value.is_anonymous is True, "Organization should be anonymous"

        response = await test_api_client.post("/_/api/keys")
        assert response.status_code == 401
        assert response.json() == {"detail": "Endpoint is only available for non-anonymous tenants"}
        mock_api_keys_service.create_key.assert_not_called()

        # Non-anonymous organization as a sanity check
        mock_user_org_dep.return_value.org_id = "org_123"
        assert mock_user_org_dep.return_value.is_anonymous is False, "Organization should not be anonymous"

        mock_api_keys_service.create_key.return_value = (
            APIKey(
                id="1",
                name="test",
                partial_key="123",
                created_at=datetime.now(),
                last_used_at=None,
                created_by=UserIdentifier(),
            ),
            "hello",
        )

        response = await test_api_client.post("/_/api/keys", json={"name": "test"})
        assert response.status_code == 201
        mock_api_keys_service.create_key.assert_awaited_once()


class TestDeleteAPIKey:
    async def test_delete_api_key_with_api_key_auth_success(
        self,
        test_api_client: AsyncClient,
        mock_user_org_dep: Mock,
        mock_api_keys_service: Mock,
        mock_user_dep: Mock,
    ):
        """Test that deleting an API key using API key authentication works correctly.

        This test verifies the fix for the bug where API key authentication
        would fail when deleting keys. Now it should work properly.
        """
        # Setup non-anonymous organization
        mock_user_org_dep.return_value.org_id = "org_123"

        # Mock API key authentication (user will be None)
        mock_user_dep.return_value = None

        # Mock successful deletion
        mock_api_keys_service.delete_key.return_value = True

        # This should now work correctly with the fix
        response = await test_api_client.delete("/_/api/keys/test_key_id")

        # The fix: operation succeeds when using API key authentication
        assert response.status_code == 204
        mock_api_keys_service.delete_key.assert_called_once_with("test_key_id")

    async def test_delete_api_key_user_with_empty_id_fails(
        self,
        test_api_client: AsyncClient,
        mock_user_org_dep: Mock,
        mock_api_keys_service: Mock,
        mock_user_dep: Mock,
    ):
        """Test that users with empty user_id are still unauthorized."""
        # Setup non-anonymous organization
        mock_user_org_dep.return_value.org_id = "org_123"

        # Mock user with empty user_id (invalid user)
        mock_user_dep.return_value = Mock(user_id="")

        # Should not even attempt to delete
        response = await test_api_client.delete("/_/api/keys/test_key_id")

        assert response.status_code == 401
        assert response.json() == {"detail": "You are not authorized to delete this API key"}
        # Delete should not be called since authorization failed first
        mock_api_keys_service.delete_key.assert_not_called()

    async def test_delete_api_key_not_found(
        self,
        test_api_client: AsyncClient,
        mock_user_org_dep: Mock,
        mock_api_keys_service: Mock,
        mock_user_dep: Mock,
    ):
        """Test deleting a non-existent API key."""
        # Setup non-anonymous organization
        mock_user_org_dep.return_value.org_id = "org_123"

        # Mock user authentication
        mock_user_dep.return_value = Mock(user_id="user123")

        # Mock key not found
        mock_api_keys_service.delete_key.return_value = False

        response = await test_api_client.delete("/_/api/keys/nonexistent_key")

        assert response.status_code == 404
        assert response.json() == {"detail": "API key not found"}
        mock_api_keys_service.delete_key.assert_called_once_with("nonexistent_key")

    async def test_delete_api_key_with_user_auth_success(
        self,
        test_api_client: AsyncClient,
        mock_user_org_dep: Mock,
        mock_api_keys_service: Mock,
        mock_user_dep: Mock,
    ):
        """Test successful deletion with user authentication."""
        # Setup non-anonymous organization
        mock_user_org_dep.return_value.org_id = "org_123"

        # Mock user authentication
        mock_user_dep.return_value = Mock(user_id="user123")

        # Mock successful deletion
        mock_api_keys_service.delete_key.return_value = True

        response = await test_api_client.delete("/_/api/keys/test_key_id")

        assert response.status_code == 204
        mock_api_keys_service.delete_key.assert_called_once_with("test_key_id")
