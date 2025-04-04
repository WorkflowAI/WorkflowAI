import logging
from collections.abc import Iterable
from typing import Generic, List, TypedDict, TypeVar

import httpx
from typing_extensions import NotRequired, override

from core.services.users.user_service import UserDetails, UserService

_logger = logging.getLogger(__name__)


class ClerkUserService(UserService):
    def __init__(self, clerk_secret: str):
        self._clerk_secret = clerk_secret
        self._url = "https://api.clerk.com/v1"

    def _client(self):
        return httpx.AsyncClient(
            base_url=self._url,
            headers={"Authorization": f"Bearer {self._clerk_secret}"},
        )

    @override
    async def get_user(self, user_id: str) -> UserDetails:
        async with self._client() as client:
            response = await client.get(f"/users/{user_id}")
        response.raise_for_status()
        data: ClerkUserDict = response.json()
        return UserDetails(email=_find_primary_email(data), name=_full_name(data))

    async def _get_org_admin_ids(self, client: httpx.AsyncClient, org_id: str, max_users: int) -> list[str]:
        # https://clerk.com/docs/reference/backend-api/tag/Organization-Memberships#operation/ListOrganizationMemberships

        response = await client.get(f"/organizations/{org_id}/memberships?role=admin&limit={max_users}")
        response.raise_for_status()
        data: DataDict[OrganizationMemberShipDict] = response.json()
        if data.get("total_count", 0) != len(data["data"]):
            # No need to handle pagination for now... If an org has more than 100 admins, we will just ignore the rest
            # and log a warning
            # Listing users does not accept more than 100 users anyway
            _logger.warning(
                "There are more admins that requested in clerk call",
                extra={"org_id": org_id, "total_count": data.get("total_count", 0), "count": len(data["data"])},
            )
        return [user["public_user_data"]["user_id"] for user in data["data"]]

    async def _get_users_by_id(
        self,
        client: httpx.AsyncClient,
        user_ids: Iterable[str],
    ) -> list[UserDetails]:
        response = await client.get(f"/users?user_ids={','.join(user_ids)}")
        response.raise_for_status()
        data: DataDict[ClerkUserDict] = response.json()
        return [UserDetails(email=_find_primary_email(user), name=_full_name(user)) for user in data["data"]]

    @override
    async def get_org_admins(self, org_id: str, max_users: int = 5) -> list[UserDetails]:
        async with self._client() as client:
            user_ids = await self._get_org_admin_ids(client, org_id, max_users)
            return await self._get_users_by_id(client, user_ids)


_TD = TypeVar("_TD")


class EmailAddressDict(TypedDict):
    id: str
    email_address: str


class ClerkUserDict(TypedDict):
    id: str
    primary_email_address_id: NotRequired[str]
    first_name: NotRequired[str]
    last_name: NotRequired[str]
    email_addresses: List[EmailAddressDict]


class PublicUserDataDict(TypedDict):
    user_id: str


class OrganizationMemberShipDict(TypedDict):
    public_user_data: PublicUserDataDict


class DataDict(TypedDict, Generic[_TD]):
    data: list[_TD]
    total_count: int


def _find_primary_email(user: ClerkUserDict) -> str:
    if primary_id := user.get("primary_email_address_id"):
        try:
            return next(email["email_address"] for email in user["email_addresses"] if email["id"] == primary_id)
        except StopIteration:
            pass
    return user["email_addresses"][0]["email_address"]


def _full_name(user: ClerkUserDict) -> str:
    first_name = user.get("first_name")
    last_name = user.get("last_name")
    return " ".join((name for name in [first_name, last_name] if name))
