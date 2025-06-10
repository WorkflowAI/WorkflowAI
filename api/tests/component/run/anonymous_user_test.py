from tests.component.common import ANON_JWT, IntegrationTestClient, create_task, create_version


async def test_anonymous_user_starter_credits(
    test_client: IntegrationTestClient,
):
    test_client.authenticate(ANON_JWT)
    org = await test_client.get("/_/organization/settings")
    assert org["is_anonymous"] is True
    assert org["added_credits_usd"] == 0.2
    assert org["current_credits_usd"] == 0.2


async def test_anonymous_user_accessible_endpoints(
    test_client: IntegrationTestClient,
):
    test_client.authenticate(ANON_JWT)
    org = await test_client.get("/_/organization/settings")
    assert org["is_anonymous"] is True
    assert org["added_credits_usd"] == 0.2
    assert org["current_credits_usd"] == 0.2

    task = await create_task(test_client.int_api_client, test_client.patched_broker, test_client.httpx_mock)
    await create_version(
        test_client.int_api_client,
        task["task_id"],
        task["task_schema_id"],
        {"model": "gpt-4o-2024-11-20"},
    )
    versions = await test_client.get(
        f"/_/agents/{task['task_id']}/versions",
    )

    assert versions["count"] == 1

    python_code = await test_client.post(
        f"/_/agents/{task['task_id']}/schemas/{task['task_schema_id']}/python",
        json={
            "group_iteration": 1,
            "group_environment": "production",
            "example_task_run_input": {"input": "Hello, World!"},
        },
    )
    assert python_code["sdk"]["code"] == "pip install workflowai"
    assert python_code["run"] is not None
