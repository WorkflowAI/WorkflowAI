import time

from freezegun import freeze_time
from httpx import AsyncClient
from pytest_httpx import HTTPXMock
from taskiq import InMemoryBroker

from tests.component.common import (
    create_task,
    get_amplitude_events,
    result_or_raise,
    wait_for_completed_tasks,
)


@freeze_time("2021-02-25T00:00:00Z")
async def test_clerk_webhook(int_api_client: AsyncClient, patched_broker: InMemoryBroker, httpx_mock: HTTPXMock):
    result_or_raise(
        await int_api_client.post(
            "/webhooks/clerk",
            json={
                "data": {
                    "admin_delete_enabled": True,
                    "created_at": 1719400194393,
                    "created_by": "user_2h5YYUW7eTZWWeodFd5ldQjRr1O",
                    "has_image": False,
                    "id": "org_2iPlfJ5X4LwiQybM9qeT00YPdBe",
                    "image_url": "https://img.clerk.com/eyJ0eXBlIjoiZGVmYXVsdCIsImlpZCI6Imluc18yZjFXNkthRDg4c3BNVE0za2hRaEMxczNtU0MiLCJyaWQiOiJvcmdfMmlQbGZKNVg0THdpUXliTTlxZVQwMFlQZEJlIiwiaW5pdGlhbHMiOiJUIn0",
                    "logo_url": None,
                    "max_allowed_memberships": 0,
                    "name": "test 18",
                    "object": "organization",
                    "private_metadata": {},
                    "public_metadata": {},
                    "slug": "test-21",
                    "updated_at": 1719866213329,
                },
                "event_attributes": {"http_request": {"client_ip": "", "user_agent": "clerk/clerk-sdk-go@v2.0.0"}},
                "object": "event",
                "type": "organization.created",
            },
            headers={
                "Authorization": "",
                "svix-id": "msg_p5jXN8AQM9LWM0D4loKWxJek",
                "svix-timestamp": f"{time.time()}",
                "svix-signature": "v1,qN81SydtpztziUhxO6gGMUunG+2gJcoNISG4vxIyXnE=",
            },
        ),
    )

    await wait_for_completed_tasks(patched_broker)

    req = await get_amplitude_events(httpx_mock)
    assert len(req) == 0


async def test_clerk_webhook_with_credits(
    int_api_client: AsyncClient,
    patched_broker: InMemoryBroker,
    httpx_mock: HTTPXMock,
):
    # Trigger the Clerk webhook
    await test_clerk_webhook(int_api_client, patched_broker, httpx_mock)

    # Fetch the organization settings
    org = result_or_raise(await int_api_client.get("/_/organization/settings"))

    # Assert the organization has 5 credits
    assert org["added_credits_usd"] == 5.0
    assert org["current_credits_usd"] == 5.0

    # Create a task to update credits
    await create_task(int_api_client, patched_broker, httpx_mock)

    # Fetch the organization settings again
    org = result_or_raise(await int_api_client.get("/_/organization/settings"))

    # Assert the organization has 10 credits
    assert org["added_credits_usd"] == 10.0
    assert org["current_credits_usd"] == 10.0

    # Create another task
    await create_task(int_api_client, patched_broker, httpx_mock)

    # Fetch the organization settings again
    org = result_or_raise(await int_api_client.get("/_/organization/settings"))

    # Assert the organization still has 10 credits (no additional credits added)
    assert org["added_credits_usd"] == 10.0
    assert org["current_credits_usd"] == 10.0

    # Fetch the tasks to ensure task count is 2
    tasks = result_or_raise(await int_api_client.get(f"/{org['tenant']}/agents"))
    assert len(tasks) == 2
