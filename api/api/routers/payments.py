import os

import stripe
from fastapi import APIRouter
from pydantic import BaseModel, Field, model_validator

from api.dependencies.security import RequiredUserDep, RequiredUserOrganizationDep
from api.dependencies.services import PaymentServiceDep, PaymentSystemServiceDep
from api.services.payments_service import PaymentMethodResponse, PaymentService
from api.tags import RouteTags
from core.utils.background import add_background_task

router = APIRouter(prefix="/organization/payments", tags=[RouteTags.PAYMENTS])


stripe.api_key = os.getenv("STRIPE_API_KEY")


class PaymentMethodRequest(BaseModel):
    payment_method_id: str
    payment_method_currency: str = "USD"


class PaymentMethodIdResponse(BaseModel):
    payment_method_id: str


@router.post("/payment-methods", description="Add a payment method to the organization")
async def add_payment_method(
    payment_service: PaymentServiceDep,
    request: PaymentMethodRequest,
    user_org: RequiredUserOrganizationDep,
    required_user: RequiredUserDep,
) -> PaymentMethodIdResponse:
    payment_method_id = await payment_service.add_payment_method(
        user_org,
        request.payment_method_id,
        required_user.sub,
    )
    return PaymentMethodIdResponse(
        payment_method_id=payment_method_id,
    )


class CustomerCreatedResponse(BaseModel):
    customer_id: str


@router.post(
    "/customers",
    description="Create a customer in Stripe for the organization",
    deprecated=True,
    include_in_schema=False,
)
async def create_customer(
    payment_service: PaymentServiceDep,
    userDep: RequiredUserDep,
) -> CustomerCreatedResponse:
    return CustomerCreatedResponse(customer_id=await payment_service.create_customer(userDep.sub))


class PaymentIntentCreatedResponse(BaseModel):
    client_secret: str = Field(
        description="The stripe client secret for the payment intent, "
        "that can be used by the client to retrieve the payment using the client secret and a publishable key.",
    )
    payment_intent_id: str


class CreatePaymentIntentRequest(BaseModel):
    amount: float


@router.post("/payment-intents", description="Create a manual payment intent in Stripe for the organization")
async def create_payment_intent(
    request: CreatePaymentIntentRequest,
    user_org: RequiredUserOrganizationDep,
) -> PaymentIntentCreatedResponse:
    payment_intent = await PaymentService.create_payment_intent(user_org, request.amount, trigger="manual")
    if not payment_intent.client_secret:
        raise ValueError("Payment intent creation failed")
    return PaymentIntentCreatedResponse(
        client_secret=payment_intent.client_secret,
        payment_intent_id=payment_intent.payment_intent_id,
    )


@router.get("/payment-methods", description="Get the payment method attached to the organization")
async def get_payment_method(
    user_org: RequiredUserOrganizationDep,
) -> PaymentMethodResponse | None:
    return await PaymentService.get_payment_method(user_org)


@router.delete("/payment-methods", description="Delete the payment method attached to the organization")
async def delete_payment_method(
    payment_service: PaymentServiceDep,
    user_org: RequiredUserOrganizationDep,
) -> None:
    await payment_service.delete_payment_method(user_org)


class AutomaticPaymentRequest(BaseModel):
    opt_in: bool
    threshold: float | None = None
    balance_to_maintain: float | None = None

    @model_validator(mode="after")
    def validate_threshold_and_balance_to_maintain(self: "AutomaticPaymentRequest") -> "AutomaticPaymentRequest":
        if self.opt_in:
            if self.threshold is None or self.balance_to_maintain is None:
                raise ValueError("Threshold and balance_to_maintain are required when opt_in is true")
            if self.threshold > self.balance_to_maintain:
                raise ValueError("Threshold must be greater than balance_to_maintain")
        else:
            if self.threshold is not None or self.balance_to_maintain is not None:
                raise ValueError("Threshold and balance_to_maintain must be None when opt_in is false")
        return self


@router.put("/automatic-payments", description="Enable or disable automatic payments")
async def update_automatic_payments(
    request: AutomaticPaymentRequest,
    payment_service: PaymentServiceDep,
    payment_system_service: PaymentSystemServiceDep,
    user_org: RequiredUserOrganizationDep,
) -> None:
    await payment_service.configure_automatic_payment(
        opt_in=request.opt_in,
        threshold=request.threshold,
        balance_to_maintain=request.balance_to_maintain,
    )
    if request.opt_in:
        # Trigger a credit decrement if 9 to trigger a payment if needed
        add_background_task(payment_system_service.decrement_credits(user_org.tenant, 0))


@router.post("/automatic-payments/retry", description="Retry a failed automatic payment")
async def retry_automatic_payment(
    payment_service: PaymentSystemServiceDep,
    user_org: RequiredUserOrganizationDep,
) -> None:
    await payment_service.retry_automatic_payment(user_org)
