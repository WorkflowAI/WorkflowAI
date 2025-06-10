import pytest
from httpx import AsyncClient


async def test_create_api_key(
    int_api_client: AsyncClient,
):
    """Test creating a new API key"""
    response = await int_api_client.post(
        "/chiefofstaff.ai/api/keys",
        json={"name": "test key"},
    )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["name"] == "test key"
    assert "key" in data
    assert data["key"].startswith("wai-")
    assert "partial_key" in data
    assert "created_at" in data


async def test_list_api_keys(int_api_client: AsyncClient):
    """Test listing API keys"""
    # First create a key
    await int_api_client.post(
        "/chiefofstaff.ai/api/keys",
        json={"name": "test key"},
    )

    response = await int_api_client.get("/chiefofstaff.ai/api/keys")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1  # pyright: ignore [reportUnknownArgumentType]
    key_doc = data[0]  # pyright: ignore [reportUnknownVariableType]
    assert "id" in key_doc
    assert "name" in key_doc
    assert "partial_key" in key_doc
    assert "created_at" in key_doc
    assert "created_by" in key_doc
    assert "key" not in key_doc  # Full key should not be returned in list


async def test_delete_api_key(int_api_client: AsyncClient):
    """Test deleting an API key"""
    # First create a key
    create_response = await int_api_client.post(
        "/chiefofstaff.ai/api/keys",
        json={"name": "test key"},
    )
    key_id = create_response.json()["id"]

    # Delete the key
    delete_response = await int_api_client.delete(f"/chiefofstaff.ai/api/keys/{key_id}")
    assert delete_response.status_code == 204

    # Verify key is deleted
    list_response = await int_api_client.get("/chiefofstaff.ai/api/keys")
    assert list_response.status_code == 200
    keys = list_response.json()
    assert not any(key["id"] == key_id for key in keys)


async def test_delete_nonexistent_key(int_api_client: AsyncClient):
    """Test deleting a non-existent API key"""
    response = await int_api_client.delete("/chiefofstaff.ai/api/keys/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.parametrize(
    "invalid_name,expected_status",
    [
        ("", 400),  # empty string
        (None, 422),  # null
        ("ab", 400),
    ],
)
async def test_create_api_key_validation(
    int_api_client: AsyncClient,
    invalid_name: str | None,
    expected_status: int,
):
    """Test validation when creating API keys"""
    response = await int_api_client.post(
        "/chiefofstaff.ai/api/keys",
        json={"name": invalid_name},
    )
    assert response.status_code == expected_status


async def test_api_key_authentication_with_api_keys(int_api_client: AsyncClient):
    """Test that API key can be used to authenticate requests to protected endpoints"""
    # Create an API key
    create_response = await int_api_client.post(
        "/chiefofstaff.ai/api/keys",
        json={"name": "test key"},
    )
    assert create_response.status_code == 201
    api_key = create_response.json()["key"]

    # Create a new client with the API key in headers
    headers = {"Authorization": f"Bearer {api_key}"}

    # Test accessing the api keys endpoint with API key
    response = await int_api_client.get(
        "/chiefofstaff.ai/api/keys",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    invalid_api_key = "invalid-api-key"
    headers = {"Authorization": f"Bearer {invalid_api_key}"}

    # Test accessing tasks endpoint without API key should fail
    response_without_key = await int_api_client.get("/chiefofstaff.ai/api/keys", headers=headers)
    assert response_without_key.status_code == 401


async def test_invalid_api_key(int_api_client: AsyncClient):
    """Test that an invalid API key returns a 401 error"""

    response = await int_api_client.post(
        "/v1/_/agents/test-agent/schemas/1/run",
        headers={"Authorization": "Bearer wai-invalid-api-key"},
        json={"task_input": {}, "version": "production"},
    )
    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "authentication_failed",
            "message": "Invalid API key provided: wai-i***.\nGrab a fresh one (plus $5 in free LLM credits for new users) at https://workflowai.com/keys 🚀",
            "status_code": 401,
        },
    }


async def test_missing_bearer(int_api_client: AsyncClient):
    """Test that an invalid API key returns a 401 error"""

    response = await int_api_client.post(
        "/v1/_/agents/test-agent/schemas/1/run",
        headers={"Authorization": "wai-invalid-api-key"},
        json={"task_input": {}, "version": "production"},
    )
    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "authentication_failed",
            "message": "Invalid authorization header: wai-i***. A valid header with an API key looks like 'Bearer wai-****'. If you need a new API key, Grab a fresh one (plus $5 in free LLM credits for new users) at https://workflowai.com/keys 🚀",
            "status_code": 401,
        },
    }
