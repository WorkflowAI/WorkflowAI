from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from core.domain.errors import DuplicateValueError
from core.domain.users import UserIdentifier
from core.storage.mongo.models.organization_document import APIKeyDocument

from .api_keys import APIKeyService, GeneratedAPIKey


@pytest.fixture(scope="function")
def mock_storage():
    return AsyncMock()


@pytest.fixture(scope="function")
def api_key_service(mock_storage: AsyncMock) -> APIKeyService:
    return APIKeyService(storage=mock_storage)


class TestGetHashedKey:
    def test_get_hashed_key(self):
        key = "test_key"
        hashed = APIKeyService._get_hashed_key(key)  # pyright: ignore[reportPrivateUsage]
        assert len(hashed) == 64
        assert hashed == "92488e1e3eeecdf99f3ed2ce59233efb4b4fb612d5655c0ce9ea52b5a502e655"


class TestAPIKeyService:
    async def test_generate_api_key(self, api_key_service: APIKeyService):
        generated = api_key_service._generate_api_key()  # pyright: ignore[reportPrivateUsage]

        assert isinstance(generated, GeneratedAPIKey)
        assert generated.key.startswith("wai-")
        assert len(generated.key) > 20  # Ensure reasonable length
        assert generated.partial == f"{generated.key[:9]}****"
        assert generated.hashed == api_key_service._get_hashed_key(generated.key)  # pyright: ignore[reportPrivateUsage]

    async def test_create_key(self, api_key_service: APIKeyService, mock_storage: AsyncMock):
        name = "test key"
        created_by = UserIdentifier(user_id="test_user", user_email="test@example.com")

        mock_doc = APIKeyDocument(
            id="test_id",
            name=name,
            hashed_key="hashed123",
            partial_key="wai-****",
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
        )
        mock_storage.create_api_key_for_organization.return_value = mock_doc

        api_key, raw_key = await api_key_service.create_key(name, created_by)

        assert api_key.name == name
        assert api_key.created_by == created_by
        assert raw_key.startswith("wai-")

        mock_storage.create_api_key_for_organization.assert_called_once()
        call_args = mock_storage.create_api_key_for_organization.call_args
        assert call_args.args[0] == name
        assert call_args.args[3] == created_by
        assert call_args.args[1].startswith("")  # hashed key
        assert call_args.args[2].startswith("wai-")  # partial key

    async def test_delete_key(self, api_key_service: APIKeyService, mock_storage: AsyncMock):
        key_id = "test_key_id"
        mock_storage.delete_api_key_for_organization.return_value = True

        result = await api_key_service.delete_key(key_id)

        assert result is True
        mock_storage.delete_api_key_for_organization.assert_called_once_with(key_id)

    async def test_get_keys(self, api_key_service: APIKeyService, mock_storage: AsyncMock):
        mock_docs = [
            APIKeyDocument(
                id="id1",
                name="key1",
                hashed_key="hash1",
                partial_key="partial1",
                created_by=UserIdentifier(user_id="user1", user_email="test1@example.com"),
                created_at=datetime.now(timezone.utc),
            ),
            APIKeyDocument(
                id="id2",
                name="key2",
                hashed_key="hash2",
                partial_key="partial2",
                created_by=UserIdentifier(user_id="user2", user_email="test2@example.com"),
                created_at=datetime.now(timezone.utc),
            ),
        ]
        mock_storage.get_api_keys_for_organization.return_value = mock_docs

        keys = await api_key_service.get_keys()

        assert len(keys) == 2
        assert keys[0].id == "id1"
        assert keys[1].id == "id2"
        mock_storage.get_api_keys_for_organization.assert_called_once()

    async def test_create_key_duplicate(self, api_key_service: APIKeyService, mock_storage: AsyncMock):
        name = "test key"
        created_by = UserIdentifier(user_id="test_user", user_email="test@example.com")

        mock_storage.create_api_key_for_organization.side_effect = DuplicateValueError

        with pytest.raises(DuplicateValueError):
            await api_key_service.create_key(name, created_by)


class TestIsAPIKey:
    @pytest.mark.parametrize(
        "key, expected",
        [
            ("wai-cdsdf45DGSG543gdbccvVfdXdgcgtwh", True),
            ("sk-cdsdf45DGSG543gdbccvVfdXdgcgtwh", False),
            ("wfai-cdsdf45DGSG543gdbccvVfdXdgcgtwh", False),
            ("cdsdf45DGSG543gdbccvVfdXdgcgtwh", False),
        ],
    )
    def test_is_api_key(self, key: str, expected: bool):
        assert APIKeyService.is_api_key(key) == expected
