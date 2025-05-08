import openai
import pytest
from openai import AsyncOpenAI
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall, Function

from tests.integration.common import IntegrationTestClient
from tests.integration.conftest import _TEST_JWT  # pyright: ignore [reportPrivateUsage]


@pytest.fixture()
def openai_client(test_client: IntegrationTestClient):
    yield AsyncOpenAI(http_client=test_client.int_api_client, api_key=_TEST_JWT)


async def test_raw_string_output(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    test_client.mock_openai_call(raw_content="Hello James!")

    res = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello, world!"}],
    )

    assert res.choices[0].message.content == "Hello James!"

    await test_client.wait_for_completed_tasks()

    task_id, run_id = res.id.split("/")
    run = await test_client.fetch_run({"id": task_id}, run_id=run_id, v1=True)
    assert run["id"] == run_id
    assert run["task_output"] == "Hello James!"

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

    res = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe the image in a sassy manner"},
                    {"type": "image_url", "image_url": {"url": "https://hello.com/image.png"}},
                ],
            },
        ],
    )
    assert res.choices[0].message.content == "This is a test image"

    await test_client.wait_for_completed_tasks()


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
