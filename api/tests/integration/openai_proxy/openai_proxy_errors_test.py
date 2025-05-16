import pytest
from openai import AsyncOpenAI, BadRequestError

from tests.integration.common import IntegrationTestClient
from tests.integration.openai_proxy.common import save_version_from_completion


async def test_deployment_with_no_input_variables(
    test_client: IntegrationTestClient,
    openai_client: AsyncOpenAI,
):
    """Check the error when a user triggers a deployment with no input variables but
    passes input variables"""

    test_client.mock_openai_call(raw_content="Hello James!")

    res = await openai_client.chat.completions.create(
        model="my-agent/gpt-4o",
        messages=[{"role": "user", "content": "Hello, world!"}],
    )
    assert res.choices[0].message.content == "Hello James!"
    await test_client.wait_for_completed_tasks()

    # Created version will have no input variables
    version = await save_version_from_completion(test_client, res, "production")
    assert "messages" not in version["properties"]

    # Re-running with the same messages should work
    test_client.mock_openai_call(raw_content="Hello John!")
    res = await openai_client.chat.completions.create(
        model="my-agent/#1/production",
        messages=[{"role": "user", "content": "Hello, world!"}],
    )
    assert res.choices[0].message.content == "Hello John!"

    # If we try and re-run with input variables we should get a bad request
    with pytest.raises(BadRequestError) as e:
        res = await openai_client.chat.completions.create(
            model="my-agent/#1/production",
            messages=[{"role": "user", "content": "Hello, world!"}],
            extra_body={"input": {"name": "John"}},
        )
    assert "The deployment you are trying to use does not contain any messages" in str(e.value)
