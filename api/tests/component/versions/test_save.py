import asyncio

from core.domain.models import Model
from tests.component.common import IntegrationTestClient, result_or_raise, task_url_v1
from tests.utils import request_json_body


async def test_save_version(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    test_client.mock_detect_chain_of_thought(False)

    # Create a first version
    v1 = await test_client.create_version(
        task=task,
        version_properties={
            "model": Model.GPT_4O_2024_11_20,
            "instructions": "You are a helpful assistant.",
        },
    )
    await test_client.wait_for_completed_tasks()
    v1 = await test_client.fetch_version(task, v1["id"])
    # Version is autosaved since it's the first version
    # TODO[iteration]: Remove this once we no longer need to support iterations
    assert v1["iteration"] == 1
    assert v1["semver"] == [1, 1]

    # Create a second version, with a different model
    v2 = await test_client.create_version(
        task=task,
        version_properties={
            "model": Model.GEMINI_1_5_PRO_002,
            "instructions": "You are a helpful assistant.",
        },
    )
    await test_client.wait_for_completed_tasks()
    v2 = await test_client.fetch_version(task, v2["id"])
    assert "semver" not in v2

    # Now create a third version, with different instructions
    await test_client.create_version(
        task=task,
        version_properties={"model": Model.GPT_4O_2024_11_20, "instructions": "You are not a helpful assistant."},
    )

    # Create a 4th version with different instructions
    v4 = await test_client.create_version(
        task=task,
        version_properties={"model": Model.GPT_4O_2024_11_20, "instructions": "You are not a helpful assistant at all"},
    )

    await test_client.wait_for_completed_tasks()

    def _get_changelog_request():
        return test_client.httpx_mock.get_request(
            url=test_client.internal_task_url("generate-changelog-from-properties"),
        )

    # Still no changelog since we have not saved anything
    assert _get_changelog_request() is None

    async def _list_versions():
        return result_or_raise(await test_client.int_api_client.get(task_url_v1(task, "versions")))["items"]

    async def _save_version(hash: str):
        result_or_raise(await test_client.int_api_client.post(task_url_v1(task, f"versions/{hash}/save")))

    # Now we save the first version
    versions = await _list_versions()
    assert len(versions) == 1
    assert versions[0]["major"] == 1
    assert versions[0]["minors"][0]["id"] == v1["id"]
    assert versions[0]["minors"][0]["minor"] == 1

    # And save the second version
    await _save_version(v2["id"])
    versions = await _list_versions()
    assert len(versions) == 1
    assert versions[0]["major"] == 1
    assert len(versions[0]["minors"]) == 2
    assert versions[0]["minors"][0]["id"] == v1["id"]
    assert versions[0]["minors"][0]["minor"] == 1
    assert versions[0]["minors"][1]["id"] == v2["id"]
    assert versions[0]["minors"][1]["minor"] == 2

    await test_client.wait_for_completed_tasks()

    # We should still not have a changelog
    assert _get_changelog_request() is None

    test_client.mock_internal_task("generate-changelog-from-properties", {"changes": ["na", "na", "nere"]})

    # Finally we save the 4th version
    await _save_version(v4["id"])
    versions = await _list_versions()
    assert len(versions) == 2
    assert versions[0]["major"] == 1
    assert versions[1]["major"] == 2

    await test_client.wait_for_completed_tasks()

    # At this point we should have generated a changelog
    req = _get_changelog_request()
    assert req
    body = request_json_body(req)
    assert body["task_input"]["old_task_group"]["properties"]["instructions"] == "You are a helpful assistant."
    assert (
        body["task_input"]["new_task_group"]["properties"]["instructions"] == "You are not a helpful assistant at all"
    )

    versions = await _list_versions()
    assert versions[1]["previous_version"]["major"] == 1
    assert versions[1]["previous_version"]["changelog"] == ["na", "na", "nere"]

    # I can also fetch the version using the id
    version = result_or_raise(await test_client.int_api_client.get(task_url_v1(task, f"versions/{v4['id']}")))
    assert version["id"] == v4["id"]
    assert version["semver"] == [2, 1]
    assert "created_at" in version

    # And I can fetch the version using the semver
    version1 = result_or_raise(await test_client.int_api_client.get(task_url_v1(task, "versions/2.1")))
    assert version1 == version


async def test_update_version_notes_and_favorites(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    test_client.mock_detect_chain_of_thought(False)

    # Create a first version
    v1 = await test_client.create_version(
        task=task,
        version_properties={
            "model": Model.GPT_4O_2024_11_20,
            "instructions": "You are a helpful assistant.",
        },
        # Forcing not to save for the test
        save=False,
        autowait=True,
    )

    # I can add notes even if the version is not saved
    await test_client.int_api_client.patch(task_url_v1(task, f"versions/{v1['id']}/notes"), json={"notes": "test"})

    # the notes should be returned when I fetch by ID
    fetched = await test_client.fetch_version(task, v1["id"])
    assert fetched["notes"] == "test"
    assert "semver" not in fetched

    # I can also add favorites
    await test_client.int_api_client.post(
        task_url_v1(task, f"versions/{v1['id']}/favorite"),
    )
    fetched = await test_client.fetch_version(task, v1["id"])
    assert fetched["is_favorite"]

    # Then if I save the version it is returned in the list with the favorites and notes
    result_or_raise(await test_client.int_api_client.post(task_url_v1(task, f"versions/{v1['id']}/save")))
    versions = result_or_raise(await test_client.int_api_client.get(task_url_v1(task, "versions")))["items"]
    assert versions and len(versions) == 1
    assert len(versions[0]["minors"]) == 1
    assert versions[0]["minors"][0]["id"] == v1["id"]
    assert versions[0]["minors"][0]["is_favorite"]
    assert versions[0]["minors"][0]["notes"] == "test"

    fetched = await test_client.fetch_version(task, v1["id"])
    assert fetched["semver"] == [1, 1]


async def test_with_direct_run_from_api_key(test_client: IntegrationTestClient):
    # Create an API key
    response = await test_client.post(
        "/chiefofstaff.ai/api/keys",
        json={"name": "test key"},
    )
    key = response["key"]
    test_client.authenticate(key)

    task = await test_client.create_task()

    test_client.mock_openai_call()

    run = await test_client.run_task_v1(task)
    fetched_run = await test_client.fetch_run(task, run_id=run["id"])

    grp_id = fetched_run["group"]["id"]
    # Now save the version
    await test_client.post(task_url_v1(task, f"versions/{grp_id}/save"))

    # Now fetch the version
    version = await test_client.get(task_url_v1(task, f"versions/{grp_id}"))
    assert version["semver"] == [1, 1]
    # Versions was created by the API key so for now there is no created_by
    assert not version.get("created_by")

    # I can also list versions
    versions = await test_client.get(task_url_v1(task, "versions"))
    assert versions["items"] and len(versions["items"]) == 1


async def test_autosave_version(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    # Create a first version
    v1 = await test_client.create_version(
        task=task,
        version_properties={"model": Model.GPT_4O_2024_11_20, "instructions": "You are a helpful assistant."},
        mock_chain_of_thought=False,
        autowait=True,
    )

    # The version is saved automatically since it is the first version
    v1 = await test_client.fetch_version(task, v1["id"])
    assert v1["semver"] == [1, 1]

    v2 = await test_client.create_version(
        task=task,
        version_properties={"model": Model.GPT_4O_2024_11_20, "instructions": "You are a helpful assistant1"},
    )

    assert "semver" not in v2

    # Create a new schema
    task1 = await test_client.create_task(input_schema={"properties": {"another_prop": {"type": "string"}}})
    assert task1["task_schema_id"] == 2, "sanity"

    await asyncio.gather(
        test_client.create_version(
            task=task1,
            version_properties={"model": Model.GPT_4O_2024_11_20, "instructions": "You are a helpful assistant"},
        ),
        test_client.create_version(
            task=task1,
            version_properties={"model": Model.GPT_4O_2024_11_20, "instructions": "You are a helpful assistant2"},
        ),
    )
    await test_client.wait_for_completed_tasks()

    versions = await test_client.get(task_url_v1(task1, "versions"))
    assert len(versions["items"]) == 2
    assert versions["items"][0]["minors"][0]["id"] == v1["id"]
    assert len(versions["items"][0]["minors"]) == 1


async def test_autosave_version_when_ran_from_sdk(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    test_client.mock_openai_call(model=Model.GPT_4O_2024_11_20)

    await test_client.run_task_v1(task, headers={"x-workflowai-source": "sdk"}, model=Model.GPT_4O_2024_11_20)

    await test_client.wait_for_completed_tasks()

    versions = await test_client.get(task_url_v1(task, "versions"))
    # This version was saved since it was the first version
    assert len(versions["items"]) == 1
    assert len(versions["items"][0]["minors"]) == 1

    test_client.mock_openai_call(model=Model.GPT_4O_2024_11_20)
    await test_client.run_task_v1(
        task,
        version={"model": Model.GPT_4O_2024_11_20, "instructions": "bla"},
        headers={"x-workflowai-source": "sdk"},
    )
    await test_client.wait_for_completed_tasks()

    versions = await test_client.get(task_url_v1(task, "versions"))
    assert len(versions["items"]) == 2
    assert all(len(v["minors"]) == 1 for v in versions["items"])

    # Now if we run without the source it should not be autosaved
    test_client.mock_openai_call(model=Model.GPT_4O_2024_11_20)
    await test_client.run_task_v1(
        task,
        version={"model": Model.GPT_4O_2024_11_20, "instructions": "bliblu"},
    )
    await test_client.wait_for_completed_tasks()

    versions = await test_client.get(task_url_v1(task, "versions"))
    assert len(versions["items"]) == 2
    assert all(len(v["minors"]) == 1 for v in versions["items"])
