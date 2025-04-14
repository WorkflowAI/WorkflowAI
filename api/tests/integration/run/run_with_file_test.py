from tests.integration.common import (
    IntegrationTestClient,
)


async def test_run_with_file_url(test_client: IntegrationTestClient):
    task = await test_client.create_task(
        input_schema={
            "type": "object",
            "properties": {
                "image": {
                    "$ref": "#/$defs/Image",
                },
            },
            "required": ["image"],
        },
    )

    assert "url" in task["input_schema"]["json_schema"]["$defs"]["Image"]["properties"]

    test_client.mock_openai_call()

    test_client.httpx_mock.add_response(
        url="https://bla.com/image.png",
        method="GET",
        status_code=200,
        content=b"fhefheziuhfzeuihfeuizhfuezh",
    )

    task_run = await test_client.run_task_v1(
        task=task,
        task_input={"image": {"url": "https://bla.com/image.png"}},
    )

    await test_client.wait_for_completed_tasks()
    fetched_task_run = await test_client.fetch_run(task, run_id=task_run["id"])
    assert fetched_task_run["task_input_preview"] == "image: [[img:https://bla.com/image.png]]"

    assert fetched_task_run["task_input"] == {
        "image": {
            "url": "https://bla.com/image.png",
            "content_type": "image/png",
            "storage_url": test_client.storage_url(
                task,
                "23439dd28abda73e46eb007534630bebe9cd930710f22171af0d62fa75187bb8.png",
            ),
        },
    }


async def test_run_previews_list_images(test_client: IntegrationTestClient):
    task = await test_client.create_task(
        input_schema={
            "type": "object",
            "properties": {
                "images": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/Image"},
                },
            },
        },
    )
    test_client.httpx_mock.add_response(
        url="https://bla.com/image.png",
        method="GET",
        status_code=200,
        content=b"fhefheziuhfzeuihfeuizhfuezh",
    )
    test_client.mock_openai_call()

    task_run = await test_client.run_task_v1(
        task=task,
        task_input={
            "images": [
                {"url": "https://bla.com/image.png"},
                {"url": "https://bla.com/image.png"},
                {"url": "https://bla.com/image.png"},
            ],
        },
    )

    await test_client.wait_for_completed_tasks()
    fetched_task_run = await test_client.fetch_run(task, run_id=task_run["id"])
    assert (
        fetched_task_run["task_input_preview"]
        == "images: [[[img:https://bla.com/image.png]], [[img:https://bla.com/image.png]], [[img:https://bla.com/image.png]]]"
    )


async def test_run_previews_with_data_url(test_client: IntegrationTestClient):
    task = await test_client.create_task(
        input_schema={
            "type": "object",
            "properties": {"image": {"$ref": "#/$defs/Image"}},
        },
    )

    test_client.mock_openai_call()

    task_run = await test_client.run_task_v1(
        task=task,
        task_input={
            "image": {
                "url": "data:image/png;base64,ZmhlZmhleml1aGZ6ZXVpaGZldWl6aGZ1ZXpo",
            },
        },
    )

    await test_client.wait_for_completed_tasks()
    storage_url = test_client.storage_url(
        task,
        "23439dd28abda73e46eb007534630bebe9cd930710f22171af0d62fa75187bb8.png",
    )
    expected_preview = f"image: [[img:{storage_url}]]"

    fetched_task_run = await test_client.fetch_run(task, run_id=task_run["id"])
    assert fetched_task_run["task_input_preview"] == expected_preview

    run1 = await test_client.run_task_v1(
        task=task,
        task_input={
            "image": {
                "content_type": "image/png",
                "data": "ZmhlZmhleml1aGZ6ZXVpaGZldWl6aGZ1ZXpo",
            },
        },
    )

    await test_client.wait_for_completed_tasks()
    fetched_task_run1 = await test_client.fetch_run(task, run_id=run1["id"])
    assert fetched_task_run1["task_input_preview"] == expected_preview


async def test_run_preview_with_downloaded_file(test_client: IntegrationTestClient):
    task = await test_client.create_task(
        input_schema={
            "type": "object",
            "properties": {"image": {"$ref": "#/$defs/Image"}},
        },
    )
    # When the content type is not guessable, we have to download the file
    test_client.mock_vertex_call()

    test_client.httpx_mock.add_response(
        url="https://bla.com/image",
        method="GET",
        status_code=200,
        # Prefix for a jpeg file
        content=b"\xff\xd8\xffjfiezjfeziojfeiozjfezio",
    )

    task_run = await test_client.run_task_v1(
        task=task,
        task_input={
            "image": {
                "url": "https://bla.com/image",
            },
        },
        model=test_client.DEFAULT_VERTEX_MODEL,
    )

    await test_client.wait_for_completed_tasks()
    fetched_task_run = await test_client.fetch_run(task, run_id=task_run["id"])
    assert fetched_task_run["task_input_preview"] == "image: [[img:https://bla.com/image]]"
