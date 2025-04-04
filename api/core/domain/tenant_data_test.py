from datetime import datetime

import pytest

from core.domain.tenant_data import TenantData


@pytest.mark.parametrize(
    "tenant_data, threshold",
    [
        pytest.param(
            TenantData(
                current_credits_usd=3.0,
                low_credits_email_sent_by_threshold=None,
            ),
            5.0,
            id="no_previous_emails",
        ),
        pytest.param(
            TenantData(
                current_credits_usd=3.0,
                low_credits_email_sent_by_threshold={800: datetime.now()},
            ),
            5.0,
            id="previous_email_for_higher_threshold",
        ),
        pytest.param(
            TenantData(
                current_credits_usd=3.0,
                low_credits_email_sent_by_threshold={
                    800: datetime.now(),
                    600: datetime.now(),
                },
            ),
            5.0,
            id="multiple_previous_emails_all_higher",
        ),
    ],
)
def test_should_send_low_credits_email(tenant_data: TenantData, threshold: float):
    assert tenant_data.should_send_low_credits_email(threshold)


@pytest.mark.parametrize(
    "tenant_data, threshold",
    [
        pytest.param(
            TenantData(
                current_credits_usd=10.0,
                low_credits_email_sent_by_threshold=None,
            ),
            5.0,
            id="credits_above_threshold",
        ),
        pytest.param(
            TenantData(
                current_credits_usd=5.0,
                low_credits_email_sent_by_threshold=None,
            ),
            5.0,
            id="credits_equal_threshold",
        ),
        pytest.param(
            TenantData(
                current_credits_usd=3.0,
                low_credits_email_sent_by_threshold={500: datetime.now()},
            ),
            5.0,
            id="previous_email_for_same_threshold",
        ),
        pytest.param(
            TenantData(
                current_credits_usd=3.0,
                low_credits_email_sent_by_threshold={300: datetime.now()},
            ),
            5.0,
            id="previous_email_for_lower_threshold",
        ),
    ],
)
def test_should_not_send_low_credits_email(tenant_data: TenantData, threshold: float):
    assert not tenant_data.should_send_low_credits_email(threshold)
