import datetime
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
import workflowai

from api.services.api_keys import APIKeyService
from api.services.internal_tasks.integration_service import (
    ApiKeyResult,
    IntegrationAgentInput,
    IntegrationChatMessage,
    IntegrationChatResponse,
    IntegrationService,
    MessageKind,
    RelevantRunAndAgent,
)
from api.services.runs.runs_service import RunsService
from core.agents.agent_name_suggestion_agent import (
    AgentNameSuggestionAgentOutput,
)
from core.constants import DEFAULT_AGENT_ID
from core.domain.agent_run import AgentRun
from core.domain.errors import ObjectNotFoundError
from core.domain.events import EventRouter
from core.domain.integration.integration_domain import (
    Integration,
    IntegrationKind,
)
from core.domain.integration.integration_mapping import OFFICIAL_INTEGRATIONS
from core.domain.task_variant import SerializableTaskVariant
from core.domain.users import User
from core.storage.backend_storage import BackendStorage
from tests.utils import mock_aiter


@pytest.fixture
def mock_user():
    return Mock(spec=User)


@pytest.fixture
def mock_storage():
    storage = Mock(spec=BackendStorage)
    storage.task_variants = Mock()
    storage.task_variants.get_task_variant_by_uid = AsyncMock()
    storage.task_runs = Mock()
    return storage


@pytest.fixture
def mock_event_router():
    return Mock(spec=EventRouter)


@pytest.fixture
def mock_runs_service():
    return Mock(spec=RunsService)


@pytest.fixture
def mock_api_keys_service():
    svc = Mock(spec=APIKeyService)
    svc.get_keys = AsyncMock()
    svc.create_key = AsyncMock()
    return svc


@pytest.fixture
def integration_service(
    mock_storage: BackendStorage,
    mock_event_router: EventRouter,
    mock_runs_service: RunsService,
    mock_api_keys_service: APIKeyService,
    mock_user: User,
) -> IntegrationService:
    return IntegrationService(
        storage=mock_storage,
        event_router=mock_event_router,
        runs_service=mock_runs_service,
        api_keys_service=mock_api_keys_service,
        user=mock_user,
    )


@pytest.fixture
def mock_integration() -> Integration:
    # Use the first official integration for testing

    return OFFICIAL_INTEGRATIONS[0]


class TestGetIntegrationForSlug:
    def test_get_integration_valid_slug(
        self,
        integration_service: IntegrationService,
        mock_integration: Integration,
    ):
        # Should return the integration when slug matches
        with patch(
            "api.services.internal_tasks.integration_service.OFFICIAL_INTEGRATIONS",
            [mock_integration],
        ):
            result = integration_service._get_integration_for_slug(mock_integration.slug)  # pyright: ignore[reportPrivateUsage]
            assert result == mock_integration

    def test_get_integration_invalid_slug(
        self,
        integration_service: IntegrationService,
        mock_integration: Integration,
    ):
        # Should raise if slug not found
        with patch(
            "api.services.internal_tasks.integration_service.OFFICIAL_INTEGRATIONS",
            [],  # type: ignore[reportUnknownMemberType]
        ):
            with pytest.raises(ObjectNotFoundError):
                integration_service._get_integration_for_slug(mock_integration.slug)  # pyright: ignore[reportPrivateUsage]


class TestBuildIntegrationChatAgentInput:
    async def test_build_input_with_messages(
        self,
        integration_service: IntegrationService,
    ):
        now = datetime.datetime.now()
        messages = [
            IntegrationChatMessage(
                sent_at=now,
                role="USER",
                content="Hello",
                message_kind=MessageKind.non_specific,
            ),
            IntegrationChatMessage(
                sent_at=now,
                role="ASSISTANT",
                content="Hi there",
                message_kind=MessageKind.non_specific,
            ),
        ]

        result = await integration_service._build_integration_chat_agent_input(messages, Mock(spec=Integration))  # pyright: ignore[reportPrivateUsage]

        assert isinstance(result, IntegrationAgentInput)
        assert len(result.chat_messages) == 2
        assert result.chat_messages[0].role == "USER"
        assert result.chat_messages[0].content == "Hello"
        assert result.chat_messages[1].role == "ASSISTANT"
        assert result.chat_messages[1].content == "Hi there"


class TestGetInitialCodeSnippetMessages:
    def test_get_initial_code_snippet_existing_key(
        self,
        integration_service: IntegrationService,
        mock_integration: Integration,
    ):
        now = datetime.datetime.now()
        api_key_result = ApiKeyResult(api_key="test-api-key", was_existing=True)

        result = IntegrationService._get_initial_code_snippet_messages(  # pyright: ignore[reportPrivateUsage]
            now,
            mock_integration,
            api_key_result,
        )

        assert result.role == "ASSISTANT"
        assert result.message_kind == MessageKind.api_key_code_snippet
        assert "test-api-key" in result.content
        assert "Use your existing WorkflowAI key" in result.content

    def test_get_initial_code_snippet_new_key(
        self,
        integration_service: IntegrationService,
        mock_integration: Integration,
    ):
        now = datetime.datetime.now()
        api_key_result = ApiKeyResult(api_key="test-api-key", was_existing=False)

        result = IntegrationService._get_initial_code_snippet_messages(  # pyright: ignore[reportPrivateUsage]
            now,
            mock_integration,
            api_key_result,
        )

        assert result.role == "ASSISTANT"
        assert result.message_kind == MessageKind.api_key_code_snippet
        assert "test-api-key" in result.content
        assert "Use your new WorkflowAI key" in result.content


class TestGetAgentNamingCodeSnippetMessages:
    def test_get_agent_naming_code_snippet(
        self,
        integration_service: IntegrationService,
        mock_integration: Integration,
    ):
        now = datetime.datetime.now()
        proposed_agent_name = "test-agent"

        result = IntegrationService._get_agent_naming_code_snippet_messages(  # pyright: ignore[reportPrivateUsage]
            now,
            proposed_agent_name,
            workflowai.Model.GPT_4O_LATEST.value,
            mock_integration,
        )

        assert result.role == "ASSISTANT"
        assert result.message_kind == MessageKind.agent_naming_code_snippet
        assert proposed_agent_name in result.content
        assert f"{proposed_agent_name}/" in result.content


class TestHasSentAgentNamingCodeSnippet:
    @pytest.mark.parametrize(
        "messages,expected_result",
        [
            (
                [
                    IntegrationChatMessage(
                        sent_at=datetime.datetime.now(),
                        role="ASSISTANT",
                        content="Message 1",
                        message_kind=MessageKind.non_specific,
                    ),
                ],
                False,
            ),
            (
                [
                    IntegrationChatMessage(
                        sent_at=datetime.datetime.now(),
                        role="ASSISTANT",
                        content="Message with snippet",
                        message_kind=MessageKind.agent_naming_code_snippet,
                    ),
                ],
                True,
            ),
            (
                [
                    IntegrationChatMessage(
                        sent_at=datetime.datetime.now(),
                        role="ASSISTANT",
                        content="Message 1",
                        message_kind=MessageKind.non_specific,
                    ),
                    IntegrationChatMessage(
                        sent_at=datetime.datetime.now(),
                        role="ASSISTANT",
                        content="Message with snippet",
                        message_kind=MessageKind.agent_naming_code_snippet,
                    ),
                ],
                True,
            ),
        ],
    )
    async def test_has_sent_agent_naming_code_snippet(
        self,
        integration_service: IntegrationService,
        messages: list[IntegrationChatMessage],
        expected_result: bool,
    ):
        result = await integration_service.has_sent_agent_naming_code_snippet(messages)
        assert result == expected_result


class TestGetAgentByUid:
    async def test_get_agent_by_uid(
        self,
        integration_service: IntegrationService,
    ):
        mock_agent = Mock(spec=SerializableTaskVariant)
        # override the real method with an AsyncMock that returns our agent
        integration_service.storage.task_variants.get_task_variant_by_uid = AsyncMock(return_value=mock_agent)

        result = await integration_service._get_agent_by_uid(123)  # pyright: ignore[reportPrivateUsage]
        assert result == mock_agent


class TestFindRelevantRunAndAgent:
    async def test_find_relevant_run_no_runs(
        self,
        integration_service: IntegrationService,
    ):
        start_time = datetime.datetime.now()
        # Mock list_latest_runs to return an async iterator
        integration_service.storage.task_runs.list_latest_runs = lambda *args, **kwargs: mock_aiter()  # type: ignore[reportUnknownLambdaType]

        result = await integration_service._find_relevant_run_and_agent(start_time)  # pyright: ignore[reportPrivateUsage]
        assert result is None

    async def test_find_relevant_run_default_agent(
        self,
        integration_service: IntegrationService,
    ):
        start_time = datetime.datetime.now()

        # Create a mock run
        mock_run = Mock(spec=AgentRun)
        mock_run.task_uid = 123

        # Create a mock agent with default name
        mock_agent = Mock(spec=SerializableTaskVariant)
        mock_agent.task_id = DEFAULT_AGENT_ID

        # Setup the storage mock to return our mock run and agent
        integration_service.storage.task_runs.list_latest_runs = lambda *args, **kwargs: mock_aiter(mock_run)  # type: ignore[reportUnknownLambdaType]

        # Patch the _get_agent_by_uid method to return our mock agent
        with patch.object(
            integration_service,
            "_get_agent_by_uid",
            return_value=mock_agent,
        ) as mock_get_agent:
            result = await integration_service._find_relevant_run_and_agent(start_time)  # pyright: ignore[reportPrivateUsage]

            assert result is not None
            assert result.run == mock_run
            assert result.agent == mock_agent
            mock_get_agent.assert_called_once_with(123)

    async def test_find_relevant_run_new_named_agent(
        self,
        integration_service: IntegrationService,
    ):
        start_time = datetime.datetime.now()

        # Create a mock run
        mock_run = Mock(spec=AgentRun)
        mock_run.task_uid = 123

        # Create a mock agent with custom name but created after start_time
        mock_agent = Mock(spec=SerializableTaskVariant)
        mock_agent.task_id = "custom-agent"
        mock_agent.created_at = start_time + datetime.timedelta(minutes=5)

        # Setup the storage mock to return our mock run and agent
        integration_service.storage.task_runs.list_latest_runs = lambda *args, **kwargs: mock_aiter(mock_run)  # type: ignore[reportUnknownLambdaType]

        # Patch the _get_agent_by_uid method to return our mock agent
        with patch.object(
            integration_service,
            "_get_agent_by_uid",
            return_value=mock_agent,
        ) as mock_get_agent:
            result = await integration_service._find_relevant_run_and_agent(start_time)  # pyright: ignore[reportPrivateUsage]

            assert result is not None
            assert result.run == mock_run
            assert result.agent == mock_agent
            mock_get_agent.assert_called_once_with(123)

    async def test_find_relevant_run_ignore_old_named_agent(
        self,
        integration_service: IntegrationService,
    ):
        start_time = datetime.datetime.now()

        # Create a mock run
        mock_run = Mock(spec=AgentRun)
        mock_run.task_uid = 123

        # Create a mock agent with custom name but created before start_time
        mock_agent = Mock(spec=SerializableTaskVariant)
        mock_agent.task_id = "custom-agent"
        mock_agent.created_at = start_time - datetime.timedelta(minutes=5)

        # Setup the storage mock to return our mock run and agent
        integration_service.storage.task_runs.list_latest_runs = lambda *args, **kwargs: mock_aiter(mock_run)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownLambdaType]

        # Patch the _get_agent_by_uid method to return our mock agent
        with patch.object(
            integration_service,
            "_get_agent_by_uid",
            return_value=mock_agent,
        ) as mock_get_agent:
            result = await integration_service._find_relevant_run_and_agent(start_time)  # pyright: ignore[reportPrivateUsage]

            assert result is None
            mock_get_agent.assert_called_once_with(123)


class TestGetApiKey:
    async def test_get_existing_api_key(self, integration_service: IntegrationService):
        # Mock APIKeyService to return existing keys
        mock_key = Mock()
        mock_key.partial_key = "existing-key"
        # Use AsyncMock to mock get_keys
        integration_service.api_keys_service.get_keys = AsyncMock(return_value=[mock_key])
        integration_service.api_keys_service.create_key = AsyncMock()

        result = await integration_service._get_api_key()  # pyright: ignore[reportPrivateUsage]

        assert result.api_key == "existing-key"
        assert result.was_existing is True
        integration_service.api_keys_service.get_keys.assert_awaited_once()
        integration_service.api_keys_service.create_key.assert_not_called()

    async def test_create_new_api_key(self, integration_service: IntegrationService):
        # Mock APIKeyService to return no existing keys and create a new one
        integration_service.api_keys_service.get_keys = AsyncMock(return_value=[])
        integration_service.api_keys_service.create_key = AsyncMock(return_value=(None, "new-key"))
        integration_service.user.identifier = Mock(return_value="user-id")

        result = await integration_service._get_api_key()  # pyright: ignore[reportPrivateUsage]

        assert result.api_key == "new-key"
        assert result.was_existing is False
        integration_service.api_keys_service.get_keys.assert_awaited_once()
        integration_service.api_keys_service.create_key.assert_awaited_once_with(
            "workflowai-api-key",
            "user-id",
            3,
        )


class TestStreamIntegrationChatResponse:
    @patch("api.services.internal_tasks.integration_service.integration_chat_agent")
    async def test_initial_message_empty_list(
        self,
        mock_integration_agent: workflowai.WorkflowAI,
        integration_service: IntegrationService,
        mock_integration: Integration,
    ):
        # Setup
        with (
            patch.object(
                integration_service,
                "_get_integration_for_slug",
                return_value=mock_integration,
            ),
            patch.object(
                integration_service,
                "_get_api_key",
                return_value=ApiKeyResult("test-key", False),
            ),
        ):
            # Call the method with empty messages list (initial case)
            results = [
                result
                async for result in integration_service.stream_integration_chat_response(
                    IntegrationKind.INSTRUCTOR_PYTHON,
                    [],
                )
            ]

            # Verify results
            assert len(results) == 1
            assert isinstance(results[0], IntegrationChatResponse)
            assert len(results[0].messages) == 1
            assert results[0].messages[0].role == "ASSISTANT"
            assert results[0].messages[0].message_kind == MessageKind.api_key_code_snippet
            assert "test-key" in results[0].messages[0].content

    @patch("api.services.internal_tasks.integration_service.integration_chat_agent")
    async def test_assistant_message_with_found_run_unnamed_agent(
        self,
        mock_integration_agent: Any,
        integration_service: IntegrationService,
        mock_integration: Integration,
    ):
        # Setup for testing when frontend polls and we find an unnamed agent
        now = datetime.datetime.now()
        messages = [
            IntegrationChatMessage(
                sent_at=now - datetime.timedelta(minutes=5),
                role="USER",
                content="Hello",
                message_kind=MessageKind.non_specific,
            ),
            IntegrationChatMessage(
                sent_at=now,
                role="ASSISTANT",
                content="Hi there",
                message_kind=MessageKind.non_specific,
            ),
        ]

        # Mock the run and agent
        mock_run = Mock(spec=AgentRun, group=Mock(properties=Mock(model=workflowai.Model.GPT_4O_LATEST.value)))
        mock_run.llm_completions = "some completions"

        mock_agent = Mock(spec=SerializableTaskVariant)
        mock_agent.name = DEFAULT_AGENT_ID
        mock_agent.task_id = DEFAULT_AGENT_ID

        # Mock agent name suggestion
        mock_agent_name_suggestion_output = Mock(spec=AgentNameSuggestionAgentOutput)
        mock_agent_name_suggestion_output.agent_name = "suggested-agent-name"

        # Patch methods
        with (
            patch.object(
                integration_service,
                "_get_integration_for_slug",
                return_value=mock_integration,
            ),
            patch.object(
                integration_service,
                "_find_relevant_run_and_agent",
                return_value=RelevantRunAndAgent(run=mock_run, agent=mock_agent),
            ),
            patch.object(
                integration_service,
                "has_sent_agent_naming_code_snippet",
                return_value=False,
            ),
            patch(
                "api.services.internal_tasks.integration_service.agent_name_suggestion_agent.run",
                new_callable=AsyncMock,
                return_value=Mock(output=mock_agent_name_suggestion_output),
            ),
        ):
            # Call the method
            results = [
                result
                async for result in integration_service.stream_integration_chat_response(
                    IntegrationKind.INSTRUCTOR_PYTHON,
                    messages,
                )
            ]

            # Verify results
            assert len(results) == 1
            assert isinstance(results[0], IntegrationChatResponse)
            assert len(results[0].messages) == 1
            assert results[0].messages[0].role == "ASSISTANT"
            assert results[0].messages[0].message_kind == MessageKind.agent_naming_code_snippet
            assert "suggested-agent-name" in results[0].messages[0].content

    @patch("api.services.internal_tasks.integration_service.integration_chat_agent")
    async def test_assistant_message_with_found_run_named_agent(
        self,
        mock_integration_agent: Any,
        integration_service: IntegrationService,
        mock_integration: Integration,
    ):
        # Setup for testing when frontend polls and we find a named agent
        now = datetime.datetime.now()
        messages = [
            IntegrationChatMessage(
                sent_at=now - datetime.timedelta(minutes=5),
                role="USER",
                content="Hello",
                message_kind=MessageKind.non_specific,
            ),
            IntegrationChatMessage(
                sent_at=now,
                role="ASSISTANT",
                content="Hi there",
                message_kind=MessageKind.non_specific,
            ),
        ]

        # Mock the run and agent with a name that's not the default
        mock_run = Mock(spec=AgentRun)

        mock_agent = Mock(spec=SerializableTaskVariant)
        mock_agent.name = "named-agent"
        mock_agent.task_id = "named-agent"
        mock_agent.task_schema_id = 123
        integration_service.storage.task_variants.update_task = AsyncMock()

        # Patch methods
        with (
            patch.object(
                integration_service,
                "_get_integration_for_slug",
                return_value=mock_integration,
            ),
            patch.object(
                integration_service,
                "_find_relevant_run_and_agent",
                return_value=RelevantRunAndAgent(run=mock_run, agent=mock_agent),
            ),
        ):
            # Call the method
            results = [
                result
                async for result in integration_service.stream_integration_chat_response(
                    IntegrationKind.INSTRUCTOR_PYTHON,
                    messages,
                )
            ]

            # Verify results
            assert len(results) == 1
            assert isinstance(results[0], IntegrationChatResponse)
            assert results[0].messages == []
            assert results[0].redirect_to_agent_playground is not None
            assert results[0].redirect_to_agent_playground.agent_id == "named-agent"

    @patch("api.services.internal_tasks.integration_service.integration_chat_agent")
    async def test_user_message(
        self,
        mock_integration_agent: Any,
        integration_service: IntegrationService,
        mock_integration: Integration,
    ):
        # Setup for testing user message processing
        now = datetime.datetime.now()
        messages = [
            IntegrationChatMessage(
                sent_at=now,
                role="USER",
                content="How do I use this?",
                message_kind=MessageKind.non_specific,
            ),
        ]

        # Mock the integration_chat_agent.stream output
        mock_chunk = Mock()
        mock_chunk.output.content = "Here's how to use it"
        mock_integration_agent.stream.return_value = mock_aiter(mock_chunk)

        # Patch methods
        with (
            patch.object(
                integration_service,
                "_get_integration_for_slug",
                return_value=mock_integration,
            ),
            patch.object(
                integration_service,
                "_build_integration_chat_agent_input",
                new_callable=AsyncMock,
                return_value=Mock(),
            ),
        ):
            # Call the method
            results = [
                result
                async for result in integration_service.stream_integration_chat_response(
                    IntegrationKind.INSTRUCTOR_PYTHON,
                    messages,
                )
            ]

            # Verify results
            assert len(results) == 1
            assert isinstance(results[0], IntegrationChatResponse)
            assert len(results[0].messages) == 1
            assert results[0].messages[0].role == "ASSISTANT"
            assert results[0].messages[0].content == "Here's how to use it"
            assert results[0].messages[0].message_kind == MessageKind.non_specific

            # Verify mock calls
            mock_integration_agent.stream.assert_called_once()


class TestGetIntegrationAgentChatMessages:
    def test_get_integration_agent_chat_messages(self, integration_service: IntegrationService):
        now = datetime.datetime(year=2025, month=1, day=1, hour=12, minute=0, second=0)

        secret_key = "wai-Abcdefghijklmnopqrstuvwxyz1234567890ABCDEFG"  # Valid format API key
        obfuscated_secret_key = "wai-Abcde****"

        messages = [
            IntegrationChatMessage(
                sent_at=now,
                role="USER",
                content="Hello",
                message_kind=MessageKind.non_specific,
            ),
            IntegrationChatMessage(
                sent_at=now,
                role="ASSISTANT",
                content=f"message with secret key: {secret_key}",
                message_kind=MessageKind.non_specific,
            ),
            IntegrationChatMessage(
                sent_at=now,
                role="USER",
                content=f"Another message with the same key: {secret_key} and a non-key: test-key",
                message_kind=MessageKind.non_specific,
            ),
        ]

        # Call the method on the instance
        result = integration_service._get_integration_agent_chat_messages(messages)  # pyright: ignore[reportPrivateUsage]

        assert len(result) == 3
        assert result[0].role == "USER"
        assert result[0].content == "Hello"

        assert result[1].role == "ASSISTANT"
        assert secret_key not in result[1].content
        assert obfuscated_secret_key in result[1].content
        assert f"message with secret key: {obfuscated_secret_key}" == result[1].content

        assert result[2].role == "USER"
        assert secret_key not in result[2].content
        assert obfuscated_secret_key in result[2].content
        assert "test-key" in result[2].content  # Ensure non-matching keys are not obfuscated
        assert (
            f"Another message with the same key: {obfuscated_secret_key} and a non-key: test-key" == result[2].content
        )


class TestGetMessagesPayloadForCodeSnippet:
    @pytest.fixture
    def mock_version(self):
        """Create a mock for VersionsService.EnrichedVersion."""
        version = Mock()
        version.group = Mock()
        version.group.properties = Mock()
        return version

    @pytest.fixture
    def mock_task_tuple(self):
        """Create a mock for TaskTuple."""
        from core.storage import TaskTuple

        return Mock(spec=TaskTuple)

    async def test_get_messages_payload_with_version_messages(
        self,
        integration_service: IntegrationService,
        mock_version: Mock,
        mock_task_tuple: Mock,
    ):
        # Create message mocks that have model_dump method
        message1 = Mock()
        message1.model_dump.return_value = {"role": "system", "content": "You are a helpful assistant."}
        message2 = Mock()
        message2.model_dump.return_value = {"role": "user", "content": "Hello"}

        # Set up mock version with message objects that have model_dump method
        mock_version.group.properties.messages = [message1, message2]

        # Make sure runs_service.latest_run is properly mocked
        integration_service.runs_service.latest_run = AsyncMock()

        # For testing protected methods, we need to access them directly
        # Call the method
        result = await integration_service._get_messages_payload_for_code_snippet(  # type: ignore # pylint: disable=protected-access
            version=mock_version,
            task_tuple=mock_task_tuple,
            task_schema_id=123,
        )

        # Verify result contains the expected messages
        assert (
            "[{'role': 'system', 'content': 'You are a helpful assistant.'}, {'role': 'user', 'content': 'Hello'}]"
            in result
        )
        # Verify runs_service.latest_run was not called
        integration_service.runs_service.latest_run.assert_not_called()

    async def test_get_messages_payload_with_successful_run(
        self,
        integration_service: IntegrationService,
        mock_version: Mock,
        mock_task_tuple: Mock,
    ):
        # Set up mock version without messages
        mock_version.group.properties.messages = None

        # Set up mock run
        mock_run = Mock()
        mock_run.task_input = {"messages": [{"role": "user", "content": "Hello from run"}]}
        integration_service.runs_service.latest_run = AsyncMock(return_value=mock_run)

        # Call the method
        result = await integration_service._get_messages_payload_for_code_snippet(  # type: ignore # pylint: disable=protected-access
            version=mock_version,
            task_tuple=mock_task_tuple,
            task_schema_id=123,
        )

        # Verify result
        assert "{'messages': [{'role': 'user', 'content': 'Hello from run'}]}" in result
        # Verify runs_service.latest_run was called with correct parameters
        integration_service.runs_service.latest_run.assert_awaited_once_with(
            task_uid=mock_task_tuple,
            schema_id=123,
            is_success=True,
            exclude_fields=set(),
        )

    async def test_get_messages_payload_with_no_successful_run(
        self,
        integration_service: IntegrationService,
        mock_version: Mock,
        mock_task_tuple: Mock,
    ):
        # Set up mock version without messages
        mock_version.group.properties.messages = None

        # Mock runs_service.latest_run to raise ObjectNotFoundException
        from core.storage import ObjectNotFoundException

        integration_service.runs_service.latest_run = AsyncMock(side_effect=ObjectNotFoundException("No run found"))

        # Get a reference to the logger to avoid protected access warning
        logger = integration_service._logger  # type: ignore # pylint: disable=protected-access

        # Spy on logger.warning
        with patch.object(logger, "warning") as mock_warning:
            # Call the method
            result = await integration_service._get_messages_payload_for_code_snippet(  # type: ignore # pylint: disable=protected-access
                version=mock_version,
                task_tuple=mock_task_tuple,
                task_schema_id=123,
            )

            # Verify result contains default system message
            assert "system" in result
            assert "You're a helpful assistant." in result

            # Verify logger.warning was called
            mock_warning.assert_called_once()
            assert "No successful run found" in mock_warning.call_args[0][0]

        # Verify runs_service.latest_run was called
        integration_service.runs_service.latest_run.assert_awaited_once()
