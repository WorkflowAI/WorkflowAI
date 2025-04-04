from api.dependencies.analytics import analytics_organization_properties
from core.domain.tenant_data import TenantData


class TestAnalyticsOrganizationProperties:
    def test_user_org_with_org_id(self):
        user_org = TenantData(
            org_id="org_123",
            slug="org-123",
            name="Org 123",
        )

        properties = analytics_organization_properties(user_org)
        assert properties.organization_id == "org_123"
        assert properties.organization_slug == "org-123"
        assert properties.organization_credits_usd == 0
