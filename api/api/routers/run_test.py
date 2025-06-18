import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from freezegun import freeze_time
from httpx import AsyncClient

from api.dependencies.security import user_organization
from api.routers.run import (
    DeprecatedVersionReference,
    RunRequest,
    RunResponse,
    RunResponseStreamChunk,
    version_reference_to_domain,
)
from core.domain.agent_run import AgentRun
from core.domain.ban import Ban
from core.domain.llm_completion import LLMCompletion
from core.domain.llm_usage import LLMUsage
from core.domain.major_minor import MajorMinor
from core.domain.models import Provider
from core.domain.run_output import RunOutput
from core.domain.task_group import TaskGroup
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_info import TaskInfo
from core.domain.task_run_builder import TaskRunBuilder
from core.domain.task_variant import SerializableTaskVariant
from core.domain.tool_call import ToolCall, ToolCallRequestWithID
from core.domain.version_environment import VersionEnvironment
from core.domain.version_reference import VersionReference
from core.providers.base.provider_error import InvalidGenerationError, ProviderRateLimitError
from core.runners.abstract_runner import AbstractRunner
from core.runners.workflowai.workflowai_runner import WorkflowAIRunner
from tests import models as test_models
from tests.models import task_run_ser
from tests.utils import mock_aiter


class TestVersionReferenceToDomain:
    @pytest.mark.parametrize(
        "version,expected",
        [
            ("production", VersionReference(version=VersionEnvironment.PRODUCTION)),
            ("dev", VersionReference(version=VersionEnvironment.DEV)),  # noqa: F821
            ("staging", VersionReference(version=VersionEnvironment.STAGING)),
            (1, VersionReference(version=1)),
            ("1", VersionReference(version=1)),
            ("1.0", VersionReference(version=MajorMinor(1, 0))),
            (
                TaskGroupProperties(model="gpt-4o", temperature=0.5),
                VersionReference(properties=TaskGroupProperties(model="gpt-4o", temperature=0.5)),
            ),
            ("blabla", VersionReference(version="blabla")),
            # Keeping 32 char hashes with only numbers as strings
            ("12345678901234567890123456789012", VersionReference(version="12345678901234567890123456789012")),
        ],
    )
    def test_environment_alias(self, version: str, expected: VersionReference):
        assert version_reference_to_domain(version) == expected  # type: ignore


class TestDeprecatedVersionReferenceToDomain:
    @pytest.mark.parametrize(
        "version,expected",
        [
            (DeprecatedVersionReference(alias="environment=production"), VersionReference(version="production")),
            (DeprecatedVersionReference(iteration=1), VersionReference(version=1)),
        ],
    )
    def test_environment_alias(self, version: DeprecatedVersionReference, expected: VersionReference):
        assert version.to_domain() == expected


class TestRunModelsNotAuthenticated:
    @pytest.mark.unauthenticated
    async def test_run_models_not_authenticated(self, test_api_client: AsyncClient):
        # Unauthenticated
        models = await test_api_client.get("/v1/models")
        assert models.status_code == 200


class TestRunResponseFromDomain:
    def test_with_none_output(self):
        run = test_models.task_run_ser()
        run.task_output = None

        res = RunResponse.from_domain(run, "")
        assert res.task_output == {}

    def test_with_empty_string(self):
        run = test_models.task_run_ser()
        run.task_output = ""

        res = RunResponse.from_domain(run, "")
        assert res.task_output == ""


class TestRunResponseStreamChunkFromDomain:
    def test_with_none_output(self):
        run = test_models.task_run_ser()
        run.task_output = None

        res = RunResponseStreamChunk.from_stream("hello", RunOutput(None))
        assert res.task_output == {}

    def test_with_empty_string(self):
        run = test_models.task_run_ser()
        run.task_output = ""

        res = RunResponseStreamChunk.from_stream("hello", RunOutput(""))
        assert res.task_output == ""


@pytest.fixture(scope="function")
def mock_runner(hello_task: SerializableTaskVariant, mock_group_service: Mock) -> AbstractRunner[Any]:
    mock = Mock(spec=AbstractRunner)
    mock.task = hello_task
    mock_builder = Mock(spec=TaskRunBuilder)
    mock_builder.id = "1"
    mock.task_run_builder = AsyncMock(return_value=mock_builder)

    mock_group_service.sanitize_groups_for_internal_runner.return_value = mock, True
    return mock


@pytest.fixture
async def reset_security_dependencies(test_app: FastAPI):
    mock_user_org = Mock()
    mock_user_org.current_credits_usd = -10
    mock_user_org.organization_id = "test_org_id"
    mock_user_org.organization_slug = "test_org_slug"
    mock_user_org.organization_name = "Test Organization"

    # Set explicit attribute values to avoid Pydantic validation issues
    mock_user_org.org_id = "test_org_id"
    mock_user_org.slug = "test_org_slug"
    mock_user_org.name = "Test Organization"
    mock_user_org.tenant = "test_org_id"

    # Override dependencies to return this mock organization
    test_app.dependency_overrides[user_organization] = lambda: mock_user_org


@pytest.fixture
def mock_runs_service(test_app: FastAPI) -> Mock:
    from api.dependencies.services import runs_service as runs_service_dep
    from api.services.runs.runs_service import RunsService

    runs_service = Mock(spec=RunsService)
    test_app.dependency_overrides[runs_service_dep] = lambda: runs_service
    return runs_service


@pytest.fixture
def patch_run_from_builder():
    with patch("api.services.run.RunService.run_from_builder") as mock_run_from_builder:
        yield mock_run_from_builder


@pytest.fixture(autouse=True)
def mocked_task_info(mock_storage: Mock):
    task_info = TaskInfo(
        task_id="task_id",
        name="task_name",
        is_public=False,
        ban=None,
    )
    mock_storage.tasks.get_task_info.return_value = task_info
    return task_info


class TestDeprecatedRun:
    async def test_run_schema_insufficient_credits(
        self,
        test_api_client: AsyncClient,
        mock_group_service: Mock,
        mock_runner: Mock,
        reset_security_dependencies: None,
    ):
        # Perform the test request
        response = await test_api_client.post(
            "/test/tasks/123/schemas/1/run",
            json={
                "task_input": {"input": 1},
                "group": {"iteration": 1},
                "metadata": {"meta": "data"},
            },
        )

        # Assert the status code for insufficient credits (402)
        assert response.status_code == 402

    async def test_run(
        self,
        test_api_client: AsyncClient,
        patch_run_from_builder: Mock,
        mock_storage: Mock,
        mock_runner: Mock,
    ):
        patch_run_from_builder.return_value = AgentRun(
            id="blabla",
            task_id="123",
            task_schema_id=1,
            task_input_hash="1",
            task_output_hash="1",
            task_input={},
            task_output={},
            group=TaskGroup(iteration=1),
        )

        res = await test_api_client.post(
            "/test/tasks/123/schemas/1/run",
            json={
                "task_input": {"input": 1},
                "group": {
                    "iteration": 1,
                },
                "metadata": {"meta": "data"},
            },
        )
        res.raise_for_status()

        mock_storage.tasks.get_task_info.assert_called_once()

        assert res.status_code == 200

    async def test_run_429(
        self,
        test_api_client: AsyncClient,
        mock_runner: Mock,
        patch_run_from_builder: Mock,
        mock_storage: Mock,
    ):
        patch_run_from_builder.side_effect = ProviderRateLimitError(retry_after=10)

        mock_storage.tasks.get_task_info.return_value = TaskInfo(
            task_id="task_id",
            name="task_name",
            is_public=True,
            ban=None,
        )

        res = await test_api_client.post(
            "/test/tasks/123/schemas/1/run",
            json={
                "task_input": {"input": 1},
                "group": {
                    "iteration": 1,
                },
                "metadata": {"meta": "data"},
            },
        )

        mock_storage.tasks.get_task_info.assert_called_once()

        assert res.status_code == 429
        assert res.headers["Retry-After"] == "10"

    async def test_run_429_date(
        self,
        test_api_client: AsyncClient,
        mock_runner: Mock,
        mock_storage: Mock,
        patch_run_from_builder: Mock,
    ):
        patch_run_from_builder.side_effect = ProviderRateLimitError(
            retry_after=datetime(2021, 1, 1, 2, 3, 4, tzinfo=timezone.utc),
        )

        mock_storage.tasks.get_task_info.return_value = TaskInfo(
            task_id="task_id",
            name="task_name",
            is_public=True,
            ban=None,
        )

        res = await test_api_client.post(
            "/test/tasks/123/schemas/1/run",
            json={
                "task_input": {"input": 1},
                "group": {
                    "iteration": 1,
                },
                "metadata": {"meta": "data"},
            },
        )

        mock_storage.tasks.get_task_info.assert_called_once()

        assert res.status_code == 429
        assert res.headers["Retry-After"] == "2021-01-01T02:03:04+00:00"

    async def _stream_run(
        self,
        test_api_client: AsyncClient,
        data: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []

        async with test_api_client.stream(
            "POST",
            "/test/tasks/123/schemas/1/run",
            json=data
            or {
                "task_input": {"input": 1},
                "group": {
                    "iteration": 1,
                },
                "metadata": {"meta": "data"},
                "stream": True,
            },
        ) as res:
            async for chunk in res.aiter_bytes():
                assert chunk.startswith(b"data: ")
                assert chunk.endswith(b"\n\n")
                payload = json.loads(chunk[6:-2])
                payloads.append(payload)
        return payloads

    @pytest.fixture
    async def patched_stream_builder(self):
        with patch("api.services.run.RunService.stream_from_builder") as mock_stream:
            yield mock_stream

    async def test_stream(
        self,
        test_api_client: AsyncClient,
        mock_runner: WorkflowAIRunner,
        mock_storage: Mock,
        patched_stream_builder: AsyncMock,
    ):
        patched_stream_builder.return_value = mock_aiter(
            RunOutput({"say_hello": "hell"}),
            RunOutput({"say_hello": "hello wo"}),
            RunOutput({"say_hello": "hello world"}),
        )

        mock_storage.tasks.get_task_info.return_value = TaskInfo(
            task_id="task_id",
            name="task_name",
            is_public=True,
            ban=None,
        )

        payloads = await self._stream_run(test_api_client)
        mock_storage.tasks.get_task_info.assert_called_once()
        assert len(payloads) == 3
        assert payloads[0] == {"run_id": "1", "task_output": {"say_hello": "hell"}}

    async def test_stream_with_tools(
        self,
        test_api_client: AsyncClient,
        mock_group_service: Mock,
        patched_stream_builder: AsyncMock,
        mock_runner: Mock,
        mock_storage: Mock,
    ):
        patched_stream_builder.return_value = mock_aiter(
            RunOutput(
                {"say_hello": "hell"},
                [ToolCall(tool_name="test_tool", tool_input_dict={"arg": "value"})],
            ),
            RunOutput({"say_hello": "hello wo"}),
            RunOutput({"say_hello": "hello world"}),
        )

        mock_storage.tasks.get_task_info.return_value = TaskInfo(
            task_id="task_id",
            name="task_name",
            is_public=True,
            ban=None,
        )

        payloads = await self._stream_run(test_api_client)
        mock_storage.tasks.get_task_info.assert_called_once()
        assert len(payloads) == 3
        # TODO: when we duplicate tests for the v1 endpoint, there should be tools here
        assert payloads[0] == {
            "run_id": "1",
            "task_output": {"say_hello": "hell"},
        }

    async def test_stream_429(
        self,
        test_api_client: AsyncClient,
        mock_group_service: Mock,
        patched_stream_builder: AsyncMock,
        mock_runner: Mock,
        mock_storage: Mock,
    ):
        patched_stream_builder.side_effect = ProviderRateLimitError(retry_after=10, provider=Provider.OPEN_AI)

        mock_storage.tasks.get_task_info.return_value = TaskInfo(
            task_id="task_id",
            name="task_name",
            is_public=True,
            ban=None,
        )

        payloads = await self._stream_run(test_api_client)
        assert payloads == [
            {
                "error": {
                    "title": "Error",
                    "message": "Rate limit exceeded",
                    "code": "rate_limit",
                    "status_code": 429,
                    "details": {
                        "provider": "openai",
                        "provider_error": None,
                        "provider_options": None,
                        "provider_status_code": None,
                    },
                },
            },
        ]
        mock_storage.tasks.get_task_info.assert_called_once()

    async def test_stream_422(
        self,
        test_api_client: AsyncClient,
        mock_group_service: Mock,
        patched_stream_builder: AsyncMock,
        mock_runner: Mock,
        mock_storage: Mock,
    ):
        async def _stream_run_and_raise(*args: Any, **kwargs: Any):  # pyright: ignore[reportUnknownParameterType]
            yield RunOutput({"say_hello": "hell"})
            raise InvalidGenerationError("argggg", provider=Provider.OPEN_AI)

        patched_stream_builder.side_effect = _stream_run_and_raise

        mock_storage.tasks.get_task_info.return_value = TaskInfo(
            task_id="task_id",
            name="task_name",
            is_public=True,
            ban=None,
        )

        payloads = await self._stream_run(test_api_client)
        assert payloads == [
            {
                "run_id": "1",
                "task_output": {"say_hello": "hell"},
            },
            {
                "error": {
                    "title": "Error",
                    "code": "invalid_generation",
                    "details": {
                        "provider": "openai",
                        "provider_error": None,
                        "provider_options": None,
                        "provider_status_code": None,
                    },
                    "message": "argggg",
                    "status_code": 400,
                },
            },
        ]
        mock_storage.tasks.get_task_info.assert_called_once()

    async def test_run_banned_task(
        self,
        test_api_client: AsyncClient,
        mock_group_service: Mock,
        patch_run_from_builder: Mock,
        mock_storage: Mock,
    ):
        patch_run_from_builder.return_value = AgentRun(
            id="blabla",
            task_id="123",
            task_schema_id=1,
            task_input_hash="1",
            task_output_hash="1",
            task_input={},
            task_output={},
            group=TaskGroup(iteration=1),
        )
        mock_storage.tasks.get_task_info.return_value = TaskInfo(
            task_id="task_id",
            name="task_name",
            is_public=True,
            ban=Ban(
                reason="task_run_non_compliant",
                banned_at=datetime.now(timezone.utc),
                related_ids=["related_id"],
            ),
        )

        res = await test_api_client.post(
            "/test/tasks/123/schemas/1/run",
            json={
                "task_input": {"input": 1},
                "group": {
                    "iteration": 1,
                },
                "metadata": {"meta": "data"},
            },
        )

        assert res.status_code == 400
        assert res.json()["error"]["code"] == "task_banned"
        mock_storage.tasks.get_task_info.assert_called_once()

    async def test_invalid_input_is_accepted(
        self,
        test_api_client: AsyncClient,
        mock_group_service: Mock,
        mock_runner: Mock,
        mock_storage: Mock,
        patch_run_from_builder: Mock,
    ):
        patch_run_from_builder.return_value = task_run_ser()
        mock_storage.tasks.get_task_info.return_value = TaskInfo(
            task_id="task_id",
            name="task_name",
            is_public=True,
            ban=None,
        )

        res = await test_api_client.post(
            "/test/tasks/123/schemas/1/run",
            json={
                "task_input": {"name": 1},
                "group": {
                    "iteration": 1,
                },
                "metadata": {"meta": "data"},
            },
        )

        assert res.status_code == 200

        mock_storage.tasks.get_task_info.assert_called_once()


class TestRun:
    @pytest.mark.parametrize("path", ["agents", "tasks"])
    async def test_run_version_changed(
        self,
        test_api_client: AsyncClient,
        mock_runner: Mock,
        patch_run_from_builder: Mock,
        hello_task: SerializableTaskVariant,
        path: str,
    ):
        # Actually testing the underlying run service
        # Because it returns a Response object for now...
        patch_run_from_builder.return_value = AgentRun(
            id="blabla",
            task_id=hello_task.id,
            task_schema_id=hello_task.task_schema_id,
            task_input_hash="1",
            task_output_hash="1",
            group=TaskGroup(
                iteration=1,
                properties=TaskGroupProperties(model="gpt-4o", instructions="You are a helpful assistant."),
            ),
            task_input={"name": ""},
            task_output={"say_hello": ""},
            version_changed=True,
        )

        res = await test_api_client.post(
            f"/v1/_/{path}/123/schemas/1/run",
            json={
                "task_input": {"name": ""},
                "version": "production",
            },
        )

        assert res.status_code == 200
        raw_res = res.json()
        assert raw_res["task_output"] == {"say_hello": ""}
        assert raw_res["version"]["properties"] == {
            "has_templated_instructions": False,
            "instructions": "You are a helpful assistant.",
            "model": "gpt-4o",
        }

    @pytest.mark.parametrize("path", ["agents", "tasks"])
    async def test_run_no_version_change(
        self,
        test_api_client: AsyncClient,
        mock_runner: Mock,
        patch_run_from_builder: Mock,
        hello_task: SerializableTaskVariant,
        path: str,
    ):
        # Actually testing the underlying run service
        # Because it returns a Response object for now...
        patch_run_from_builder.return_value = task_run_ser(
            task=hello_task,
            task_input={"name": ""},
            task_output={"say_hello": ""},
            group=TaskGroup(
                iteration=1,
                properties=TaskGroupProperties(model="gpt-4o", instructions="You are a helpful assistant."),
            ),
        )

        res = await test_api_client.post(
            f"/v1/_/{path}/123/schemas/1/run",
            json={
                "task_input": {"name": ""},
                "version": "production",
            },
        )

        assert res.status_code == 200
        raw_res = res.json()
        assert raw_res["task_output"] == {"say_hello": ""}
        assert raw_res["version"]["properties"] == {"model": "gpt-4o"}


class TestReply:
    @freeze_time("2025-04-17T12:56:41.413541")
    async def test_reply(
        self,
        test_api_client: AsyncClient,
        mock_runner: Mock,
        patch_run_from_builder: Mock,
        mock_runs_service: Mock,
        hello_task: SerializableTaskVariant,
    ):
        mock_runs_service.run_by_id.return_value = AgentRun(
            id="blabla",
            task_id="123",
            task_schema_id=1,
            task_input_hash="1",
            task_output_hash="1",
            group=TaskGroup(iteration=1),
            task_input={},
            task_output={},
            llm_completions=[
                LLMCompletion(
                    messages=[
                        {"role": "user", "content": "Hello"},
                    ],
                    usage=LLMUsage(),
                    provider=Provider.OPEN_AI,
                ),
            ],
        )
        # Actually testing the underlying run service
        # Because it returns a Response object for now...
        patch_run_from_builder.return_value = task_run_ser(
            task=hello_task,
            group=TaskGroup(
                id="1",
                iteration=1,
                properties=TaskGroupProperties(model="gpt-4o", instructions="You are a helpful assistant."),
            ),
            task_input={"name": ""},
            task_output={"say_hello": ""},
            tool_call_requests=[ToolCallRequestWithID(id="1", tool_name="test_tool", tool_input_dict={"arg": "value"})],
        )

        res = await test_api_client.post(
            "/v1/_/agents/123/runs/abcd/reply",
            json={
                "user_message": "Hello",
            },
        )

        assert res.status_code == 200
        assert res.json() == {
            "duration_seconds": 1.0,
            "id": "run_id",
            "feedback_token": "eyJ0IjoxLCJ1IjoxLCJyIjoicnVuX2lkIn0=.l70649xjrowih8DX75xLBkWxa3NFmeMbaAYiYtiZPKM=",
            "task_output": {"say_hello": ""},
            "tool_call_requests": [
                {
                    "id": "1",
                    "input": {
                        "arg": "value",
                    },
                    "name": "test_tool",
                },
            ],
            "version": {
                "id": "1",
                "properties": {
                    "model": "gpt-4o",
                },
            },
        }


class TestRunRequestValidation:
    @pytest.mark.parametrize(
        "private_fields,expected_contains",
        [
            pytest.param(["task_input"], ["task_input"], id="task_input_only"),
            pytest.param(["task_output"], ["task_output"], id="task_output_only"),
            pytest.param(["task_input", "task_output"], ["task_input", "task_output"], id="both_task_input_and_output"),
            pytest.param(
                ["task_input.image", "metadata.secret"],
                ["task_input.image", "metadata.secret"],
                id="custom_field_paths",
            ),
        ],
    )
    def test_private_fields_accepts_task_input_and_task_output(
        self,
        private_fields: list[str],
        expected_contains: list[str],
    ):
        """Test that private_fields accepts both 'task_input' and 'task_output' as valid literal values.

        This test ensures that the private_fields type annotation correctly includes both
        'task_input' and 'task_output' (not a duplicate 'task_input').
        """
        request = RunRequest.model_validate(
            {
                "task_input": {"test": "data"},
                "version": 1,
                "private_fields": private_fields,
            },
        )
        assert request.private_fields
        for expected_field in expected_contains:
            assert expected_field in request.private_fields
