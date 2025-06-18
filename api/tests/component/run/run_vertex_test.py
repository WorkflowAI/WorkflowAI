import os
from unittest.mock import Mock, patch

import pytest
from httpx import HTTPStatusError

from core.domain.models import Model
from core.domain.models.utils import get_model_data
from core.providers.google.vertex_base_config import VertexBaseConfig
from tests.component.common import (
    IntegrationTestClient,
    mock_gemini_call,
    vertex_url,
)
from tests.utils import request_json_body


@patch.dict(os.environ, {"GOOGLE_VERTEX_AI_LOCATION": "us-central1,us-east4,us-west1"})
@patch(
    "core.providers.google.vertex_base_config.VertexBaseConfig.all_available_regions",
    return_value={"us-central1", "us-east4", "us-west1"},
)
async def test_vertex_region_switch(
    mock_available_regions: Mock,
    test_client: IntegrationTestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    task = await test_client.create_task()
    regions = ["us-central1", "us-west1", "us-east4"]

    # Now prepare all providers
    region_iter = iter(regions)
    monkeypatch.setattr(VertexBaseConfig, "_get_random_region", lambda self, choices: next(region_iter))  # type: ignore

    # Mock only one failed region at a time
    test_client.mock_vertex_call(model=Model.GEMINI_1_5_PRO_002, status_code=429, regions=["us-central1", "us-west1"])
    test_client.mock_vertex_call(model=Model.GEMINI_1_5_PRO_002, status_code=200, regions=["us-east4"])
    # provider = GoogleProvider()
    # assert provider.config.vertex_location == ["us-central1", "us-east4", "us-west1"]
    run = await test_client.run_task_v1(task, model=Model.GEMINI_1_5_PRO_002)
    assert run
    assert sorted(run["metadata"]["workflowai.vertex_api_excluded_regions"].split(",")) == ["us-central1", "us-west1"]
    assert run["metadata"]["workflowai.vertex_api_region"] == "us-east4"


async def test_vertex_global(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    # Mock only one failed region at a time
    test_client.mock_vertex_call(
        model=Model.GEMINI_2_5_FLASH,
        url=vertex_url(Model.GEMINI_2_5_FLASH, region="global"),
    )

    run = await test_client.run_task_v1(task, model=Model.GEMINI_2_5_FLASH)
    assert run


async def test_vertex_invalid_response(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    # Mock only one failed region at a time
    test_client.mock_vertex_call(
        model=Model.GEMINI_2_5_FLASH,
        url=vertex_url(Model.GEMINI_2_5_FLASH, region="global"),
        # parts have a missing name so the validation will fail
        parts=[{"functionCall": {"args": {"url": "https://pastacaponi.it/"}}}],
    )
    # So we will fallback to gemin
    mock_gemini_call(test_client.httpx_mock, model=Model.GEMINI_2_5_FLASH)

    # assert provider.config.vertex_location == ["us-central1", "us-east4", "us-west1"]
    run = await test_client.run_task_v1(task, model=Model.GEMINI_2_5_FLASH)
    assert run


async def test_vertex_prompt_feedback(test_client: IntegrationTestClient):
    """Sometimes vertex returns a 200 with prompt feedback with a usage. This is a
    content moderation error that should incur cost"""
    task = await test_client.create_task()

    test_client.mock_vertex_call(
        model=Model.GEMINI_1_5_PRO_002,
        status_code=200,
        json={
            "modelVersion": "gemini-2.0-flash-thinking-exp-01-21",
            "promptFeedback": {
                "blockReason": "OTHER",
            },
            "usageMetadata": {
                "promptTokenCount": 100,
                "totalTokenCount": 200,
            },
        },
    )

    with pytest.raises(HTTPStatusError) as e:
        await test_client.run_task_v1(task, model=Model.GEMINI_1_5_PRO_002)
    assert e.value.response.status_code == 400

    res = e.value.response.json()
    assert res["error"]["code"] == "content_moderation"

    # Fetch the run and check that it has a cost
    fetched = await test_client.fetch_run(task, run_id=res["id"])
    assert fetched["cost_usd"] > 0


async def test_pdf_no_conversion(test_client: IntegrationTestClient):
    """Check that we do not convert PDFs to images when the model does supports pdfs"""

    model_data = get_model_data(Model.GEMINI_2_0_FLASH_001)
    assert model_data.supports_input_image, "sanity check"
    assert model_data.supports_input_pdf, "sanity check"

    task = await test_client.create_task(
        input_schema={
            "$defs": {"File": {}},
            "type": "object",
            "properties": {"pdf": {"$ref": "#/$defs/File"}},
        },
    )

    test_client.mock_vertex_call(
        url=vertex_url(Model.GEMINI_2_0_FLASH_001, region="global"),
    )
    test_client.httpx_mock.add_response(
        url="https://hello.com/world.pdf",
        status_code=200,
        content=b"Hello world pdf",
    )

    task_input = {
        "pdf": {
            "url": "https://hello.com/world.pdf",
        },
    }
    res = await test_client.run_task_v1(task, model=Model.GEMINI_2_0_FLASH_001, task_input=task_input)
    assert res

    call = test_client.httpx_mock.get_request(url=vertex_url(Model.GEMINI_2_0_FLASH_001, region="global"))
    assert call
    body = request_json_body(call)
    assert body["contents"] == [
        {
            "parts": [
                {
                    "text": "Input is a single file",
                },
                {
                    "fileData": {
                        "fileUri": "https://hello.com/world.pdf",
                        "mimeType": "application/pdf",
                    },
                },
            ],
            "role": "user",
        },
    ]
