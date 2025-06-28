from tests.component.common import DEFAULT_INPUT_HASH, IntegrationTestClient, run_id_url, task_schema_url
from tests.utils import request_json_body


async def test_update_evaluations(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    # Create a run
    test_client.mock_openai_call(json_content={"greeting": "Hello James!"}, is_reusable=True)
    run1 = await test_client.run_task_v1(task)
    assert run1["id"] is not None, "sanity check"

    test_client.mock_openai_call(json_content={"greeting": "Hello John!"}, is_reusable=True)

    run2 = await test_client.run_task_v1(task, use_cache="never")
    assert run2["id"] is not None and run2["id"] != run1["id"], "sanity check"

    # Send a review
    test_client.mock_ai_review("unsure", is_reusable=True)
    await test_client.user_review(task, run1, "positive")

    review_calls = test_client.httpx_mock.get_requests(url=test_client.internal_task_url("evaluate-output"))
    assert len(review_calls) == 1
    body = request_json_body(review_calls[0])
    assert body["task_input"]["correct_outputs"] == ['{"greeting": "Hello James!"}']

    # We should have a review on the second run
    res = await test_client.get(run_id_url(task, run2["id"], "reviews"))
    assert len(res["items"]) == 1
    assert res["items"][0]["created_by"]["reviewer_type"] == "ai"
    assert res["items"][0]["outcome"] == "unsure"

    # We should have an evaluated input
    res = await test_client.get(task_schema_url(task, "evaluation/inputs"))
    assert len(res["items"]) == 1

    assert res["items"][0]["task_input_hash"] == DEFAULT_INPUT_HASH
    assert res["items"][0]["task_input"] == {"name": "John", "age": 30}, "sanity"
    assert res["items"][0]["correct_outputs"] == [{"greeting": "Hello James!"}]
    assert res["items"][0]["incorrect_outputs"] == []
    assert res["items"][0]["evaluation_instructions"] == ""

    # I can update the evaluation instructions for that input
    res = await test_client.patch(
        task_schema_url(task, f"evaluation/inputs/{DEFAULT_INPUT_HASH}"),
        json={"update_input_evaluation_instructions": "You should be positive"},
    )
    assert res["evaluation_instructions"] == "You should be positive"

    await test_client.wait_for_completed_tasks()
    assert (
        len(
            test_client.httpx_mock.get_requests(
                url=test_client.internal_task_url("evaluate-output"),
            ),
        )
        == 2
    )

    # I should be able to retrieve the same input again
    res1 = await test_client.get(task_schema_url(task, "evaluation/inputs"))
    assert len(res1["items"]) == 1
    assert res1["items"][0] == res

    # I can also update the correct and incorrect outputs
    res = await test_client.patch(
        task_schema_url(task, f"evaluation/inputs/{DEFAULT_INPUT_HASH}"),
        json={"add_correct_output": {"greeting": "Hello John!"}},
    )
    assert res["correct_outputs"] == [{"greeting": "Hello James!"}, {"greeting": "Hello John!"}]

    await test_client.wait_for_completed_tasks()

    # Now we should have a positive review since the output is in the correct outputs
    res = await test_client.get(run_id_url(task, run2["id"], "reviews"))
    assert len(res["items"]) == 1
    assert res["items"][0]["outcome"] == "positive"

    # No call here since the output is in the correct outputs
    assert (
        len(
            test_client.httpx_mock.get_requests(
                url=test_client.internal_task_url("evaluate-output"),
            ),
        )
        == 2
    )

    res = await test_client.patch(
        task_schema_url(task, f"evaluation/inputs/{DEFAULT_INPUT_HASH}"),
        json={"add_incorrect_output": {"greeting": "Hello not John!"}},
    )
    assert res["correct_outputs"] == [{"greeting": "Hello James!"}, {"greeting": "Hello John!"}]
    assert res["incorrect_outputs"] == [{"greeting": "Hello not John!"}]

    res1 = await test_client.get(task_schema_url(task, "evaluation/inputs"))
    assert len(res1["items"]) == 1
    assert res1["items"][0] == res

    await test_client.wait_for_completed_tasks()
    # A single request since the run 1 output is in the correct outputs
    requests = test_client.httpx_mock.get_requests(
        url=test_client.internal_task_url("evaluate-output"),
    )
    assert len(requests) == 2
