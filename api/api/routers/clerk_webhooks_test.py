import time
from unittest.mock import Mock, patch

import pytest
from freezegun import freeze_time
from httpx import AsyncClient
from pydantic import BaseModel

from api.routers.clerk_webhooks import (  # pyright: ignore [reportPrivateUsage]
    _ClerkWebhookSigner,  # pyright: ignore [reportPrivateUsage]
)
from tests.utils import fixtures_json


class _TestModel(BaseModel):
    test: int


class TestVerifySignature:
    def test_success(self):
        signer = _ClerkWebhookSigner("whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw")

        svix_id = "msg_p5jXN8AQM9LWM0D4loKWxJek"
        svix_timestamp = "1614265330"
        svix_signature = "v1,g0hM9SsE+OTPJTGt/tmIKtSyZlE3uFJELVlNIOLJ1OE="

        payload = '{"test": 2432232314}'

        verified = signer.verify_signature(svix_id, svix_timestamp, payload, svix_signature, _TestModel)
        assert verified.test == 2432232314


class TestPost:
    @pytest.fixture(scope="function")
    async def patch_tenant_storage(self, mock_storage: Mock):
        with patch("api.services.storage.storage_for_tenant", return_value=mock_storage) as m:
            yield m

    @freeze_time("2021-02-25T00:00:00Z")
    async def test_success(self, test_api_client: AsyncClient, patch_tenant_storage: Mock):
        body = fixtures_json("clerk/wh_org.json")
        response = await test_api_client.post(
            "/webhooks/clerk",
            json=body,
            headers={
                "svix-id": "msg_p5jXN8AQM9LWM0D4loKWxJek",
                "svix-timestamp": f"{time.time()}",
                "svix-signature": "v1,QYNrnPzi5IezdgVj+H34VQIArNn+UBXvC34nDKYL754=",
            },
        )
        assert response.status_code == 204
