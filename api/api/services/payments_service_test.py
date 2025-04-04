from unittest import mock
from unittest.mock import AsyncMock, Mock, patch

import pytest
import stripe

from api.services.payments_service import PaymentMethodResponse, PaymentService, PaymentSystemService
from core.domain.errors import BadRequestError
from core.domain.tenant_data import TenantData
from core.utils.background import wait_for_background_tasks


@pytest.fixture()
def payment_service(mock_storage: Mock):
    return PaymentService(org_storage=mock_storage.organizations)


@pytest.fixture()
def payment_system_service(mock_storage: Mock, mock_email_service: Mock):
    return PaymentSystemService(org_storage=mock_storage.organizations, email_service=mock_email_service)


@pytest.fixture()
def mock_stripe():
    with patch("api.services.payments_service.stripe") as mock:
        mock.PaymentIntent = Mock(spec=stripe.PaymentIntent)
        mock.Customer = Mock(spec=stripe.Customer)
        mock.PaymentMethod = Mock(spec=stripe.PaymentMethod)

        yield mock


def _mock_customer(stripe_mock: Mock, payment_method: bool):
    # It would be better to build customer objects but the inits are weird
    customer = Mock()
    customer.id = "cus_123"
    customer.invoice_settings = Mock()
    if payment_method:
        customer.invoice_settings.default_payment_method = Mock()
        customer.invoice_settings.default_payment_method.id = "pm_123"
        customer.invoice_settings.default_payment_method.card = Mock()
        customer.invoice_settings.default_payment_method.card.last4 = "4242"
        customer.invoice_settings.default_payment_method.card.brand = "visa"
        customer.invoice_settings.default_payment_method.card.exp_month = 12
        customer.invoice_settings.default_payment_method.card.exp_year = 2025
    else:
        customer.invoice_settings.default_payment_method = None

    stripe_mock.Customer.retrieve_async.return_value = customer


def _payment_intent():
    payment_intent = AsyncMock()
    payment_intent.client_secret = "secret_123"
    payment_intent.id = "pi_123"
    return payment_intent


class TestCreateCustomer:
    async def test_create_new_customer(
        self,
        payment_service: PaymentService,
        mock_storage: AsyncMock,
        monkeypatch: Mock,
    ):
        # Mock stripe.Customer.create
        mock_customer = Mock()
        mock_customer.id = "cus_123"
        mock_storage.organizations.get_organization.return_value = TenantData(
            tenant="test-tenant",
            name="Test Org",
            slug="test-org",
            stripe_customer_id=None,
            uid=1,
        )
        mock_create = AsyncMock(return_value=mock_customer)
        monkeypatch.setattr(stripe.Customer, "create_async", mock_create)

        customer_id = await payment_service.create_customer("test@example.com")

        assert customer_id == "cus_123"
        mock_create.assert_called_once_with(
            name="Test Org",
            email="test@example.com",
            metadata={
                "tenant": "test-tenant",
                "slug": "test-org",
                "tenant_uid": "1",
            },
        )
        mock_storage.organizations.update_customer_id.assert_called_once_with(stripe_customer_id="cus_123")

    async def test_return_existing_customer(
        self,
        payment_service: PaymentService,
        mock_storage: AsyncMock,
    ):
        # Set existing customer ID
        mock_storage.organizations.get_organization.return_value.stripe_customer_id = "existing_cus_123"

        customer_id = await payment_service.create_customer("test@example.com")

        assert customer_id == "existing_cus_123"
        mock_storage.organizations.update_customer_id.assert_not_called()


class TestAddPaymentMethod:
    async def test_add_payment_method(
        self,
        payment_service: PaymentService,
        mock_storage: AsyncMock,
        monkeypatch: Mock,
    ):
        mock_storage.organizations.get_organization.return_value.stripe_customer_id = "cus_123"

        # Mock stripe methods
        mock_payment_method = Mock()
        mock_payment_method.id = "pm_123"
        mock_attach = AsyncMock(return_value=mock_payment_method)
        mock_modify = AsyncMock()
        monkeypatch.setattr(stripe.PaymentMethod, "attach_async", mock_attach)
        monkeypatch.setattr(stripe.Customer, "modify_async", mock_modify)

        payment_method_id = await payment_service.add_payment_method(
            mock_storage.organizations.get_organization.return_value,
            "pm_123",
            "test@example.com",
        )

        assert payment_method_id == "pm_123"
        mock_attach.assert_called_once_with(
            "pm_123",
            customer="cus_123",
        )
        mock_modify.assert_called_once_with(
            "cus_123",
            invoice_settings={"default_payment_method": "pm_123"},
        )

    async def test_add_payment_method_no_customer(
        self,
        payment_service: PaymentService,
        mock_storage: AsyncMock,
        mock_stripe: Mock,
    ):
        """Check that a customer is created if one does not exist"""
        mock_storage.organizations.get_organization.return_value = TenantData(
            tenant="test-tenant",
            name="Test Org",
            slug="test-org",
            stripe_customer_id=None,
            uid=1,
        )
        _mock_customer(mock_stripe, payment_method=False)
        mock_stripe.PaymentMethod.attach_async = AsyncMock(
            return_value=Mock(id="pm_id"),
        )

        await payment_service.add_payment_method(
            mock_storage.organizations.get_organization.return_value,
            "pm_123",
            "test@example.com",
        )
        mock_stripe.PaymentMethod.attach_async.assert_called_once()
        mock_stripe.Customer.modify_async.assert_called_once()

    async def test_add_payment_method_invalid_card(
        self,
        payment_service: PaymentService,
        mock_storage: AsyncMock,
        monkeypatch: Mock,
    ):
        mock_payment_method = Mock()
        mock_payment_method.id = "pm_123"
        mock_attach = AsyncMock(
            side_effect=stripe.CardError(
                message="Your card's security code is incorrect.",
                code="incorrect_cvc",
                param="cvc",
            ),
        )
        monkeypatch.setattr(stripe.PaymentMethod, "attach_async", mock_attach)

        with pytest.raises(stripe.CardError, match="Your card's security code is incorrect."):
            await payment_service.add_payment_method(
                mock_storage.organizations.get_organization.return_value,
                "pm_123",
                "test@example.com",
            )


class TestGetPaymentMethod:
    async def test_get_payment_method(
        self,
        payment_service: PaymentService,
        mock_storage: AsyncMock,
        monkeypatch: Mock,
    ):
        mock_storage.organizations.get_organization.return_value.stripe_customer_id = "cus_123"

        # Mock stripe.Customer.retrieve
        mock_payment_method = Mock()
        mock_payment_method.id = "pm_123"
        mock_payment_method.card.last4 = "4242"
        mock_payment_method.card.brand = "visa"
        mock_payment_method.card.exp_month = 12
        mock_payment_method.card.exp_year = 2025

        mock_customer = Mock()
        mock_customer.invoice_settings.default_payment_method = mock_payment_method
        monkeypatch.setattr(stripe.Customer, "retrieve_async", AsyncMock(return_value=mock_customer))

        payment_method = await payment_service.get_payment_method(
            mock_storage.organizations.get_organization.return_value,
        )

        assert isinstance(payment_method, PaymentMethodResponse)
        assert payment_method.payment_method_id == "pm_123"
        assert payment_method.last4 == "4242"
        assert payment_method.brand == "visa"
        assert payment_method.exp_month == 12
        assert payment_method.exp_year == 2025

    async def test_get_payment_method_no_default(
        self,
        payment_service: PaymentService,
        mock_storage: AsyncMock,
        monkeypatch: Mock,
    ):
        mock_storage.organizations.get_organization.return_value.stripe_customer_id = "cus_123"

        mock_customer = Mock()
        mock_customer.invoice_settings.default_payment_method = None
        monkeypatch.setattr(stripe.Customer, "retrieve_async", AsyncMock(return_value=mock_customer))

        payment_method = await payment_service.get_payment_method(
            mock_storage.organizations.get_organization.return_value,
        )

        assert payment_method is None


class TestDeletePaymentMethod:
    async def test_delete_payment_method(
        self,
        payment_service: PaymentService,
        mock_storage: AsyncMock,
        monkeypatch: Mock,
    ):
        mock_storage.organizations.get_organization.return_value.stripe_customer_id = "cus_123"
        mock_storage.organizations.get_organization.return_value.automatic_payment_enabled = True
        mock_storage.organizations.get_organization.return_value.automatic_payment_threshold = 10.0
        mock_storage.organizations.get_organization.return_value.automatic_payment_balance_to_maintain = 15.0

        # Mock stripe.Customer.retrieve
        mock_payment_method = Mock()
        mock_payment_method.id = "pm_123"
        mock_payment_method.card.last4 = "4242"
        mock_payment_method.card.brand = "visa"
        mock_payment_method.card.exp_month = 12
        mock_payment_method.card.exp_year = 2025

        mock_customer = Mock()
        mock_customer.invoice_settings.default_payment_method = mock_payment_method
        monkeypatch.setattr(stripe.Customer, "retrieve_async", AsyncMock(return_value=mock_customer))

        monkeypatch.setattr(stripe.PaymentMethod, "detach_async", AsyncMock(return_value=mock_payment_method))
        mock_customer2 = Mock()
        mock_customer2.invoice_settings.default_payment_method = None
        monkeypatch.setattr(stripe.Customer, "modify_async", AsyncMock(return_value=mock_customer2))

        await payment_service.delete_payment_method(mock_storage.organizations.get_organization.return_value)

        mock_storage.organizations.update_automatic_payment.assert_called_once_with(
            opt_in=False,
            threshold=None,
            balance_to_maintain=None,
        )


class TestCreatePaymentIntent:
    async def test_create_payment_intent(
        self,
        payment_service: PaymentService,
        mock_storage: AsyncMock,
        mock_stripe: Mock,
    ):
        mock_storage.organizations.get_organization.return_value = TenantData(
            tenant="test-tenant",
            name="Test Org",
            slug="test-org",
            stripe_customer_id="cus_123",
            uid=1,
        )

        # Create a fake payment method
        _mock_customer(mock_stripe, payment_method=True)

        # Mock payment intent creation

        mock_stripe.PaymentIntent.create_async.return_value = _payment_intent()

        payment_intent = await payment_service.create_payment_intent(
            mock_storage.organizations.get_organization.return_value,
            100.0,
            trigger="manual",
        )

        assert payment_intent.client_secret == "secret_123"
        assert payment_intent.payment_intent_id == "pi_123"

        mock_stripe.PaymentIntent.create_async.assert_called_once_with(
            amount=10000,  # $100.00 in cents
            currency="usd",
            customer="cus_123",
            payment_method="pm_123",
            setup_future_usage="off_session",
            automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
            metadata={
                "tenant": "test-tenant",
                "slug": "test-org",
                "trigger": "manual",
                "tenant_uid": "1",
            },
        )

    async def test_create_payment_intent_no_payment_method(
        self,
        payment_service: PaymentService,
        mock_storage: AsyncMock,
        mock_stripe: Mock,
    ):
        mock_storage.organizations.get_organization.return_value.stripe_customer_id = "cus_123"

        _mock_customer(mock_stripe, payment_method=False)

        with pytest.raises(BadRequestError, match="Organization has no default payment method"):
            await payment_service.create_payment_intent(
                mock_storage.organizations.get_organization.return_value,
                100.0,
                trigger="manual",
            )


class TestDecrementCredits:
    @pytest.fixture
    def test_org(self, mock_storage: AsyncMock):
        """Patch the org returned by decrement_credits"""
        org = TenantData(
            tenant="test-tenant",
            name="Test Org",
            slug="test-org",
            current_credits_usd=4.0,  # Below threshold
            stripe_customer_id="cus_123",
            automatic_payment_enabled=True,
            automatic_payment_threshold=5.0,
            automatic_payment_balance_to_maintain=10.0,
        )

        mock_storage.organizations.decrement_credits.return_value = org
        return org

    async def test_decrement_credits_no_automatic_payment(
        self,
        payment_system_service: PaymentSystemService,
        mock_storage: AsyncMock,
        test_org: TenantData,
    ):
        """Test when automatic payment is disabled"""
        test_org.automatic_payment_enabled = False

        await payment_system_service.decrement_credits("test-tenant", 100.0)

        mock_storage.organizations.decrement_credits.assert_called_once_with(tenant="test-tenant", credits=100.0)
        # No attempt to lock since credits are above threshold
        mock_storage.organizations.attempt_lock_for_payment.assert_not_called()

    async def test_decrement_credits_triggers_automatic_payment(
        self,
        payment_system_service: PaymentSystemService,
        mock_storage: AsyncMock,
        mock_stripe: Mock,
        test_org: TenantData,
    ):
        # Mock the organization document returned after decrementing credits

        # Mock successful lock attempt
        mock_storage.organizations.attempt_lock_for_payment.return_value = test_org.model_copy(
            update={"locked_for_payment": True},
        )
        _mock_customer(mock_stripe, payment_method=True)
        mock_stripe.PaymentIntent.create_async.return_value = _payment_intent()
        # Not sure why just using a return_value does not work here
        mock_stripe.PaymentIntent.confirm_async = AsyncMock(return_value=Mock(status="succeeded"))

        await payment_system_service.decrement_credits("test-tenant", 3.0)

        # Verify all the expected calls
        mock_storage.organizations.decrement_credits.assert_called_once_with(tenant="test-tenant", credits=3.0)
        mock_storage.organizations.attempt_lock_for_payment.assert_called_once()
        mock_storage.organizations.unlock_payment_for_failure.assert_not_called()
        mock_storage.organizations.unlock_payment_for_success.assert_not_called()

    async def test_decrement_credits_automatic_payment_fails(
        self,
        payment_system_service: PaymentSystemService,
        mock_storage: AsyncMock,
        test_org: TenantData,
        mock_stripe: Mock,
        mock_email_service: Mock,
    ):
        # Mock successful lock attempt
        mock_lock_doc = Mock()
        mock_lock_doc.locked_for_payment = True
        mock_storage.organizations.attempt_lock_for_payment.return_value = test_org.model_copy(
            update={"locked_for_payment": True},
        )

        # Mock payment method retrieval
        _mock_customer(mock_stripe, payment_method=True)

        # Mock payment intent creation and confirmation
        mock_payment_intent = Mock()
        mock_payment_intent.id = "pi_123"
        mock_stripe.PaymentIntent.create_async.return_value = mock_payment_intent
        mock_stripe.PaymentIntent.confirm_async.side_effect = Exception("Confirm payment failed")

        await payment_system_service.decrement_credits("test-tenant", 100.0)

        # Verify all the expected calls
        mock_storage.organizations.decrement_credits.assert_called_once_with(tenant="test-tenant", credits=100.0)
        mock_storage.organizations.attempt_lock_for_payment.assert_called_once()
        mock_storage.organizations.unlock_payment_for_failure.assert_called_once_with(
            tenant="test-tenant",
            now=mock.ANY,
            code="internal",
            failure_reason=mock.ANY,
        )

        await wait_for_background_tasks()
        mock_email_service.send_payment_failure_email.assert_called_once_with("test-tenant")
