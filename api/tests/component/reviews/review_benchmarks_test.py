import pytest
from httpx import HTTPStatusError

from core.domain.models import Model
from tests.component.common import (
    IntegrationTestClient,
    fetch_run,
    result_or_raise,
    task_schema_url,
    task_url_v1,
)
from tests.utils import fixtures_json


async def test_review_benchmarks(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    # First we create a run
    test_client.mock_openai_call(is_reusable=True)
    run1 = await test_client.run_task_v1(task)

    # Now we send a review
    await test_client.user_review(task, run1, "positive")

    # Fetch the run and make sure the review is there
    fetched_run1 = await fetch_run(test_client.int_api_client, task, run1)
    assert fetched_run1["user_review"] == "positive"

    # We can add the version
    benchmark = await test_client.patch(
        task_schema_url(task, "reviews/benchmark"),
        json={"add_versions": [1]},
    )
    assert len(benchmark["results"]) == 1
    assert benchmark["results"][0]["iteration"] == 1
    assert benchmark["results"][0]["properties"] == {
        "model": "gpt-4o-2024-11-20",
        "temperature": 0.0,
        "model_name": "GPT-4o (2024-11-20)",
        "model_icon": "https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
    }

    await test_client.wait_for_completed_tasks()

    fetched_benchmark = await test_client.get(task_schema_url(task, "reviews/benchmark"))

    first_result = fetched_benchmark["results"][0]
    assert first_result["positive_review_count"] == 1
    assert first_result["positive_user_review_count"] == 1
    assert first_result["negative_review_count"] == 0
    assert first_result["negative_user_review_count"] == 0
    assert first_result["unsure_review_count"] == 0
    assert first_result["in_progress_review_count"] == 0
    assert first_result["average_cost_usd"] is not None
    # The duration is really small here so it's likely to be 0 or None
    # assert first_result["average_duration_seconds"] is not None

    # Now we add another version, which will trigger runs
    # The output will match the first run, so we should get 2 positive reviews
    test_client.mock_vertex_call(
        parts=[{"text": '{"greeting": "Hello James!"}'}],
        model=Model.GEMINI_1_5_PRO_002,
        is_reusable=True,
    )

    v = await test_client.create_version(task, {"model": Model.GEMINI_1_5_PRO_002}, autowait=True)
    assert v["iteration"] == 2, "sanity"
    await test_client.patch(
        task_schema_url(task, "reviews/benchmark"),
        json={"add_versions": [2]},
    )

    await test_client.wait_for_completed_tasks()

    fetched_benchmark = await test_client.get(task_schema_url(task, "reviews/benchmark"))
    assert len(fetched_benchmark["results"]) == 2
    first_result = fetched_benchmark["results"][0]
    assert first_result["positive_review_count"] == 1, "no new positive reviews for first version"
    second_result = fetched_benchmark["results"][1]
    assert second_result["positive_review_count"] == 1, "no new positive reviews for second version"

    # Now we add a third version, with a different output, an AI review should be triggered
    test_client.mock_vertex_call(model=Model.GEMINI_1_5_FLASH_002, is_reusable=True)
    test_client.mock_ai_review(outcome="unsure", is_reusable=True)
    v = await test_client.create_version(task, {"model": Model.GEMINI_1_5_FLASH_002})

    await test_client.patch(
        task_schema_url(task, "reviews/benchmark"),
        json={"add_versions": [3]},
    )

    await test_client.wait_for_completed_tasks()

    fetched_benchmark = result_or_raise(
        await test_client.int_api_client.get(task_schema_url(task, "reviews/benchmark")),
    )
    assert fetched_benchmark["results"][2]["unsure_review_count"] == 1

    # Add a new input to the benchmark, and check that it triggers new runs
    run3 = await test_client.run_task_v1(task, task_input={"name": "Jane", "age": 31})
    await test_client.user_review(task, run3, "negative")
    await test_client.wait_for_completed_tasks()

    fetched_benchmark = result_or_raise(
        await test_client.int_api_client.get(task_schema_url(task, "reviews/benchmark")),
    )
    counts = [
        (r["positive_review_count"], r["negative_review_count"], r["unsure_review_count"])
        for r in fetched_benchmark["results"]
    ]
    # First and second ones have 1 positive and 1 negative since they are based on user reviews
    # 3rd one only went through AI reviews so 2 unsure
    assert counts == [(1, 1, 0), (1, 1, 0), (0, 0, 2)]


async def test_with_failed_runs(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    # Create a failed run
    test_client.mock_openai_call(
        status_code=400,
        json=fixtures_json("openai/content_moderation.json"),
        model=Model.GPT_4O_MINI_2024_07_18,
    )
    with pytest.raises(HTTPStatusError) as e:
        await test_client.run_task_v1(task, model=Model.GPT_4O_MINI_2024_07_18)
    assert e.value.response.status_code == 400
    error_json = e.value.response.json()
    assert error_json["error"]["code"] == "content_moderation"

    failed_run = await test_client.fetch_run(task, run_id=error_json["id"])
    assert failed_run["group"]["iteration"] == 1, "sanity"

    # Create a new run that succeeds
    test_client.mock_openai_call(model=Model.GPT_4O_2024_11_20, is_reusable=True)
    run1 = await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20)
    successful_run = await test_client.fetch_run(task, run_id=run1["id"])
    assert successful_run["group"]["iteration"] == 2, "sanity"

    # Now let's add a review
    await test_client.user_review(task, successful_run, "positive")

    # And add both versions to the benchmark, one at a time like the client does it
    await test_client.patch(
        task_schema_url(task, "reviews/benchmark"),
        json={"add_versions": [1]},
    )

    await test_client.patch(
        task_schema_url(task, "reviews/benchmark"),
        json={"add_versions": [2]},
    )

    await test_client.wait_for_completed_tasks()

    # Get the benchmark
    benchmark = await test_client.get(task_schema_url(task, "reviews/benchmark"))
    assert len(benchmark["results"]) == 2
    assert benchmark["results"][0]["iteration"] == 1
    assert benchmark["results"][0]["positive_review_count"] == 0
    assert benchmark["results"][0]["negative_review_count"] == 1
    assert benchmark["results"][1]["iteration"] == 2
    assert benchmark["results"][1]["positive_review_count"] == 1
    assert benchmark["results"][1]["negative_review_count"] == 0

    # Now fetch all runs, we should only have 2 runs
    runs = await test_client.post(task_url_v1(task, "runs/search"), json={})
    assert len(runs["items"]) == 2

    # Just to make sure, add and remove the version that failed in quick succession
    await test_client.patch(
        task_schema_url(task, "reviews/benchmark"),
        json={"remove_versions": [1]},
    )
    await test_client.patch(
        task_schema_url(task, "reviews/benchmark"),
        json={"add_versions": [1]},
    )

    await test_client.wait_for_completed_tasks()

    benchmark = await test_client.get(task_schema_url(task, "reviews/benchmark"))
    assert len(benchmark["results"]) == 2

    sorted_results = sorted(benchmark["results"], key=lambda x: x["iteration"])
    assert sorted_results[0]["positive_review_count"] == 0
    assert sorted_results[0]["negative_review_count"] == 1
    assert sorted_results[1]["positive_review_count"] == 1
    assert sorted_results[1]["negative_review_count"] == 0

    runs = await test_client.post(task_url_v1(task, "runs/search"), json={})
    assert len(runs["items"]) == 2
