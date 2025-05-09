from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from core.domain.errors import DuplicateValueError
from core.domain.users import UserIdentifier
from core.storage.mongo.models.organization_document import APIKeyDocument

from .api_keys import APIKeyService, GeneratedAPIKey, find_api_key_in_text


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

    async def test_generated_key_matches_find_pattern(self, api_key_service: APIKeyService):
        # This test relies on find_api_key_in_text using the *corrected* regex
        generated = api_key_service._generate_api_key()  # pyright: ignore[reportPrivateUsage]

        # Check 3: find_api_key_in_text should find this generated key
        assert find_api_key_in_text(generated.key) == {generated.key}, (
            f"Generated key {generated.key} was not found by find_api_key_in_text when tested standalone."
        )

        # Check 4: find_api_key_in_text should find this key when embedded in other text
        text_with_key = f"Some text before {generated.key} and some text after."
        assert find_api_key_in_text(text_with_key) == {generated.key}, (
            f"Generated key {generated.key} was not found by find_api_key_in_text when embedded in text."
        )


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


class TestFindAPIKeyInText:
    # Predefined keys for clarity in tests
    KEY_ALPHANUM = "wai-Abcdefghijklmnopqrstuvwxyz1234567890ABCDEFG"  # 26+10+7=43
    KEY_HYPHENS_UNDERSCORES = "wai-key-with-hyphens_and_underscores_is_valid"  # 4+5+8+4+11+3+6 = 41, need 2 more
    KEY_HYPHENS_UNDERSCORES_FIXED = "wai-key-with-hyphens_and_underscores_is_validOK"  # 43
    KEY_NUMERIC_ONLY = "wai-0123456789012345678901234567890123456789012"  # 43
    KEY_LOWER_ALPHA_ONLY = "wai-abcdefghijklmnopqrstuvwxyzabcdefghijklmnopq"  # 43

    @pytest.mark.parametrize(
        "description, input_text, expected_keys",
        [
            ("Empty string", "", set[str]()),
            ("No API key", "Some random text without any keys.", set[str]()),
            (
                "Single key, standalone",
                KEY_LOWER_ALPHA_ONLY,
                {KEY_LOWER_ALPHA_ONLY},
            ),
            (
                "Single key at start",
                f"{KEY_ALPHANUM} is at the start.",
                {KEY_ALPHANUM},
            ),
            (
                "Single key in middle",
                f"Text {KEY_HYPHENS_UNDERSCORES_FIXED} in the middle.",
                {KEY_HYPHENS_UNDERSCORES_FIXED},
            ),
            (
                "Single key at end",
                f"Text at the end is {KEY_NUMERIC_ONLY}",
                {KEY_NUMERIC_ONLY},
            ),
            (
                "Two distinct keys",
                f"Key one {KEY_ALPHANUM}, key two {KEY_HYPHENS_UNDERSCORES_FIXED}.",
                {KEY_ALPHANUM, KEY_HYPHENS_UNDERSCORES_FIXED},
            ),
            (
                "Duplicate keys in text",
                f"Key {KEY_ALPHANUM} and same key {KEY_ALPHANUM}.",
                {KEY_ALPHANUM},
            ),
            (
                "Adjacent keys",
                f"{KEY_ALPHANUM}{KEY_NUMERIC_ONLY}",
                {KEY_ALPHANUM, KEY_NUMERIC_ONLY},
            ),
            (
                "Key with only numbers",
                f"Key: {KEY_NUMERIC_ONLY}",
                {KEY_NUMERIC_ONLY},
            ),
            (
                "Key with only lowercase alpha",
                f"Key: {KEY_LOWER_ALPHA_ONLY}",
                {KEY_LOWER_ALPHA_ONLY},
            ),
            (
                "Key with hyphens and underscores",
                f"Key: {KEY_HYPHENS_UNDERSCORES_FIXED}",
                {KEY_HYPHENS_UNDERSCORES_FIXED},
            ),
            (
                "Key with mixed case, numbers, hyphens, underscores",
                f"A complex key: {KEY_ALPHANUM} is here.",  # KEY_ALPHANUM is mixed case and numbers
                {KEY_ALPHANUM},
            ),
            (
                "Mixed valid and invalid (short)",
                f"Valid: {KEY_ALPHANUM} but invalid: wai-shortkey",
                {KEY_ALPHANUM},
            ),
            (
                "Mixed valid and invalid (bad char)",
                f"Invalid: wai-key!{'x' * 40} and then valid: {KEY_NUMERIC_ONLY}",
                {KEY_NUMERIC_ONLY},
            ),
            (
                "Text containing a key that is almost too long",
                "wai-ThisKeyIsExactly43CharsLongAndIsValidNow" + "X",  # This makes the key part 44 chars
                set[str](),  # Should not match wai-ThisKeyIsExactly43CharsLongAndIsValidNow
            ),
            (
                "Text containing a key that is almost too short",
                "wai-ThisKeyIsExactly43CharsLongAndIsValidNo"[:-1],  # This makes the key part 42 chars
                set[str](),
            ),
        ],
    )
    def test_find_api_keys_valid_scenarios(
        self,
        description: str,
        input_text: str,
        expected_keys: set[str],
    ):
        assert find_api_key_in_text(input_text) == expected_keys, f"Failed: {description}"

    @pytest.mark.parametrize(
        "text, description",
        [
            ("wxi-" + "a" * 43, "Wrong prefix 'wxi-'"),
            ("wai." + "a" * 43, "Wrong prefix separator '.'"),
            ("wai-" + "a" * 42, "Payload too short (42 chars)"),
            ("wai-" + "a" * 20 + "!" + "a" * 22, "Invalid char '!' in payload"),
            (
                "wai-@bcdefghijklmnopqrstuvwxyz1234567890ABCDEFG",
                "Invalid char '@' at start of payload",
            ),  # 43 chars after wai-
            (
                "wai-abcdefghijklmnopqrstuvwxyz1234567890ABCDEF@",
                "Invalid char '@' at end of payload",
            ),  # 43 chars after wai-
            ("wai- abcdefghijklmnopqrstuvwxyz1234567890ABCDEF", "Space at start of payload"),  # 43 chars after wai-
            ("wai-abcdefghijklmno pqrstuvwxyz1234567890ABC", "Space in middle of payload"),  # 43 chars after wai-
            ("wai-abcdefghijklmno*pqrstuvwxyz1234567890ABC", "Asterisk in payload"),  # 43 chars after wai-
        ],
    )
    def test_find_api_keys_invalid_scenarios(self, text: str, description: str):
        assert find_api_key_in_text(text) == set(), f"Failed for: {description}"
