import pytest

from core.domain.tenant_data import ProviderConfig
from core.providers.google.google_provider import GoogleProviderConfig
from core.providers.groq.groq_provider import GroqConfig
from core.providers.openai.openai_provider import OpenAIConfig
from core.storage.mongo.models.organization_document import (
    OrganizationDocument,
    ProviderSettingsSchema,
)
from core.utils.encryption import Encryption


@pytest.mark.parametrize(
    "config",
    [
        GroqConfig(api_key="key"),
        OpenAIConfig(api_key="key"),
        GoogleProviderConfig(vertex_credentials="k", vertex_project="p", vertex_location=["l"]),
    ],
)
def test_provider_settings_schema_sanity(config: ProviderConfig, mock_encryption: Encryption) -> None:
    schema = ProviderSettingsSchema.from_domain(config, mock_encryption)

    assert schema.provider == config.provider
    assert schema.secrets

    domain = schema.to_domain(mock_encryption)
    assert domain.decrypt() == config


class TestDeserializeOrganization:
    def test_anon_organization(self):
        payload = {
            "id": "67a505ab458926e9301ba153",
            "tenant": "8c94d523-da6a-4089-b1d3-34a3ffbce484",
            "anonymous_user_id": "8c94d523-da6a-4089-b1d3-34a3ffbce484",
            "domain": "8c94d523-da6a-4089-b1d3-34a3ffbce484",
            "added_credits_usd": 0.2,
            "current_credits_usd": 0.2,
            "no_tasks_yet": True,
            "anonymous": True,
            "automatic_payment_enabled": False,
        }

        org = OrganizationDocument.model_validate(payload)
        assert org.tenant == "8c94d523-da6a-4089-b1d3-34a3ffbce484"
        assert org.anonymous_user_id == "8c94d523-da6a-4089-b1d3-34a3ffbce484"
        assert org.domain == "8c94d523-da6a-4089-b1d3-34a3ffbce484"
        assert org.added_credits_usd == 0.2
        assert org.current_credits_usd == 0.2
        assert org.no_tasks_yet is True


class TestToDomainPublic:
    def test_success(self):
        org = OrganizationDocument(
            tenant="tenant",
            slug="slug",
            org_id="org_id",
            owner_id="owner_id",
            providers=[],
            uid=1,
        )
        public_org = org.to_domain_public()
        assert public_org.tenant == "tenant"
        assert public_org.slug == "slug"
        assert public_org.org_id == "org_id"

        # Check that all fields are present. This ensures that we don't forget a field in PublicOrganizationData
        assert public_org.model_dump(exclude_unset=True) == public_org.model_dump()
