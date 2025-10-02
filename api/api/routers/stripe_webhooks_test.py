# pyright: reportPrivateUsage=false

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
import stripe
from httpx import AsyncClient

from api.routers.stripe_webhooks import _skip_webhook, verify_stripe_signature
from core.domain.errors import DefaultError


@pytest.fixture(autouse=True)
def mock_stripe_webhook_secret():
    with patch.dict("os.environ", {"STRIPE_WEBHOOK_SECRET": "whsec_test_secret"}):
        yield


class TestVerifyStripeSignature:
    async def test_success(self, monkeypatch: Mock):
        mock_event = {
            "id": "evt_123",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "object": "payment_intent",
                    "id": "pi_123",
                    "amount": 1000,  # $10.00 in cents
                    "metadata": {"tenant": "test-tenant"},
                    "status": "succeeded",
                },
            },
        }
        mock_construct = Mock(return_value=mock_event)
        monkeypatch.setattr(stripe.Webhook, "construct_event", mock_construct)

        mock_request = Mock()
        mock_request.body = AsyncMock(return_value=b"test_body")

        event = await verify_stripe_signature(
            request=mock_request,
            stripe_signature="test_signature",
        )

        assert event["type"] == "payment_intent.succeeded"
        assert event["data"]["object"]["id"] == "pi_123"
        mock_construct.assert_called_once_with(
            payload=b"test_body",
            sig_header="test_signature",
            secret="whsec_test_secret",
        )

    async def test_missing_signature(self):
        with pytest.raises(DefaultError) as exc:
            await verify_stripe_signature(
                request=Mock(),
                stripe_signature=None,
            )
        assert exc.value.status_code == 400
        assert exc.value.capture is True
        assert exc.value.args[0] == "No signature header"

    async def test_invalid_signature(self, monkeypatch: Mock):
        mock_construct = Mock(side_effect=stripe.StripeError("Invalid", "sig"))
        monkeypatch.setattr(stripe.Webhook, "construct_event", mock_construct)

        with pytest.raises(stripe.StripeError):
            await verify_stripe_signature(
                request=Mock(body=AsyncMock(return_value="test_body")),
                stripe_signature="invalid_signature",
            )


def _mock_event(obj: dict[str, Any]):
    return stripe.Event.construct_from(
        {
            "id": "evt_123",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "object": "payment_intent",
                    "id": "pi_123",
                    "amount": 1000,
                    "metadata": {"tenant": "test-tenant"},
                    "status": "succeeded",
                    **obj,
                },
            },
        },
        key="evt_123",
    )


class TestWebhook:
    @pytest.fixture(scope="function")
    async def patch_storage(self, mock_storage: Mock):
        with patch("api.services.storage.storage_for_tenant", return_value=mock_storage) as m:
            yield m

    async def test_payment_intent_succeeded(self, test_api_client: AsyncClient, patch_storage: Mock, monkeypatch: Mock):
        mock_event = stripe.Event.construct_from(
            {
                "id": "evt_123",
                "type": "payment_intent.succeeded",
                "data": {
                    "object": {
                        "object": "payment_intent",
                        "id": "pi_123",
                        "amount": 1000,
                        "metadata": {"tenant": "test-tenant"},
                        "status": "succeeded",
                    },
                },
            },
            key="evt_123",
        )

        mock_construct = Mock(return_value=mock_event)
        monkeypatch.setattr(stripe.Webhook, "construct_event", mock_construct)

        response = await test_api_client.post(
            "/webhooks/stripe",
            json={"some": "data"},
            headers={"Stripe-Signature": "test_signature"},
        )

        assert response.status_code == 200
        patch_storage.return_value.organizations.add_credits_to_tenant.assert_called_once_with(
            "test-tenant",
            10.0,
        )

    async def test_payment_intent_no_tenant(self, test_api_client: AsyncClient, patch_storage: Mock, monkeypatch: Mock):
        mock_event = stripe.Event.construct_from(
            {
                "id": "evt_123",
                "type": "payment_intent.succeeded",
                "data": {
                    "object": {
                        "object": "payment_intent",
                        "id": "pi_123",
                        "amount": 1000,
                        "metadata": {"tenan"},
                        "status": "succeeded",
                    },
                },
            },
            key="evt_123",
        )

        mock_construct = Mock(return_value=mock_event)
        monkeypatch.setattr(stripe.Webhook, "construct_event", mock_construct)

        response = await test_api_client.post(
            "/webhooks/stripe",
            json={"some": "data"},
            headers={"Stripe-Signature": "test_signature"},
        )

        assert response.status_code == 500
        patch_storage.return_value.organizations.add_credits_to_tenant.assert_not_called()

    async def test_ignored(self, test_api_client: AsyncClient, patch_storage: Mock, monkeypatch: Mock):
        mock_event = stripe.Event.construct_from(
            {
                "id": "evt_123",
                "type": "payment_intent.succeeded",
                "data": {
                    "object": {
                        "object": "payment_intent",
                        "id": "pi_123",
                        "amount": 1000,
                        "metadata": {"webhook_ignore": "true"},
                        "status": "succeeded",
                    },
                },
            },
            key="evt_123",
        )

        mock_construct = Mock(return_value=mock_event)
        monkeypatch.setattr(stripe.Webhook, "construct_event", mock_construct)

        response = await test_api_client.post(
            "/webhooks/stripe",
            json={"some": "data"},
            headers={"Stripe-Signature": "test_signature"},
        )

        assert response.status_code == 200
        patch_storage.return_value.organizations.add_credits_to_tenant.assert_not_called()


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        ({"webhook_ignore": "true"}, True),
        ({"app": "workflowai"}, False),
        ({"webhook_ignore": "true", "app": "workflowai"}, True),
        ({"webhook_ignore": "true", "app": "workflowai"}, True),
        ({"app": None}, False),
        ({"app": "other"}, True),
        ({}, False),
    ],
)
async def test_skip_webhook(metadata: dict[str, Any], expected: bool):
    event = _mock_event({"metadata": metadata})
    assert _skip_webhook(event) == expected
