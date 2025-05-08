import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.dependencies.security import SystemStorageDep
from core.domain.helpscout_email import HelpScoutEmail
from core.services.customers.customer_service import CustomerService

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/helpscout", include_in_schema=False)


class RawWebhookEvent(BaseModel):
    id: int
    type: str  # non-email will be ignored
    subject: str

    class Customer(BaseModel):
        email: str

    primaryCustomer: Customer

    class Embedded(BaseModel):
        class Thread(BaseModel):
            id: int
            createdAt: datetime
            body: str | None = None

            class CreatedByData(BaseModel):
                email: str

            createdBy: CreatedByData
            cc: list[str]
            bcc: list[str]

        threads: list[Thread]

    embedded: Embedded = Field(alias="_embedded")

    def to_email(self) -> HelpScoutEmail:
        # The latest email is the first thread in Helpscout's webhook
        last_thread = self.embedded.threads[0]

        return HelpScoutEmail(
            conversation_id=self.id,
            customer_email=self.primaryCustomer.email,
            from_email=last_thread.createdBy.email,
            cc_emails=last_thread.cc,
            bcc_emails=last_thread.bcc,
            body=last_thread.body or "",
            subject=self.subject,
            sent_at=last_thread.createdAt,
        )


# Accept both "" and "/" withouth yield a 307 that would provoke the webhook to be called several times
@router.post("/")
@router.post("")
async def helpscout_webhook(request: Request, storage: SystemStorageDep):
    try:
        payload = await request.json()
        _logger.info("Received Helpscout webhook", extra={"payload": payload})
        event = RawWebhookEvent.model_validate(payload)
        if event.type != "email":
            _logger.info("Received non-email webhook event, skipping", extra={"event": event})
            return {"status": "success"}

        email = event.to_email()

        await CustomerService.handle_helpscout_email_sent(email, storage)

        return {"status": "success"}
    except Exception as e:
        _logger.exception("Error processing Helpscout webhook", extra={"error": e})
        raise HTTPException(status_code=400, detail=str(e))
