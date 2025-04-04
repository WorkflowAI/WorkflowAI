import os

from core.services.users.clerk_user_service import ClerkUserService
from core.services.users.noop_user_service import NoopUserService
from core.services.users.user_service import UserService


def _default_user_service() -> UserService:
    if "CLERK_SECRET_KEY" in os.environ:
        return ClerkUserService(
            clerk_secret=os.environ["CLERK_SECRET_KEY"],
        )
    return NoopUserService()


shared_user_service = _default_user_service()
