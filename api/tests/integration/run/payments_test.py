import asyncio
import json
from collections.abc import Callable
from typing import Any, Literal
from unittest.mock import AsyncMock, Mock, patch

import pytest
import stripe
from stripe._expandable_field import ExpandableField

from core.domain.models import Model
from tests.integration.common import (
    CLERK_BASE_URL,
    LOOPS_TRANSACTIONAL_URL,
    USER_JWT,
    IntegrationTestClient,
    result_or_raise,
)
from tests.utils import approx, fixtures_json


@pytest.fixture()
def stripe_customer() -> stripe.Customer:
    customer = stripe.Customer(
        id="cus_123",
        object="customer",
        name="Test Org",
        email="test@example.com",
    )
    # Then update with invoice settings after payment method is attached
    customer.invoice_settings = stripe.Customer.InvoiceSettings(
        default_payment_method={
            "id": "pm_123",
            "object": "payment_method",
            "type": "card",
            "card": {"last4": "4242", "brand": "visa", "exp_month": 12, "exp_year": 2025},
        },
    )
    def_payment_meth: ExpandableField[stripe.PaymentMethod] = stripe.PaymentMethod(
        id="pm_123",
        object="payment_method",
        type="card",
    )

    customer.invoice_settings.default_payment_method = def_payment_meth
    customer.invoice_settings.default_payment_method.card = stripe.PaymentMethod.Card()
    customer.invoice_settings.default_payment_method.card.last4 = "4242"
    customer.invoice_settings.default_payment_method.card.brand = "visa"
    customer.invoice_settings.default_payment_method.card.exp_month = 12
    customer.invoice_settings.default_payment_method.card.exp_year = 2025
    return customer


@pytest.fixture()
def stripe_payment_method() -> stripe.PaymentMethod:
    return stripe.PaymentMethod(
        id="pm_123",
        object="payment_method",
        type="card",
        card=stripe.Card(
            last4="4242",
            brand="visa",
            exp_month=12,
            exp_year=2025,
        ),
    )


@pytest.fixture
def stripe_payment_intent(test_client: IntegrationTestClient) -> stripe.PaymentIntent:
    payment_intent = stripe.PaymentIntent(
        id="pi_123",
        object="payment_intent",
        amount=500,  # $5.00
        status="requires_action",
        metadata={"tenant": test_client.tenant},
    )
    payment_intent.client_secret = "secret_123"
    return payment_intent


@pytest.fixture()
def mock_stripe(
    stripe_customer: stripe.Customer,
    stripe_payment_method: stripe.PaymentMethod,
    stripe_payment_intent: stripe.PaymentIntent,
):
    with (
        patch("stripe.Customer", spec=stripe.Customer) as customer_cls,
        patch("stripe.PaymentMethod", spec=stripe.PaymentMethod) as payment_method_cls,
        patch("stripe.PaymentIntent", spec=stripe.PaymentIntent) as payment_intent_cls,
        patch("stripe.Webhook", spec=stripe.Webhook) as webhook_cls,
    ):
        # Setup async method returns
        customer_cls.create_async = AsyncMock(return_value=stripe_customer)
        customer_cls.modify_async = AsyncMock(return_value=stripe_customer)
        customer_cls.retrieve_async = AsyncMock(return_value=stripe_customer)

        payment_method_cls.attach_async = AsyncMock(return_value=stripe_payment_method)
        payment_intent_cls.create_async = AsyncMock(return_value=stripe_payment_intent)
        payment_intent_cls.confirm_async = AsyncMock(return_value=Mock(status="succeeded"))

        mock = Mock(spec=stripe)
        mock.Customer = customer_cls
        mock.PaymentMethod = payment_method_cls
        mock.PaymentIntent = payment_intent_cls
        mock.Webhook = webhook_cls
        yield mock


@pytest.fixture(autouse=True)
def patch_payment_service_retry_delay():
    with patch("api.services.payments_service.PaymentSystemService.WAIT_BETWEEN_RETRIES_SECONDS", 0.01):
        yield


async def test_decrement_credits(test_client: IntegrationTestClient, mock_stripe: Mock):
    task = await test_client.create_task()

    # Check initial credits
    org = result_or_raise(await test_client.int_api_client.get("/organization/settings"))
    assert org["current_credits_usd"] == 10.0  # Initial credits
    assert org["automatic_payment_enabled"] is False, "sanity check"

    # Mock a response that will consume all credits
    test_client.mock_openai_call(
        usage={
            "prompt_tokens": int(round(4 * 1 / 0.000_002_5)),  # prompt count for $8 on GPT_4O_2024_11_20
            "completion_tokens": 0,
        },
    )

    # First run should succeed but consume all credits
    await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20)
    await test_client.wait_for_completed_tasks()

    # Verify credits are depleted
    org = result_or_raise(await test_client.int_api_client.get("/organization/settings"))
    assert org["automatic_payment_enabled"] is False, "sanity check"
    await test_client.wait_for_completed_tasks()

    # Decrement credits
    test_client.mock_openai_call(
        usage={
            "prompt_tokens": int(round(4 * 1 / 0.000_002_5)),  # prompt count for $4 on GPT_4O_2024_11_20
            "completion_tokens": 0,
        },
    )

    # First run should succeed but consume all credits
    await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20, use_cache="never")
    await test_client.wait_for_completed_tasks()

    # Verify credits are decremented
    org = result_or_raise(await test_client.int_api_client.get("/organization/settings"))
    assert org["automatic_payment_enabled"] is False

    # Nothing happens when we decrement credits when the automatic payment is disabled
    await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20, use_cache="never")
    await test_client.wait_for_completed_tasks()

    # Verify credits are decremented
    org = result_or_raise(await test_client.int_api_client.get("/organization/settings"))
    assert org["current_credits_usd"] < 0
    assert org["automatic_payment_enabled"] is False

    mock_stripe.PaymentIntent.create_async.assert_not_called()
    mock_stripe.PaymentIntent.confirm_async.assert_not_called()
    mock_stripe.PaymentMethod.retrieve_async.assert_not_called()


async def _setup_automatic_payment(test_client: IntegrationTestClient):
    org = await test_client.get_org()

    assert org["current_credits_usd"] == approx(10), "sanity check"
    assert org["automatic_payment_enabled"] is False, "sanity check"

    # Create customer, add payment method
    await test_client.post(
        "/organization/payments/payment-methods",
        json={"payment_method_id": "pm_123"},
    )

    # Enable automatic payments
    await test_client.put(
        "/organization/payments/automatic-payments",
        json={"opt_in": True, "threshold": 5, "balance_to_maintain": 10},
    )
    org = await test_client.get_org()
    assert org["current_credits_usd"] == approx(10)
    assert org["automatic_payment_enabled"] is True


def _assert_payment_created(
    test_client: IntegrationTestClient,
    mock_stripe: Mock,
    usd: float,
    metadata: dict[str, Any] | None = None,
):
    if metadata is None:
        metadata = {
            "tenant": test_client.tenant,
            "tenant_uid": str(test_client.tenant_uid),
            "organization_id": test_client.org.get("org_id") or None,
            "trigger": "automatic",
            "slug": test_client.org.get("slug") or None,
            "owner_id": test_client.org.get("owner_id") or None,
        }
    mock_stripe.PaymentIntent.create_async.assert_called_once_with(
        amount=approx(usd * 100, abs=1),  # ok at 1 cent diff
        currency="usd",
        customer="cus_123",
        payment_method="pm_123",
        setup_future_usage="off_session",
        automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
        metadata={k: v for k, v in metadata.items() if v is not None},
    )
    mock_stripe.PaymentIntent.confirm_async.assert_called_once()


async def _deplete_credits(test_client: IntegrationTestClient, task: dict[str, Any], usd: float):
    """Deplete the credits by creating a few runs. The total amount will be a bit more than the provided usd"""
    # Mock a response that will consume all credits
    test_client.mock_openai_call(
        usage={
            "prompt_tokens": int(round(usd * 1 / 0.000_002_5)),  # prompt count for $usd on GPT_4O_2024_11_20
            "completion_tokens": 0,
        },
    )

    # Run task to trigger credit depletion
    await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20, use_cache="never", autowait=False)
    # We also re-run the task to make sure we only run the payment once
    # Run antoher time before background jobs are completed
    test_client.mock_openai_call()  # usage here will be minimal and should not trigger a payment
    await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20, use_cache="never", autowait=False)

    await test_client.wait_for_completed_tasks()

    # Run another time after background jobs are completed
    test_client.mock_openai_call()  # usage here will be minimal and should not trigger a payment
    await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20, use_cache="never", autowait=False)
    await test_client.wait_for_completed_tasks()


async def _mock_stripe_webhook(
    test_client: IntegrationTestClient,
    mock_stripe: Mock,
    event_type: str = "payment_intent.succeeded",
    trigger: Literal["automatic", "manual"] = "automatic",
    amount: float = 800,
    wait_for: Callable[[], bool] | None = None,
):
    if wait_for is not None:
        for _ in range(10):
            if wait_for():
                break
            await asyncio.sleep(0.1)

    event = stripe.Event()
    event.id = "evt_123"
    event.type = event_type  # pyright: ignore
    event.data = stripe.Event.Data()
    metadata = {
        "tenant": test_client.tenant,
        "tenant_uid": str(test_client.tenant_uid),
        "organization_id": test_client.org.get("org_id") or None,
        "trigger": trigger,
        "slug": test_client.org.get("slug") or None,
        "owner_id": test_client.org.get("owner_id") or None,
    }
    event.data.object = {
        "object": "payment_intent",
        "id": "pi_123",
        "amount": amount,
        "metadata": {k: v for k, v in metadata.items() if v is not None},
        "status": "succeeded",
    }
    mock_stripe.Webhook.construct_event.return_value = event
    await test_client.post(
        "/webhooks/stripe",
        headers={"Stripe-Signature": "mock_signature"},
        json={"some": "payload"},
    )


async def test_automatic_payment_success(
    test_client: IntegrationTestClient,
    mock_stripe: Mock,
):
    task = await test_client.create_task()

    await _setup_automatic_payment(test_client)

    await _deplete_credits(test_client, task, 8)

    # Here we should have called stripe already
    _assert_payment_created(test_client, mock_stripe, 8)

    # Verify credits are decremented and not yet added because webhook is not yet mocked
    org = await test_client.get_org()
    assert org["current_credits_usd"] == approx(1.999, abs=0.001)  # pyright: ignore reportUnknownArgumentType

    mock_stripe.Webhook.construct_event.assert_not_called()

    # Send webhook event
    await _mock_stripe_webhook(test_client, mock_stripe, amount=800)

    # Verify credits are added
    org = await test_client.get_org()
    assert org["current_credits_usd"] == approx(9.999, abs=0.001)

    # Now check that we can do it again, organization should be unlocked for payment
    test_client.mock_openai_call(
        usage={
            # This will consume 5$, bring just below the 5$ threshold
            "prompt_tokens": int(round(5 * 1 / 0.000_002_5)),
            "completion_tokens": 0,
        },
    )

    mock_stripe.PaymentIntent.create_async.reset_mock()
    mock_stripe.PaymentIntent.confirm_async.reset_mock()

    await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20, use_cache="never")
    await test_client.wait_for_completed_tasks()
    _assert_payment_created(test_client, mock_stripe, 5.01)
    await _mock_stripe_webhook(test_client, mock_stripe, amount=501)
    org = await test_client.get_org()
    assert org["current_credits_usd"] == approx(10, abs=0.01)


def _prepare_organization_payment_failure_emails(test_client: IntegrationTestClient):
    test_client.httpx_mock.add_response(
        url=f"{CLERK_BASE_URL}/organizations/{test_client.org['org_id']}/memberships?role=admin&limit=5",
        json=fixtures_json("clerk/membership_list.json"),
    )
    test_client.httpx_mock.add_response(
        url=f"{CLERK_BASE_URL}/users?user_ids=user_1,user_2",
        json=fixtures_json("clerk/user_list.json"),
    )
    test_client.httpx_mock.add_response(
        url=LOOPS_TRANSACTIONAL_URL,
        status_code=200,
    )


async def test_automatic_payment_failure_with_retry(
    test_client: IntegrationTestClient,
    mock_stripe: Mock,
):
    """Test a payment failure with a retry when the user is an organization"""
    task = await test_client.create_task()

    await _setup_automatic_payment(test_client)

    # Also prepare for email send, we have an organization so all the admins should get an email
    _prepare_organization_payment_failure_emails(test_client)

    # Deplete credits which should trigger payments
    await _deplete_credits(test_client, task, 8)
    _assert_payment_created(test_client, mock_stripe, 8)

    # But now the call fails
    await _mock_stripe_webhook(test_client, mock_stripe, event_type="payment_intent.payment_failed")
    await test_client.wait_for_completed_tasks()

    # Credits were not added because the payment failed and organization has a payment failure
    org = await test_client.get_org()
    assert org["current_credits_usd"] == approx(1.999, abs=0.001)
    assert org["payment_failure"]
    assert org["payment_failure"]["failure_code"] == "payment_failed"

    # Check that the emails were sent
    email_requests = test_client.httpx_mock.get_requests(url=LOOPS_TRANSACTIONAL_URL)
    # 2 payment failed, 2 low balance
    assert len(email_requests) == 4
    emails = {json.loads(request.content)["email"] for request in email_requests}
    assert emails == {"john@example.com", "jane@example.com"}

    # Running does not trigger a new payment
    mock_stripe.PaymentIntent.create_async.reset_mock()
    mock_stripe.PaymentIntent.confirm_async.reset_mock()

    test_client.mock_openai_call()
    await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20, use_cache="never")
    mock_stripe.PaymentIntent.create_async.assert_not_called()
    mock_stripe.PaymentIntent.confirm_async.assert_not_called()

    # But we can retry
    mock_stripe.PaymentIntent.create_async.reset_mock()
    mock_stripe.PaymentIntent.confirm_async.reset_mock()

    # We have to run both at the same time otherwise retry will never return
    async with asyncio.TaskGroup() as tg:
        tg.create_task(test_client.post("/organization/payments/automatic-payments/retry"))
        # We delay by 10ms to make sure the payment intent is created before we call
        tg.create_task(
            _mock_stripe_webhook(
                test_client,
                mock_stripe,
                amount=800,
                wait_for=lambda: mock_stripe.PaymentIntent.confirm_async.call_count > 0,
            ),
        )

    _assert_payment_created(test_client, mock_stripe, 8)
    # Now we succeed

    org = await test_client.get_org()
    assert org["current_credits_usd"] == approx(10, abs=0.01)
    assert org.get("payment_failure") is None

    # And now we can run again and automatic payments are back
    mock_stripe.PaymentIntent.create_async.reset_mock()
    mock_stripe.PaymentIntent.confirm_async.reset_mock()

    await _deplete_credits(test_client, task, 5)
    _assert_payment_created(test_client, mock_stripe, 5.01)
    await _mock_stripe_webhook(test_client, mock_stripe, amount=501)
    org = await test_client.get_org()
    assert org["current_credits_usd"] == approx(10, abs=0.01)


async def test_automatic_payment_failure_with_retry_single_user(
    test_client: IntegrationTestClient,
    mock_stripe: Mock,
):
    """Test a payment failure with a retry when the user is a single user"""
    test_client.authenticate(USER_JWT)

    org = await test_client.refresh_org_data()
    assert org["org_id"] is None, "sanity check"
    assert org["owner_id"] == "user_1234", "sanity check"

    payment_metadata = {
        "tenant": test_client.tenant,
        "tenant_uid": str(test_client.tenant_uid),
        "trigger": "automatic",
        "owner_id": "user_1234",
    }

    task = await test_client.create_task()
    await _setup_automatic_payment(test_client)

    # Also prepare for email send, we have an organization so all the admins should get an email

    test_client.httpx_mock.add_response(
        url=f"{CLERK_BASE_URL}/users/user_1234",
        json=fixtures_json("clerk/user.json"),
    )
    test_client.httpx_mock.add_response(
        url=LOOPS_TRANSACTIONAL_URL,
        status_code=200,
    )

    # Deplete credits which should trigger payments
    await _deplete_credits(test_client, task, 8)
    _assert_payment_created(test_client, mock_stripe, 8, metadata=payment_metadata)

    # But now the call fails
    await _mock_stripe_webhook(test_client, mock_stripe, event_type="payment_intent.payment_failed")
    await test_client.wait_for_completed_tasks()

    # Credits were not added because the payment failed and organization has a payment failure
    org = await test_client.get_org()
    assert org["current_credits_usd"] == approx(1.999, abs=0.001)
    assert org["payment_failure"]
    assert org["payment_failure"]["failure_code"] == "payment_failed"

    # Check that the emails were sent
    email_requests = test_client.httpx_mock.get_requests(url=LOOPS_TRANSACTIONAL_URL)
    # 1 payment failed, 1 low balance
    assert len(email_requests) == 2
    emails = {json.loads(request.content)["email"] for request in email_requests}
    assert emails == {"john@example.com"}

    # Running does not trigger a new payment
    mock_stripe.PaymentIntent.create_async.reset_mock()
    mock_stripe.PaymentIntent.confirm_async.reset_mock()

    test_client.mock_openai_call()
    await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20, use_cache="never")
    mock_stripe.PaymentIntent.create_async.assert_not_called()
    mock_stripe.PaymentIntent.confirm_async.assert_not_called()

    # But we can retry
    mock_stripe.PaymentIntent.create_async.reset_mock()
    mock_stripe.PaymentIntent.confirm_async.reset_mock()
    async with asyncio.TaskGroup() as tg:
        tg.create_task(test_client.post("/organization/payments/automatic-payments/retry"))
        # We delay by 10ms to make sure the payment intent is created before we call
        tg.create_task(
            _mock_stripe_webhook(
                test_client,
                mock_stripe,
                amount=800,
                wait_for=lambda: mock_stripe.PaymentIntent.confirm_async.call_count > 0,
            ),
        )

    _assert_payment_created(test_client, mock_stripe, 8, metadata=payment_metadata)

    org = await test_client.get_org()
    assert org["current_credits_usd"] == approx(10, abs=0.01)
    assert org.get("payment_failure") is None

    # And now we can run again and automatic payments are back
    mock_stripe.PaymentIntent.create_async.reset_mock()
    mock_stripe.PaymentIntent.confirm_async.reset_mock()

    await _deplete_credits(test_client, task, 5)
    _assert_payment_created(test_client, mock_stripe, 5.01, metadata=payment_metadata)
    await _mock_stripe_webhook(test_client, mock_stripe, amount=501)
    org = await test_client.get_org()
    assert org["current_credits_usd"] == approx(10, abs=0.01)


# async def test_enable_automatic_payment_multiple_runs(
#     test_client: IntegrationTestClient,
#     stripe_webhook_event: StripeEvent,
#     mocked_stripe: dict[str, Any],
# ):
#     task = await test_client.create_task()

#     # Check initial credits and automatic payment setting
#     org = result_or_raise(await test_client.int_api_client.get("/organization/settings"))
#     assert org["current_credits_usd"] == 10.0
#     assert org["automatic_payment_enabled"] is False

#     test_client.mock_openai_call(
#         usage={
#             "prompt_tokens": int(round(2 * 1 / 0.000_002_5)),
#             "completion_tokens": 0,
#         },
#     )

#     # Run task to trigger credit depletion
#     await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20, use_cache="never")
#     await test_client.wait_for_completed_tasks()

#     # Enable automatic payments
#     result_or_raise(
#         await test_client.int_api_client.put(
#             "/organization/payments/automatic-payments",
#             json={"opt_in": True, "threshold": 10, "balance_to_maintain": 10},
#         ),
#     )

#     # Verify credits
#     org = result_or_raise(await test_client.int_api_client.get("/organization/settings"))
#     expected_credits = 8  # 10 - 2
#     assert abs(org["current_credits_usd"] - expected_credits) < 0.001
#     assert org["automatic_payment_enabled"] is True

#     # Create customer and add payment method
#     result_or_raise(await test_client.int_api_client.post("/organization/payments/customers"))
#     result_or_raise(
#         await test_client.int_api_client.post(
#             "/organization/payments/payment-methods",
#             json={"payment_method_id": "pm_123"},
#         ),
#     )

#     # Process webhook

#     async def send_webhook():
#         with patch("stripe.Webhook.construct_event", return_value=stripe_webhook_event):
#             await test_client.int_api_client.post(
#                 "/webhooks/stripe",
#                 headers={"Stripe-Signature": "mock_signature"},
#                 json={"some": "payload"},
#             )

#     # Run multiple tasks concurrently
#     await asyncio.gather(
#         test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20, use_cache="never"),
#         send_webhook(),
#         test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20, use_cache="never"),
#         test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20, use_cache="never"),
#     )
#     await test_client.wait_for_completed_tasks()

#     # not a full test, because the credits are added from webhook, but outlines the expected behavior
#     # Verify final credits
#     org = result_or_raise(await test_client.int_api_client.get("/organization/settings"))
#     expected_credits = 7  # 10 - 6 + 5 (only once) - 2 (third run)
#     assert abs(org["current_credits_usd"] - expected_credits) < 0.001
#     assert org["automatic_payment_enabled"] is True


# async def test_enable_automatic_payment_multiple_runs_with_failed_payment(
#     test_client: IntegrationTestClient,
#     mocked_stripe: dict[str, Any],
# ):
#     task = await test_client.create_task()

#     # Check initial credits
#     org = result_or_raise(await test_client.int_api_client.get("/organization/settings"))
#     assert org["current_credits_usd"] == 10.0
#     assert org["automatic_payment_enabled"] is False

#     test_client.mock_openai_call(
#         usage={
#             "prompt_tokens": int(round(5 * 1 / 0.000_002_5)),
#             "completion_tokens": 0,
#         },
#     )

#     # Run task to trigger credit depletion
#     await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20, use_cache="never")
#     await test_client.wait_for_completed_tasks()

#     # Enable automatic payments
#     result_or_raise(
#         await test_client.int_api_client.put(
#             "/organization/payments/automatic-payments",
#             json={"opt_in": True, "threshold": 5, "balance_to_maintain": 10},
#         ),
#     )
#     org = result_or_raise(await test_client.int_api_client.get("/organization/settings"))
#     assert org["current_credits_usd"] == 5.0
#     assert org["automatic_payment_enabled"] is True
#     assert org["automatic_payment_threshold"] == 5.0
#     assert org["automatic_payment_balance_to_maintain"] == 10.0

#     # Create customer and add payment method
#     result_or_raise(await test_client.int_api_client.post("/organization/payments/customers"))
#     result_or_raise(
#         await test_client.int_api_client.post(
#             "/organization/payments/payment-methods",
#             json={"payment_method_id": "pm_123"},
#         ),
#     )

#     # Override payment intent confirmation to simulate failure
#     payment_intent = mocked_stripe["payment_intent"]
#     payment_intent.status = "requires_action"

#     # Run task to trigger failed payment
#     await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20, use_cache="never")
#     await test_client.wait_for_completed_tasks()

#     # Verify credits and payment failure
#     org = result_or_raise(await test_client.int_api_client.get("/organization/settings"))
#     expected_credits = 0  # 10 - 5 - 5
#     assert abs(org["current_credits_usd"] - expected_credits) < 0.001
#     assert org["automatic_payment_enabled"] is True
#     assert org["last_payment_failed_at"] is not None


async def test_add_payment_method_invalid_card(
    test_client: IntegrationTestClient,
    mock_stripe: Mock,
):
    # Mock stripe.PaymentMethod.attach_async to raise a CardError
    mock_stripe.PaymentMethod.attach_async.side_effect = stripe.CardError(
        message="Your card's security code is incorrect.",
        param="cvc",
        code="incorrect_cvc",
        http_status=402,
        json_body={
            "error": {
                "message": "Your card's security code is incorrect.",
                "param": "cvc",
                "code": "incorrect_cvc",
            },
        },
    )

    # Attempt to add invalid payment method
    response = await test_client.int_api_client.post(
        "/organization/payments/payment-methods",
        json={"payment_method_id": "pm_123"},
    )

    assert response.status_code == 402
    error_data = response.json()
    assert error_data["error"]["message"] == "Your card's security code is incorrect."
    assert error_data["error"]["code"] == "card_validation_error"

    # Verify the payment method was not attached
    mock_stripe.PaymentMethod.attach_async.assert_called_once()
    mock_stripe.Customer.create_async.assert_called_once()


# async def test_enable_automatic_payment_multiple_runs_with_failed_payment_and_payment_method_added_after_failure(
#     test_client: IntegrationTestClient,
#     mocked_stripe: dict[str, Any],
# ):
#     task = await test_client.create_task()

#     # Check initial credits
#     org = result_or_raise(await test_client.int_api_client.get("/organization/settings"))
#     assert org["current_credits_usd"] == 10.0
#     assert org["automatic_payment_enabled"] is False

#     test_client.mock_openai_call(
#         usage={
#             "prompt_tokens": int(round(5 * 1 / 0.000_002_5)),
#             "completion_tokens": 0,
#         },
#     )

#     # Run task to trigger credit depletion
#     await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20, use_cache="never")
#     await test_client.wait_for_completed_tasks()

#     # Enable automatic payments
#     result_or_raise(
#         await test_client.int_api_client.put(
#             "/organization/payments/automatic-payments",
#             json={"opt_in": True, "threshold": 5, "balance_to_maintain": 10},
#         ),
#     )
#     org = result_or_raise(await test_client.int_api_client.get("/organization/settings"))
#     assert org["current_credits_usd"] == 5.0
#     assert org["automatic_payment_enabled"] is True
#     assert org["automatic_payment_threshold"] == 5.0
#     assert org["automatic_payment_balance_to_maintain"] == 10.0

#     # Create customer and add payment method
#     result_or_raise(await test_client.int_api_client.post("/organization/payments/customers"))
#     result_or_raise(
#         await test_client.int_api_client.post(
#             "/organization/payments/payment-methods",
#             json={"payment_method_id": "pm_123"},
#         ),
#     )

#     # Override payment intent confirmation to simulate failure
#     payment_intent = mocked_stripe["payment_intent"]
#     payment_intent.status = "requires_action"

#     # Run task to trigger failed payment
#     await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20, use_cache="never")
#     await test_client.wait_for_completed_tasks()

#     # Verify credits and payment failure
#     org = result_or_raise(await test_client.int_api_client.get("/organization/settings"))
#     expected_credits = 0  # 10 - 5 - 5
#     assert abs(org["current_credits_usd"] - expected_credits) < 0.001
#     assert org["automatic_payment_enabled"] is True
#     assert org["last_payment_failed_at"] is not None

#     # Add payment method
#     result_or_raise(
#         await test_client.int_api_client.post(
#             "/organization/payments/payment-methods",
#             json={"payment_method_id": "pm_123"},
#         ),
#     )

#     org = result_or_raise(await test_client.int_api_client.get("/organization/settings"))
#     assert org["current_credits_usd"] == 0.0
#     assert org["automatic_payment_enabled"] is True
#     assert org["last_payment_failed_at"] is None


async def test_automatic_payment_failure_manual_credit_addition(
    test_client: IntegrationTestClient,
    mock_stripe: Mock,
):
    """Test a payment failure with a retry when the user is an organization"""
    task = await test_client.create_task()

    await _setup_automatic_payment(test_client)

    # Also prepare for email send, we have an organization so all the admins should get an email
    _prepare_organization_payment_failure_emails(test_client)

    # Deplete credits which should trigger payments
    await _deplete_credits(test_client, task, 8)
    _assert_payment_created(test_client, mock_stripe, 8)

    # But now the call fails
    await _mock_stripe_webhook(test_client, mock_stripe, event_type="payment_intent.payment_failed")
    await test_client.wait_for_completed_tasks()

    # Credits were not added because the payment failed and organization has a payment failure
    org = await test_client.get_org()
    assert org["current_credits_usd"] == approx(1.999, abs=0.001)
    assert org["payment_failure"]
    assert org["payment_failure"]["failure_code"] == "payment_failed"

    # Now I trigger a manual payment
    await _mock_stripe_webhook(test_client, mock_stripe, amount=800, trigger="manual")

    org = await test_client.get_org()
    assert org["current_credits_usd"] == approx(10, abs=0.01)
    assert org.get("payment_failure") is None

    # And now we can run again and automatic payments are back
    mock_stripe.PaymentIntent.create_async.reset_mock()
    mock_stripe.PaymentIntent.confirm_async.reset_mock()

    await _deplete_credits(test_client, task, 5)
    _assert_payment_created(test_client, mock_stripe, 5.01)
    await _mock_stripe_webhook(test_client, mock_stripe, amount=501)
    org = await test_client.get_org()
    assert org["current_credits_usd"] == approx(10, abs=0.01)
