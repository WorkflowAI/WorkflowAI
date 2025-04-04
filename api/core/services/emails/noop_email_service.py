import logging
from typing import override

from core.services.emails.email_service import EmailService


class NoopEmailService(EmailService):
    @property
    def _logger(self):
        return logging.getLogger(self.__class__.__name__)

    @override
    async def send_payment_failure_email(self, tenant: str) -> None:
        self._logger.warning("NoopEmailService.send_payment_failure_email called")

    @override
    async def send_low_credits_email(self, tenant: str) -> None:
        self._logger.warning("NoopEmailService.send_low_credits_email called")
