import pytest
from httpx import HTTPStatusError

from core.domain.models import Model
from tests.component.common import IntegrationTestClient, fetch_run, result_or_raise, run_id_url, run_url
from tests.utils import request_json_body


async def test_reviews(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    # First we create a run
    test_client.mock_openai_call()
    # run1 and run2 will have the same input / output hash
    run1 = await test_client.run_task_v1(task)
    run2 = await test_client.run_task_v1(task, use_cache="never")
    assert run1["id"] != run2["id"]
    assert run1["task_output"] == run2["task_output"]

    # Now we send a review
    await test_client.user_review(task, run1, "positive")
    await test_client.wait_for_completed_tasks()

    # Both runs should have a postive review
    fetched_run1 = await fetch_run(test_client.int_api_client, task, run1)
    assert fetched_run1["user_review"] == "positive"
    fetched_run2 = await fetch_run(test_client.int_api_client, task, run2)
    assert fetched_run2["user_review"] == "positive"

    # We also try and fetch the reviews run1 and 2, we should only have 1
    # This is to check that we don't triigger ai reviews on runs that already have a user review
    fetched_reviews1 = await test_client.get(run_url(task, run1["id"]) + "/reviews")
    assert len(fetched_reviews1["items"]) == 1

    # Now I create a new run with the same input / output
    # It should also get the positive review
    run3 = await test_client.run_task_v1(task, use_cache="never")
    await test_client.wait_for_completed_tasks()
    fetched_run3 = await fetch_run(test_client.int_api_client, task, run3)
    assert fetched_run3["user_review"] == "positive"

    # We should still have a single review
    fetched_reviews1 = await test_client.get(run_url(task, run1["id"]) + "/reviews")
    assert len(fetched_reviews1["items"]) == 1

    # Create a new run with a different output
    test_client.mock_openai_call(json_content={"greeting": "Hello not James!"})
    test_client.mock_ai_review(outcome="negative", negative_aspects=["should be John"])

    run4 = await test_client.run_task_v1(task, use_cache="never")
    assert run4["task_output"] != run3["task_output"], "sanity"
    await test_client.wait_for_completed_tasks()
    fetched_run4 = await fetch_run(test_client.int_api_client, task, run4)
    assert fetched_run4["ai_review"] == "negative"

    # Get the review
    fetched_reviews = result_or_raise(
        await test_client.int_api_client.get(run_id_url(task, run4["id"], "reviews")),
    )
    assert len(fetched_reviews["items"]) == 1
    assert fetched_reviews["items"][0]["outcome"] == "negative"
    assert fetched_reviews["items"][0]["negative_aspects"] == ["should be John"]


async def test_extra_fields(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    test_client.httpx_mock.reset(False)
    # First we create a run with some extra fields
    test_client.mock_openai_call(
        json_content={"greeting": "Hello James!", "internal_steps": ["bla"]},
    )
    run1 = await test_client.run_task_v1(task, use_cache="never")
    assert run1["task_output"] == {"greeting": "Hello James!", "internal_steps": ["bla"]}, "sanity"

    test_client.httpx_mock.reset(False)
    # Now same run but without other extra fields
    test_client.mock_openai_call(
        json_content={"greeting": "Hello James!"},
        model=Model.GPT_4O_2024_11_20.value,
    )
    run2 = await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20.value, use_cache="never")
    assert run2["task_output"] == {"greeting": "Hello James!"}, "sanity"
    assert run2["id"] != run1["id"]

    await test_client.wait_for_completed_tasks()

    fetched_run1 = await fetch_run(test_client.int_api_client, task, run1)
    fetched_run2 = await fetch_run(test_client.int_api_client, task, run2)
    assert fetched_run1["task_input_hash"] == fetched_run2["task_input_hash"]
    assert fetched_run1["task_output_hash"] == fetched_run2["task_output_hash"]

    # Now we add a review
    # Review is created from the run that contains the extra fields
    await test_client.user_review(task, run1, "positive")
    await test_client.wait_for_completed_tasks()

    # Check that it is correctly propagated to both runs
    fetched_run1 = await fetch_run(test_client.int_api_client, task, run1)
    assert fetched_run1["user_review"] == "positive"
    fetched_run2 = await fetch_run(test_client.int_api_client, task, run2)
    assert fetched_run2["user_review"] == "positive"

    # Now let's create a third run that will be evaluated by the AI
    test_client.mock_openai_call(
        json_content={"greeting": "Hello John!", "internal_steps": ["blablo"]},
        model=Model.GPT_4O_2024_11_20.value,
    )
    test_client.mock_ai_review(outcome="negative")
    run3 = await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20.value, use_cache="never")
    assert run3["id"] != run1["id"]
    assert run3["id"] != run2["id"]
    await test_client.wait_for_completed_tasks()

    fetched_run3 = await fetch_run(test_client.int_api_client, task, run3)
    assert fetched_run3["task_input_hash"] == fetched_run1["task_input_hash"]
    assert fetched_run3["ai_review"] == "negative"

    requests = test_client.httpx_mock.get_requests(url=test_client.internal_task_url("evaluate-output"))
    assert len(requests) == 1
    body = request_json_body(requests[0])
    # Check the correct output and evaluated output are correctly set
    assert body["task_input"]["evaluated_output"] == '{"greeting": "Hello John!"}'
    assert body["task_input"]["correct_outputs"] == ['{"greeting": "Hello James!"}']

    # Resetting the httpx mock
    test_client.httpx_mock.reset(False)

    # Finally make another run with an input / output that match above except with some extra fields
    test_client.mock_openai_call(
        json_content={"greeting": "Hello James!", "internal_steps": ["blabloblu"]},
        model=Model.GPT_4O_2024_11_20.value,
    )
    run4 = await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20.value, use_cache="never")
    assert run4["id"] not in [run1["id"], run2["id"], run3["id"]]
    await test_client.wait_for_completed_tasks()

    fetched_run4 = await fetch_run(test_client.int_api_client, task, run4)
    # positive since we are in the correct ouputs
    assert fetched_run4["user_review"] == "positive"
    # Double check that no evaluation request was sent
    requests = test_client.httpx_mock.get_requests(url=test_client.internal_task_url("evaluate-output"))
    assert len(requests) == 0


async def test_update_ai_evaluator(test_client: IntegrationTestClient):
    # Setup a reviewable input
    task = await test_client.create_task()

    # First we create a run
    test_client.mock_openai_call()
    # run1 and run2 will have the same input / output hash
    run1 = await test_client.run_task_v1(task)
    # Now we send a review, this will create a correct output so the AI reviewer can start from there
    await test_client.user_review(task, run1, "positive")

    # Mock the AI review
    test_client.mock_ai_review(outcome="negative")
    # Next run will have a different output and trigger an AI review
    test_client.mock_openai_call(json_content={"greeting": "Hello not James!"})
    run2 = await test_client.run_task_v1(task, use_cache="never")
    assert run2["task_output"] != run1["task_output"], "sanity"
    await test_client.wait_for_completed_tasks()
    fetched_run2 = await fetch_run(test_client.int_api_client, task, run2)
    assert fetched_run2["ai_review"] == "negative"
    fetched_review2 = result_or_raise(await test_client.int_api_client.get(run_id_url(task, run2["id"], "reviews")))
    assert len(fetched_review2["items"]) == 1
    review2 = fetched_review2["items"][0]
    assert review2["outcome"] == "negative"

    # There should be no actual completed tasks here
    await test_client.wait_for_completed_tasks()

    # Now we can respond to the review
    # First create a user review that disagrees with the AI review
    await test_client.user_review(task, run2, "positive")
    test_client.mock_internal_task(
        "update-correct-outputs-and-instructions",
        {
            "updated_correct_outputs": ['{"greeting": "Hello James!"}', '{"greeting": "Hello not James!"}'],
            "updated_evaluation_instruction": "Evaluate the greeting",
            "update_evaluation_instruction_for_input": "James or not james",
        },
    )
    # Then call the respond endpoint
    result_or_raise(
        await test_client.int_api_client.post(
            run_id_url(task, run2["id"], f"reviews/{review2['id']}/respond"),
            json={"comment": "I disagree with the AI review"},
        ),
    )

    # The generation of the evaluation instructions happen here
    await test_client.wait_for_completed_tasks()

    internal_reqs = await test_client.get_internal_task_request_bodies("update-correct-outputs-and-instructions", 12)
    assert internal_reqs == [
        {
            "correct_outputs": [
                '{"greeting": "Hello James!"}',
                '{"greeting": "Hello not James!"}',
            ],
            "evaluated_output": '{"greeting": "Hello not James!"}',
            "evaluation_instruction": "",
            "evaluation_result": "FAIL",
            "incorrect_outputs": [],
            "why_is_the_evaluated_output_also_correct": "I disagree with the AI review",
            "why_is_the_evaluated_output_incorrect": None,
        },
    ]

    # In total we should only have had one evaluation run since a single AI review was triggered
    evaluation_reqs = await test_client.get_internal_task_request_bodies("evaluate-output", 13)
    assert evaluation_reqs == [
        {
            "correct_outputs": [
                '{"greeting": "Hello James!"}',
            ],
            "evaluated_output": '{"greeting": "Hello not James!"}',
            "evaluation_instruction": "",
            "incorrect_outputs": [],
            "input_evaluation_instruction": None,
            "task_input": '{"name": "John", "age": 30}',
        },
    ]

    test_client.reset_http_requests()

    # Let's trigger an AI review again and make sure it uses the updated instructions
    test_client.mock_ai_review(outcome="negative")
    test_client.mock_openai_call(json_content={"greeting": "Hello John!"})
    run3 = await test_client.run_task_v1(task, use_cache="never")
    assert run3["task_output"] != run2["task_output"], "sanity"
    assert run3["task_output"] != run1["task_output"], "sanity"
    await test_client.wait_for_completed_tasks()

    fetched_run3 = await fetch_run(test_client.int_api_client, task, run3)
    assert fetched_run3["ai_review"] == "negative"

    evaluation_reqs = await test_client.get_internal_task_request_bodies("evaluate-output", 13)
    assert evaluation_reqs == [
        {
            "correct_outputs": [
                '{"greeting": "Hello James!"}',
                '{"greeting": "Hello not James!"}',
            ],
            "evaluated_output": '{"greeting": "Hello John!"}',
            "evaluation_instruction": "Evaluate the greeting",
            "incorrect_outputs": [],
            "input_evaluation_instruction": "James or not james",
            "task_input": '{"name": "John", "age": 30}',
        },
    ]


async def test_image_evaluations(test_client: IntegrationTestClient):
    # Create a task with an image input and create a reviewable input
    task = await test_client.create_task(input_schema={"properties": {"image": {"$ref": "#/$defs/Image"}}})
    # First we create a run
    test_client.mock_openai_call()
    test_client.httpx_mock.add_response(
        url="https://example.com/image.png",
        method="GET",
        content=b"image_data",
    )
    # run1 and run2 will have the same input / output hash
    run1 = await test_client.run_task_v1(task, task_input={"image": {"url": "https://example.com/image.png"}})
    # Now we send a review, this will create a correct output so the AI reviewer can start from there
    await test_client.user_review(task, run1, "positive")

    # Now we create a second run with a different output to trigger an AI review
    test_client.mock_openai_call(json_content={"greeting": "Hello not James!"})
    test_client.mock_ai_review(outcome="negative")
    test_client.mock_internal_task("describe-images-with-context", {"description": "A cat"})

    run2 = await test_client.run_task_v1(
        task,
        task_input={"image": {"url": "https://example.com/image.png"}},
        use_cache="never",
    )
    assert run2["task_output"] != run1["task_output"], "sanity"

    await test_client.wait_for_completed_tasks()

    fetched_run2 = await fetch_run(test_client.int_api_client, task, run2)
    assert fetched_run2["ai_review"] == "negative"
    assert "storage_url" in fetched_run2["task_input"]["image"], "sanity"

    # And check the payload that was sent to the internal tasks
    describe_image_reqs = await test_client.get_internal_task_request_bodies("describe-images-with-context", 3)
    assert describe_image_reqs == [
        {
            "images": [
                {
                    "url": fetched_run2["task_input"]["image"]["storage_url"],
                    "content_type": "image/png",
                    "data": None,
                    "name": None,
                },
            ],
            "instructions": None,
        },
    ]


async def test_failed_runs(test_client: IntegrationTestClient):
    # Create a failed run
    task = await test_client.create_task()
    test_client.mock_openai_call(
        json={
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"refusal": "I'm sorry, I can't assist with that.", "role": "assistant"},
                },
            ],
        },
    )
    with pytest.raises(HTTPStatusError) as e:
        await test_client.run_task_v1(task, use_cache="never")

    assert e.value.response.status_code == 400, "sanity"

    task_run_id = e.value.response.json()["id"]
    fetched1 = await test_client.fetch_run(task, run_id=task_run_id)
    assert fetched1["status"] == "failure"
    # negative review since the run failed, but we should not have a review record here
    assert not fetched1.get("user_review")
    assert fetched1["cost_usd"] != 0  # we charge as it is during extraction of the provider response

    # If I fetch the reviews for the run it whould be empty
    reviews = result_or_raise(await test_client.int_api_client.get(run_id_url(task, task_run_id, "reviews")))
    assert len(reviews["items"]) == 0

    # Now I'll create a new run that will succeed and add a review
    test_client.mock_openai_call()
    run2 = await test_client.run_task_v1(task)
    await test_client.user_review(task, run2, "positive")
    fetched2 = await test_client.fetch_run(task, run_id=run2["id"])
    assert fetched2["user_review"] == "positive", "sanity"

    # Because I added a review for the same input, now the previous run should also have a review
    await test_client.wait_for_completed_tasks()

    # If I fetch the reviews for the run it should no longer be empty
    reviews = result_or_raise(await test_client.int_api_client.get(run_id_url(task, fetched1["id"], "reviews")))
    assert len(reviews["items"]) == 1
    assert reviews["items"][0]["outcome"] == "negative"


# TODO[test]: it would be interesting to convert this test to eval v2
# @pytest.mark.parametrize("task_input", [{"name": "", "age": 30}, {"name": None, "age": 30}, {"age": 30}])
# async def test_run_with_empty_string_in_input(
#     httpx_mock: HTTPXMock,
#     int_api_client: AsyncClient,
#     task_input: dict[str, Any],
#     patched_broker: InMemoryBroker,
# ):
#     task = await create_task_without_required_fields(int_api_client, patched_broker, httpx_mock)

#     # Add an evaluator to the task
#     result_or_raise(
#         await int_api_client.post(
#             task_schema_url(task, "evaluators"),
#             json={
#                 "name": "eval_1",
#                 "evaluator_type": {
#                     "type": "field_based",
#                     "field_based_evaluation_config": {
#                         "options": {"type": "object", "property_evaluations": {"greeting": {"type": "string"}}},
#                     },
#                 },
#             },
#         ),
#     )

#     # Create an example
#     _ = result_or_raise(
#         await int_api_client.post(
#             f"/_/agents/{task["task_id"]}/schemas/{task["task_schema_id"]}/examples",
#             json={
#                 "task_input": {"age": 30},
#                 "task_output": {"greeting": "hello sir !"},
#             },
#         ),
#     )

#     mock_vertex_call(
#         httpx_mock,
#         model="gemini-1.5-pro-002",
#         parts=[{"text": '{"greeting": "hello sir !"}', "inlineData": None}],
#         usage={"promptTokenCount": None, "candidatesTokenCount": None, "totalTokenCount": None},
#     )

#     # Run the task the first time
#     task_run = await run_task_v1(
#         int_api_client,
#         task_id="greet",
#         task_schema_id=1,
#         task_input=task_input,
#         model="gemini-1.5-pro-002",
#     )

#     await wait_for_completed_tasks(patched_broker)

#     # Fetch the task run
#     fetched = await int_api_client.get(f"/chiefofstaff.ai/agents/greet/runs/{task_run['id']}")
#     assert fetched.status_code == 200
#     fetched_task_run = fetched.json()

#     assert fetched_task_run["task_input"] == task_input
#     assert fetched_task_run["task_output"] == {"greeting": "hello sir !"}
#     assert (  # Test that "greetings": "", "greeting": None and {} are considered valid
#         fetched_task_run["scores"][0]["score"] == 1.0
#     )

# TODO[test]: it would be interesting to convert this test to eval v2
# @pytest.mark.parametrize("example_output", [{"greeting": ""}, {"greeting": None}, {}])
# @pytest.mark.parametrize("return_str", ['{"greeting": ""}', '{"greeting": null}', "{}"])
# async def test_run_with_empty_string_in_output(
#     httpx_mock: HTTPXMock,
#     int_api_client: AsyncClient,
#     return_str: str,
#     patched_broker: InMemoryBroker,
#     example_output: dict[str, Any],
# ):
#     task = await create_task_without_required_fields(int_api_client, patched_broker, httpx_mock)

#     # Add an evaluator to the task
#     result_or_raise(
#         await int_api_client.post(
#             task_schema_url(task, "evaluators"),
#             json={
#                 "name": "eval_1",
#                 "evaluator_type": {
#                     "type": "field_based",
#                     "field_based_evaluation_config": {
#                         "options": {"type": "object", "property_evaluations": {"greeting": {"type": "string"}}},
#                     },
#                 },
#             },
#         ),
#     )

#     # Create an example
#     _ = result_or_raise(
#         await int_api_client.post(
#             f"/_/agents/{task['task_id']}/schemas/{task['task_schema_id']}/examples",
#             json={
#                 "task_input": {"name": "John", "age": 30},
#                 "task_output": example_output,
#             },
#         ),
#     )

#     mock_vertex_call(
#         httpx_mock,
#         model="gemini-1.5-pro-002",
#         parts=[{"text": return_str, "inlineData": None}],
#         usage={"promptTokenCount": None, "candidatesTokenCount": None, "totalTokenCount": None},
#     )

#     # Run the task the first time
#     task_run = await run_task_v1(
#         int_api_client,
#         task_id="greet",
#         task_schema_id=1,
#         task_input={"name": "John", "age": 30},
#         model="gemini-1.5-pro-002",
#     )

#     await wait_for_completed_tasks(patched_broker)

#     # Fetch the task run
#     fetched = await int_api_client.get(f"/chiefofstaff.ai/agents/greet/runs/{task_run['id']}")
#     assert fetched.status_code == 200
#     fetched_task_run = fetched.json()

#     assert fetched_task_run["task_output"] == {}
#     assert (  # Test that "greetings": "", "greeting": None and {} are considered valid
#         fetched_task_run["scores"][0]["score"] == 1.0
#     )
