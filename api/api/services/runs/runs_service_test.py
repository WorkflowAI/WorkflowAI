from base64 import b64encode
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pytest_httpx import HTTPXMock

from api.services.runs.runs_service import (
    LLMCompletionTypedMessages,
    RunsService,
)
from core.domain.agent_run import AgentRun
from core.domain.analytics_events.analytics_events import RanTaskEventProperties
from core.domain.events import RunCreatedEvent
from core.domain.fields.file import File
from core.domain.llm_completion import LLMCompletion
from core.domain.llm_usage import LLMUsage
from core.domain.models import Model, Provider
from core.domain.task_group import TaskGroup
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_io import RawMessagesSchema, RawStringMessageSchema, SerializableTaskIO
from core.domain.task_run_query import SerializableTaskRunQuery
from core.domain.task_variant import SerializableTaskVariant
from core.domain.tool_call import ToolCallRequestWithID
from core.providers.base.abstract_provider import AbstractProvider
from core.providers.base.models import ImageContentDict, ImageURLDict, StandardMessage
from core.utils.schema_sanitation import streamline_schema
from tests.models import review, task_run_ser
from tests.utils import mock_aiter


@pytest.fixture()
def mock_provider(mock_provider_factory: AsyncMock):
    provider = AsyncMock(spec=AbstractProvider)
    mock_provider_factory.get_provider.return_value = provider

    def _finalize_completion(model: Model, completion: LLMCompletion, timeout: float | None):
        completion.usage.prompt_cost_usd = 1
        completion.usage.completion_cost_usd = 2
        return completion

    provider.finalize_completion.side_effect = _finalize_completion
    return provider


@pytest.fixture()
def runs_service(
    mock_storage: AsyncMock,
    mock_provider_factory: AsyncMock,
    mock_event_router: AsyncMock,
    mock_analytics_service: AsyncMock,
    mock_file_storage: AsyncMock,
) -> RunsService:
    return RunsService(
        storage=mock_storage,
        provider_factory=mock_provider_factory,
        event_router=mock_event_router,
        analytics_service=mock_analytics_service,
        file_storage=mock_file_storage,
    )


def _llm_completion(
    messages: list[dict[str, Any]] | None = None,
    usage: LLMUsage | None = None,
    model: Model | None = None,
    response: str | None = None,
    tool_calls: list[ToolCallRequestWithID] | None = None,
    provider: Provider = Provider.AMAZON_BEDROCK,
    duration_seconds: float | None = None,
):
    return LLMCompletion(
        messages=messages or [],
        model=model,
        usage=usage or LLMUsage(),
        response=response,
        tool_calls=tool_calls,
        provider=provider,
        duration_seconds=duration_seconds,
    )


class TestStoreTaskRun:
    @pytest.fixture()
    def non_legacy_task(self):
        return SerializableTaskVariant(
            input_schema=SerializableTaskIO(
                version="input_version",
                json_schema=streamline_schema(
                    {"type": "object", "properties": {"image": {"$ref": "#/$defs/File", "format": "image"}}},
                ),
            ),
            output_schema=SerializableTaskIO(
                json_schema={},
                version="output_version",
            ),
            id="test_task",
            task_schema_id=1,
            name="test_task",
        )

    @pytest.fixture()
    def legacy_task(self, non_legacy_task: SerializableTaskVariant):
        non_legacy_task.input_schema.json_schema = {
            "$defs": {
                "Image": {
                    "type": "object",
                    "properties": {
                        "data": {"type": "string"},
                        "name": {"type": "string"},
                        "content_type": {"type": "string"},
                    },
                    "required": ["data", "name", "content_type"],
                },
            },
            "type": "object",
            "properties": {"image": {"$ref": "#/$defs/Image"}},
        }
        return non_legacy_task

    @pytest.fixture()
    def non_legacy_task_run(self):
        return AgentRun(
            task_id="test_task",
            task_input={
                "image": {
                    "url": "https://test-url.com/file",
                },
            },
            task_output={},
            id="test_id",
            task_schema_id=1,
            task_input_hash="test_input_hash",
            task_output_hash="test_output_hash",
            group=TaskGroup(
                id="test_group_id",
                iteration=1,
                properties=TaskGroupProperties(
                    model=Model.CLAUDE_3_5_SONNET_20240620.value,
                    provider=Provider.AMAZON_BEDROCK.value,
                ),
            ),
            llm_completions=[_llm_completion(provider=Provider.AMAZON_BEDROCK)],
        )

    @pytest.fixture()
    def legacy_task_run(self, non_legacy_task_run: AgentRun):
        non_legacy_task_run.task_input["image"] = {
            "data": "1234",
            "name": "test_name",
            "content_type": "image",
        }
        return non_legacy_task_run

    @pytest.fixture(autouse=True)
    def mock_store_task_run_resource(self, mock_storage: Mock):
        async def store(
            task_variant: SerializableTaskVariant,
            task_run: AgentRun,
            *args: Any,
            **kwargs: Any,
        ):
            return task_run

        mock_storage.store_task_run_resource.side_effect = store

    async def test_store_task_run_with_files(
        self,
        non_legacy_task: SerializableTaskVariant,
        non_legacy_task_run: AgentRun,
        runs_service: RunsService,
        mock_storage: Mock,
        mock_file_storage: Mock,
        mock_provider_factory: Mock,
        mock_provider: Mock,
        mock_event_router: AsyncMock,
        mock_analytics_service: AsyncMock,
        httpx_mock: HTTPXMock,
    ):
        httpx_mock.add_response(url="https://test-url.com/file", method="GET", status_code=200, content=b"1234")
        mock_file_storage.store_file = AsyncMock(return_value="https://test-url.com/file-2")

        # Execute
        result = await runs_service.store_task_run(
            task_variant=non_legacy_task,
            task_run=non_legacy_task_run.model_copy(),
            trigger="user",
        )

        # Verify
        assert non_legacy_task_run.llm_completions
        assert mock_file_storage.store_file.call_count == 1
        mock_provider_factory.get_provider.assert_called_once_with(Provider.AMAZON_BEDROCK)
        mock_provider.finalize_completion.assert_awaited_once_with(
            Model.CLAUDE_3_5_SONNET_20240620,
            non_legacy_task_run.llm_completions[0],
            timeout=None,
        )
        mock_storage.store_task_run_resource.assert_awaited_once()

        stored_task_run = mock_storage.store_task_run_resource.call_args[0][1]
        assert isinstance(stored_task_run, AgentRun)
        assert stored_task_run.llm_completions
        assert stored_task_run.llm_completions[0].usage.prompt_cost_usd == 1
        assert stored_task_run.llm_completions[0].usage.completion_cost_usd == 2
        stored_task_run.llm_completions = non_legacy_task_run.llm_completions
        # This works because the same object is returned
        assert stored_task_run == result

        # Verify file data was modified
        stored_file = stored_task_run.task_input["image"]
        assert stored_file == {
            "url": "https://test-url.com/file",
            "storage_url": "https://test-url.com/file-2",
        }

        mock_event_router.assert_called_once_with(RunCreatedEvent(run=stored_task_run))
        mock_analytics_service.send_event.assert_called_once()
        # the call arg is a lambda so we need to call it to get the event properties
        event_properties = mock_analytics_service.send_event.call_args[0][0]()

        assert event_properties == RanTaskEventProperties.from_task_run(stored_task_run, "user")

    async def test_with_files_for_raw_messages(
        self,
        non_legacy_task_run: AgentRun,
        runs_service: RunsService,
        mock_storage: Mock,
        mock_file_storage: Mock,
    ):
        """Check that files are correctly stored when using messages"""
        variant = SerializableTaskVariant(
            input_schema=RawMessagesSchema,
            output_schema=RawStringMessageSchema,
            id="test_task",
            task_schema_id=1,
            name="test_task",
        )
        non_legacy_task_run.task_input = {
            "workflowai.messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            # File will automatically fill the data and content_type fields
                            "file": File(url="data:image/png;base64,aGVsbG8K").model_dump(mode="json"),
                        },
                    ],
                },
            ],
        }

        mock_file_storage.store_file = AsyncMock(return_value="https://test-url.com/file-2")

        # Execute
        result = await runs_service.store_task_run(
            task_variant=variant,
            task_run=non_legacy_task_run.model_copy(),
            trigger="user",
        )

        # Verify
        assert mock_file_storage.store_file.call_count == 1
        assert result.task_input == {
            "workflowai.messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "file": {
                                "content_type": "image/png",
                                "url": "https://test-url.com/file-2",
                                "storage_url": "https://test-url.com/file-2",
                            },
                        },
                    ],
                },
            ],
        }

    async def test_store_task_run_with_files_in_output_as_base64(
        self,
        non_legacy_task: SerializableTaskVariant,
        non_legacy_task_run: AgentRun,
        runs_service: RunsService,
        mock_storage: Mock,
        mock_file_storage: Mock,
        mock_provider_factory: Mock,
        mock_provider: Mock,
        mock_event_router: AsyncMock,
        mock_analytics_service: AsyncMock,
        httpx_mock: HTTPXMock,
    ):
        non_legacy_task.input_schema.json_schema = streamline_schema(
            {"type": "object", "properties": {"text": {"type": "string"}}},
        )
        non_legacy_task.output_schema.json_schema = streamline_schema(
            {"type": "object", "properties": {"image": {"$ref": "#/$defs/File", "format": "image"}}},
        )
        non_legacy_task_run.task_input = {"text": "hello"}
        non_legacy_task_run.task_output["image"] = {
            "data": b64encode(b"1234").decode(),
            "content_type": "image/png",
        }

        mock_file_storage.store_file = AsyncMock(return_value="https://test-url.com/file-2")

        # Execute
        result = await runs_service.store_task_run(
            task_variant=non_legacy_task,
            task_run=non_legacy_task_run.model_copy(),
            trigger="user",
        )

        # Verify
        assert mock_file_storage.store_file.call_count == 1
        assert non_legacy_task_run.llm_completions
        mock_provider_factory.get_provider.assert_called_once_with(Provider.AMAZON_BEDROCK)
        mock_provider.finalize_completion.assert_awaited_once_with(
            Model.CLAUDE_3_5_SONNET_20240620,
            non_legacy_task_run.llm_completions[0],
            timeout=None,
        )
        mock_storage.store_task_run_resource.assert_awaited_once()

        stored_task_run = mock_storage.store_task_run_resource.call_args[0][1]
        assert isinstance(stored_task_run, AgentRun)
        # This works because the same object is returned
        assert stored_task_run == result

        # Verify file data was modified
        stored_file = stored_task_run.task_output["image"]
        assert stored_file == {
            "content_type": "image/png",
            "url": "https://test-url.com/file-2",
            "storage_url": "https://test-url.com/file-2",
        }

    async def test_store_task_run_with_files_in_output_as_url(
        self,
        non_legacy_task: SerializableTaskVariant,
        non_legacy_task_run: AgentRun,
        runs_service: RunsService,
        mock_storage: Mock,
        mock_file_storage: Mock,
        mock_provider_factory: Mock,
        mock_provider: Mock,
        mock_event_router: AsyncMock,
        mock_analytics_service: AsyncMock,
        httpx_mock: HTTPXMock,
    ):
        non_legacy_task.input_schema.json_schema = streamline_schema(
            {"type": "object", "properties": {"text": {"type": "string"}}},
        )
        non_legacy_task.output_schema.json_schema = streamline_schema(
            {"type": "object", "properties": {"image": {"$ref": "#/$defs/File", "format": "image"}}},
        )
        non_legacy_task_run.task_input = {"text": "hello"}
        non_legacy_task_run.task_output["image"] = {
            "url": "https://test-url.com/file.png",
        }

        httpx_mock.add_response(url="https://test-url.com/file.png", method="GET", status_code=200, content=b"1234")

        mock_file_storage.store_file = AsyncMock(return_value="https://test-url.com/file-2")

        # Execute
        result = await runs_service.store_task_run(
            task_variant=non_legacy_task,
            task_run=non_legacy_task_run.model_copy(),
            trigger="user",
        )

        # Verify
        assert non_legacy_task_run.llm_completions
        assert mock_file_storage.store_file.call_count == 1
        mock_provider_factory.get_provider.assert_called_once_with(Provider.AMAZON_BEDROCK)
        mock_provider.finalize_completion.assert_awaited_once_with(
            Model.CLAUDE_3_5_SONNET_20240620,
            non_legacy_task_run.llm_completions[0],
            timeout=None,
        )
        mock_storage.store_task_run_resource.assert_awaited_once()

        stored_task_run = mock_storage.store_task_run_resource.call_args[0][1]
        assert isinstance(stored_task_run, AgentRun)
        # This works because the same object is returned
        assert stored_task_run == result

        # Verify file data was modified
        stored_file = stored_task_run.task_output["image"]
        assert stored_file == {
            "content_type": "image/png",
            "url": "https://test-url.com/file.png",
            "storage_url": "https://test-url.com/file-2",
        }
        assert stored_task_run.task_input["text"] == "hello"

        assert httpx_mock.get_request(url="https://test-url.com/file.png")

    async def test_store_task_run_without_files(
        self,
        runs_service: RunsService,
        mock_storage: Mock,
        mock_file_storage: Mock,
        non_legacy_task: SerializableTaskVariant,
        non_legacy_task_run: AgentRun,
    ):
        non_legacy_task.input_schema.json_schema = {"type": "object", "properties": {"text": {"type": "string"}}}
        non_legacy_task_run.task_input = {"text": "hello"}

        # Execute
        result = await runs_service.store_task_run(
            task_variant=non_legacy_task,
            task_run=non_legacy_task_run.model_copy(),
            trigger="user",
        )

        # Verify
        mock_file_storage.store_file.assert_not_called()
        mock_storage.store_task_run_resource.assert_awaited_with(
            non_legacy_task,
            result,  # store_task_runs_resource is the same as what is returned. The comparison is below
            None,  # user_identifier
            None,  # source
        )

        excluded = {"task_input_preview", "task_output_preview"}
        assert result.model_dump(exclude=excluded) == non_legacy_task_run.model_dump(exclude=excluded)

    async def test_compute_preview_error(
        self,
        runs_service: RunsService,
        non_legacy_task: SerializableTaskVariant,
        non_legacy_task_run: AgentRun,
    ):
        non_legacy_task.input_schema.json_schema = {"type": "object", "properties": {"text": {"type": "string"}}}
        non_legacy_task_run.task_input = {"text": "hello"}

        # Patch the assign_run_previews to raise an error
        with patch("api.services.runs.runs_service.assign_run_previews", side_effect=Exception("test")):
            result = await runs_service.store_task_run(
                task_variant=non_legacy_task,
                task_run=non_legacy_task_run.model_copy(),
                trigger="user",
            )

        assert result.task_input_preview == ""
        assert result.task_output_preview == ""


class TestStripPrivateFields:
    @pytest.mark.parametrize(("is_input"), (True, False))
    @pytest.mark.parametrize(
        "input,fields,expected",
        (
            ({"hello": "world"}, [""], {}),  # entire field
            ({"a": {"b": "c"}, "d": "e"}, [".a"], {"d": "e"}),  # single key
            ({"a": {"b": "c"}, "d": "e"}, [".a.b", ".d"], {"a": {}}),  # multiple keys
            ({"a": {"b": "c"}}, [".a.b", ".a"], {}),  # overlapping keys
            ({"a": "b"}, ["c.b"], {"a": "b"}),  # Non existing key
        ),
    )
    def test_strip_private_fields_input(
        self,
        input: dict[str, Any],
        fields: list[str],
        expected: dict[str, Any],
        is_input: bool,
        runs_service: RunsService,
    ):
        prefix = "task_input" if is_input else "task_output"

        task_run = task_run_ser()
        if is_input:
            task_run.task_input = input
        else:
            task_run.task_output = input

        task_run.private_fields = {f"{prefix}{field}" for field in fields}

        runs_service._strip_private_fields(task_run)  # pyright: ignore [reportPrivateUsage]
        final = task_run.task_input if is_input else task_run.task_output
        assert final == expected

    def test_both_input_and_output(self, runs_service: RunsService):
        task_run = task_run_ser()
        task_run.task_input = {"a": "b"}
        task_run.task_output = {"c": "d"}
        task_run.private_fields = {"task_input", "task_output"}
        runs_service._strip_private_fields(task_run)  # pyright: ignore [reportPrivateUsage]
        assert task_run.task_input == {}
        assert task_run.task_output == {}


class TestComputeCost:
    async def test_compute_cost_no_provider(
        self,
        runs_service: RunsService,
        mock_provider_factory: Mock,
        mock_provider: Mock,
    ):
        task_run = task_run_ser()
        task_run.group.properties.model = Model.CLAUDE_3_5_SONNET_20240620.value
        task_run.group.properties.provider = None
        task_run.llm_completions = [
            _llm_completion(provider=Provider.AMAZON_BEDROCK),
            # Add a message to be able to distinguish between the two completions
            _llm_completion(provider=Provider.AMAZON_BEDROCK, messages=[{"role": "user"}]),
        ]
        task_run.cost_usd = 0.0

        def _finalize_completion(model: Model, completion: LLMCompletion, timeout: float | None):
            assert model == Model.CLAUDE_3_5_SONNET_20240620
            if completion.messages:
                completion.usage.prompt_cost_usd = 3.0
                completion.usage.completion_cost_usd = 4.0
            else:
                completion.usage.prompt_cost_usd = 1.0
                completion.usage.completion_cost_usd = 2.0

        mock_provider.finalize_completion.side_effect = _finalize_completion

        await runs_service._compute_cost(task_run, mock_provider_factory)  # pyright: ignore [reportPrivateUsage]
        assert task_run.cost_usd == 10.0

        assert mock_provider.finalize_completion.call_count == 2
        # Bedrock is the provider used for pricing here
        assert mock_provider_factory.get_provider.call_count == 2
        assert all(c[0][0] == Provider.AMAZON_BEDROCK for c in mock_provider_factory.get_provider.call_args_list)

    async def test_compute_cost_with_provider(
        self,
        runs_service: RunsService,
        mock_provider_factory: Mock,
        mock_provider: Mock,
    ):
        task_run = task_run_ser()
        task_run.group.properties.model = Model.CLAUDE_3_5_SONNET_20240620.value
        # Now we force a provider
        task_run.group.properties.provider = Provider.ANTHROPIC.value
        task_run.llm_completions = [
            _llm_completion(provider=Provider.ANTHROPIC),
            _llm_completion(provider=Provider.ANTHROPIC, messages=[{"role": "user"}]),
        ]
        task_run.cost_usd = 0.0

        def _finalize_completion(model: Model, completion: LLMCompletion, timeout: float | None):
            assert model == Model.CLAUDE_3_5_SONNET_20240620
            if completion.messages:
                completion.usage.prompt_cost_usd = 3.1
                completion.usage.completion_cost_usd = 4.1
            else:
                completion.usage.prompt_cost_usd = 1.1
                completion.usage.completion_cost_usd = 2.1

        mock_provider.finalize_completion.side_effect = _finalize_completion

        await runs_service._compute_cost(task_run, mock_provider_factory)  # pyright: ignore [reportPrivateUsage]
        assert task_run.cost_usd == pytest.approx(10.4)  # pyright: ignore [reportUnknownMemberType]

        assert mock_provider.finalize_completion.call_count == 2
        # Bedrock is the provider used for pricing here
        assert mock_provider_factory.get_provider.call_count == 2
        assert all(c[0][0] == Provider.ANTHROPIC for c in mock_provider_factory.get_provider.call_args_list)

    async def test_compute_cost_different_provider_and_model(
        self,
        runs_service: RunsService,
        mock_provider_factory: Mock,
        mock_provider: Mock,
    ):
        task_run = task_run_ser()
        task_run.group.properties.model = Model.CLAUDE_3_5_SONNET_20240620.value
        task_run.llm_completions = [
            _llm_completion(provider=Provider.ANTHROPIC),
            _llm_completion(provider=Provider.AMAZON_BEDROCK, messages=[{"role": "user"}]),
            _llm_completion(
                provider=Provider.OPEN_AI,
                model=Model.GPT_3_5_TURBO_0125,
                messages=[{"role": "user"}],
            ),
        ]
        task_run.cost_usd = 0.0

        await runs_service._compute_cost(task_run, mock_provider_factory)  # pyright: ignore [reportPrivateUsage]

        assert mock_provider.finalize_completion.call_count == 3
        assert [c[0][0] for c in mock_provider_factory.get_provider.call_args_list] == [
            Provider.ANTHROPIC,
            Provider.AMAZON_BEDROCK,
            Provider.OPEN_AI,
        ]


class TestLLMCompletions:
    async def test_llm_completions(
        self,
        runs_service: RunsService,
        mock_storage: Mock,
        mock_provider_factory: Mock,
    ):
        # Setup mock data
        task_run = task_run_ser()
        task_run.metadata = {"workflowai.provider": Provider.FIREWORKS.value}
        task_run.llm_completions = [
            _llm_completion(
                messages=[{"role": "user", "content": "Hello"}],
                response="Hi there!",
                usage=LLMUsage(prompt_cost_usd=1, completion_cost_usd=2),
                # That's the provider that should be used to sanitize the completion
                provider=Provider.OPEN_AI,
            ),
        ]

        mock_storage.task_runs.fetch_task_run_resource.return_value = task_run
        mock_provider = Mock()
        mock_provider.standardize_messages.return_value = [StandardMessage(role="user", content="Hello")]
        mock_provider_factory.get_provider.return_value = mock_provider
        # Execute
        result = await runs_service.llm_completions_by_id(("a", 0), "test_id")

        # Verify
        mock_storage.task_runs.fetch_task_run_resource.assert_awaited_once_with(
            ("a", 0),
            "test_id",
            include={"llm_completions", "metadata", "group.properties"},
        )
        assert len(result.completions) == 1
        assert isinstance(result.completions[0], LLMCompletionTypedMessages)
        assert len(result.completions[0].messages) == 1
        assert result.completions[0].messages[0]["role"] == "user"
        assert result.completions[0].messages[0]["content"] == "Hello"
        assert result.completions[0].response == "Hi there!"
        assert result.completions[0].usage.prompt_cost_usd == 1
        assert result.completions[0].usage.completion_cost_usd == 2
        mock_provider_factory.get_provider.assert_called_once_with(Provider.OPEN_AI)

    async def test_llm_completions_with_image_content(
        self,
        runs_service: RunsService,
        mock_storage: Mock,
        mock_provider_factory: Mock,
    ):
        # Setup mock data
        task_run = task_run_ser()
        task_run.metadata = {"workflowai.provider": Provider.FIREWORKS.value}
        task_run.llm_completions = [
            LLMCompletion(
                messages=[{"role": "user", "content": "Hello"}],
                response="Hi there!",
                usage=LLMUsage(prompt_cost_usd=1, completion_cost_usd=2),
                provider=Provider.FIREWORKS,
                duration_seconds=10,
            ),
        ]

        mock_storage.task_runs.fetch_task_run_resource.return_value = task_run
        mock_provider = Mock()
        mock_provider.standardize_messages.return_value = [
            StandardMessage(
                role="user",
                content=[ImageContentDict(image_url=ImageURLDict(url="https://test-url.com/image"), type="image_url")],
            ),
        ]
        mock_provider_factory.get_provider.return_value = mock_provider
        # Execute
        result = await runs_service.llm_completions_by_id(("a", 0), "test_id")

        # Verify
        mock_storage.task_runs.fetch_task_run_resource.assert_awaited_once_with(
            ("a", 0),
            "test_id",
            include={"llm_completions", "metadata", "group.properties"},
        )
        assert len(result.completions) == 1
        assert isinstance(result.completions[0], LLMCompletionTypedMessages)
        assert len(result.completions[0].messages) == 1
        assert result.completions[0].messages[0]["role"] == "user"
        assert result.completions[0].messages[0]["content"][0]["image_url"]["url"] == "https://test-url.com/image"  # type: ignore
        assert result.completions[0].response == "Hi there!"
        assert result.completions[0].usage.prompt_cost_usd == 1
        assert result.completions[0].usage.completion_cost_usd == 2
        assert result.completions[0].duration_seconds == 10
        mock_provider_factory.get_provider.assert_called_once_with(Provider.FIREWORKS)


class TestListRuns:
    async def test_list_runs(
        self,
        runs_service: RunsService,
        mock_storage: Mock,
    ):
        mock_storage.task_runs.fetch_task_run_resources.return_value = mock_aiter(
            task_run_ser(task_input_hash="1", task_output_hash="2"),
            task_run_ser(task_input_hash="3", task_output_hash="4"),
        )
        mock_storage.reviews.reviews_for_eval_hashes.return_value = mock_aiter(
            review(task_input_hash="1", task_output_hash="2"),
        )
        result = await runs_service.list_runs(0, SerializableTaskRunQuery(task_id="a"))
        assert len(result.items) == 2
        runs = sorted(result.items, key=lambda x: x.task_input_hash)
        assert runs[0].user_review == "positive"
        assert runs[1].user_review is None

    async def test_list_runs_no_reviews(self, runs_service: RunsService, mock_storage: Mock):
        mock_storage.task_runs.fetch_task_run_resources.return_value = mock_aiter(
            task_run_ser(task_input_hash="1", task_output_hash="2"),
            task_run_ser(task_input_hash="3", task_output_hash="4"),
        )
        result = await runs_service.list_runs(0, SerializableTaskRunQuery(task_id="a"))
        assert len(result.items) == 2


class TestRunById:
    async def test_run_by_id(self, runs_service: RunsService, mock_storage: AsyncMock):
        mock_storage.task_runs.fetch_task_run_resource.return_value = task_run_ser(
            task_input_hash="1",
            task_output_hash="2",
        )
        mock_storage.reviews.reviews_for_eval_hashes.return_value = mock_aiter(
            review(task_input_hash="1", task_output_hash="2"),
        )
        result = await runs_service.run_by_id(("a", 0), "test_id")
        assert result.task_input_hash == "1"
        assert result.task_output_hash == "2"
        assert result.user_review == "positive"

    async def test_run_by_id_no_review(
        self,
        runs_service: RunsService,
        mock_storage: AsyncMock,
    ):
        mock_storage.task_runs.fetch_task_run_resource.return_value = task_run_ser(
            task_input_hash="1",
            task_output_hash="2",
        )
        mock_storage.reviews.reviews_for_eval_hashes.return_value = mock_aiter()
        result = await runs_service.run_by_id(("a", 0), "test_id")
        assert result.user_review is None
