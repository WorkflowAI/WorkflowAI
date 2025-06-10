from typing import Any, Protocol

import pytest

from core.domain.models import Model
from tests.component.common import IntegrationTestClient, openai_endpoint


class _ReplyFn(Protocol):
    async def __call__(
        self,
        task: dict[str, Any],
        run_id: str,
        json: dict[str, Any] | None = None,
        user_message: str | None = None,
        tool_results: list[dict[str, Any]] | None = None,
        version: int | str | dict[str, Any] | None = None,
        model: str | Model = "gpt-4o-2024-11-20",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


@pytest.fixture
def reply_fn(test_client: IntegrationTestClient) -> _ReplyFn:
    async def reply(
        task: dict[str, Any],
        run_id: str,
        json: dict[str, Any] | None = None,
        user_message: str | None = None,
        tool_results: list[dict[str, Any]] | None = None,
        version: int | str | dict[str, Any] | None = None,
        model: str | Model = "gpt-4o-2024-11-20",
        metadata: dict[str, Any] | None = None,
    ):
        if not json:
            json = {}
            if user_message:
                json["user_message"] = user_message
            if tool_results:
                json["tool_results"] = tool_results
            if version:
                json["version"] = version
            elif model:
                json["version"] = {"model": model}
            if metadata:
                json["metadata"] = metadata
        return await test_client.post(
            f"/v1/_/agents/{task['task_id']}/runs/{run_id}/reply",
            json=json,
        )

    return reply


async def test_reply(test_client: IntegrationTestClient, reply_fn: _ReplyFn):
    task = await test_client.create_task()

    # Run the task
    test_client.mock_openai_call(json_content={"greeting": "Hello John!"})
    run1 = await test_client.run_task_v1(task=task, task_input={"name": "John", "age": 32})

    # Now reply
    test_client.mock_openai_call(json_content={"greeting": "Hello James!"})
    reply = await reply_fn(task=task, run_id=run1["id"], user_message="Now say hello to James!")
    assert reply["task_output"] == {"greeting": "Hello James!"}

    requests = test_client.get_request_bodies(url=openai_endpoint())
    assert len(requests) == 2

    assert len(requests[1]["messages"]) == 4
    assert requests[0]["messages"][:2] == requests[0]["messages"]
    assert requests[1]["messages"][2] == {"role": "assistant", "content": '{"greeting": "Hello John!"}'}
    assert requests[1]["messages"][3] == {"role": "user", "content": "Now say hello to James!"}


async def test_reply_with_tools(test_client: IntegrationTestClient, reply_fn: _ReplyFn):
    task = await test_client.create_task()

    test_client.mock_openai_call(
        json={
            "id": "1",
            "choices": [
                {
                    "message": {
                        "content": '{"greeting": "Hello James!"}',
                        "tool_calls": [
                            {
                                "id": "tool_1_2b5c3a91e698ae509c7995bb88429d87",
                                "type": "function",
                                "function": {
                                    "name": "tool_1",
                                    "arguments": '{"bla": "blu"}',
                                },
                            },
                        ],
                    },
                },
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 11,
                "total_tokens": 21,
            },
        },
    )

    # Run the task
    run1 = await test_client.run_task_v1(task=task, task_input={"name": "John", "age": 32})
    assert run1["tool_call_requests"] == [
        {
            "id": "tool_1_2b5c3a91e698ae509c7995bb88429d87",
            "name": "tool_1",
            "input": {"bla": "blu"},
        },
    ]

    # Now reply
    test_client.mock_openai_call(json_content={"greeting": "Hello James!"})
    reply = await reply_fn(
        task=task,
        run_id=run1["id"],
        tool_results=[
            {"id": "tool_1_2b5c3a91e698ae509c7995bb88429d87", "output": "James"},
        ],
    )
    assert reply["task_output"] == {"greeting": "Hello James!"}
    requests = test_client.get_request_bodies(url=openai_endpoint())
    assert len(requests) == 2

    assert len(requests[1]["messages"]) == 4
    assert requests[0]["messages"][:2] == requests[0]["messages"]
    assert requests[1]["messages"][2] == {
        "role": "assistant",
        "content": [
            {
                "text": '{"greeting": "Hello James!"}',
                "type": "text",
            },
        ],
        "tool_calls": [
            {
                "function": {
                    "arguments": '{"bla": "blu"}',
                    "name": "tool_1",
                },
                "id": "tool_1_2b5c3a91e698ae509c7995bb88429d87",
                "type": "function",
            },
        ],
    }
    assert requests[1]["messages"][3] == {
        "role": "tool",
        "content": "James",
        "tool_call_id": "tool_1_2b5c3a91e698ae509c7995bb88429d87",
    }
