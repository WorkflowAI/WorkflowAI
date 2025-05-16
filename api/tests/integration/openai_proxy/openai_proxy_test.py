import json
from unittest import mock

import openai
import pytest
from openai import AsyncOpenAI
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall, Function

from core.domain.models.models import Model
from tests.integration.common import IntegrationTestClient


async def test_raw_string_output(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    test_client.mock_openai_call(raw_content="Hello James!")

    res = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello, world!"}],
    )

    assert res.choices[0].message.content == "Hello James!"
    assert res.model_extra and res.model_extra["cost_usd"]

    await test_client.wait_for_completed_tasks()

    task_id, run_id = res.id.split("/")
    run = await test_client.fetch_run({"id": task_id}, run_id=run_id, v1=True)
    assert run["id"] == run_id
    assert run["task_output"] == "Hello James!"

    runs = (await test_client.post(f"/v1/_/agents/{task_id}/runs/search", json={}))["items"]
    assert len(runs) == 1
    assert runs[0]["id"] == run_id
    assert runs[0]["task_input_preview"] == "Hello, world!"
    assert runs[0]["task_output_preview"] == "Hello James!"

    agent = await test_client.get(f"/_/agents/{task_id}/schemas/1")
    assert agent["output_schema"]["json_schema"] == {"type": "string", "format": "message"}

    # Now check that I can stream by calling the normal run endpoint
    test_client.mock_openai_stream(deltas=["Hello", " world"])

    aggs: list[str] = []
    async for chunk in test_client.stream_run_task_v1(
        task={"id": task_id, "schema_id": 1},
        model="gpt-4o-latest",
        task_input={
            "messages": [
                {"role": "user", "content": [{"text": "hello"}]},
            ],
        },
    ):
        assert "error" not in chunk
        aggs.append(chunk["task_output"])
    # TODO: for now we stream the finak output one more time than needed
    # We should fix at some point
    assert aggs == ["Hello", "Hello world", "Hello world", "Hello world"]


async def test_raw_json_mode(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    test_client.mock_openai_call(raw_content='{"whatever": "Hello world"}')

    res = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello, world!"}],
        response_format={"type": "json_object"},
    )
    assert res.choices[0].message.content == '{"whatever": "Hello world"}'

    await test_client.wait_for_completed_tasks()

    task_id, run_id = res.id.split("/")
    run = await test_client.fetch_run({"id": task_id}, run_id=run_id, v1=True)
    assert run["id"] == run_id
    assert run["task_output"] == {"whatever": "Hello world"}

    agent = await test_client.get(f"/_/agents/{task_id}/schemas/1")
    assert agent["output_schema"]["json_schema"] == {"format": "message"}


async def test_raw_json_mode_array(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    test_client.mock_openai_call(raw_content='[{"whatever": "Hello world"}]')

    res = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello, world!"}],
        response_format={"type": "json_object"},
    )
    assert res.choices[0].message.content == '[{"whatever": "Hello world"}]'
    await test_client.wait_for_completed_tasks()

    task_id, run_id = res.id.split("/")
    run = await test_client.fetch_run({"id": task_id}, run_id=run_id, v1=True)
    assert run["id"] == run_id
    assert run["task_output"] == [{"whatever": "Hello world"}]


async def test_with_json_schema(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    test_client.mock_openai_call(raw_content='{"whatever": "Hello world"}')

    res = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello, world!"}],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "test",
                "schema": {
                    "type": "object",
                    "properties": {"whatever": {"type": "string"}},
                },
            },
        },
    )
    assert res.choices[0].message.content == '{"whatever": "Hello world"}'

    await test_client.wait_for_completed_tasks()

    task_id, run_id = res.id.split("/")
    run = await test_client.fetch_run({"id": task_id}, run_id=run_id, v1=True)
    assert run["id"] == run_id
    assert run["task_output"] == {"whatever": "Hello world"}

    agent = await test_client.get(f"/_/agents/{task_id}/schemas/1")
    assert agent["output_schema"]["json_schema"] == {"type": "object", "properties": {"whatever": {"type": "string"}}}


async def test_with_image(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    test_client.mock_openai_call(raw_content="This is a test image")

    test_client.httpx_mock.add_response(
        url="https://hello.com/image.png",
        content=b"This is a test image",
    )

    res = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "Describe the image in a sassy manner",
            },
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": "https://hello.com/image.png"}},
                ],
            },
        ],
    )
    assert res.choices[0].message.content == "This is a test image"

    await test_client.wait_for_completed_tasks()

    task_id, run_id = res.id.split("/")
    run = await test_client.fetch_run({"id": task_id}, run_id=run_id, v1=True)
    assert run["id"] == run_id
    assert run["task_input"]["messages"][1]["content"][0] == {
        "file": {
            "url": "https://hello.com/image.png",
            "content_type": "image/png",
            "storage_url": mock.ANY,
        },
    }

    assert run["task_output"] == "This is a test image"

    runs = (await test_client.post("/v1/_/agents/default/runs/search", json={}))["items"]
    assert len(runs) == 1
    assert runs[0]["task_input_preview"].startswith("[[img:http://127.0.0.1")


async def test_with_image_as_data(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    """Test the input and output preview when the image is passed as data"""
    test_client.mock_openai_call(raw_content="This is a test image")

    res = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "Describe the image in a sassy manner",
            },
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,aGVsbG8K"}},
                ],
            },
        ],
    )
    assert res.choices[0].message.content == "This is a test image"

    await test_client.wait_for_completed_tasks()

    task_id, run_id = res.id.split("/")
    run = await test_client.fetch_run({"id": task_id}, run_id=run_id, v1=True)
    assert run["id"] == run_id
    assert run["task_input"]["messages"][1]["content"][0] == {
        "file": {
            "url": mock.ANY,
            "content_type": "image/png",
            "storage_url": mock.ANY,
        },
    }

    assert run["task_output"] == "This is a test image"

    runs = (await test_client.post("/v1/_/agents/default/runs/search", json={}))["items"]
    assert len(runs) == 1
    assert runs[0]["task_input_preview"].startswith("[[img:http://127.0.0.1")


async def test_with_tools(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    test_client.mock_openai_call(
        raw_content="",
        tool_calls_content=[
            {
                "id": "1",
                "type": "function",
                "function": {
                    "name": "test",
                    "arguments": '{"arg": "value"}',
                },
            },
        ],
    )

    res = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": "Hello",
            },
        ],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "test",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "arg": {
                                "type": "string",
                            },
                        },
                    },
                },
            },
        ],
    )
    assert res.choices[0].message.content == ""
    assert res.choices[0].message.tool_calls == [
        ChatCompletionMessageToolCall(
            id="1",
            type="function",
            function=Function(
                name="test",
                arguments='{"arg": "value"}',
            ),
        ),
    ]


async def test_bad_request(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    """Check that the run is correctly stored"""
    test_client.mock_openai_call(status_code=400, json={"error": {"message": "Bad request"}})
    with pytest.raises(openai.BadRequestError) as e:
        await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": "yoyo",
                },
            ],
            extra_body={"provider": "openai"},
        )

    assert "Bad request" in e.value.message

    await test_client.wait_for_completed_tasks()

    run = await test_client.get("/v1/_/agents/default/runs/latest")
    assert run["status"] == "failure"
    # TODO: We should have None here but it breaks model validation for now
    # We can fix later
    assert run["task_output"] == {}


async def test_stream_raw_string(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    test_client.mock_openai_stream(deltas=["Hello", " world"])

    streamer = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello, world!"}],
        stream=True,
    )

    chunks = [c async for c in streamer]
    assert len(chunks) == 2

    deltas = [c.choices[0].delta.content for c in chunks]
    assert deltas == ["Hello", " world"]

    await test_client.wait_for_completed_tasks()

    run = await test_client.get("/v1/_/agents/default/runs/latest")
    assert run["task_output"] == "Hello world"


async def test_stream_raw_json(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    test_client.mock_openai_stream(deltas=['{"hello": ', '"world2"}'])

    streamer = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello, world!"}],
        response_format={"type": "json_object"},
        stream=True,
    )

    chunks = [c async for c in streamer]
    assert len(chunks) == 2

    await test_client.wait_for_completed_tasks()

    run = await test_client.get("/v1/_/agents/default/runs/latest")
    assert run["task_output"] == {"hello": "world2"}


async def test_stream_structured_output(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    test_client.mock_openai_stream(deltas=['{"hello": ', '"world2"}'])

    streamer = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello, world!"}],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "test",
                "schema": {
                    "type": "object",
                    "properties": {"hello": {"type": "string"}},
                },
            },
        },
        stream=True,
    )

    chunks = [c async for c in streamer]
    assert len(chunks) == 2


async def test_templated_variables(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    test_client.mock_openai_call()

    res = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello, {{ name }}!"}],
        extra_body={"input": {"name": "John"}},
    )
    assert res.choices[0].message.content == '{"greeting": "Hello James!"}'

    await test_client.wait_for_completed_tasks()

    run = await test_client.get("/v1/_/agents/default/runs/latest")
    assert run["task_output"] == {"greeting": "Hello James!"}
    assert run["task_input"] == {"name": "John"}

    request = test_client.httpx_mock.get_request(url="https://api.openai.com/v1/chat/completions")
    assert request
    body = json.loads(request.content)
    assert len(body["messages"]) == 1
    assert body["messages"][0]["content"] == "Hello, John!"


async def test_deployment(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    test_client.mock_openai_call(raw_content="Hello James!")

    # First create a run with a templated variable and deployment
    res = await openai_client.chat.completions.create(
        model="my-agent/gpt-4o",
        messages=[{"role": "user", "content": "Hello, {{ name }}!"}],
        extra_body={"input": {"name": "John"}},
    )
    await test_client.wait_for_completed_tasks()

    # Now save and deploy the associated version
    agent_id, run_id = res.id.split("/")
    saved_version = await test_client.post(f"/v1/_/agents/{agent_id}/runs/{run_id}/version/save")
    version_id = saved_version["id"]

    # Checking the agent schema
    agent = await test_client.get(f"/_/agents/{agent_id}/schemas/1")
    assert agent["input_schema"]["json_schema"] == {
        "format": "messages",
        "type": "object",
        "properties": {"name": {"type": "string"}},
    }

    # Now we can deploy the version
    await test_client.post(
        f"/v1/_/agents/{agent_id}/versions/{version_id}/deploy",
        json={
            "environment": "production",
        },
    )

    # Now we can make a new run with the deployment
    test_client.mock_openai_call(raw_content="Hello James!")

    res = await openai_client.chat.completions.create(
        model="my-agent/#1/production",
        messages=[],
        extra_body={"input": {"name": "Cecily"}},
    )

    # Get the latest request
    requests = test_client.httpx_mock.get_requests(url="https://api.openai.com/v1/chat/completions")
    assert len(requests) == 2
    body = json.loads(requests[-1].content)
    assert body["messages"][0]["content"] == "Hello, Cecily!"

    # I can also follow up with a new message
    # TODO: would be good to change the output here but overriding mocks does not seem to be working for now
    test_client.mock_openai_call(raw_content="I'm good, thank you!")

    res = await openai_client.chat.completions.create(
        model="my-agent/#1/production",
        messages=[{"role": "assistant", "content": "Hello, Cecily!"}, {"role": "user", "content": "How are you?"}],
        extra_body={"input": {"name": "Cecily"}},
    )
    assert res.choices[0].message.content == "I'm good, thank you!"

    await test_client.wait_for_completed_tasks()

    # Check the run
    run = await test_client.get(f"/v1/_/agents/{agent_id}/runs/latest")
    assert run["task_output"] == "I'm good, thank you!"
    assert run["task_input"] == {
        "name": "Cecily",
        "workflowai.replies": [
            {"role": "assistant", "content": [{"text": "Hello, Cecily!"}]},
            {"role": "user", "content": [{"text": "How are you?"}]},
        ],
    }
    assert run["version"]["id"] == version_id


async def test_deployment_missing_error(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    with pytest.raises(openai.BadRequestError) as e:
        await openai_client.chat.completions.create(
            model="my-agent/#1/production",
            messages=[],
            extra_body={"input": {"name": "John"}},
        )

    assert e.value.status_code == 400
    assert "Deployment not found" in e.value.message


async def test_missing_model_error(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    test_client.mock_internal_task("model_suggester", {"suggested_model": "gpt-4o-mini-latest"})

    with pytest.raises(openai.BadRequestError) as e:
        await openai_client.chat.completions.create(
            # Not a valid model
            model="gpt-4",
            messages=[],
        )
    assert "Did you mean gpt-4o-mini-latest" in e.value.message


async def test_list_models(openai_client: AsyncOpenAI):
    res = await openai_client.models.list()
    assert len(res.data) > 0

    model_ids = {m.id for m in res.data}
    assert model_ids < set(Model)
    assert Model.GPT_41_LATEST in model_ids
    assert Model.GPT_3_5_TURBO_1106 not in model_ids
