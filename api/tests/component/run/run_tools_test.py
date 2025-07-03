from typing import Any

import pytest
from httpx import HTTPStatusError

from core.domain.models import Model
from tests.component.common import (
    IntegrationTestClient,
    fetch_run,
)
from tests.utils import cut_json


async def test_tool_call_recursion(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    test_client.mock_internal_task(
        "detect-chain-of-thought",
        {"should_use_chain_of_thought": False},
        create_agent=True,
    )

    # Create a version that includes a tool call
    version = await test_client.create_version(
        task,
        version_properties={
            "model": Model.GPT_4O_2024_11_20,
            "instructions": "@search-google @browser-text",
        },
        create_agent=False,
    )
    version_properties = version["properties"]
    assert set(version_properties["enabled_tools"]) == {"@search-google", "@browser-text"}

    test_client.reset_httpx_mock()

    # First call returns a tool call
    test_client.mock_openai_call(
        tool_calls_content=[
            {
                "id": "some_id",
                "type": "function",
                "function": {"name": "search-google", "arguments": '{"query": "bla"}'},
            },
        ],
    )
    # Then we return the same tool call but with an output as well
    test_client.mock_openai_call(
        json_content={
            "greeting": "Hello James!",
            "internal_agent_run_result": {"status": "success"},
        },
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

    res = await test_client.run_task_v1(task, version=version["iteration"])
    assert res
    assert res["task_output"] == {"greeting": "Hello James!"}

    assert len(test_client.httpx_mock.get_requests(url="https://google.serper.dev/search")) == 1

    fetched_run = await fetch_run(test_client.int_api_client, task, res)
    assert fetched_run["task_output"] == {"greeting": "Hello James!"}
    assert fetched_run["llm_completions"][0]["tool_calls"] == [
        {
            "tool_name": "@search-google",
            "tool_input_dict": {"query": "bla"},
            "id": "some_id",
            "index": 0,
        },
    ]
    assert len(fetched_run["llm_completions"]) == 2


async def test_tool_call_recursion_streaming(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    # Create a version that includes a tool call
    version = await test_client.create_version(
        task,
        version_properties={
            "model": Model.GPT_4O_2024_11_20,
            "instructions": "@search @browser-text to search and @search to fulfill the job.",
        },
        create_agent=False,
    )
    version_properties = version["properties"]
    assert set(version_properties["enabled_tools"]) == {"@search-google", "@browser-text"}

    await test_client.wait_for_completed_tasks()
    test_client.reset_httpx_mock()

    tool_call_1 = [
        {
            "index": 0,
            "id": "some_id",
            "type": "function",
            "function": {"name": "search-google", "arguments": '{"query"'},
        },
    ]
    tool_call_2 = [
        {
            "index": 0,
            "id": "some_id",
            "type": "function",
            "function": {"name": "search-google", "arguments": ': "b'},
        },
    ]
    tool_call_3 = [
        {
            "index": 0,
            "id": "some_id",
            "type": "function",
            "function": {"name": "search-google", "arguments": 'la"}'},
        },
    ]
    # First call returns a tool call
    test_client.mock_openai_stream(deltas=None, tool_calls_deltas=[tool_call_1, tool_call_2, tool_call_3])
    json_1: dict[str, Any] = {}
    json_1["greeting"] = "Hello James!"
    json_1["internal_agent_run_result"] = {"status": "success"}
    # Then we return the same tool call but with an output as well
    test_client.mock_openai_stream(deltas=list(cut_json(json_1, [5, 10, 30, 45, 60, 80])))

    test_client.httpx_mock.add_response(
        url="https://google.serper.dev/search",
        text="blabla",
    )

    chunks = [c async for c in test_client.stream_run_task_v1(task, version=version["iteration"])]
    assert chunks

    assert len(test_client.httpx_mock.get_requests(url="https://google.serper.dev/search")) == 1

    fetched_run = await fetch_run(test_client.int_api_client, task, run_id=chunks[0]["id"])
    assert fetched_run["task_output"] == {
        "greeting": "Hello James!",
    }
    assert fetched_run["llm_completions"][0]["tool_calls"] == [
        {"tool_name": "@search-google", "tool_input_dict": {"query": "bla"}, "id": "some_id", "index": 0},
    ]

    # TODO[tools]: check tool_call field

    assert len(fetched_run["llm_completions"]) == 2


async def test_tool_call_run_failed(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    # First call returns a tool call
    test_client.mock_openai_call(
        tool_calls_content=[
            {
                "id": "some_id",
                "type": "function",
                "function": {"name": "search-google", "arguments": '{"query": "bla"}'},
            },
        ],
    )
    test_client.mock_openai_call(
        json_content={
            "internal_agent_run_result": {"status": "failure", "error": {"error_message": "This sucks"}},
        },
    )

    test_client.httpx_mock.add_response(
        url="https://google.serper.dev/search",
        status_code=500,
    )

    with pytest.raises(HTTPStatusError) as e:
        await test_client.run_task_v1(
            task,
            version={
                "model": Model.GPT_4O_2024_11_20,
                "instructions": "@search @browser-text",
            },
        )

    assert e.value.response.status_code == 424
    assert e.value.response.json()["error"]["message"] == "Agent run failed: This sucks"

    assert len(test_client.httpx_mock.get_requests(url="https://google.serper.dev/search")) == 1


async def test_tool_call_request(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    test_client.mock_openai_call(
        raw_content=None,
        tool_calls_content=[
            {
                "id": "some_id",
                "type": "function",
                "function": {"name": "hello", "arguments": '{"query": "bla"}'},
            },
        ],
    )

    res = await test_client.run_task_v1(
        task,
        version={
            "model": Model.GPT_4O_2024_11_20,
            "instructions": "You are a helpful assistant.",
            "enabled_tools": {
                "name": "hello",
                "description": "Say hello",
                "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
                "output_schema": {"type": "object", "properties": {"greeting": {"type": "string"}}},
            },
        },
    )
    assert res
    assert res["task_output"] == {}
    assert res["tool_call_requests"] == [
        {
            "id": "some_id",
            "name": "hello",
            "input": {"query": "bla"},
        },
    ]

    # Now fetching the run should return the tool call request
    fetched_run = await fetch_run(test_client.int_api_client, task, res, v1=True)
    assert fetched_run["status"] == "success"
    assert fetched_run["tool_call_requests"] == [
        {
            "id": "some_id",
            "name": "hello",
            "input": {"query": "bla"},
        },
    ]
