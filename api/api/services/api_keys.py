import re
import secrets
from typing import List

from pydantic import BaseModel

from core.domain.api_key import APIKey
from core.domain.errors import DuplicateValueError
from core.domain.users import UserIdentifier
from core.storage.organization_storage import OrganizationStorage
from core.utils.hash import secure_hash


class GeneratedAPIKey(BaseModel):
    key: str
    hashed: str
    partial: str


class APIKeyService:
    def __init__(self, storage: OrganizationStorage):
        self.storage = storage

    @classmethod
    def _get_hashed_key(cls, api_key: str) -> str:
        return secure_hash(api_key)

    @classmethod
    def is_api_key(cls, key: str) -> bool:
        """Check if the string matches API key pattern 'wai-'"""
        return key.startswith("wai-")

    def _generate_api_key(self) -> GeneratedAPIKey:
        """Generate a new API key, its hash, and partial display version."""
        key = f"wai-{secrets.token_urlsafe(32)}"
        hashed = self._get_hashed_key(key)
        partial = f"{key[:9]}****"
        return GeneratedAPIKey(key=key, hashed=hashed, partial=partial)

    async def create_key(self, name: str, created_by: UserIdentifier, max_retries: int = 3) -> tuple[APIKey, str]:
        retries = 0
        while retries < max_retries:
            # Retry to generate a unique API key
            try:
                generated_key = self._generate_api_key()
                doc = await self.storage.create_api_key_for_organization(
                    name,
                    generated_key.hashed,
                    generated_key.partial,
                    created_by,
                )

                return doc, generated_key.key
            except DuplicateValueError:
                retries += 1
                continue

        raise DuplicateValueError("API key generation failed")

    async def delete_key(self, key_id: str) -> bool:
        return await self.storage.delete_api_key_for_organization(key_id)

    async def get_keys(self) -> List[APIKey]:
        return [key for key in await self.storage.get_api_keys_for_organization()]


def find_api_key_in_text(text: str) -> set[str]:
    # api keys are generated as secrets.token_urlsafe(32)
    # equals to 43 characters in base64 (A-Z, a-z, 0-9, -, _)
    return set(re.findall(r"wai-[-A-Za-z0-9_]{43}", text))
