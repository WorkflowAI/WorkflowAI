import pytest

from core.domain.models import Model
from tests.component.common import IntegrationTestClient, task_schema_url_v1


@pytest.mark.parametrize("is_authenticated", [True, False])
async def test_list_models(test_client: IntegrationTestClient, is_authenticated: bool):
    if not is_authenticated:
        pytest.mark.unauthenticated(test_client.int_api_client)

    create_task = await test_client.create_task()

    response = await test_client.int_api_client.post(task_schema_url_v1(create_task, "models"))
    # Check if the request was successful
    assert response.status_code == 200

    data = response.json()

    # Check if the response contains a 'models' key
    assert "items" in data

    # Check if the models list is not empty
    assert len(data["items"]) > 0

    # Check if each model has the expected structure
    for model in data["items"]:
        assert "id" in model
        assert "name" in model
        assert "modes" in model
        # Check that providers is not empty
        assert model.get("providers")


@pytest.mark.parametrize("is_authenticated", [True, False])
async def test_list_models_get(test_client: IntegrationTestClient, is_authenticated: bool):
    if not is_authenticated:
        pytest.mark.unauthenticated(test_client.int_api_client)

    create_task = await test_client.create_task()

    response = await test_client.int_api_client.get(task_schema_url_v1(create_task, "models"))
    # Check if the request was successful
    assert response.status_code == 200

    data = response.json()

    # Check if the response contains a 'models' key
    assert "items" in data

    # Check if the models list is not empty
    assert len(data["items"]) > 0

    # Check if each model has the expected structure
    for model in data["items"]:
        assert "id" in model
        assert "name" in model
        assert "modes" in model
        # Check that providers is not empty
        assert model.get("providers")


async def test_list_models_with_is_default_true(test_client: IntegrationTestClient):
    create_task = await test_client.create_task()

    response = await test_client.int_api_client.post(task_schema_url_v1(create_task, "models"))
    assert response.status_code == 200

    data = response.json()
    default_models = [model for model in data["items"] if model["is_default"]]
    assert len(default_models) >= 3
    # Sanity check for test belows
    models_by_id = {model["id"]: model for model in data["items"]}
    gpt_4o = models_by_id["gpt-4o-latest"]
    assert not gpt_4o.get("is_not_supported_reason")


async def test_list_models_with_and_without_tools(test_client: IntegrationTestClient):
    """
    The goal of this tests is to check that when we have instructions with tools, the 'is_not_supported_reason'
    is correctly applied.
    """

    model_not_supporting_tools = Model.LLAMA_3_3_70B.value
    model_supporting_tools = Model.GEMINI_1_5_FLASH_002.value

    create_task = await test_client.create_task()

    # Test with tools in instructions, a 'is_not_supported_reason' is expected for the non-supporting model
    response_with_tools = await test_client.int_api_client.post(
        json={"instructions": "Use @search-google"},
        url=task_schema_url_v1(task=create_task, path="models"),
    )
    assert response_with_tools.status_code == 200
    data = response_with_tools.json()
    item_non_supporting = [item for item in data["items"] if item["id"] == model_not_supporting_tools][0]
    assert "does not support tool calling" in item_non_supporting["is_not_supported_reason"]
    item_supporting = [item for item in data["items"] if item["id"] == model_supporting_tools][0]
    assert "is_not_supported_reason" not in item_supporting

    # Test without instructions, no 'is_not_supported_reason' is expected for neither model
    response_wthout_tools = await test_client.int_api_client.post(
        url=task_schema_url_v1(task=create_task, path="models"),
    )
    assert response_wthout_tools.status_code == 200
    data = response_wthout_tools.json()
    item_non_supporting = [item for item in data["items"] if item["id"] == model_not_supporting_tools][0]
    assert "is_not_supported_reason" not in item_non_supporting
    item_supporting = [item for item in data["items"] if item["id"] == model_supporting_tools][0]
    assert "is_not_supported_reason" not in item_supporting

    # Test without tools in instructions, no 'is_not_supported_reason' is expected for neither model
    response_wthout_tools = await test_client.int_api_client.post(
        json={"instructions": "hello"},
        url=task_schema_url_v1(task=create_task, path="models"),
    )
    assert response_wthout_tools.status_code == 200
    data = response_wthout_tools.json()
    item_non_supporting = [item for item in data["items"] if item["id"] == model_not_supporting_tools][0]
    assert "is_not_supported_reason" not in item_non_supporting
    item_supporting = [item for item in data["items"] if item["id"] == model_supporting_tools][0]
    assert "is_not_supported_reason" not in item_supporting

    # Test without tools in instructions but requires_tools is True, a 'is_not_supported_reason' is expected for the non-supporting model
    response_wthout_tools = await test_client.int_api_client.post(
        json={"instructions": "hello", "requires_tools": True},
        url=task_schema_url_v1(task=create_task, path="models"),
    )
    assert response_wthout_tools.status_code == 200
    data = response_wthout_tools.json()
    item_non_supporting = [item for item in data["items"] if item["id"] == model_not_supporting_tools][0]
    assert "is_not_supported_reason" in item_non_supporting
    item_supporting = [item for item in data["items"] if item["id"] == model_supporting_tools][0]
    assert "is_not_supported_reason" not in item_supporting

    # Test with both tools in instructions and requires_tools is True, a 'is_not_supported_reason' is expected for the non-supporting model
    response_wthout_tools = await test_client.int_api_client.post(
        json={"instructions": "Use @search-google", "requires_tools": True},
        url=task_schema_url_v1(task=create_task, path="models"),
    )
    assert response_wthout_tools.status_code == 200
    data = response_wthout_tools.json()
    item_non_supporting = [item for item in data["items"] if item["id"] == model_not_supporting_tools][0]
    assert "is_not_supported_reason" in item_non_supporting
    item_supporting = [item for item in data["items"] if item["id"] == model_supporting_tools][0]
    assert "is_not_supported_reason" not in item_supporting

    # Test with no instruction and requires_tools is True, a 'is_not_supported_reason' is expected for the non-supporting model
    response_wthout_tools = await test_client.int_api_client.post(
        json={"requires_tools": True},
        url=task_schema_url_v1(task=create_task, path="models"),
    )
    assert response_wthout_tools.status_code == 200
    data = response_wthout_tools.json()
    item_non_supporting = [item for item in data["items"] if item["id"] == model_not_supporting_tools][0]
    assert "is_not_supported_reason" in item_non_supporting
    item_supporting = [item for item in data["items"] if item["id"] == model_supporting_tools][0]
    assert "is_not_supported_reason" not in item_supporting


async def test_list_models_audio(test_client: IntegrationTestClient):
    # Create a task while referencing an Audio ref
    create_task = await test_client.create_task(
        input_schema={
            "type": "object",
            "properties": {"audio": {"$ref": "#/$defs/Audio"}},
        },
    )

    response = await test_client.int_api_client.get(task_schema_url_v1(create_task, "models"))
    assert response.status_code == 200

    data = response.json()
    assert "items" in data
    models_by_id = {model["id"]: model for model in data["items"]}

    # 4o does not support audio
    gpt_4o = models_by_id["gpt-4o-latest"]
    assert gpt_4o["is_not_supported_reason"]


async def test_list_models_pdfs(test_client: IntegrationTestClient):
    # Create a task while referencing a PDF ref
    create_task = await test_client.create_task(
        input_schema={
            "type": "object",
            "properties": {"pdf": {"$ref": "#/$defs/PDF"}},
        },
    )

    response = await test_client.int_api_client.get(task_schema_url_v1(create_task, "models"))
    assert response.status_code == 200

    data = response.json()
    models_by_id = {model["id"]: model for model in data["items"]}

    # gpt4o does not support pdfs directly but since it supports images it can handle pdfs
    assert not models_by_id["gpt-4o-latest"].get("is_not_supported_reason")
    # # llama3-70b-8192 does not support pdfs or images, but since its available through
    # TODO: add another test for a fireworks model
    # # fireworks with document inlining it is not marked as unsupported
    # assert not models_by_id["llama3-70b-8192"].get("is_not_supported_reason")
