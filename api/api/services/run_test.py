import json
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.responses import StreamingResponse

from core.domain.run_output import RunOutput
from core.domain.task_run_builder import TaskRunBuilder
from core.domain.task_variant import SerializableTaskVariant
from core.domain.users import UserIdentifier
from core.runners.abstract_runner import AbstractRunner
from core.storage.azure.azure_blob_file_storage import AzureBlobFileStorage
from tests import models
from tests.dummy_runner import DummyRunner
from tests.utils import mock_aiter

from .run import RunService


@pytest.fixture(scope="function")
def run_service(
    mock_wai: Mock,
    mock_storage: Mock,
    mock_event_router: Mock,
    mock_group_service: Mock,
    mock_analytics_service: Mock,
) -> RunService:
    return RunService(
        storage=mock_storage,
        event_router=mock_event_router,
        group_service=mock_group_service,
        analytics_service=mock_analytics_service,
        user=UserIdentifier(user_id="test_user_id", user_email="test_user_email@example.com"),
    )


@pytest.fixture(scope="function")
def mock_runner(hello_task: SerializableTaskVariant) -> AbstractRunner[Any]:
    mock = Mock(spec=AbstractRunner)
    mock.task = hello_task
    return mock


@pytest.fixture(scope="function")
def mock_file_storage() -> Mock:
    return Mock(name="file_storage", spec=AzureBlobFileStorage)


def _chunk_serializer(run_id: str, task_output: RunOutput):
    from api.routers.run import RunTaskStreamChunk

    return RunTaskStreamChunk.from_stream(run_id, task_output)


@pytest.fixture
def patched_run_from_builder():
    with patch("api.services.run.RunService.run_from_builder", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def patched_stream_from_builder():
    with patch("api.services.run.RunService.stream_from_builder", new_callable=AsyncMock) as mock:
        yield mock


class TestRun:
    async def test_run(
        self,
        run_service: RunService,
        patched_run_from_builder: Mock,
        mock_runner: AbstractRunner[Any],
        hello_task: SerializableTaskVariant,
    ):
        task_input = {"name": "world"}

        patched_run_from_builder.return_value = models.task_run_ser(task=hello_task)

        mock_builder = Mock(spec=TaskRunBuilder)
        mock_runner.task_run_builder = AsyncMock(return_value=mock_builder)

        response = await run_service.run(
            task_input,
            mock_runner,
            task_run_id="1",
            stream_serializer=None,
            cache="always",
            metadata={"key": "value"},
            trigger="user",
            serializer=lambda run, __: run,
            start_time=1,
        )

        patched_run_from_builder.assert_awaited_once_with(
            builder=mock_builder,
            runner=mock_runner,
            cache="always",
            trigger="user",
            store_inline=False,
            source=None,
            file_storage=None,
        )

        mock_runner.task_run_builder.assert_called_once_with(
            input=task_input,
            task_run_id="1",
            metadata={"key": "value"},
            private_fields=None,
            start_time=1,
            conversation_id=None,
        )
        assert response

    async def test_stream(
        self,
        run_service: RunService,
        patched_stream_from_builder: Mock,
        mock_runner: AbstractRunner[Any],
    ):
        task_input = {"name": "world"}

        mock_builder = AsyncMock(spec=TaskRunBuilder)
        mock_builder.id = "1"
        mock_runner.task_run_builder = AsyncMock(return_value=mock_builder)

        patched_stream_from_builder.return_value = mock_aiter({"name": "world"}, {"name": "world2"})

        response = await run_service.run(
            task_input,
            mock_runner,
            task_run_id="1",
            cache="always",
            metadata={"key": "value"},
            trigger="user",
            stream_serializer=_chunk_serializer,
            serializer=lambda run, __: run,
            start_time=1,
        )

        assert response and isinstance(response, StreamingResponse)
        mock_send = AsyncMock()
        await response.stream_response(mock_send)

        patched_stream_from_builder.assert_called_once_with(
            builder=mock_builder,
            runner=mock_runner,
            cache="always",
            trigger="user",
            user=UserIdentifier(user_id="test_user_id", user_email="test_user_email@example.com"),
            store_inline=False,
            source=None,
            file_storage=None,
        )

        mock_runner.task_run_builder.assert_called_once_with(
            input=task_input,
            task_run_id="1",
            metadata={"key": "value"},
            private_fields=None,
            start_time=1,
            conversation_id=None,
        )

    async def test_stream_with_cache(
        self,
        run_service: RunService,
        mock_cache_fetcher: Mock,
        hello_task: SerializableTaskVariant,
    ):
        runner = DummyRunner(hello_task, cache_fetcher=mock_cache_fetcher)

        task_input = {"name": "world"}

        mock_cache_fetcher.return_value = models.task_run_ser(
            task=hello_task,
            task_input={"name": "world"},
            task_output={"say_hello": "hello world"},
            group=models.task_group(iteration=1),
        )

        response = await run_service.run(
            task_input,
            runner,
            task_run_id="1",
            cache="always",
            metadata={"key": "value"},
            trigger="user",
            source=None,
            stream_serializer=_chunk_serializer,
            serializer=lambda run, __: run,
            start_time=1,
        )
        assert response and isinstance(response, StreamingResponse)
        mock_send = AsyncMock()
        await response.stream_response(mock_send)

        call_args_list = mock_send.call_args_list
        # Send is called 3 times, one for start + end and one for the actual body
        assert len(call_args_list) == 3

        assert call_args_list[0].args[0]["type"] == "http.response.start", "sanity"
        assert "body" not in call_args_list[0].args[0], "sanity"

        assert call_args_list[2].args[0]["type"] == "http.response.body", "sanity"
        assert call_args_list[2].args[0]["body"] == b"", "sanity"

        body = call_args_list[1].args[0]["body"]
        assert body.startswith(b"data: {"), "sanity"
        assert body.endswith(b"\n\n"), "sanity"

        payload = json.loads(body[6:-2])
        # Checking that the ID is actually the one from the cache
        assert payload == {"run_id": "run_id", "task_output": {"say_hello": "hello world"}}
