import pytest
from httpx import HTTPStatusError
from pytest_httpx import IteratorStream

from core.domain.models import Model
from core.domain.models.providers import Provider
from tests.component.common import (
    IntegrationTestClient,
)
from tests.utils import fixtures_json, fixtures_stream_hex


async def test_content_moderation_failed_generation_wrapper(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    test_client.httpx_mock.add_response(
        url="https://bedrock-runtime.us-west-2.amazonaws.com/model/us.anthropic.claude-3-opus-20240229-v1:0/converse-stream",
        status_code=200,
        stream=IteratorStream(fixtures_stream_hex("bedrock", "stream_content_moderation.txt")),
    )

    task_run = test_client.stream_run_task_v1(
        task,
        version={"model": Model.CLAUDE_3_OPUS_20240229, "provider": Provider.AMAZON_BEDROCK},
    )

    assert task_run
    chunks = [c async for c in task_run]
    assert chunks
    assert chunks[0]["error"]["code"] == "content_moderation"
    assert (
        chunks[0]["error"]["details"]["provider_error"]
        == "I apologize, but I do not feel comfortable responding to or repeating the inappropriate language at the end of this product review. Perhaps we could have a more respectful discussion focused on the merits of the dishwashing gloves themselves. Let me know if you would like me to analyze the review excluding that final sentence."
    )


async def test_content_moderation_failed_generation_wrapper_with_completion(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    test_client.httpx_mock.add_response(
        url="https://bedrock-runtime.us-west-2.amazonaws.com/model/us.anthropic.claude-3-opus-20240229-v1:0/converse",
        status_code=200,
        json=fixtures_json("bedrock", "completion_fixture_content_moderation.json"),
    )

    with pytest.raises(HTTPStatusError) as e:
        await test_client.run_task_v1(
            task,
            version={"model": Model.CLAUDE_3_OPUS_20240229, "provider": Provider.AMAZON_BEDROCK},
        )

    assert e.value.response.json()["error"]["code"] == "content_moderation"
    assert (
        e.value.response.json()["error"]["details"]["provider_error"]
        == "I apologize, but I cannot engage with or produce offensive language or content. Please rephrase your request in a respectful manner."
    )
