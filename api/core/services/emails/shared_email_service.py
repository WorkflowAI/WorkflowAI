import os
from collections.abc import Callable

from core.services.emails.email_service import EmailService
from core.services.users.user_service import UserService
from core.storage.organization_storage import PublicOrganizationStorage


def _default_email_service_builder() -> Callable[[PublicOrganizationStorage, UserService], EmailService]:
    if "LOOPS_API_KEY" in os.environ:
        from core.services.emails.loops_email_service import LoopsEmailService

        def _builder(storage: PublicOrganizationStorage, user_service: UserService) -> EmailService:
            return LoopsEmailService(
                api_key=os.environ["LOOPS_API_KEY"],
                organization_storage=storage,
                user_service=user_service,
            )

        return _builder

    def _noop_builder(storage: PublicOrganizationStorage, user_service: UserService) -> EmailService:
        from core.services.emails.noop_email_service import NoopEmailService

        return NoopEmailService()

    return _noop_builder


email_service_builder = _default_email_service_builder()
