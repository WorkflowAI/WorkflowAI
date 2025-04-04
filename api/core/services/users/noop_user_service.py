import logging
from typing import override

from core.services.users.user_service import UserDetails, UserService


class NoopUserService(UserService):
    @property
    def _logger(self):
        return logging.getLogger(self.__class__.__name__)

    @override
    async def get_user(self, user_id: str) -> UserDetails:
        self._logger.warning("NoopUserService.get_user called")
        return UserDetails(email="", name="")

    @override
    async def get_org_admins(self, org_id: str) -> list[UserDetails]:
        self._logger.warning("NoopUserService.get_org_admins called")
        return []
