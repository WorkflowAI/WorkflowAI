import json
from collections.abc import Awaitable, Callable
from typing import Any
from unittest import mock

import openai
import pytest
from openai import AsyncOpenAI, RateLimitError
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall, Function

from core.domain.models.models import Model
from core.domain.models.providers import Provider
from core.storage.mongo.mongo_types import AsyncCollection
from tests.component.common import IntegrationTestClient
from tests.component.openai_proxy.common import save_version_from_completion
from tests.pausable_memory_broker import PausableInMemoryBroker
from tests.utils import approx


async def test_raw_string_output(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    test_client.mock_openai_call(raw_content="Hello James!")

    res = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello, world!"}],
    )

    assert res.choices[0].message.content == "Hello James!"

    assert res.choices[0].cost_usd > 0  # type: ignore
    assert res.choices[0].duration_seconds  # type: ignore
    assert res.choices[0].feedback_token  # type: ignore

    await test_client.wait_for_completed_tasks()

    # Check the amplitude call
    amplitude_events = test_client.amplitude_events_with_type("org.ran.task")
    assert len(amplitude_events) == 1, "no amplitude event"
    assert amplitude_events[0]["event_properties"]["task"]["id"] == "default"

    task_id, run_id = res.id.split("/")
    run = await test_client.fetch_run({"id": task_id}, run_id=run_id, v1=True)
    assert run["id"] == run_id
    assert run["task_output"] == "Hello James!"

    runs = (await test_client.post(f"/v1/_/agents/{task_id}/runs/search", json={}))["items"]
    assert len(runs) == 1
    assert runs[0]["id"] == run_id
    assert runs[0]["task_input_preview"] == "User: Hello, world!"
    assert runs[0]["task_output_preview"] == "Assistant: Hello James!"

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
    assert run["task_input"]["workflowai.messages"][1]["content"][0] == {
        "file": {
            "url": "https://hello.com/image.png",
            "content_type": "image/png",
            "storage_url": mock.ANY,
        },
    }

    assert run["task_output"] == "This is a test image"

    runs = (await test_client.post("/v1/_/agents/default/runs/search", json={}))["items"]
    assert len(runs) == 1
    assert runs[0]["task_input_preview"].startswith("User: [[img:http://127.0.0.1")


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
    assert run["task_input"]["workflowai.messages"][1]["content"][0] == {
        "file": {
            "url": mock.ANY,
            "content_type": "image/png",
            "storage_url": mock.ANY,
        },
    }

    assert run["task_output"] == "This is a test image"

    runs = (await test_client.post("/v1/_/agents/default/runs/search", json={}))["items"]
    assert len(runs) == 1
    assert runs[0]["task_input_preview"].startswith("User: [[img:http://127.0.0.1")


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
    assert res.choices[0].message.content is None
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
    assert len(chunks) == 3

    deltas = [c.choices[0].delta.content for c in chunks]
    assert deltas == ["Hello", " world", None]

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
    assert len(chunks) == 3
    assert chunks[0].id.startswith("default/")

    await test_client.wait_for_completed_tasks()

    run = await test_client.get("/v1/_/agents/default/runs/latest")
    assert run["task_output"] == {"hello": "world2"}

    # Here we don't add a message since
    request = test_client.httpx_mock.get_request(url="https://api.openai.com/v1/chat/completions")
    assert request
    body = json.loads(request.content)
    assert len(body["messages"]) == 2
    assert body["messages"][0]["content"] == "Return a single JSON object"
    assert body["messages"][1]["content"] == "Hello, world!"


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
    assert len(chunks) == 3


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
        "workflowai.messages": [
            {"role": "assistant", "content": [{"text": "Hello, Cecily!"}]},
            {"role": "user", "content": [{"text": "How are you?"}]},
        ],
    }
    assert run["version"]["id"] == version_id


async def test_missing_model_error(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    test_client.mock_internal_task("model_suggester", {"suggested_model": "gpt-4o-mini-latest"})

    with pytest.raises(openai.BadRequestError) as e:
        await openai_client.chat.completions.create(
            # Not a valid model
            model="gpt-4n",
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


async def test_deployed_version_no_messages(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    test_client.mock_openai_call(raw_content="Hello James!")

    # Create a version that will result in empty messages in the version
    res = await openai_client.chat.completions.create(
        model="my-agent/gpt-4o",
        messages=[
            {"role": "user", "content": "Hello, world!"},
        ],
    )
    assert res.choices[0].message.content == "Hello James!"
    await test_client.wait_for_completed_tasks()

    version = await save_version_from_completion(test_client, res, "production")
    assert version["properties"].get("messages") is None

    # Now use the deployed version
    test_client.mock_openai_call(raw_content="Hello James!")

    res = await openai_client.chat.completions.create(
        model="my-agent/#1/production",
        messages=[{"role": "user", "content": "Hello hades!"}],
    )
    assert res.choices[0].message.content == "Hello James!"

    request = test_client.httpx_mock.get_requests(url="https://api.openai.com/v1/chat/completions")
    assert len(request) == 2, "sanity"

    body = json.loads(request[-1].content)
    assert len(body["messages"]) == 1
    assert body["messages"][0]["content"] == "Hello hades!"


async def test_deployed_version_no_messages_with_empty_input(
    test_client: IntegrationTestClient,
    openai_client: AsyncOpenAI,
):
    test_client.mock_openai_call(raw_content="Hello James!")

    # Create a version that will result in empty messages in the version
    res = await openai_client.chat.completions.create(
        model="my-agent/gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello, world!"},
        ],
        # Passing an empty input signals that the first system message should be used in the version
        extra_body={"input": {}},
    )
    assert res.choices[0].message.content == "Hello James!"
    await test_client.wait_for_completed_tasks()

    version = await save_version_from_completion(test_client, res, "production")
    assert version["properties"].get("messages") == [
        {"role": "system", "content": [{"text": "You are a helpful assistant"}]},
    ]

    # Now use the deployed version
    test_client.mock_openai_call(raw_content="Hello James!")

    res = await openai_client.chat.completions.create(
        model="my-agent/#1/production",
        messages=[{"role": "user", "content": "Hello hades!"}],
    )
    assert res.choices[0].message.content == "Hello James!"

    request = test_client.httpx_mock.get_requests(url="https://api.openai.com/v1/chat/completions")
    assert len(request) == 2, "sanity"

    body = json.loads(request[-1].content)
    assert len(body["messages"]) == 2
    assert body["messages"][0]["content"] == "You are a helpful assistant"
    assert body["messages"][1]["content"] == "Hello hades!"


async def test_profile_db_calls(
    test_client: IntegrationTestClient,
    openai_client: AsyncOpenAI,
    patched_broker: PausableInMemoryBroker,
    start_mongo_profiling: Callable[[], Awaitable[AsyncCollection]],
):
    """Check that we make a minimal number of db calls on the critical path"""
    # Pause the broker so we know nothing comes from tasks

    # First call, the task will be created and stored

    test_client.mock_openai_call(raw_content="Hello, world!")
    res = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello, world!"}],
    )
    assert res.choices[0].message.content == "Hello, world!"

    await test_client.wait_for_completed_tasks()

    # Second call, now we should really not have a lot of calls
    patched_broker.pause()
    system_profile_col = await start_mongo_profiling()

    test_client.mock_openai_call(raw_content="Hello, world!")
    await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello, world 2"}],
    )

    # Check the number of calls we actually made
    calls = [a async for a in system_profile_col.find({})]
    assert len(calls) == 2

    assert calls[0]["op"] == "query"
    assert calls[0]["ns"] == "workflowai_int_test.org_settings"
    assert "IXSCAN" in calls[0]["planSummary"]

    assert calls[1]["op"] == "query"
    assert calls[1]["ns"] == "workflowai_int_test.tasks"
    assert "IXSCAN" in calls[1]["planSummary"]


async def test_internal_tools(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    test_client.mock_openai_call(
        tool_calls_content=[
            {
                "id": "some_id",
                "type": "function",
                "function": {"name": "search-google", "arguments": '{"query": "bla"}'},
            },
        ],
    )
    test_client.httpx_mock.add_response(
        url="https://google.serper.dev/search",
        text="blabla",
    )
    test_client.mock_openai_call(raw_content="Hello, world!")

    res = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Use @search-google to find information"},
            {"role": "user", "content": "Hello, world!"},
        ],
    )
    assert res.choices[0].message.content == "Hello, world!"

    await test_client.wait_for_completed_tasks()

    serper_request = test_client.httpx_mock.get_request(url="https://google.serper.dev/search")
    assert serper_request
    assert serper_request.content == b'{"q": "bla"}'


@pytest.mark.parametrize("use_deployment", [True, False])
async def test_with_model_fallback_on_rate_limit(
    test_client: IntegrationTestClient,
    use_deployment: bool,
    openai_client: AsyncOpenAI,
):
    model = f"greet/{Model.CLAUDE_3_5_SONNET_20241022}" if not use_deployment else "greet/#1/production"
    completion_kwargs: dict[str, Any] = {"model": model, "messages": [{"role": "user", "content": "Hello, world!"}]}

    if use_deployment:
        # We automatically add a system message for structured gen to anthropic and bedrock
        anthropic_message_count = 2
        task = await test_client.create_agent_v1(input_schema={"type": "object", "format": "messages"})
        version = await test_client.create_version_v1(task, {"model": Model.CLAUDE_3_5_SONNET_20241022})
        await test_client.post(
            f"/v1/_/agents/{task['id']}/versions/{version['id']}/deploy",
            json={"environment": "production"},
        )
    else:
        # raw string output
        anthropic_message_count = 1

    # Anthropic and bedrock always return a 429 so we will proceed with model fallback
    test_client.mock_anthropic_call(status_code=429)
    test_client.mock_bedrock_call(model=Model.CLAUDE_3_5_SONNET_20241022, status_code=429)

    # OpenAI returns a 200
    test_client.mock_openai_call()

    # Disable fallback -> we will raise
    with pytest.raises(RateLimitError):
        await openai_client.chat.completions.create(**completion_kwargs, extra_body={"use_fallback": "never"})

    # Auto fallback will use openai
    res: Any = await openai_client.chat.completions.create(**completion_kwargs, extra_body={"use_fallback": None})
    await test_client.wait_for_completed_tasks()

    agent_id, run_id = res.id.split("/")
    completions1 = (await test_client.fetch_completions({"id": agent_id}, run_id=run_id))["completions"]
    assert len(completions1) == 3
    assert [(c["model"], c["provider"], len(c["messages"]), c.get("cost_usd")) for c in completions1] == [
        (Model.CLAUDE_3_5_SONNET_20241022, Provider.ANTHROPIC, anthropic_message_count, None),
        (Model.CLAUDE_3_5_SONNET_20241022, Provider.AMAZON_BEDROCK, anthropic_message_count, None),
        (Model.GPT_41_2025_04_14, Provider.OPEN_AI, 1, approx((10 * 2 + 11 * 8) / 1_000_000)),
    ]

    # And manual fallback can be used to switch to a different model
    res: Any = await openai_client.chat.completions.create(
        **completion_kwargs,
        extra_body={"use_fallback": [Model.O3_2025_04_16_LOW_REASONING_EFFORT], "use_cache": "never"},
    )
    await test_client.wait_for_completed_tasks()

    agent_id, run_id = res.id.split("/")
    completions2 = (await test_client.fetch_completions({"id": agent_id}, run_id=run_id))["completions"]
    assert len(completions2) == 3
    assert [(c["model"], c["provider"], len(c["messages"]), c.get("cost_usd")) for c in completions2] == [
        # We automatically add a system message for structured gen to anthropic and bedrock
        (Model.CLAUDE_3_5_SONNET_20241022, Provider.ANTHROPIC, anthropic_message_count, None),
        (Model.CLAUDE_3_5_SONNET_20241022, Provider.AMAZON_BEDROCK, anthropic_message_count, None),
        (Model.O3_2025_04_16_LOW_REASONING_EFFORT, Provider.OPEN_AI, 1, approx((10 * 10 + 11 * 40) / 1_000_000)),
    ]


async def test_with_cache(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    test_client.mock_openai_call(raw_content="Hello, world!")

    # Create a first completion
    res = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello, world!"}],
    )

    await test_client.wait_for_completed_tasks()

    # Now create a second completion with the same input and use the cache
    res = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello, world!"}],
        extra_body={"use_cache": "always"},
    )
    assert res.choices[0].message.content == "Hello, world!"

    # Check that we did not make any new calls
    assert len(test_client.httpx_mock.get_requests(url="https://api.openai.com/v1/chat/completions")) == 1

    # Same with streaming
    streamer = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello, world!"}],
        extra_body={"use_cache": "always"},
        stream=True,
    )
    chunks = [c async for c in streamer]
    assert len(chunks) == 1
    assert chunks[0].choices[0].delta.content == "Hello, world!"


async def test_none_content(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    # Check that we return None content when there is no text content
    test_client.mock_openai_call(
        raw_content=None,
        tool_calls_content=[
            {
                "id": "1",
                "type": "function",
                "function": {"name": "get_current_weather", "arguments": '{"location": "San Francisco"}'},
            },
        ],
    )

    res = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello, world!"}],
    )
    assert res.choices[0].message.content is None
    assert res.choices[0].message.tool_calls is not None


async def test_with_n_value_of_1(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    test_client.mock_openai_call(raw_content="Hello, world!")

    res = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello, world!"}],
        n=1,
    )
    assert res.choices[0].message.content == "Hello, world!"


async def test_with_files_in_variables(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    test_client.mock_openai_call(raw_content="Hello, world!")
    test_client.httpx_mock.add_response(
        url="https://blabla",
        content=b"This is a test image",
    )

    res = await openai_client.chat.completions.create(
        model="greeting/gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image"},
                    {"type": "image_url", "image_url": {"url": "{{ image_url }}"}},
                ],
            },
        ],
        extra_body={
            "input": {
                "image_url": "https://blabla",
            },
        },
    )
    assert res.choices[0].message.content == "Hello, world!"

    agent = await test_client.get("/_/agents/greeting/schemas/1")
    assert agent["input_schema"]["json_schema"] == {
        "$defs": mock.ANY,
        "format": "messages",
        "properties": {
            "image_url": {
                "$ref": "#/$defs/Image",
            },
        },
        "type": "object",
    }

    req = test_client.httpx_mock.get_request(url="https://api.openai.com/v1/chat/completions")
    assert req
    body = json.loads(req.content)
    assert body["messages"][0]["content"][1]["image_url"]["url"] == "https://blabla"
