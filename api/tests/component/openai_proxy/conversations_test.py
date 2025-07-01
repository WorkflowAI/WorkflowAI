from openai import AsyncOpenAI
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam

from tests.component.common import IntegrationTestClient
from tests.component.openai_proxy.common import fetch_run_from_completion


async def test_raw_string_messages(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    # Creating 3 text only completions in quick succession
    test_client.mock_openai_call(raw_content="Hello James!")
    messages: list[ChatCompletionMessageParam] = [{"role": "user", "content": "Hello, world!"}]
    res1 = await openai_client.chat.completions.create(model="gpt-4o", messages=messages)

    test_client.mock_openai_call(raw_content="Hello John!")
    messages.append(res1.choices[0].message.model_dump(exclude_none=True))  # type: ignore
    messages.append({"role": "user", "content": "1"})
    res2 = await openai_client.chat.completions.create(model="gpt-4o", messages=messages)

    test_client.mock_openai_call(raw_content="Hello Eliot!")
    messages.append(res2.choices[0].message.model_dump(exclude_none=True))  # type: ignore
    messages.append({"role": "user", "content": "2"})
    res3 = await openai_client.chat.completions.create(model="gpt-4o", messages=messages)

    await test_client.wait_for_completed_tasks()

    # Now fetching the runs
    run1 = await fetch_run_from_completion(test_client, res1)
    run2 = await fetch_run_from_completion(test_client, res2)
    run3 = await fetch_run_from_completion(test_client, res3)

    # assert run1["conversation_id"] == run2["conversation_id"] == run3["conversation_id"]

    assert run2["task_input"] == {
        "workflowai.messages": [
            {"role": "user", "content": [{"text": "Hello, world!"}]},
            {"role": "assistant", "content": [{"text": "Hello James!"}], "run_id": run1["id"]},
            {"role": "user", "content": [{"text": "1"}]},
        ],
    }

    assert run3["task_input"] == {
        "workflowai.messages": [
            {"role": "user", "content": [{"text": "Hello, world!"}]},
            {"role": "assistant", "content": [{"text": "Hello James!"}], "run_id": run1["id"]},
            {"role": "user", "content": [{"text": "1"}]},
            {"role": "assistant", "content": [{"text": "Hello John!"}], "run_id": run2["id"]},
            {"role": "user", "content": [{"text": "2"}]},
        ],
    }


async def test_with_tool_calls(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    # First tool call
    test_client.mock_openai_call(
        tool_calls_content=[
            {
                "id": "1",
                "type": "function",
                "function": {"name": "get_current_weather", "arguments": '{"location": "San Francisco"}'},
            },
        ],
        raw_content=None,
    )
    messages: list[ChatCompletionMessageParam] = [{"role": "user", "content": "Hello, world!"}]
    res1 = await openai_client.chat.completions.create(model="gpt-4o", messages=messages)
    assert res1.choices[0].message.tool_calls is not None, "sanity"

    test_client.mock_openai_call(raw_content="Hello John!")
    messages.append(res1.choices[0].message.model_dump(exclude_none=True))  # type: ignore
    messages.append(
        {
            "role": "tool",
            "tool_call_id": "1",
            "content": "Sunny",
        },
    )
    res2 = await openai_client.chat.completions.create(model="gpt-4o", messages=messages)

    await test_client.wait_for_completed_tasks()

    # Now fetching the runs
    run1 = await fetch_run_from_completion(test_client, res1)
    run2 = await fetch_run_from_completion(test_client, res2)

    assert run1["conversation_id"] == run2["conversation_id"]

    assert run2["task_input"] == {
        "workflowai.messages": [
            {"role": "user", "content": [{"text": "Hello, world!"}]},
            {
                "role": "assistant",
                "content": [
                    {
                        "tool_call_request": {
                            "id": "1",
                            "tool_input_dict": {
                                "location": "San Francisco",
                            },
                            "tool_name": "get_current_weather",
                            "index": 0,
                        },
                    },
                ],
                "run_id": run1["id"],
            },
            {
                "role": "user",
                "content": [
                    {
                        "tool_call_result": {
                            "id": "1",
                            "result": "Sunny",
                            "tool_input_dict": {"location": "San Francisco"},
                            "tool_name": "get_current_weather",
                            "index": 0,
                        },
                    },
                ],
            },
        ],
    }


async def test_with_deployed_version(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    # First create a version with a system message and deploy it to prod
    task = await test_client.create_agent_v1(
        input_schema={"type": "object", "format": "messages"},
        output_schema={"format": "message", "type": "string"},
    )
    version = await test_client.create_version_v1(
        task,
        {
            "model": "gpt-4o-latest",
            "messages": [
                {"role": "system", "content": [{"text": "You are helpful"}]},
            ],
        },
    )
    await test_client.post(
        f"/v1/_/agents/{task['id']}/versions/{version['id']}/deploy",
        json={"environment": "production"},
    )

    # Now create a conversation with that version
    test_client.mock_openai_call(raw_content="Hello John!")
    messages: list[ChatCompletionMessageParam] = [{"role": "user", "content": "Hello, world!"}]
    res1 = await openai_client.chat.completions.create(model="greet/#1/production", messages=messages)
    messages.append(res1.choices[0].message.model_dump(exclude_none=True))  # type: ignore

    test_client.mock_openai_call(raw_content="Hello James!")
    messages.append({"role": "user", "content": "Finally"})
    res2 = await openai_client.chat.completions.create(model="greet/#1/production", messages=messages)

    await test_client.wait_for_completed_tasks()

    # Now fetching the runs
    run1 = await fetch_run_from_completion(test_client, res1)
    assert run1["conversation_id"] is not None
    run2 = await fetch_run_from_completion(test_client, res2)
    assert run2["conversation_id"] == run1["conversation_id"]


async def test_with_different_model(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    # Start a conversation with model 1

    test_client.mock_openai_call(raw_content="Hello James!")
    messages: list[ChatCompletionMessageParam] = [{"role": "user", "content": "Hello, world!"}]
    res1 = await openai_client.chat.completions.create(model="gpt-4o", messages=messages)

    # Now switch to model 2
    test_client.mock_openai_call(raw_content="Hello John!")
    messages.append(res1.choices[0].message.model_dump(exclude_none=True))  # type: ignore
    messages.append({"role": "user", "content": "1"})
    res2 = await openai_client.chat.completions.create(model="gpt-4o-mini", messages=messages)

    # And finally go back to model 1 with the same messages
    test_client.mock_openai_call(raw_content="Hello Blu!")
    res3 = await openai_client.chat.completions.create(model="gpt-4o", messages=messages)

    await test_client.wait_for_completed_tasks()

    # Now fetching the runs
    run1 = await fetch_run_from_completion(test_client, res1)
    run2 = await fetch_run_from_completion(test_client, res2)
    run3 = await fetch_run_from_completion(test_client, res3)

    assert run1["conversation_id"] == run3["conversation_id"]
    assert run1["conversation_id"] != run2["conversation_id"]

    # Check that the run_id is in run3 input but not run2
    assert run2["task_input"] == {
        "workflowai.messages": [
            {"role": "user", "content": [{"text": "Hello, world!"}]},
            {"role": "assistant", "content": [{"text": "Hello James!"}]},
            {"role": "user", "content": [{"text": "1"}]},
        ],
    }
    assert run3["task_input"] == {
        "workflowai.messages": [
            {"role": "user", "content": [{"text": "Hello, world!"}]},
            {"role": "assistant", "content": [{"text": "Hello James!"}], "run_id": run1["id"]},
            {"role": "user", "content": [{"text": "1"}]},
        ],
    }
