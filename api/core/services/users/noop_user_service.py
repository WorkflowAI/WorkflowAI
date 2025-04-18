import logging
from datetime import datetime
from typing import override

from core.services.users.user_service import OrganizationDetails, UserDetails, UserService


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

    @override
    async def get_organization(self, org_id: str) -> OrganizationDetails:
        self._logger.warning("NoopUserService.get_organization called")
        return OrganizationDetails(name="", slug="", id="")

    @override
    async def count_registrations(self, since: datetime) -> int:
        self._logger.warning("NoopUserService.count_registrations called")
        return 0
