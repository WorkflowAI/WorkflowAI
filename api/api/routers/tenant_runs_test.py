# pyright: reportPrivateUsage=False

from httpx import AsyncClient
from taskiq import InMemoryBroker

from tests.component.common import create_task


async def test_search_tenant_runs_basic(
    int_api_client: AsyncClient,
    patched_broker: InMemoryBroker,
):
    """Test basic tenant-wide run search functionality"""

    # Create two different agents
    agent1 = await create_task(
        int_api_client,
        patched_broker,
        task_id="agent1",
        input_schema={"type": "object", "properties": {"message": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"response": {"type": "string"}}},
    )

    agent2 = await create_task(
        int_api_client,
        patched_broker,
        task_id="agent2",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"answer": {"type": "string"}}},
    )

    # TODO: Create some runs for both agents
    # This would require setting up proper mock LLM responses and run execution

    # Test basic search without filters
    response = await int_api_client.post(
        "/v1/_/runs/search",
        json={
            "limit": 20,
            "offset": 0,
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert "items" in data
    assert "count" in data
    assert isinstance(data["items"], list)
    assert isinstance(data["count"], int)


async def test_search_tenant_runs_with_agent_filter(
    int_api_client: AsyncClient,
    patched_broker: InMemoryBroker,
):
    """Test tenant-wide run search with agent filtering"""

    agent = await create_task(
        int_api_client,
        patched_broker,
        task_id="test_agent",
    )

    # Test search with specific agent filter
    response = await int_api_client.post(
        "/v1/_/runs/search",
        json={
            "agent_ids": ["test_agent"],
            "limit": 10,
            "offset": 0,
        },
    )

    assert response.status_code == 200
    data = response.json()

    # All returned runs should be from the specified agent
    for item in data["items"]:
        assert item["agent_id"] == "test_agent"


async def test_search_tenant_runs_with_field_queries(
    int_api_client: AsyncClient,
    patched_broker: InMemoryBroker,
):
    """Test tenant-wide run search with field queries"""

    await create_task(int_api_client, patched_broker)

    # Test search with status filter
    response = await int_api_client.post(
        "/v1/_/runs/search",
        json={
            "field_queries": [
                {
                    "field_name": "status",
                    "operator": "is",
                    "values": ["success"],
                    "type": "string",
                },
            ],
            "limit": 10,
            "offset": 0,
        },
    )

    assert response.status_code == 200
    data = response.json()

    # All returned runs should have success status
    for item in data["items"]:
        assert item["status"] == "success"


async def test_get_tenant_agents_with_runs(
    int_api_client: AsyncClient,
    patched_broker: InMemoryBroker,
):
    """Test getting agents summary for the tenant"""

    await create_task(int_api_client, patched_broker, task_id="active_agent")

    response = await int_api_client.get("/v1/_/runs/agents?days=30")

    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)

    # Each agent summary should have required fields
    for agent_summary in data:
        assert "agent_id" in agent_summary
        assert "name" in agent_summary
        assert "run_count" in agent_summary
        assert "total_cost_usd" in agent_summary
        assert "period_days" in agent_summary
        assert agent_summary["period_days"] == 30


async def test_search_tenant_runs_pagination(
    int_api_client: AsyncClient,
    patched_broker: InMemoryBroker,
):
    """Test pagination in tenant-wide run search"""

    await create_task(int_api_client, patched_broker)

    # Test first page
    response1 = await int_api_client.post(
        "/v1/_/runs/search",
        json={
            "limit": 5,
            "offset": 0,
        },
    )

    assert response1.status_code == 200
    data1 = response1.json()

    # Test second page
    response2 = await int_api_client.post(
        "/v1/_/runs/search",
        json={
            "limit": 5,
            "offset": 5,
        },
    )

    assert response2.status_code == 200
    data2 = response2.json()

    # Pages should not overlap
    ids_page1 = {item["id"] for item in data1["items"]}
    ids_page2 = {item["id"] for item in data2["items"]}
    assert ids_page1.isdisjoint(ids_page2)


async def test_search_tenant_runs_invalid_agent_ids(
    int_api_client: AsyncClient,
    patched_broker: InMemoryBroker,
):
    """Test tenant-wide run search with invalid agent IDs"""

    # Test search with non-existent agent
    response = await int_api_client.post(
        "/v1/_/runs/search",
        json={
            "agent_ids": ["non_existent_agent"],
            "limit": 10,
            "offset": 0,
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Should return empty results for non-existent agents
    assert data["items"] == []
    assert data["count"] == 0


async def test_search_tenant_runs_limit_validation(
    int_api_client: AsyncClient,
    patched_broker: InMemoryBroker,
):
    """Test validation of limit parameter"""

    # Test limit too high
    response = await int_api_client.post(
        "/v1/_/runs/search",
        json={
            "limit": 150,  # Over the maximum of 100
            "offset": 0,
        },
    )

    assert response.status_code == 422  # Validation error

    # Test limit too low
    response = await int_api_client.post(
        "/v1/_/runs/search",
        json={
            "limit": 0,  # Below minimum of 1
            "offset": 0,
        },
    )

    assert response.status_code == 422  # Validation error


async def test_tenant_runs_response_schema(
    int_api_client: AsyncClient,
    patched_broker: InMemoryBroker,
):
    """Test that tenant runs response follows the expected schema"""

    await create_task(int_api_client, patched_broker)

    response = await int_api_client.post(
        "/v1/_/runs/search",
        json={
            "limit": 1,
            "offset": 0,
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert "items" in data
    assert "count" in data

    if data["items"]:
        item = data["items"][0]

        # Check required fields
        required_fields = [
            "id",
            "agent_id",
            "task_schema_id",
            "version",
            "status",
            "created_at",
            "task_input_preview",
            "task_output_preview",
            "feedback_token",
        ]

        for field in required_fields:
            assert field in item, f"Missing required field: {field}"

        # Check version structure
        version = item["version"]
        assert "id" in version
        assert "iteration" in version
        assert "properties" in version

        # Check status is valid
        assert item["status"] in ["success", "failure"]
