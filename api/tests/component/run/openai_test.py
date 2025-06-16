import pytest

from core.domain.models import Model
from core.domain.models.utils import get_model_data
from tests.component.common import IntegrationTestClient, openai_endpoint
from tests.utils import fixture_bytes, request_json_body


async def test_unmarked_image_url(test_client: IntegrationTestClient):
    """Test that the OpenAI provider does not download the image before sending when:
    - the image url does not have an extension
    - there is no content type
    - but the schema refers to an image via a named def

    We had an issue where:
    - since we cannot "guess" the content type of a URL without extension,
    - and since OpenAI requires sending files other than images as base64,
    we were downloading the image before sending it to OpenAI.
    """
    # Create a task with a $ref: "#/$defs/Image" as opposed to #/$defs/File with a format
    task = await test_client.create_task(
        input_schema={
            "type": "object",
            "properties": {
                "image": {
                    "$ref": "#/$defs/Image",
                },
            },
        },
    )

    # Mock a response for the giphy image and the openai call
    # Because the storage also happens in the background we can't really mock after we run the task
    # since there is no way to control when the call will happen
    # We will check the payload send to OpenAI instead
    test_client.httpx_mock.add_response(
        url="https://media3.giphy.com/media/giphy",
        status_code=200,
        content=b"GIF87ahello",  # signature for gif
    )
    test_client.mock_openai_call()

    # Input with no extension and no content type
    task_input = {
        "image": {
            "url": "https://media3.giphy.com/media/giphy",
        },
    }
    res = await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20, task_input=task_input)
    assert res

    # Checking that we did download the image at some point
    assert test_client.httpx_mock.get_request(url="https://media3.giphy.com/media/giphy") is not None

    # Checking that the payload sent to OpenAI does not contain the image as base64
    call = test_client.httpx_mock.get_request(url=openai_endpoint())
    assert call
    body = request_json_body(call)
    assert len(body["messages"]) == 2
    assert body["messages"][1]["content"][-1] == {
        "image_url": {
            "url": "https://media3.giphy.com/media/giphy",
        },
        "type": "image_url",
    }


@pytest.mark.poppler
async def test_pdf_conversion(test_client: IntegrationTestClient):
    """Check that we correctly convert PDFs to images when the model supports it"""

    model_data = get_model_data(Model.GPT_4O_2024_11_20)
    assert model_data.supports_input_image, "sanity check"
    assert not model_data.supports_input_pdf, "sanity check"

    task = await test_client.create_task(
        input_schema={
            "$defs": {"File": {}},
            "type": "object",
            "properties": {"pdf": {"$ref": "#/$defs/File"}},
        },
    )

    test_client.mock_openai_call()
    test_client.httpx_mock.add_response(
        url="http://hello.com/world.pdf",
        status_code=200,
        content=fixture_bytes("files/MSFT_SEC.pdf"),
        is_reusable=True,
    )

    task_input = {
        "pdf": {
            "url": "http://hello.com/world.pdf",
        },
    }
    res = await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20, task_input=task_input)
    assert res

    call = test_client.httpx_mock.get_request(url=openai_endpoint())
    assert call
    body = request_json_body(call)
    assert len(body["messages"]) == 2
    assert len(body["messages"][-1]["content"]) == 3

    assert body["messages"][-1]["content"][1]["type"] == "image_url"
    assert body["messages"][-1]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert body["messages"][-1]["content"][2]["type"] == "image_url"
    assert body["messages"][-1]["content"][2]["image_url"]["url"].startswith("data:image/jpeg;base64,")
