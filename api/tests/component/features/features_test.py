from tests.component.common import IntegrationTestClient


async def test_get_feature_sections(test_client: IntegrationTestClient) -> None:
    """Test the endpoint to get feature sections preview."""

    # Make the API call
    response = await test_client.int_api_client.get("/features/sections")

    # Check that we got a successful response
    assert response.status_code == 200

    # Verify the response structure
    data = response.json()
    assert "sections" in data
    assert isinstance(data["sections"], list)

    # Verify that each section has the expected structure
    for section in data["sections"]:
        assert "name" in section
        assert "tags" in section
        assert isinstance(section["tags"], list)


async def test_search_features_endpoint(test_client: IntegrationTestClient) -> None:
    """Test the successful case where features are found."""

    # Use a tag that should exist in the system
    tag = "Featured"

    # Make the API call
    response = await test_client.int_api_client.get(f"/features/search?tags={tag}")

    # Check that we got a successful response
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

    # Read the stream chunks to verify content
    chunks = [chunk async for chunk in response.aiter_text()]

    # Ensure we got at least one data chunk
    sse_content = "".join(chunks)
    assert "data:" in sse_content

    # Verify at least one event has a features list
    assert '"features":' in sse_content


async def test_search_features_endpoint_not_found(test_client: IntegrationTestClient) -> None:
    """Test the case where no features are found."""

    # Use a tag that should not exist in the system
    tag = "nonexistent_tag_that_should_not_be_found"

    # Make the API call
    response = await test_client.int_api_client.get(f"/features/search?tags={tag}")

    # When streaming, even with errors the initial response is 200 OK
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

    # Read the stream chunks
    chunks = [chunk async for chunk in response.aiter_text()]
    sse_content = "".join(chunks)

    # In the stream, the error will be formatted as an SSE event with an ErrorResponse object
    assert 'data: {"error":' in sse_content

    # The error should contain the specific message about the missing tag
    assert f"No feature tag found with tag: {tag}" in sse_content

    # The error should have the correct error code for ObjectNotFoundException
    assert '"code":"object_not_found"' in sse_content
