import time

from freezegun import freeze_time

from tests.component.common import (
    IntegrationTestClient,
    get_amplitude_events,
    result_or_raise,
)


@freeze_time("2021-02-25T00:00:00Z")
async def test_clerk_webhook(test_client: IntegrationTestClient):
    result_or_raise(
        await test_client.int_api_client.post(
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
                "svix-signature": "v1,FuxohqHmR0W00p2/Sjbbmh4PTx6XYuzQX5y5JRFd+V4=",
            },
        ),
    )

    await test_client.wait_for_completed_tasks()

    req = await get_amplitude_events(test_client.httpx_mock)
    assert len(req) == 0


async def test_clerk_webhook_with_credits(
    test_client: IntegrationTestClient,
):
    # Trigger the Clerk webhook
    await test_clerk_webhook(test_client)

    # Fetch the organization settings
    org = result_or_raise(await test_client.int_api_client.get("/_/organization/settings"))

    # Assert the organization has 5 credits
    assert org["added_credits_usd"] == 5.0
    assert org["current_credits_usd"] == 5.0

    # Create a task to update credits
    await test_client.create_task()

    # Fetch the organization settings again
    org = result_or_raise(await test_client.int_api_client.get("/_/organization/settings"))

    # Assert the organization has 10 credits
    assert org["added_credits_usd"] == 10.0
    assert org["current_credits_usd"] == 10.0

    # Create another task
    await test_client.create_task()

    # Fetch the organization settings again
    org = result_or_raise(await test_client.int_api_client.get("/_/organization/settings"))

    # Assert the organization still has 10 credits (no additional credits added)
    assert org["added_credits_usd"] == 10.0
    assert org["current_credits_usd"] == 10.0

    # Fetch the tasks to ensure task count is 2
    tasks = result_or_raise(await test_client.int_api_client.get(f"/{org['tenant']}/agents"))
    assert len(tasks) == 2
