import openai
import pytest
from openai import AsyncOpenAI, BadRequestError

from tests.component.common import IntegrationTestClient
from tests.component.openai_proxy.common import save_version_from_completion


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
    assert "You send input variables but the deployment you are trying to use does not expect any" in str(e.value)


async def test_unfulfilled_tool_call_request(
    openai_client: AsyncOpenAI,
):
    """Check that we raise an error when there's an unfulfilled tool request followed by text"""

    with pytest.raises(BadRequestError) as e:
        await openai_client.chat.completions.create(
            model="my-agent/gpt-4o",
            messages=[
                {"role": "user", "content": "What is the weather in Tokyo and in Paris?"},
                {
                    "role": "assistant",
                    "content": "Let me get the weather in tokyo and Paris",
                    "tool_calls": [
                        {
                            "id": "tool_use_01NhMGWVdTLvEuDB6Rx76hYJ",
                            "type": "function",
                            "function": {"name": "get_weather", "arguments": "Tokyo"},
                        },
                        {
                            "id": "tool_use_01NhMGWVdTLvEuDB6Rx76hYF",
                            "type": "function",
                            "function": {"name": "get_weather", "arguments": "Paris"},
                        },
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": "tool_use_01NhMGWVdTLvEuDB6Rx76hYJ",
                    "content": "Weather in Tokyo is sunny",
                },
            ],
        )
    assert "still pending" in str(e.value)


async def test_unsupported_parameter(openai_client: AsyncOpenAI):
    # Only one unsupported field
    with pytest.raises(openai.BadRequestError) as e:
        await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello, world!"}],
            logit_bias={"hello": 1},
        )

    assert "Field `logit_bias` is not supported" in str(e)

    # Multiple unsupported fields
    with pytest.raises(openai.BadRequestError) as e:
        await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello, world!"}],
            logit_bias={"hello": 1},
            stop="hello",
        )

    assert "Fields `logit_bias`, `stop` are not supported" in str(e)


async def test_deployment_missing_error(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    with pytest.raises(openai.BadRequestError) as e:
        await openai_client.chat.completions.create(
            model="my-agent/#1/production",
            messages=[],
            extra_body={"input": {"name": "John"}},
        )

    assert e.value.status_code == 400
    assert "Deployment not found" in e.value.message


async def test_deployed_version_no_messages_with_empty_input(
    test_client: IntegrationTestClient,
    openai_client: AsyncOpenAI,
):
    # This will break since we are passing a message that has no variables but also variables
    with pytest.raises(openai.BadRequestError):
        await openai_client.chat.completions.create(
            model="my-agent/gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Hello, world!"},
            ],
            extra_body={"input": {"hello": "helllo"}},
        )

    # Try again with a proper input and message to create a version
    test_client.mock_openai_call(raw_content="Hello James!")
    res = await openai_client.chat.completions.create(
        model="my-agent/gpt-4o",
        messages=[
            {"role": "system", "content": "{{instructions}}"},
        ],
        # Passing an empty input signals that the first system message should be used in the version
        extra_body={"input": {"instructions": "elllo"}},
    )
    assert res
    await test_client.wait_for_completed_tasks()

    await save_version_from_completion(test_client, res, "production")

    # Now not passing any input should break
    with pytest.raises(openai.BadRequestError) as e:
        await openai_client.chat.completions.create(
            model="my-agent/#1/production",
            messages=[],
        )

    assert "Your deployment on schema #1 expects input variables" in str(e.value)

    # I should get the same error if I pass messages

    with pytest.raises(openai.BadRequestError) as e:
        await openai_client.chat.completions.create(
            model="my-agent/#1/production",
            messages=[{"role": "user", "content": "Hello, world!"}],
        )

    assert "Your deployment on schema #1 expects input variables" in str(e.value)

    test_client.mock_openai_call(raw_content="Hello James!")
    await openai_client.chat.completions.create(
        model="my-agent/#1/production",
        messages=[],
        extra_body={"input": {"instructions": "elllo"}},
    )

    test_client.mock_openai_call(raw_content="Hello James!")
    await openai_client.chat.completions.create(
        model="my-agent/#1/production",
        messages=[{"role": "user", "content": "Hello, world!"}],
        extra_body={"input": {"instructions": "elllo"}},
    )

    # Just for sanity check that it works when passing an input

    # assert res.choices[0].message.content == "Hello James!"
    # await test_client.wait_for_completed_tasks()

    # version = await save_version_from_completion(test_client, res, "production")
    # assert version["properties"].get("messages") == [
    #     {"role": "system", "content": [{"text": "You are a helpful assistant"}]},
    # ]

    # # Now use the deployed version
    # test_client.mock_openai_call(raw_content="Hello James!")

    # res = await openai_client.chat.completions.create(
    #     model="my-agent/#1/production",
    #     messages=[{"role": "user", "content": "Hello hades!"}],
    # )
    # assert res.choices[0].message.content == "Hello James!"

    # request = test_client.httpx_mock.get_requests(url="https://api.openai.com/v1/chat/completions")
    # assert len(request) == 2, "sanity"

    # body = json.loads(request[-1].content)
    # assert len(body["messages"]) == 2
    # assert body["messages"][0]["content"] == "You are a helpful assistant"
    # assert body["messages"][1]["content"] == "Hello hades!"
