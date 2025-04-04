import asyncio
import logging
import os
from math import ceil
from typing import Literal, NamedTuple

import stripe
from pydantic import BaseModel, field_serializer, field_validator

from core.domain.errors import BadRequestError, DefaultError, InternalError
from core.domain.tenant_data import TenantData
from core.services.emails.email_service import EmailService
from core.storage import ObjectNotFoundException
from core.storage.organization_storage import OrganizationStorage, OrganizationSystemStorage
from core.utils.background import add_background_task
from core.utils.fields import datetime_factory
from core.utils.models.dumps import safe_dump_pydantic_model

_logger = logging.getLogger("PaymentService")

stripe.api_key = os.getenv("STRIPE_API_KEY")


class PaymentMethodResponse(BaseModel):
    payment_method_id: str
    last4: str
    brand: str
    exp_month: int
    exp_year: int


class PaymentIntent(NamedTuple):
    client_secret: str
    payment_intent_id: str


class _CustomerMetadata(BaseModel):
    tenant: str
    tenant_uid: int = 0
    slug: str | None = None
    organization_id: str | None = None
    owner_id: str | None = None

    @field_serializer("tenant_uid")
    def serialize_tenant_uid(self, tenant_uid: int) -> str:
        return str(tenant_uid)

    @field_validator("tenant_uid")
    def validate_tenant_uid(cls, v: int | str) -> int:
        if isinstance(v, str):
            return int(v)
        return v


class _IntentMetadata(_CustomerMetadata):
    trigger: Literal["automatic", "manual"] = "manual"


class PaymentService:
    def __init__(self, org_storage: OrganizationStorage):
        self._org_storage = org_storage

    @classmethod
    def _get_stripe_customer_id_from_org(cls, org_settings: TenantData) -> str:
        if org_settings.stripe_customer_id is None:
            raise BadRequestError(
                "Organization has no Stripe customer ID",
                capture=True,
                extra={"org_settings": safe_dump_pydantic_model(org_settings)},
            )
        return org_settings.stripe_customer_id

    async def add_payment_method(
        self,
        org_settings: TenantData,
        payment_method_id: str,
        user_email: str,
    ) -> str:
        stripe_customer_id = org_settings.stripe_customer_id
        if stripe_customer_id is None:
            stripe_customer_id = await self.create_customer(user_email)

        payment_method = await stripe.PaymentMethod.attach_async(
            payment_method_id,
            customer=stripe_customer_id,
        )

        # Set as default payment method
        await stripe.Customer.modify_async(
            stripe_customer_id,
            invoice_settings={"default_payment_method": payment_method.id},
        )

        return payment_method.id

    async def create_customer(self, user_email: str) -> str:
        if not stripe.api_key:
            _logger.error("Stripe API key is not set. Skipping customer creation.")
            return ""

        org_settings = await self._org_storage.get_organization()
        if org_settings.stripe_customer_id is not None:
            return org_settings.stripe_customer_id

        metadata = _CustomerMetadata(
            organization_id=org_settings.org_id or None,
            tenant=org_settings.tenant,
            slug=org_settings.slug or None,
            tenant_uid=org_settings.uid,
            owner_id=org_settings.owner_id or None,
        )

        # TODO: protect against race conditions here, we could be creating multiple customers
        customer = await stripe.Customer.create_async(
            name=org_settings.name or org_settings.slug,
            email=user_email,
            metadata=metadata.model_dump(exclude_none=True),
        )

        await self._org_storage.update_customer_id(stripe_customer_id=customer.id)
        return customer.id

    @classmethod
    async def create_payment_intent(
        cls,
        org_settings: TenantData,
        amount: float,
        trigger: Literal["automatic", "manual"],
    ) -> PaymentIntent:
        stripe_customer_id = cls._get_stripe_customer_id_from_org(org_settings)

        customer = await stripe.Customer.retrieve_async(
            stripe_customer_id,
            expand=["invoice_settings.default_payment_method"],
        )
        if customer.invoice_settings is None or customer.invoice_settings.default_payment_method is None:
            # This can happen if the client creates a payment intent before
            # Setting a default payment method.
            raise BadRequestError(
                "Organization has no default payment method",
                capture=True,
                extra={"tenant": org_settings.tenant},
            )

        metadata = _IntentMetadata(
            organization_id=org_settings.org_id or None,
            tenant=org_settings.tenant,
            slug=org_settings.slug or None,
            tenant_uid=org_settings.uid,
            owner_id=org_settings.owner_id or None,
            trigger=trigger,
        )

        payment_intent = await stripe.PaymentIntent.create_async(
            amount=int(ceil(amount * 100)),
            currency="usd",
            customer=stripe_customer_id,
            payment_method=customer.invoice_settings.default_payment_method.id,  # pyright: ignore
            setup_future_usage="off_session",
            # For automatic payment processing, we need to disable redirects to avoid getting stuck in a redirect path.
            # This does not affect manual payment processing.
            automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
            metadata=metadata.model_dump(exclude_none=True),
        )

        # Client secret is not a great name but from the stripe doc it's
        # meant to be used by the client in combination with a publishable key.
        if not payment_intent.client_secret:
            raise ValueError("Payment intent has no client secret")

        return PaymentIntent(
            client_secret=payment_intent.client_secret,
            payment_intent_id=payment_intent.id,
        )

    @classmethod
    async def get_payment_method(cls, org_settings: TenantData) -> PaymentMethodResponse | None:
        if not stripe.api_key:
            _logger.error("Stripe API key is not set. Skipping payment method retrieval.")
            return None
        if not org_settings.stripe_customer_id:
            return None

        customer = await stripe.Customer.retrieve_async(
            org_settings.stripe_customer_id,
            expand=["invoice_settings.default_payment_method"],
        )
        if customer.invoice_settings is None:
            raise ValueError("Organization has no invoice settings")

        if not customer.invoice_settings.default_payment_method:
            return None

        pm = customer.invoice_settings.default_payment_method
        return PaymentMethodResponse(
            payment_method_id=pm.id,  # pyright: ignore
            last4=pm.card.last4,  # pyright: ignore
            brand=pm.card.brand,  # pyright: ignore
            exp_month=pm.card.exp_month,  # pyright: ignore
            exp_year=pm.card.exp_year,  # pyright: ignore
        )

    async def delete_payment_method(self, org_settings: TenantData) -> None:
        stripe_customer_id = self._get_stripe_customer_id_from_org(org_settings)

        customer = await stripe.Customer.retrieve_async(stripe_customer_id)

        invoice_settings = customer.invoice_settings
        if invoice_settings is None:
            _logger.info("Organization has no invoice settings")
            return

        default_payment_method = invoice_settings.default_payment_method
        if default_payment_method is None:
            _logger.info("Organization has no default payment method")
            return

        await stripe.PaymentMethod.detach_async(
            default_payment_method,  # pyright: ignore
        )

        await stripe.Customer.modify_async(
            stripe_customer_id,
            invoice_settings={"default_payment_method": ""},
        )

        # Opt-out from automatic payments
        await self._org_storage.update_automatic_payment(opt_in=False, threshold=None, balance_to_maintain=None)

        _logger.info("Deleted payment method", extra={"payment_method_id": default_payment_method})  # pyright: ignore

    async def configure_automatic_payment(
        self,
        opt_in: bool,
        threshold: float | None,
        balance_to_maintain: float | None,
    ):
        await self._org_storage.update_automatic_payment(opt_in, threshold, balance_to_maintain)


class PaymentSystemService:
    """A payment service that is not tied to a specific organization.
    It is used to handle payments for all organizations."""

    WAIT_BETWEEN_RETRIES_SECONDS = 1

    def __init__(self, org_storage: OrganizationSystemStorage, email_service: EmailService):
        self._org_storage = org_storage
        self._email_service = email_service

    @classmethod
    def _autocharge_amount(cls, tenant: TenantData, min_amount: float) -> float:
        """Returns the amount to charge or `min_amount` if no amount is needed"""
        if (
            tenant.automatic_payment_threshold is None
            or tenant.automatic_payment_balance_to_maintain is None
            or tenant.current_credits_usd > tenant.automatic_payment_threshold
        ):
            return min_amount

        amount = tenant.automatic_payment_balance_to_maintain - tenant.current_credits_usd
        # This can happen if automatic_payment_threshold > automatic_payment_balance_to_maintain
        # For example: threshold = 100, maintain = 50, current = 75
        # This would be a stupid case.
        if amount <= min_amount:
            _logger.warning(
                "Automatic payment would charge negative amount",
                extra={"tenant": tenant.model_dump(exclude_none=True, exclude={"providers"})},
            )
            # Returning the balance to maintain to avoid charging 0
            return min_amount or tenant.automatic_payment_balance_to_maintain

        return amount

    async def _start_automatic_payment_for_locked_org(self, org_settings: TenantData, min_amount: float):
        """Create and confirm a payment intent on Stripe.
        This function expects that the org has already been locked for payment.
        It does not add credits or unlock the organization for intents since
        we need to wait for the webhook."""

        charge_amount = self._autocharge_amount(org_settings, min_amount)
        if not charge_amount:
            # This should never happen
            raise InternalError(
                "Charge amount is None. Discarding Automatic payment",
                extra={"org_settings": org_settings.model_dump()},
            )

        _logger.info(
            "Organization has less than threshold credits so automatic payment processing is starting",
            extra={"organization_settings": org_settings.model_dump()},
        )

        payment_intent = await PaymentService.create_payment_intent(org_settings, charge_amount, trigger="automatic")

        default_payment_method = await PaymentService.get_payment_method(org_settings)
        if default_payment_method is None:
            raise InternalError(
                "Organization has no default payment method",
                extra={"org_settings": org_settings.model_dump()},
            )

        # We need to confirm the payment so that it does not
        # remain in requires_confirmation state
        # From https://docs.stripe.com/payments/paymentintents/lifecycle it looks like
        # We may not need to do this in 2 steps (create + confirm) but ok for now
        res = await stripe.PaymentIntent.confirm_async(
            payment_intent.payment_intent_id,
            payment_method=default_payment_method.payment_method_id,
        )
        if not res.status == "succeeded":
            raise InternalError(
                "Confirming payment intent failed",
                extra={"confirm_response": res},
            )

    async def _unlock_payment_for_failure(
        self,
        tenant: str,
        code: Literal["internal", "payment_failed"],
        failure_reason: str,
    ):
        await self._org_storage.unlock_payment_for_failure(
            tenant=tenant,
            now=datetime_factory(),
            code=code,
            failure_reason=failure_reason,
        )

        add_background_task(self._email_service.send_payment_failure_email(tenant))

    async def trigger_automatic_payment_if_needed(
        self,
        tenant: str,
        min_amount: float,
    ):
        """Trigger an automatic payment
        If `min_amount` is provided, a payment will be triggered no matter what the current balance is.

        Returns true if the payment was triggered successfully"""
        org_settings = await self._org_storage.attempt_lock_for_payment(tenant)

        if not org_settings:
            # There is already a payment being processed so there is no need to retry
            _logger.info("Failed to lock for payment")
            return False

        # TODO: check for org autopay status

        try:
            await self._start_automatic_payment_for_locked_org(org_settings, min_amount=min_amount)
        except Exception:
            await self._unlock_payment_for_failure(
                tenant,
                code="internal",
                failure_reason="The payment process could not be initiated. This could be due to an internal error on "
                "our side or Stripe's. Your runs will not be locked for now until the issue is resolved.",
            )
            # TODO: send slack message, this is important as the error could be on our side
            # For now, since we don't really know what could cause the failure, we should fix manually
            # by updating the db or triggering a retry on the customer account.
            _logger.exception("Automatic payment failed due to an internal error", extra={"tenant": tenant})
            return False

        return True

    async def decrement_credits(self, event_tenant: str, credits: float) -> None:
        org_doc = await self._org_storage.decrement_credits(tenant=event_tenant, credits=credits)

        if (
            org_doc.automatic_payment_enabled
            and not org_doc.locked_for_payment
            and not org_doc.payment_failure
            and self._autocharge_amount(org_doc, min_amount=0)
        ):
            # Not using the amount here, we will get the final amount post lock
            # The minimum payment amount is 2$ to avoid cases where the threshold and balance to maintain are
            # too close
            await self.trigger_automatic_payment_if_needed(org_doc.tenant, min_amount=2)
            return

        # We fail silently here, no point in failint the entire
        add_background_task(self._send_low_credits_email_if_needed(org_doc))

    @classmethod
    def _get_tenant_from_metadata(cls, metadata: dict[str, str]) -> str:
        tenant = metadata.get("tenant")
        if not tenant:
            raise InternalError(
                "No tenant in payment intent metadata",
                extra={"metadata": metadata},
            )
        return tenant

    async def handle_payment_success(self, metadata: dict[str, str], amount: float):
        try:
            parsed_metadata = _IntentMetadata.model_validate(metadata)
            if parsed_metadata.trigger == "automatic":
                await self._org_storage.unlock_payment_for_success(parsed_metadata.tenant, amount)
                return
            # Otherwise we just need to add the credits
            await self._org_storage.add_credits_to_tenant(parsed_metadata.tenant, amount)
        except Exception as e:
            # Wrap everything in an InternalError to make sure it's easy to spot
            raise InternalError(
                "Urgent: Failed to process adding credits",
                extra={"metadata": metadata, "amount": amount},
            ) from e

    async def handle_payment_requires_action(self, metadata: dict[str, str]):
        parsed_metadata = _IntentMetadata.model_validate(metadata)
        if parsed_metadata.trigger == "automatic":
            _logger.error("Automatic payment requires action", extra={"metadata": metadata})

    async def handle_payment_failure(self, metadata: dict[str, str], failure_reason: str):
        parsed_metadata = _IntentMetadata.model_validate(metadata)
        if parsed_metadata.trigger == "automatic":
            await self._unlock_payment_for_failure(
                parsed_metadata.tenant,
                code="payment_failed",
                failure_reason=failure_reason,
            )

    async def retry_automatic_payment(self, org_data: TenantData):
        if not org_data.payment_failure:
            raise BadRequestError(
                "Cannot retry payment for an organization that has not failed",
                # Capturing, that would mean a bug in the frontend
                capture=True,
                extra={"org_data": org_data.model_dump()},
            )

        if not await self.trigger_automatic_payment_if_needed(org_data.tenant, min_amount=1):
            # Let's just check if the error magically resolved
            try:
                failure = await self._org_storage.check_unlocked_payment_failure(org_data.tenant)
                if not failure:
                    return
            except ObjectNotFoundException:
                # Organization is locked
                pass
            # No need to log, error will already be logged elsewhere
            raise DefaultError(
                "The payment could not be triggered, either because a payment is already in progress "
                "or because of an internal error",
                code="payment_failed",
                status_code=402,  # conflict
            )

        # Organization is now locked to we can wait until it is unlocked and check whether
        # the failure has been cleared or not
        # We retry a total of 30 times so 30s
        for _ in range(30):
            try:
                payment_failure = await self._org_storage.check_unlocked_payment_failure(org_data.tenant)
            except ObjectNotFoundException:
                # Organization is locked so we can keep retrying
                await asyncio.sleep(self.WAIT_BETWEEN_RETRIES_SECONDS)
                continue

            if payment_failure:
                raise DefaultError(
                    "The payment did not succeed",
                    code="payment_failed",
                    status_code=402,  # payment_required
                )
            # Otherwise we are done
            return
        raise InternalError(
            "An internal error occurred and we never received an update on the payment",
            code="payment_failed",
            status_code=402,  # payment_required
        )

    async def _send_low_credits_email_if_needed(self, org_data: TenantData):
        # For now only a single email at $5
        threshold = 5

        if not org_data.should_send_low_credits_email(threshold_usd=threshold):
            return

        try:
            await self._email_service.send_low_credits_email(org_data.tenant)
        except Exception:
            _logger.exception("Failed to send low credits email", extra={"tenant": org_data.tenant})

        await self._org_storage.add_low_credits_email_sent(org_data.tenant, threshold)
