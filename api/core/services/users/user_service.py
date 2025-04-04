from typing import NamedTuple, Protocol


class UserDetails(NamedTuple):
    email: str
    name: str


class UserService(Protocol):
    """Service to manage users and organizations"""

    async def get_user(self, user_id: str) -> UserDetails: ...

    async def get_org_admins(self, org_id: str) -> list[UserDetails]: ...
