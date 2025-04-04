import logging
import os
from typing import Any, Literal

import stripe
from fastapi import APIRouter, Header, Request, Response
from pydantic import BaseModel

from api.dependencies.security import OrgSystemStorageDep
from api.dependencies.services import EmailServiceDep
from api.services.payments_service import PaymentSystemService
from core.domain.errors import DefaultError

router = APIRouter(prefix="/webhooks/stripe", include_in_schema=False)
_logger = logging.getLogger(__name__)


class PaymentIntentData(BaseModel):
    object: Literal["payment_intent"]
    id: str
    amount: int
    metadata: dict[str, Any]
    status: str

    class LastPaymentError(BaseModel):
        message: str | None

    last_payment_error: LastPaymentError | None = None

    @property
    def error_message(self) -> str | None:
        return self.last_payment_error.message if self.last_payment_error else None


async def verify_stripe_signature(
    request: Request,
    stripe_signature: str | None = Header(None, alias="Stripe-Signature"),
) -> stripe.Event:
    if not stripe_signature:
        raise DefaultError(
            "No signature header",
            capture=True,
            status_code=400,
        )

    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        raise DefaultError(
            "Webhook secret not configured",
            capture=True,
            status_code=500,
        )

    body = await request.body()
    stripe_event: stripe.Event = stripe.Webhook.construct_event(  # type: ignore
        payload=body,
        sig_header=str(stripe_signature),
        secret=str(webhook_secret),
    )
    _logger.info("Raw Stripe Event", extra={"stripe_event": stripe_event})
    return stripe_event


@router.post("")
async def stripe_webhook(
    storage: OrgSystemStorageDep,
    email_service: EmailServiceDep,
    request: Request,
    stripe_signature: str | None = Header(None, alias="Stripe-Signature"),
) -> Response:
    _logger.debug("Received Stripe webhook", extra={"request": request, "stripe_signature": stripe_signature})
    event = await verify_stripe_signature(request, stripe_signature)
    payment_service = PaymentSystemService(storage, email_service)

    match event.type:
        case "payment_intent.succeeded":
            payment_intent = PaymentIntentData.model_validate(event.data.object)
            await payment_service.handle_payment_success(payment_intent.metadata, payment_intent.amount / 100)
        case "payment_intent.requires_action":
            # Not sure what to do here, it should not happen for automatic payments
            payment_intent = PaymentIntentData.model_validate(event.data.object)
            await payment_service.handle_payment_requires_action(payment_intent.metadata)
        case "payment_intent.payment_failed":
            payment_intent = PaymentIntentData.model_validate(event.data.object)
            failure_reason = payment_intent.error_message
            if not failure_reason:
                _logger.error("Payment failed with an unknown error", extra={"event": event.data.object})
                failure_reason = "Payment failed with an unknown error"
            await payment_service.handle_payment_failure(payment_intent.metadata, failure_reason)
        case _:
            _logger.warning("Unhandled Stripe event", extra={"event": event.data.object})

    return Response(status_code=200)
