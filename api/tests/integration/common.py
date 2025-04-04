import asyncio
import json
import os
import re
import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from json import dumps as json_dumps
from typing import Any, Literal

from freezegun import freeze_time
from httpx import AsyncClient, HTTPStatusError, Request, Response
from pytest_httpx import HTTPXMock, IteratorStream
from taskiq import InMemoryBroker

from core.domain.models import Model
from core.domain.types import CacheUsage
from core.utils.background import wait_for_background_tasks
from tests.utils import fixtures_json, request_json_body

# 03832ff71a03e47e372479593879ad2e is the input hash of `{"name": "John", "age": 30}`
DEFAULT_INPUT_HASH = "03832ff71a03e47e372479593879ad2e"
INT_TEST_TENANT = "chiefofstaff.ai"

LOOPS_TRANSACTIONAL_URL = "https://app.loops.so/api/v1/transactional"
CLERK_BASE_URL = "https://api.clerk.com/v1"


async def create_task(
    int_api_client: AsyncClient,
    patched_broker: InMemoryBroker,
    httpx_mock: HTTPXMock,
    tenant: str = "_",
    name: str = "Greet",
    input_schema: dict[str, Any] | None = None,
    output_schema: dict[str, Any] | None = None,
    creation_date: datetime | None = None,
) -> dict[str, Any]:
    async def _create_task():
        return await int_api_client.post(
            f"/{tenant}/agents",
            json={
                "name": name,
                "input_schema": input_schema
                or {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": "integer"},
                    },
                    "required": ["name", "age"],
                },
                "output_schema": output_schema
                or {
                    "type": "object",
                    "properties": {
                        "greeting": {"type": "string"},
                    },
                    "required": ["greeting"],
                },
                "skip_generation": True,
                "create_first_iteration": False,
            },
        )

    if creation_date:
        if not creation_date.tzinfo:
            # Making sure we have a timezone
            creation_date = creation_date.replace(tzinfo=timezone.utc)
        with freeze_time(creation_date):
            res = await _create_task()
    else:
        res = await _create_task()

    out = result_or_raise(res)

    # Wait for all generated events to be sent to the broker
    await wait_for_completed_tasks(patched_broker)
    amplitude_events = await get_amplitude_requests(httpx_mock)

    assert any(event["events"][0]["event_type"] == "org.created.task" for event in amplitude_events)

    # Reset the mock to clear any remaining requests
    httpx_mock._requests.clear()  # pyright: ignore [reportPrivateUsage]

    return out


async def create_task_without_required_fields(
    int_api_client: AsyncClient,
    patched_broker: InMemoryBroker,
    httpx_mock: HTTPXMock,
    tenant: str = "_",
    name: str = "Greet",
    input_schema: dict[str, Any] | None = None,
    output_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return await create_task(
        int_api_client,
        patched_broker,
        httpx_mock,
        tenant,
        name,
        input_schema=input_schema
        or {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
        },
        output_schema=output_schema
        or {
            "type": "object",
            "properties": {
                "greeting": {"type": "string"},
            },
        },
    )


# DEPRECATED tun task endpoint
async def run_task(
    int_api_client: AsyncClient,
    task_id: str,
    task_schema_id: int,
    group: dict[str, Any] | None = None,
    model: str = "gpt-4o-2024-11-20",
    tenant: str | None = None,
    task_input: dict[str, Any] | None = None,
    labels: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    headers: dict[str, Any] | None = None,
    use_cache: CacheUsage = "auto",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "group": group or {"properties": {"model": model}},
        "task_input": task_input or {"name": "John", "age": 30},
        "use_cache": use_cache,
    }
    if labels is not None:
        payload["labels"] = labels
    if metadata is not None:
        payload["metadata"] = metadata

    # Keep using the /tasks/ endpoint since it's what is used in prod
    # By people
    path = f"/tasks/{task_id}/schemas/{task_schema_id}/run"
    if tenant is not None:
        path = f"/{tenant}{path}"

    res = await int_api_client.post(
        path,
        json=payload,
        headers=headers,
    )
    return result_or_raise(res)


async def create_version(
    int_api_client: AsyncClient,
    task_id: str,
    task_schema_id: int,
    version_properties: dict[str, Any],
    tenant: str = "_",
    save: bool | None = None,
) -> dict[str, Any]:
    res = await int_api_client.post(
        f"/v1/{tenant}/agents/{task_id}/schemas/{task_schema_id}/versions",
        json={"properties": version_properties, "save": save},
    )
    return result_or_raise(res)


async def run_task_v1(
    int_api_client: AsyncClient,
    task_id: str,
    task_schema_id: int,
    version: int | str | dict[str, Any] | None = None,
    model: str = "gpt-4o-2024-11-20",
    task_input: dict[str, Any] | None = None,
    tenant: str = "_",
    metadata: dict[str, Any] | None = None,
    run_id: str | None = None,
    use_cache: CacheUsage = "auto",
    headers: dict[str, Any] | None = None,
    private_fields: list[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": version or {"model": model},
        "task_input": task_input or {"name": "John", "age": 30},
    }
    if metadata is not None:
        payload["metadata"] = metadata
    if run_id is not None:
        payload["id"] = run_id
    if private_fields is not None:
        payload["private_fields"] = private_fields
    payload["use_cache"] = use_cache

    res = await int_api_client.post(
        f"/v1/{tenant}/agents/{task_id}/schemas/{task_schema_id}/run",
        json=payload,
        headers=headers,
    )
    return result_or_raise(res)


async def stream_run_task(
    int_api_client: AsyncClient,
    task_id: str,
    task_schema_id: int,
    task_input: dict[str, Any],
    group: dict[str, Any],
    tenant: str = "_",
    labels: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
):
    payload: dict[str, Any] = {
        "group": group,
        "task_input": task_input,
        "stream": True,
    }
    if labels is not None:
        payload["labels"] = labels
    if metadata is not None:
        payload["metadata"] = metadata

    # Keep using the /tasks/ endpoint since it's what is used in prod
    # By people
    async with int_api_client.stream(
        "POST",
        f"/{tenant}/tasks/{task_id}/schemas/{task_schema_id}/run",
        json=payload,
    ) as response:
        response.raise_for_status()

        async for chunk in response.aiter_text():
            yield chunk


async def stream_run_task_v1(
    int_api_client: AsyncClient,
    task_id: str,
    task_schema_id: int,
    task_input: dict[str, Any] | None = None,
    version: int | str | dict[str, Any] | None = None,
    model: str = "gpt-4o-2024-11-20",
    tenant: str = "_",
    metadata: dict[str, Any] | None = None,
):
    payload: dict[str, Any] = {
        "version": version or {"model": model},
        "task_input": task_input or {"name": "John", "age": 30},
        "stream": True,
    }

    if metadata is not None:
        payload["metadata"] = metadata

    # Keep using the /tasks/ endpoint since it's what is used in prod
    # By people
    async with int_api_client.stream(
        "POST",
        f"/v1/{tenant}/tasks/{task_id}/schemas/{task_schema_id}/run",
        json=payload,
    ) as response:
        response.raise_for_status()

        async for chunk in response.aiter_text():
            yield chunk


async def import_task_run(
    int_api_client: AsyncClient,
    task_id: str,
    task_schema_id: int,
    task_input: dict[str, Any],
    task_output: dict[str, Any],
    group: dict[str, Any],
    tenant: str = "_",
    labels: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    cost_usd: float | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "group": group,
        "task_input": task_input,
        "task_output": task_output,
    }
    if labels is not None:
        payload["labels"] = labels
    if metadata is not None:
        payload["metadata"] = metadata
    if cost_usd is not None:
        payload["cost_usd"] = cost_usd

    res = await int_api_client.post(f"/{tenant}/agents/{task_id}/schemas/{task_schema_id}/runs", json=payload)
    assert res.status_code == 200
    return res.json()


async def wait_for_completed_tasks(broker: InMemoryBroker, max_retries: int = 10):
    """Sleep for intervals of 100 until all tasks are completed or max_retries is reached."""
    running = []
    for _ in range(max_retries):
        running = [task for task in broker._running_tasks if not task.done()]  # pyright: ignore [reportPrivateUsage]
        if not running:
            return
        await asyncio.sleep(0.1)
    raise TimeoutError(f"Tasks did not complete {[task for task in running]}")


def _task_id(task: dict[str, Any]):
    # the new v1 endpoint has an id field
    return task.get("task_id") or task["id"]


def _schema_id(task: dict[str, Any]):
    # the new v1 endpoint has a schema_id field
    return task.get("task_schema_id") or task["schema_id"]


def task_schema_url(task: dict[str, Any], path: str, tenant: str = "_") -> str:
    return f"/{tenant}/agents/{_task_id(task)}/schemas/{_schema_id(task)}/{path}"


def task_url_v1(task: dict[str, Any], path: str, tenant: str = "_") -> str:
    if path.startswith("/"):
        path = path[1:]
    return f"/v1/{tenant}/agents/{_task_id(task)}/{path}"


def task_schema_url_v1(task: dict[str, Any], path: str, tenant: str = "_") -> str:
    return task_url_v1(task, f"schemas/{_schema_id(task)}/{path}", tenant)


def run_id_url(task: dict[str, Any], run_id: str, path: str | None = None, tenant: str = "_") -> str:
    base = f"/{tenant}/agents/{_task_id(task)}/runs/{run_id}"
    if path:
        return f"{base}/{path}"
    return base


def result_or_raise(res: Response) -> Any:
    try:
        res.raise_for_status()
    except HTTPStatusError as e:
        print(e.response.text)  # noqa: T201
        raise e

    if res.text:
        return res.json()
    return None


async def create_group(
    int_api_client: AsyncClient,
    task: dict[str, Any],
    model: str = "gpt-4o-2024-11-20",
) -> dict[str, Any]:
    group_res = await int_api_client.post(
        task_schema_url(task, "groups"),
        json={
            "properties": {"model": model},
        },
    )
    return result_or_raise(group_res)


def openai_endpoint(
    provider: Literal["openai", "azure_openai"] = "openai",
    model: str | Model = "gpt-4o-2024-11-20",
    region: str = "eastus",
):
    if provider == "openai":
        return "https://api.openai.com/v1/chat/completions"

    model_str = model.value if isinstance(model, Model) else model
    base_url = f"workflowai-azure-oai-staging-{region}.openai.azure.com"
    api_version = "2024-12-01-preview"
    return f"https://{base_url}/openai/deployments/{model_str}/chat/completions?api-version={api_version}"


def azure_openai_endpoint(
    model: str = "gpt-4o-2024-11-20",
    region: str = "eastus",
):
    return f"https://workflowai-azure-oai-staging-{region}.openai.azure.com/openai/deployments/{model}/chat/completions?api-version=2024-12-01-preview"


def mock_openai_call(
    httpx_mock: HTTPXMock,
    status_code: int = 200,
    json: dict[str, Any] | None = None,
    text: str | None = None,
    json_content: dict[str, Any] | None = None,
    tool_calls_content: list[dict[str, Any]] | None = None,
    usage: dict[str, Any] | None = None,
    model: str = "gpt-4o-2024-11-20",
    provider: Literal["openai", "azure_openai"] = "openai",
    raw_content: Any | None = -1,
):
    default_usage = {
        "prompt_tokens": 10,
        "completion_tokens": 11,
        "total_tokens": 21,
    }
    if provider == "openai":
        url = openai_endpoint()
    else:
        url = azure_openai_endpoint(model)

    message: dict[str, Any] = {}
    if tool_calls_content is not None:
        message["tool_calls"] = tool_calls_content

    # Not using None here to allow passing content: null
    if raw_content == -1:
        message["content"] = '{"greeting": "Hello James!"}' if json_content is None else json_dumps(json_content)
    else:
        message["content"] = raw_content

    httpx_mock.add_response(
        url=url,
        status_code=status_code,
        json=(
            json
            or {
                "id": "1",
                "choices": [
                    {
                        "message": message,
                    },
                ],
                "usage": usage or default_usage,
            }
        )
        if text is None
        else None,
        text=text,
    )


async def create_example(
    int_api_client: AsyncClient,
    task: dict[str, Any],
    input: dict[str, Any],
    output: dict[str, Any],
    tenant: str = "_",
):
    res = await int_api_client.post(
        task_schema_url(task, "examples", tenant=tenant),
        json={"task_input": input, "task_output": output},
    )
    return result_or_raise(res)


async def create_field_evaluator(
    int_api_client: AsyncClient,
    task: dict[str, Any],
    options: dict[str, Any],
    tenant: str = "_",
):
    res = await int_api_client.post(
        task_schema_url(task, "evaluators", tenant=tenant),
        json={
            "name": "My Evaluator",
            "evaluator_type": {"type": "field_based", "field_based_evaluation_config": {"options": options}},
        },
    )
    return result_or_raise(res)


async def replace_field_evaluator(
    int_api_client: AsyncClient,
    evaluator: dict[str, Any],
    task: dict[str, Any],
    options: dict[str, Any],
    tenant: str = "_",
    name: str = "A new Evaluator",
):
    res = await int_api_client.put(
        task_schema_url(task, f"evaluators/{evaluator['id']}", tenant=tenant),
        json={
            "name": name,
            "evaluator_type": {"type": "field_based", "field_based_evaluation_config": {"options": options}},
        },
    )
    return result_or_raise(res)


def run_url(
    task: dict[str, Any],
    run_id: str | None = None,
    run: dict[str, Any] | None = None,
    tenant: str = "_",
    v1: bool = False,
):
    if not run_id:
        assert run
        run_id = run["id"]
    root = f"/{tenant}/agents/{_task_id(task)}/runs/{run_id}"
    if v1:
        return "/v1" + root
    return root


async def fetch_run(
    int_api_client: AsyncClient,
    task: dict[str, Any],
    run: dict[str, Any] | None = None,
    run_id: str | None = None,
    tenant: str = "_",
    v1: bool = False,
):
    res = await int_api_client.get(run_url(task, run_id=run_id, run=run, tenant=tenant, v1=v1))
    return result_or_raise(res)


async def get_amplitude_requests(httpx_mock: HTTPXMock):
    requests = httpx_mock.get_requests(url="https://amplitude-mock")
    events = [request_json_body(request) for request in requests]
    # Sort events based on time and event_type
    return sorted(events, key=lambda x: (x["events"][0]["time"], x["events"][0]["event_type"]))


async def create_organization_via_clerk(
    int_api_client: AsyncClient,
    httpx_mock: HTTPXMock,
    patched_broker: InMemoryBroker,
):
    with freeze_time("2021-02-25T00:00:00Z"):
        result_or_raise(
            await int_api_client.post(
                "/webhooks/clerk",
                json={
                    "data": {
                        "name": "test 18",
                        "slug": "test-21",
                        "object": "organization",
                        "id": "org_2iPlfJ5X4LwiQybM9qeT00YPdBe",
                    },
                    "object": "event",
                    "type": "organization.created",
                },
                headers={
                    "Authorization": "",
                    "svix-id": "msg_p5jXN8AQM9LWM0D4loKWxJek",
                    "svix-timestamp": f"{time.time()}",
                    "svix-signature": "v1,/fIaJ/NmgVmJFQwJmEUI4ZI45BfTsMmENHHBha7/y4U=",
                },
            ),
        )
    await wait_for_completed_tasks(patched_broker)

    # Reset the mock to clear any analytics requests
    httpx_mock._requests.clear()  # pyright: ignore [reportPrivateUsage]


async def list_groups(int_api_client: AsyncClient, task: dict[str, Any]) -> list[dict[str, Any]]:
    res = await int_api_client.get(task_schema_url(task, "groups"))
    return result_or_raise(res)["items"]


async def extract_stream_chunks(stream: AsyncIterator[str]):
    async for chunk in stream:
        assert chunk.startswith("data: ")
        assert chunk.endswith("\n\n")
        content = chunk[6:-2]
        splits = content.split("\n\ndata: ")
        for data in splits:
            yield json.loads(data)


# Old tokens did not include an org_id
LEGACY_TEST_JWT = "eyJhbGciOiJFUzI1NiJ9.eyJ0ZW5hbnQiOiJjaGllZm9mc3RhZmYuYWkiLCJzdWIiOiJndWlsbGF1bWVAY2hpZWZvZnN0YWZmLmFpIiwiaWF0IjoxNzE1OTgyMzUxLCJleHAiOjE4MzIxNjYzNTF9.NbjBXv0fcfOUGpscJ9PzC5jHna2V6tBrSte2kvHYDJTKdFv6Zg3IzOVmSVOM_jIsOgTggmC4mYSK11IHhnP4ew"
# Anon JWT with a tenant id that does not exist
ANON_JWT = "eyJhbGciOiJFUzI1NiJ9.eyJ1bmtub3duVXNlcklkIjoiOGM5NGQ1MjMtZGE2YS00MDg5LWIxZDMtMzRhM2ZmYmNlNDg0IiwiaWF0IjoxNjI4NzA3ODQ2LCJleHAiOjE4OTEyNDM4NDZ9.n4DJt-4H_3-u_3KBRQvT_xwDQb2ogBtAFhByBDYeEtqblp4auz6okicNeJygfowgIJfNYAGDr7FH1e37qQkuDg"
# {"userId":"user_1234","unknownUserId":"8c94d523-da6a-4089-b1d3-34a3ffbce484"}
USER_JWT = "eyJhbGciOiJFUzI1NiJ9.eyJ1c2VySWQiOiJ1c2VyXzEyMzQiLCJ1bmtub3duVXNlcklkIjoiOGM5NGQ1MjMtZGE2YS00MDg5LWIxZDMtMzRhM2ZmYmNlNDg0IiwiaWF0IjoxNjI4NzA3ODQ2LCJleHAiOjE4OTEyNDM4NDZ9.D7V7ZWef_X8D2xPuX9g_3fhtuCy1ib_hP82CoX-ET_GWkjJsZkDV6DdD9_wR72ipds2Zfb3Yl88svihOBMkltA"


def vertex_url_matcher(model: str | Model, region: str | None = None, publisher: str = "google", stream: bool = False):
    path = "streamGenerateContent?alt=sse" if stream else "generateContent"
    model = model.value if isinstance(model, Model) else model
    if region:
        return f"https://{region}-aiplatform.googleapis.com/v1/projects/worfklowai/locations/{region}/publishers/{publisher}/models/{model}:{path}"

    escape_1 = re.escape("-aiplatform.googleapis.com/v1/projects/worfklowai/locations/")
    escape_2 = re.escape(f"/publishers/{publisher}/models/{model}:{path}")
    return re.compile(f"https://[^/]+{escape_1}[^/]+{escape_2}")


def mock_vertex_call(
    httpx_mock: HTTPXMock,
    json: dict[str, Any] | None = None,
    model: str | Model = "gemini-1.5-pro-002",
    parts: list[dict[str, Any]] | None = None,
    region: str = "us-central1",
    usage: dict[str, Any] | None = None,
    publisher: str = "google",
    url: str | re.Pattern[str] | None = None,
    status_code: int = 200,
    latency: float | None = None,
):
    response = json or {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": parts or [{"text": '{"greeting": "Hello John!"}', "inlineData": None}],
                },
                "finishReason": None,
                "safetyRatings": None,
            },
        ],
        "usageMetadata": usage or {"promptTokenCount": 222, "candidatesTokenCount": 9, "totalTokenCount": 231},
    }
    model_str = model.value if isinstance(model, Model) else model

    async def _response(request: Request):
        if latency:
            await asyncio.sleep(latency)
        return Response(
            json=response,
            status_code=status_code,
        )

    httpx_mock.add_callback(
        _response,
        url=url
        or f"https://{region}-aiplatform.googleapis.com/v1/projects/worfklowai/locations/{region}/publishers/{publisher}/models/{model_str}:generateContent",
    )


def mock_gemini_call(
    httpx_mock: HTTPXMock,
    json: dict[str, Any] | None = None,
    model: str | Model = "gemini-exp-1206",
    usage: dict[str, Any] | None = None,
    api_version: str = "v1beta",
):
    response = json or {
        "candidates": [
            {
                "content": {"role": "model", "parts": [{"text": '{"greeting": "Hello John!"}', "inlineData": None}]},
                "finishReason": None,
                "safetyRatings": None,
            },
        ],
        "usageMetadata": usage or {"promptTokenCount": 222, "candidatesTokenCount": 9, "totalTokenCount": 231},
    }
    model_str = model.value if isinstance(model, Model) else model

    url = f"https://generativelanguage.googleapis.com/{api_version}/models/{model_str}:generateContent?key={os.environ.get('GEMINI_API_KEY')}"
    httpx_mock.add_response(
        url=url,
        json=response,
    )


def bedrock_endpoint(model: str, region: str = "us-west-2"):
    return f"https://bedrock-runtime.{region}.amazonaws.com/model/{model}/converse"


class IntegrationTestClient:
    def __init__(
        self,
        int_api_client: AsyncClient,
        httpx_mock: HTTPXMock,
        patched_broker: InMemoryBroker,
    ):
        self.int_api_client = int_api_client
        self.httpx_mock = httpx_mock
        self.patched_broker = patched_broker
        self._patches: list[Any] = []
        # Call refresh_org if needed after authenticate
        self.org: dict[str, Any] = {}

    def authenticate(self, token: str):
        self.int_api_client.headers["Authorization"] = f"Bearer {token}"

    async def close(self):
        """Clean up all patches when the client is closed."""
        for patcher in self._patches:
            patcher.stop()

    def reset_httpx_mock(self, assert_all_responses_were_requested: bool = True):
        _AMPLITUDE_URL = "https://amplitude-mock"
        _BETTERSTACK_URL = "https://in.logs.betterstack.com/metrics"
        # We are also skipping the agent creation request, depending on how it's imported we could have
        # missing calls when running multiple tests at once.
        _CREATE_AGENT_URL = "http://0.0.0.0:8000/v1/_/agents"
        try:
            self.httpx_mock.reset(assert_all_responses_were_requested=assert_all_responses_were_requested)
        except AssertionError as e:
            # As of now, httpx mock does not support excluding specific responses from the reset
            # So we do this by hand
            def _extract_missing_responses(e: AssertionError):
                lines = str(e).splitlines()
                assert "The following responses are mocked but not requested" in lines[0], "sanity"
                assert "assert not" in lines[-1], "sanity"
                return [
                    line
                    for line in lines[1:-1]
                    if _AMPLITUDE_URL not in line and _BETTERSTACK_URL not in line and _CREATE_AGENT_URL not in line
                ]

            missing_responses = _extract_missing_responses(e)
            if missing_responses:
                raise AssertionError(
                    f"The following responses are mocked but not requested:\n{'\n'.join(missing_responses)}",
                )

        self.httpx_mock.add_response(url="https://in.logs.betterstack.com/metrics", status_code=202)
        self.httpx_mock.add_response(url="https://amplitude-mock", status_code=200)

    async def create_task(
        self,
        tenant: str = "_",
        name: str = "Greet",
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        creation_date: datetime | None = None,
    ) -> dict[str, Any]:
        return await create_task(
            self.int_api_client,
            self.patched_broker,
            self.httpx_mock,
            tenant=tenant,
            name=name,
            input_schema=input_schema,
            output_schema=output_schema,
            creation_date=creation_date,
        )

    async def user_review(
        self,
        task: dict[str, Any],
        run: dict[str, Any],
        outcome: Literal["positive", "negative"],
        autowait: bool = True,
    ):
        res = await self.int_api_client.post(
            f"/_/agents/{_task_id(task)}/runs/{run['id']}/reviews",
            json={"outcome": outcome},
        )
        try:
            result_or_raise(res)
        finally:
            if autowait:
                await wait_for_completed_tasks(self.patched_broker)

    def internal_task_url(self, task_id: str) -> str:
        host = os.environ.get("WORKFLOWAI_API_URL", "run.workflowai.com")
        return f"{host}/v1/_/agents/{task_id}/schemas/1/run"

    def mock_internal_task(
        self,
        task_id: str,
        task_output: dict[str, Any],
        create_agent: bool = True,
    ):
        if create_agent:
            self.httpx_mock.add_response(
                url=f"{os.environ.get('WORKFLOWAI_API_URL', 'api.workflowai.com')}/v1/_/agents",
                json={
                    "id": task_id,
                    "schema_id": 1,
                    "variant_id": "variant_id",
                },
            )

        self.httpx_mock.add_response(
            url=self.internal_task_url(task_id),
            json={
                "id": "1",
                "version": {"properties": {"model": "gpt-4o-2024-11-20"}},
                "task_output": task_output,
            },
        )

    def mock_ai_review(
        self,
        outcome: Literal["positive", "negative", "unsure"],
        confidence_score: float | None = None,
        positive_aspects: list[str] | None = None,
        negative_aspects: list[str] | None = None,
    ):
        self.mock_internal_task(
            "evaluate-output",
            {
                "evaluation_result": outcome,
                "confidence_score": confidence_score,
                "positive_aspects": positive_aspects,
                "negative_aspects": negative_aspects,
            },
        )

    def mock_openai_call(
        self,
        status_code: int = 200,
        json: dict[str, Any] | None = None,
        text: str | None = None,
        json_content: dict[str, Any] | None = None,
        tool_calls_content: list[dict[str, Any]] | None = None,
        usage: dict[str, Any] | None = None,
        model: str | Model = "gpt-4o-2024-11-20",
        provider: Literal["openai", "azure_openai"] = "openai",
        raw_content: Any | None = -1,
    ):
        mock_openai_call(
            self.httpx_mock,
            status_code,
            json,
            text,
            json_content,
            tool_calls_content,
            usage,
            model.value if isinstance(model, Model) else model,
            provider,
            raw_content,
        )

    async def run_task_v1(
        self,
        task: dict[str, Any],
        version: int | str | dict[str, Any] | None = None,
        model: str | Model = "gpt-4o-2024-11-20",
        task_input: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        run_id: str | None = None,
        use_cache: CacheUsage = "auto",
        headers: dict[str, Any] | None = None,
        private_fields: list[str] | None = None,
        autowait: bool = True,
        tenant: str = "_",
    ) -> dict[str, Any]:
        try:
            return await run_task_v1(
                self.int_api_client,
                _task_id(task),
                _schema_id(task),
                version,
                model.value if isinstance(model, Model) else model,
                task_input,
                tenant,
                metadata,
                run_id,
                use_cache,
                headers,
                private_fields,
            )
        finally:
            if autowait:
                await wait_for_completed_tasks(self.patched_broker)

    async def stream_run_task_v1(
        self,
        task: dict[str, Any],
        task_input: dict[str, Any] | None = None,
        version: int | str | dict[str, Any] | None = None,
        model: str = "gpt-4o-2024-11-20",
        metadata: dict[str, Any] | None = None,
        autowait: bool = True,
    ):
        async for c in stream_run_task_v1(
            self.int_api_client,
            _task_id(task),
            _schema_id(task),
            task_input=task_input,
            version=version,
            model=model,
            tenant=self.tenant,
            metadata=metadata,
        ):
            assert c.startswith("data: ")
            assert c.endswith("\n\n")
            splits = c.split("\n\ndata: ")
            for s in splits:
                s = s.removeprefix("data: ").removesuffix("\n\n")
                yield json.loads(s)

        if autowait:
            await wait_for_completed_tasks(self.patched_broker)

    DEFAULT_VERTEX_MODEL = Model.GEMINI_1_5_FLASH_002.value

    def mock_vertex_call(
        self,
        json: dict[str, Any] | None = None,
        model: str | Model = DEFAULT_VERTEX_MODEL,
        parts: list[dict[str, Any]] | None = None,
        regions: list[str] | None = None,
        usage: dict[str, Any] | None = None,
        publisher: str = "google",
        url: str | re.Pattern[str] | None = None,
        status_code: int = 200,
        latency: float | None = None,
    ):
        if not regions:
            regions = os.environ.get("GOOGLE_VERTEX_AI_LOCATION", "us-central1").split(",")

        for region in regions:
            mock_vertex_call(
                self.httpx_mock,
                json,
                model,
                parts,
                region,
                usage,
                publisher,
                url,
                status_code,
                latency=latency,
            )

    async def wait_for_completed_tasks(self):
        await wait_for_completed_tasks(self.patched_broker)
        await wait_for_background_tasks()

    async def create_version(
        self,
        task: dict[str, Any],
        version_properties: dict[str, Any],
        mock_chain_of_thought: bool | None = None,
        create_agent: bool = True,
        save: bool | None = None,
        autowait: bool = False,
        tenant: str = "_",
    ) -> dict[str, Any]:
        if mock_chain_of_thought is not None:
            self.mock_detect_chain_of_thought(mock_chain_of_thought, create_agent=create_agent)
        v = await create_version(
            self.int_api_client,
            _task_id(task),
            _schema_id(task),
            version_properties,
            tenant=tenant,
            save=save,
        )
        if autowait:
            await wait_for_completed_tasks(self.patched_broker)
        return v

    async def create_version_v1(
        self,
        task: dict[str, Any],
        version_properties: dict[str, Any],
        tenant: str = "_",
    ) -> dict[str, Any]:
        res = await self.int_api_client.post(
            f"/v1/{tenant}/agents/{_task_id(task)}/schemas/{_schema_id(task)}/versions",
            json={"properties": version_properties},
        )

        return result_or_raise(res)

    def mock_openai_stream(
        self,
        deltas: list[bytes | str | tuple[str, dict[str, Any]]] | IteratorStream | None,
        tool_calls_deltas: list[list[dict[str, Any]]] | None = None,
        template: dict[str, Any] | None = None,
        model: str = "gpt-4o-2024-11-20",
        provider: str = "openai",
    ):
        tpl = template or {
            "id": "1",
            "object": "chat.completion.chunk",
            "created": 1720404416,
            "model": "gpt-4o-audio-preview-2024-10-01",
            "system_fingerprint": "fp_44132a4de3",
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": ""},
                    "logprobs": None,
                },
            ],
        }

        def build_chunk(chunk: bytes | str | tuple[str, dict[str, Any]]):
            if isinstance(chunk, bytes):
                return chunk

            t = tpl.copy()
            delta = chunk[1] if isinstance(chunk, tuple) else chunk
            overrides: dict[str, Any] = delta[1] if isinstance(delta, tuple) else {}  # type: ignore

            t["choices"][0]["delta"]["content"] = delta
            t = {**t, **overrides}
            return f"data: {json.dumps(t)}\n\n".encode()

        def build_tool_calls_chunk(chunk: list[dict[str, Any]]):
            t = tpl.copy()
            t["choices"][0]["delta"]["tool_calls"] = chunk

            return f"data: {json.dumps(t)}\n\n".encode()

        if provider == "openai":
            url = "https://api.openai.com/v1/chat/completions"
        else:
            url = f"https://workflowai-azure-oai-staging-eastus.openai.azure.com/openai/deployments/{model}/chat/completions?api-version=2024-12-01-preview"

        stream: list[bytes] = []
        if deltas is not None:
            stream = [build_chunk(c) for c in deltas]
        if tool_calls_deltas is not None:
            stream += [build_tool_calls_chunk(tool_calls_delta) for tool_calls_delta in tool_calls_deltas]

        self.httpx_mock.add_response(
            url=url,
            stream=IteratorStream(stream),
        )

    def mock_vertex_stream(
        self,
        deltas: list[bytes | str | tuple[str | None, dict[str, Any]]] | IteratorStream,
        template: dict[str, Any] | None = None,
        model: str = DEFAULT_VERTEX_MODEL,
    ):
        tpl = template or {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": ""},
                        ],
                        "role": "model",
                    },
                },
            ],
        }

        def build_chunk(chunk: bytes | str | tuple[str | None, dict[str, Any]]):
            if isinstance(chunk, bytes):
                return chunk

            t = tpl.copy()
            delta = chunk[0] if isinstance(chunk, tuple) else chunk
            overrides: dict[str, Any] = chunk[1] if isinstance(chunk, tuple) else {}  # type: ignore

            t["candidates"][0]["content"]["parts"][0]["text"] = delta
            t["candidates"][0] = {**t["candidates"][0], **overrides}
            return f"data: {json.dumps(t)}\r\n\r\n".encode()

        self.httpx_mock.add_response(
            url=vertex_url_matcher(model, stream=True),
            stream=IteratorStream([build_chunk(c) for c in deltas]),
        )

    def reset_http_requests(self):
        """Clears the HTTP requests that were mocked without removing existing callbacks"""
        self.httpx_mock._requests.clear()  # pyright: ignore [reportPrivateUsage]

    def get_request_bodies(self, **kwargs: Any) -> list[dict[str, Any]]:
        return [request_json_body(r) for r in self.httpx_mock.get_requests(**kwargs)]

    async def get_internal_task_request_bodies(self, task_id: str, schema_id: int, inputs_only: bool = True):
        url = self.internal_task_url(task_id)
        reqs = self.httpx_mock.get_requests(url=url)

        async def map_req(request: Request):
            body = request_json_body(request)
            if inputs_only:
                return body.get("task_input")
            return body

        return [await map_req(req) for req in reqs]

    def mock_mistralai_completion(self):
        self.httpx_mock.add_response(
            url="https://api.mistral.ai/v1/chat/completions",
            method="POST",
            status_code=200,
            json=fixtures_json("mistralai", "completion2.json"),
        )

    def mock_mistralai_completion_failure(self):
        self.httpx_mock.add_response(
            url="https://api.mistral.ai/v1/chat/completions",
            method="POST",
            status_code=400,
            json={"error": {"message": "Bad Request"}},
        )

    def fetch_run(
        self,
        task: dict[str, Any],
        run_id: str | None = None,
        run: dict[str, Any] | None = None,
        tenant: str = "_",
        v1: bool = False,
    ):
        return fetch_run(self.int_api_client, task, run_id=run_id, run=run, tenant=tenant, v1=v1)

    def fetch_completions(
        self,
        task: dict[str, Any],
        run_id: str | None = None,
        run: dict[str, Any] | None = None,
        tenant: str = "_",
    ):
        return self.get(run_url(task, run_id=run_id, run=run, tenant=tenant, v1=True) + "/completions")

    def mock_detect_chain_of_thought(self, chain_of_thought: bool, create_agent: bool = True):
        self.mock_internal_task(
            "detect-chain-of-thought",
            {"should_use_chain_of_thought": chain_of_thought},
            create_agent=create_agent,
        )

    async def fetch_version(
        self,
        task: dict[str, Any],
        version_id: str,
        tenant: str = "_",
    ) -> dict[str, Any]:
        return result_or_raise(await self.int_api_client.get(task_url_v1(task, f"versions/{version_id}", tenant)))

    async def get(self, url: str, **kwargs: Any) -> dict[str, Any]:
        return result_or_raise(await self.int_api_client.get(url, **kwargs))

    async def post(self, url: str, json: Any = None, **kwargs: Any) -> dict[str, Any]:
        return result_or_raise(await self.int_api_client.post(url, json=json, **kwargs))

    async def patch(self, url: str, json: Any, **kwargs: Any) -> dict[str, Any]:
        return result_or_raise(await self.int_api_client.patch(url, json=json, **kwargs))

    async def put(self, url: str, json: Any, **kwargs: Any) -> dict[str, Any]:
        return result_or_raise(await self.int_api_client.put(url, json=json, **kwargs))

    def mock_anthropic_call(
        self,
        status_code: int = 200,
        content_json: dict[str, Any] | None = None,
        model: Model = Model.CLAUDE_3_5_SONNET_20241022,
    ):
        self.httpx_mock.add_response(
            url="https://api.anthropic.com/v1/messages",
            status_code=status_code,
            json={
                "id": "msg_011FfbzF4F72Gc1rzSvvDCnR",
                "type": "message",
                "role": "assistant",
                "model": model.value,
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            content_json,
                            indent=2,
                        ),
                    },
                ],
                "stop_reason": "end_turn",
                "usage": {
                    "input_tokens": 1596,
                    "output_tokens": 79,
                },
            },
        )

    def mock_bedrock_call(
        self,
        model: str,
        status_code: int = 200,
        body: dict[str, Any] | None = None,
        json_text: dict[str, Any] | None = None,
    ):
        self.httpx_mock.add_response(
            url=bedrock_endpoint(model),
            status_code=status_code,
            json=body
            or {
                "metrics": {
                    "latencyMs": 1594,
                },
                "output": {
                    "message": {
                        "content": [
                            {
                                "text": json.dumps(json_text)
                                if json_text is not None
                                else '{"greeting": "Hello, world!"}',
                            },
                        ],
                        "role": "assistant",
                    },
                },
                "stopReason": "end_turn",
                "usage": {
                    "inputTokens": 267,
                    "outputTokens": 31,
                    "totalTokens": 298,
                },
            },
        )

    async def create_agent_v1(
        self,
        tenant: str = "_",
        id: str = "greet",
        name: str = "Greet",
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        creation_date: datetime | None = None,
        sanitize_schemas: bool = True,
    ):
        async def _create_task():
            task = await self.post(
                f"/v1/{tenant}/agents",
                json={
                    "id": id,
                    "name": name,
                    "input_schema": input_schema
                    or {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "age": {"type": "integer"},
                        },
                        "required": ["name", "age"],
                    },
                    "output_schema": output_schema
                    or {
                        "type": "object",
                        "properties": {
                            "greeting": {"type": "string"},
                        },
                        "required": ["greeting"],
                    },
                    "sanitize_schemas": sanitize_schemas,
                },
            )
            await wait_for_completed_tasks(self.patched_broker)
            return task

        if creation_date:
            if not creation_date.tzinfo:
                # Making sure we have a timezone
                creation_date = creation_date.replace(tzinfo=timezone.utc)
            with freeze_time(creation_date):
                return await _create_task()
        else:
            return await _create_task()

    async def get_org(self):
        return await self.get("/_/organization/settings")

    def storage_url(self, task: dict[str, Any], file_name: str = "test.txt", org: dict[str, Any] | None = None):
        org_uid = org["tenant"] if org else self.org["tenant"]
        return (
            f"http://127.0.0.1:10000/devstoreaccount1/workflowai-test-task-runs/{org_uid}/{_task_id(task)}/{file_name}"
        )

    async def refresh_org_data(self):
        self.org = await self.get_org()
        return self.org

    @property
    def tenant_uid(self):
        return self.org["uid"]

    @property
    def tenant(self):
        return self.org["tenant"]
