import json

from openai import AsyncOpenAI

from core.domain.consts import METADATA_KEY_FILE_DOWNLOAD_SECONDS
from core.domain.models.models import Model
from tests.component.common import IntegrationTestClient, openai_endpoint
from tests.component.openai_proxy.common import fetch_run_from_completion


async def test_image_is_not_downloaded(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    """Check that for OpenAI the image is not downloaded"""
    test_client.httpx_mock.add_response(
        url="https://example.com/image.png",
        status_code=200,
        content=b"hello",
    )
    test_client.mock_openai_call()
    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini-latest",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "https://example.com/image.png",
                        },
                    },
                ],
            },
        ],
    )
    assert METADATA_KEY_FILE_DOWNLOAD_SECONDS not in response.metadata  # type: ignore
    assert response.choices[0].message.content == '{"greeting": "Hello James!"}'


async def test_reasoning_effort(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    test_client.mock_openai_call()
    completion = await openai_client.chat.completions.create(
        model="o3-mini",
        messages=[
            {"role": "user", "content": "Hello, world!"},
        ],
        reasoning_effort="low",
    )
    assert completion.choices[0].message.content

    openai_request = test_client.httpx_mock.get_request(url=openai_endpoint())
    assert openai_request
    body = json.loads(openai_request.content)
    assert body["model"] == Model.O3_MINI_2025_01_31
    assert body["reasoning_effort"] == "low"

    await test_client.wait_for_completed_tasks()

    # Check that the reasoning effort is correctly propagated to the version
    run = await fetch_run_from_completion(test_client, completion)
    version = await test_client.fetch_version({"id": run["task_id"]}, run["version"]["id"])
    assert version["properties"]["reasoning_effort"] == "low"


async def test_reasoning_budget(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    test_client.mock_openai_call()
    completion = await openai_client.chat.completions.create(
        model="o3-mini",
        messages=[
            {"role": "user", "content": "Hello, world!"},
        ],
        extra_body={
            "reasoning": {
                "budget": 100,  # low effort, below 20% of the budget
            },
        },
    )
    assert completion.choices[0].message.content

    openai_request = test_client.httpx_mock.get_request(url=openai_endpoint())
    assert openai_request
    body = json.loads(openai_request.content)
    assert body["model"] == Model.O3_MINI_2025_01_31
    assert body["reasoning_effort"] == "low"

    await test_client.wait_for_completed_tasks()

    # Check that the reasoning effort is correctly propagated to the version
    run = await fetch_run_from_completion(test_client, completion)
    version = await test_client.fetch_version({"id": run["task_id"]}, run["version"]["id"])
    assert "reasoning_effort" not in version["properties"]
    assert version["properties"]["reasoning_budget"] == 100
