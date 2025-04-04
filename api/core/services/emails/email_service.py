from typing_extensions import Protocol


class EmailSendError(Exception):
    pass


class EmailService(Protocol):
    async def send_payment_failure_email(self, tenant: str) -> None: ...

    async def send_low_credits_email(self, tenant: str) -> None: ...
