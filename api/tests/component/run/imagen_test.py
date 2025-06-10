import base64
import json
from unittest import mock

from tests.component.common import IntegrationTestClient


async def test_imagen_provider(test_client: IntegrationTestClient):
    agent = await test_client.create_agent_v1(
        input_schema={
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                },
                "shape": {"type": "string"},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "image": {"$ref": "#/$defs/Image"},
            },
        },
    )

    _imagen_url = "https://us-central1-aiplatform.googleapis.com/v1/projects/worfklowai/locations/us-central1/publishers/google/models/imagen-3.0-generate-002:predict"
    test_client.httpx_mock.add_response(
        url=_imagen_url,
        json={
            "predictions": [
                {
                    "mimeType": "image/png",
                    "bytesBase64Encoded": base64.b64encode(b"hello").decode(),
                },
            ],
        },
    )

    run = await test_client.run_task_v1(
        task=agent,
        task_input={"description": "A wolf", "shape": "landscape"},
        model="imagen-3.0-generate-002",
    )
    assert run

    assert run["task_output"]["image"]["data"] == "aGVsbG8="
    assert run["cost_usd"] == 0.03

    requests = test_client.httpx_mock.get_requests(url=_imagen_url)
    assert requests and len(requests) == 1
    request = requests[0]
    assert json.loads(request.content) == {
        "instances": [
            {"prompt": mock.ANY},
        ],
        "parameters": {
            "aspectRatio": "16:9",
            "sampleCount": 1,
        },
    }
