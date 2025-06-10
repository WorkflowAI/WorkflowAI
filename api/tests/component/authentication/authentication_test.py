import asyncio
from typing import Any

import pytest
from httpx import HTTPStatusError

from core.utils.ids import id_uint32
from tests.component.common import ANON_JWT, LEGACY_TEST_JWT, IntegrationTestClient, run_task


async def test_unknown_user(test_client: IntegrationTestClient):
    # An anonymous user can create a task and fetch the organization
    # Without going through the clerk webhook
    test_client.authenticate(ANON_JWT)

    # This should not throw
    await test_client.create_task()

    # I can fetch the organization
    res = await test_client.get("/_/organization/settings")
    assert res["is_anonymous"] is True
    assert res["added_credits_usd"] == 5.2
    assert res["current_credits_usd"] == 5.2


async def test_known_user_but_no_hook(test_client: IntegrationTestClient):
    # Default user has an org id
    await test_client.create_task()

    await test_client.wait_for_completed_tasks()

    res = await test_client.get("/_/organization/settings")
    assert not res.get("is_anonymous")
    assert res["added_credits_usd"] == 10
    assert res["current_credits_usd"] == 10


async def test_deprecated_token(test_client: IntegrationTestClient, integration_storage: Any):
    # Authenticate with the deprecated token
    test_client.authenticate(LEGACY_TEST_JWT)
    # Call will fail because there is no tenant record and we don't auto-create tenants based on deprecated tokens
    with pytest.raises(HTTPStatusError) as e:
        await test_client.create_task()
    assert e.value.response.status_code == 401

    # Create a deprecated tenant record
    # It's deprecated because the tenant
    await integration_storage._organization_collection.insert_one(
        {
            "org_id": "org_2iPlfJ5X4LwiQybM9qeT00",
            "tenant": "chiefofstaff.ai",
            "domain": "chiefofstaff.ai",
            "uid": id_uint32(),
            "added_credits_usd": 10,
            "current_credits_usd": 10,
        },
    )

    # First create the tenant with the appropriate domain
    task = await test_client.create_task()
    # Both the old and v1 endpoints should still work
    test_client.mock_openai_call()
    await run_task(test_client.int_api_client, task["task_id"], task["task_schema_id"])

    test_client.mock_openai_call()
    await test_client.run_task_v1(task)


async def test_no_creation_for_deprecated_token(test_client: IntegrationTestClient):
    # There is no auto creation for deprecated tokens
    test_client.authenticate(LEGACY_TEST_JWT)

    with pytest.raises(HTTPStatusError) as e:
        await test_client.create_task()

    assert e.value.response.status_code == 401


async def test_race_condition_for_anonymous_org(test_client: IntegrationTestClient):
    test_client.authenticate(ANON_JWT)

    calls = await asyncio.gather(
        test_client.get("/_/organization/settings"),
        test_client.get("/_/organization/settings"),
        test_client.get("/_/organization/settings"),
        return_exceptions=True,
    )

    assert all(not isinstance(call, HTTPStatusError) for call in calls)


async def test_race_condition_for_tenant_with_org_id(test_client: IntegrationTestClient):
    calls = await asyncio.gather(
        test_client.get("/_/organization/settings"),
        test_client.get("/_/organization/settings"),
        test_client.get("/_/organization/settings"),
        return_exceptions=True,
    )

    assert all(not isinstance(call, HTTPStatusError) for call in calls)


# A user JWT


# {"unknownUserId":"8c94d523-da6a-4089-b1d3-34a3ffbce484"}
_ANON_JWT = "eyJhbGciOiJFUzI1NiJ9.eyJ1bmtub3duVXNlcklkIjoiOGM5NGQ1MjMtZGE2YS00MDg5LWIxZDMtMzRhM2ZmYmNlNDg0IiwiaWF0IjoxNjI4NzA3ODQ2LCJleHAiOjE4OTEyNDM4NDZ9.n4DJt-4H_3-u_3KBRQvT_xwDQb2ogBtAFhByBDYeEtqblp4auz6okicNeJygfowgIJfNYAGDr7FH1e37qQkuDg"
# {"userId":"user_1234","unknownUserId":"8c94d523-da6a-4089-b1d3-34a3ffbce484"}
_USER_JWT = "eyJhbGciOiJFUzI1NiJ9.eyJ1c2VySWQiOiJ1c2VyXzEyMzQiLCJ1bmtub3duVXNlcklkIjoiOGM5NGQ1MjMtZGE2YS00MDg5LWIxZDMtMzRhM2ZmYmNlNDg0IiwiaWF0IjoxNjI4NzA3ODQ2LCJleHAiOjE4OTEyNDM4NDZ9.D7V7ZWef_X8D2xPuX9g_3fhtuCy1ib_hP82CoX-ET_GWkjJsZkDV6DdD9_wR72ipds2Zfb3Yl88svihOBMkltA"
# {"orgId": "org_234", "userId":"user_1234","unknownUserId":"8c94d523-da6a-4089-b1d3-34a3ffbce484"}
_ORG_JWT = "eyJhbGciOiJFUzI1NiJ9.eyJ1c2VySWQiOiJ1c2VyXzEyMzQiLCJvcmdJZCI6Im9yZ18yMzQiLCJ1bmtub3duVXNlcklkIjoiOGM5NGQ1MjMtZGE2YS00MDg5LWIxZDMtMzRhM2ZmYmNlNDg0IiwiaWF0IjoxNjI4NzA3ODQ2LCJleHAiOjE4OTEyNDM4NDZ9.Za5fHblD6b4sY2SkRbi0Ev1k2abEYivDU56RC82K2shKxR_XqycyBH6Mj2mGyLViC-A1EU-XyVuMrUQa3wwurA"


async def test_migrating_users(test_client: IntegrationTestClient):
    test_client.authenticate(_ANON_JWT)
    await test_client.create_task()
    org1 = await test_client.get("/_/organization/settings")

    test_client.authenticate(_USER_JWT)
    agents = await test_client.get("/_/agents")
    assert len(agents["items"]) == 1
    org2 = await test_client.get("/_/organization/settings")
    assert org2["uid"] == org1["uid"]

    test_client.authenticate(_ORG_JWT)
    agents = await test_client.get("/_/agents")
    assert len(agents["items"]) == 1
    org3 = await test_client.get("/_/organization/settings")
    assert org3["uid"] == org2["uid"]

    # I can still authenticate with the user token
    test_client.authenticate(_USER_JWT)
    org4 = await test_client.get("/_/organization/settings")
    # but it will give me a different org id
    assert org4["uid"] != org1["uid"]
    assert not org4.get("is_anonymous")

    # I can authenticate with the anonymous token but I will get a different org id
    # Otherwise people would be able to bypass auth entirely by using the anonymous token
    # test_client.authenticate(_ANON_JWT)
    # org5 = await test_client.get("/_/organization/settings")
    # assert org5["uid"] != org1["uid"]
    # assert org5["uid"] != org4["uid"]
    # assert org5.get("is_anonymous")

    # If I log in as the org, I get the original org id
    test_client.authenticate(_ORG_JWT)
    org6 = await test_client.get("/_/organization/settings")
    assert org6["uid"] == org1["uid"]
