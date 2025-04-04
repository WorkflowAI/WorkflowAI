import json
import os
from typing import Dict, Union
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from pytest_httpx import HTTPXMock

from core.domain.tenant_data import PublicOrganizationData
from core.services.emails.email_service import EmailSendError
from core.services.emails.loops_email_service import LoopsEmailService
from core.services.users.user_service import UserDetails, UserService
from core.storage.organization_storage import PublicOrganizationStorage


@pytest.fixture
def mock_storage() -> AsyncMock:
    return AsyncMock(spec=PublicOrganizationStorage)


@pytest.fixture
def mock_user_service() -> AsyncMock:
    return AsyncMock(spec=UserService)


@pytest.fixture
def loops_service(mock_storage: AsyncMock, mock_user_service: AsyncMock):
    with (
        patch("core.services.emails.loops_email_service.LoopsEmailService.WAIT_TIME_BETWEEN_RETRIES", 0),
        patch.dict(
            os.environ,
            {"PAYMENT_FAILURE_EMAIL_ID": "payment_failure_id"},
        ),
    ):
        yield LoopsEmailService(
            api_key="test_api_key",
            organization_storage=mock_storage,
            user_service=mock_user_service,
        )


class TestSendEmail:
    async def test_send_email_success(self, loops_service: LoopsEmailService, httpx_mock: HTTPXMock) -> None:
        email = "test@example.com"
        transaction_id = "test_transaction"
        variables: Dict[str, Union[str, int, float]] = {"name": "Test User", "age": 30}

        httpx_mock.add_response(
            url="https://app.loops.so/api/v1/transactional",
            status_code=200,
            method="POST",
        )

        await loops_service.send_email(email, transaction_id, variables)

        request = httpx_mock.get_requests()[0]
        assert request.headers["Authorization"] == "Bearer test_api_key"
        assert "Idempotency-Key" in request.headers
        assert json.loads(request.content) == {
            "email": "test@example.com",
            "transactionalId": "test_transaction",
            "addToAudience": False,
            "dataVariables": {"name": "Test User", "age": 30},
        }

    async def test_send_email_rate_limit_retry(self, loops_service: LoopsEmailService, httpx_mock: HTTPXMock) -> None:
        email = "test@example.com"
        transaction_id = "test_transaction"

        # First response is rate limited (429), second is successful
        httpx_mock.add_response(
            url="https://app.loops.so/api/v1/transactional",
            status_code=429,
            method="POST",
        )
        httpx_mock.add_response(
            url="https://app.loops.so/api/v1/transactional",
            status_code=200,
            method="POST",
        )

        await loops_service.send_email(email, transaction_id)

        assert len(httpx_mock.get_requests()) == 2

    async def test_send_email_idempotency(self, loops_service: LoopsEmailService, httpx_mock: HTTPXMock) -> None:
        email = "test@example.com"
        transaction_id = "test_transaction"

        # Simulate idempotency conflict (409)
        httpx_mock.add_response(
            url="https://app.loops.so/api/v1/transactional",
            status_code=409,
            method="POST",
        )

        # Should not raise an error for idempotency conflict
        await loops_service.send_email(email, transaction_id)

    async def test_send_email_retry_exhaustion(self, loops_service: LoopsEmailService, httpx_mock: HTTPXMock) -> None:
        email = "test@example.com"
        transaction_id = "test_transaction"

        # Simulate repeated failures
        httpx_mock.add_response(
            url="https://app.loops.so/api/v1/transactional",
            status_code=429,
            method="POST",
        )
        httpx_mock.add_response(
            url="https://app.loops.so/api/v1/transactional",
            status_code=429,
            method="POST",
        )

        with pytest.raises(EmailSendError):
            await loops_service.send_email(email, transaction_id, retry_count=2)

        assert len(httpx_mock.get_requests()) == 2

    async def test_send_email_network_error(self, loops_service: LoopsEmailService, httpx_mock: HTTPXMock) -> None:
        email = "test@example.com"
        transaction_id = "test_transaction"

        httpx_mock.add_exception(httpx.HTTPError("Network error"))

        with pytest.raises(EmailSendError):
            await loops_service.send_email(email, transaction_id, retry_count=1)


class TestSendPaymentFailureEmail:
    async def test_success_with_org_id(
        self,
        loops_service: LoopsEmailService,
        mock_storage: AsyncMock,
        mock_user_service: AsyncMock,
        httpx_mock: HTTPXMock,
    ) -> None:
        # Mock organization storage response
        mock_storage.public_organization_by_tenant.return_value = PublicOrganizationData(
            org_id="test_org_id",
            owner_id=None,
        )

        # Mock user service response
        mock_user_service.get_org_admins.return_value = [
            UserDetails(email="admin1@example.com", name="Admin One"),
            UserDetails(email="admin2@example.com", name="Admin Two"),
        ]

        # Mock Loops API response
        httpx_mock.add_response(
            url="https://app.loops.so/api/v1/transactional",
            status_code=200,
            method="POST",
        )

        await loops_service.send_payment_failure_email("test_tenant")

        # Verify organization storage was called
        mock_storage.public_organization_by_tenant.assert_called_once_with(tenant="test_tenant")

        # Verify user service was called
        mock_user_service.get_org_admins.assert_called_once_with("test_org_id")

        # Verify Loops API was called for each admin
        requests = httpx_mock.get_requests()
        assert len(requests) == 2
        contents = [json.loads(request.content) for request in requests]
        contents.sort(key=lambda x: x["email"])
        assert contents[0] == {
            "email": "admin1@example.com",
            "transactionalId": "payment_failure_id",
            "addToAudience": False,
            "dataVariables": None,
        }
        assert contents[1] == {
            "email": "admin2@example.com",
            "transactionalId": "payment_failure_id",
            "addToAudience": False,
            "dataVariables": None,
        }

    async def test_success_with_owner_id(
        self,
        loops_service: LoopsEmailService,
        mock_storage: AsyncMock,
        mock_user_service: AsyncMock,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url="https://app.loops.so/api/v1/transactional",
            status_code=200,
            method="POST",
        )

        # Mock organization storage response with only owner_id
        mock_storage.public_organization_by_tenant.return_value = PublicOrganizationData(
            org_id=None,
            owner_id="test_owner_id",
        )

        # Mock user service response
        mock_user_service.get_user.return_value = UserDetails(email="owner@example.com", name="Owner")

        await loops_service.send_payment_failure_email("test_tenant")

        # Verify organization storage was called
        mock_storage.public_organization_by_tenant.assert_called_once_with(tenant="test_tenant")

        # Verify user service was called with owner_id
        mock_user_service.get_user.assert_called_once_with("test_owner_id")
