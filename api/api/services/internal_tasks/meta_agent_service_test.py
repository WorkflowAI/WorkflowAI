import datetime
from asyncio import TaskGroup
from typing import Any, Type
from unittest.mock import AsyncMock, Mock, patch

import pytest
from freezegun import freeze_time
from pydantic import BaseModel

from api.services.documentation_service import DocumentationService
from api.services.internal_tasks.meta_agent_service import (
    EditSchemaToolCall,
    GenerateAgentInputToolCall,
    HasActiveRunAndDate,
    ImprovePromptToolCall,
    MetaAgentChatMessage,
    MetaAgentContext,
    MetaAgentService,
    MetaAgentToolCallType,
    PlaygroundState,
    RunCurrentAgentOnModelsToolCall,
)
from api.services.internal_tasks.meta_agent_service import (
    _remove_typescript_comments as remove_ts_comments,  # pyright: ignore[reportPrivateUsage]
)
from api.services.runs.runs_service import RunsService
from core.agents.extract_company_info_from_domain_task import Product
from core.agents.meta_agent import (
    EditSchemaDescriptionAndExamplesToolCallRequest,
    EditSchemaStructureToolCallRequest,
    GenerateAgentInputToolCallRequest,
    ImprovePromptToolCallRequest,
    MetaAgentInput,
    MetaAgentOutput,
    RunCurrentAgentOnModelsToolCallRequest,
    SelectedModels,
)
from core.agents.meta_agent import PlaygroundState as PlaygroundStateDomain
from core.domain.agent_run import AgentRun
from core.domain.documentation_section import DocumentationSection
from core.domain.events import MetaAgentChatMessagesSent
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_variant import SerializableTaskVariant
from core.storage.backend_storage import BackendStorage
from tests.utils import mock_aiter


class TestMetaAgentService:
    @pytest.mark.parametrize(
        "user_email, messages, company_description, current_agents, expected_input",
        [
            (
                "user@example.com",
                [MetaAgentChatMessage(role="USER", content="Hello")],
                Mock(
                    company_name="Example Corp",
                    description="A tech company",
                    locations=["San Francisco"],
                    industries=["Technology"],
                    products=[Product(name="Product A", description="Description A")],
                ),
                ["Agent 1", "Agent 2"],
                MetaAgentInput(
                    current_datetime=datetime.datetime(2025, 1, 1),
                    messages=[MetaAgentChatMessage(role="USER", content="Hello").to_domain()],
                    company_context=MetaAgentInput.CompanyContext(
                        company_name="Example Corp",
                        company_description="A tech company",
                        company_locations=["San Francisco"],
                        company_industries=["Technology"],
                        company_products=[Product(name="Product A", description="Description A")],
                        existing_agents_descriptions=["Agent 1", "Agent 2"],
                    ),
                    workflowai_sections=[],
                    workflowai_documentation_sections=[
                        DocumentationSection(title="Some title", content="Some content"),
                    ],
                    available_tools_description="Some tools description",
                    playground_state=PlaygroundStateDomain(
                        current_agent=PlaygroundStateDomain.Agent(
                            name="",
                            schema_id=0,
                            description="",
                            input_schema={},
                            output_schema={},
                        ),
                        available_models=[],
                        selected_models=SelectedModels(
                            column_1=None,
                            column_2=None,
                            column_3=None,
                        ),
                    ),
                ),
            ),
            (
                None,  # No user email
                [MetaAgentChatMessage(role="USER", content="Help")],
                None,  # No company description
                [],  # No agents
                MetaAgentInput(
                    current_datetime=datetime.datetime(2025, 1, 1),
                    messages=[MetaAgentChatMessage(role="USER", content="Help").to_domain()],
                    company_context=MetaAgentInput.CompanyContext(
                        company_name=None,
                        company_description=None,
                        company_locations=None,
                        company_industries=None,
                        company_products=None,
                        existing_agents_descriptions=[],
                    ),
                    workflowai_sections=[],
                    workflowai_documentation_sections=[
                        DocumentationSection(title="Some title", content="Some content"),
                    ],
                    available_tools_description="Some tools description",
                    playground_state=PlaygroundStateDomain(
                        current_agent=PlaygroundStateDomain.Agent(
                            name="",
                            schema_id=0,
                            description="",
                            input_schema={},
                            output_schema={},
                        ),
                        available_models=[],
                        selected_models=SelectedModels(
                            column_1=None,
                            column_2=None,
                            column_3=None,
                        ),
                    ),
                ),
            ),
        ],
    )
    async def test_build_meta_agent_input(
        self,
        user_email: str | None,
        messages: list[MetaAgentChatMessage],
        company_description: Any,
        current_agents: list[str],
        expected_input: MetaAgentInput,
    ) -> None:
        # Create a mock storage
        mock_runs_service = Mock(spec=RunsService)
        mock_task_run = Mock(spec=AgentRun)
        mock_task_run.id = "run_id_1"
        mock_task_run.group = Mock(spec=TaskGroup)
        mock_task_run.group.properties = Mock(spec=TaskGroupProperties)
        mock_task_run.group.properties.model = "mock model"
        mock_task_run.task_output = {"foo": "bar"}
        mock_task_run.error = None
        mock_task_run.cost_usd = 1.0
        mock_task_run.duration_seconds = 1.0
        mock_task_run.llm_completions = []
        mock_task_run.user_review = "positive"
        mock_runs_service.run_by_id = AsyncMock(return_value=mock_task_run)
        mock_storage = Mock(spec=BackendStorage)
        mock_event_router = Mock()
        # Create the service with the mock storage
        service = MetaAgentService(
            storage=mock_storage,
            event_router=mock_event_router,
            runs_service=mock_runs_service,
            models_service=AsyncMock(),
            feedback_service=AsyncMock(),
            versions_service=AsyncMock(),
            reviews_service=AsyncMock(),
        )

        # Mock the dependencies
        with (
            patch(
                "api.services.internal_tasks.meta_agent_service.safe_generate_company_description_from_email",
                new_callable=AsyncMock,
                return_value=company_description,
            ) as mock_generate_company_description,
            patch(
                "api.services.internal_tasks.meta_agent_service.list_agent_summaries",
                new_callable=AsyncMock,
                return_value=current_agents,
            ) as mock_list_agents,
            patch.object(
                DocumentationService,
                "get_relevant_doc_sections",
                return_value=[
                    DocumentationSection(title="Some title", content="Some content"),
                ],
            ) as mock_get_relevant_doc_sections,
        ):
            # The 'name' parameter is a special attribute in Mock objects
            # and doesn't create a property on the mock object itself
            mock_agent = Mock(spec=SerializableTaskVariant)
            mock_agent.name = "mock agent name"
            mock_agent.task_schema_id = 0
            mock_agent.description = "mock_description"
            mock_agent.input_schema = Mock()
            mock_agent.input_schema.json_schema = {"foo": "bar"}
            mock_agent.output_schema = Mock()
            mock_agent.output_schema.json_schema = {"foo2": "bar2"}
            ui_state = PlaygroundState(
                agent_instructions="some some",
                agent_temperature=0.5,
                agent_run_ids=["run_id_1", "run_id_2"],
                selected_models=PlaygroundState.SelectedModels(
                    column_1=None,
                    column_2=None,
                    column_3=None,
                ),
            )

            # Call the method
            result, _ = await service._build_meta_agent_input(  # pyright: ignore[reportPrivateUsage]
                task_tuple=("mock agent name", 12345),
                agent_schema_id=0,
                user_email=user_email,
                messages=messages,
                current_agent=mock_agent,
                playground_state=ui_state,
            )

            # Verify the mocks were called correctly
            mock_generate_company_description.assert_called_once_with(user_email)
            mock_list_agents.assert_called_once_with(mock_storage, limit=10)
            mock_get_relevant_doc_sections.assert_called_once()

            # Verify the result
            assert result.messages == expected_input.messages
            assert result.company_context.company_name == expected_input.company_context.company_name
            assert result.company_context.company_description == expected_input.company_context.company_description
            assert result.company_context.company_locations == expected_input.company_context.company_locations
            assert result.company_context.company_industries == expected_input.company_context.company_industries
            assert (
                result.company_context.existing_agents_descriptions
                == expected_input.company_context.existing_agents_descriptions
            )
            assert result.workflowai_documentation_sections == expected_input.workflowai_documentation_sections

            # If company products exist, verify them
            if result.company_context.company_products and expected_input.company_context.company_products:
                for i, product in enumerate(result.company_context.company_products):
                    assert product.name == expected_input.company_context.company_products[i].name
                    assert product.description == expected_input.company_context.company_products[i].description

    # Freeze the "now"
    @freeze_time("2025-04-17T12:56:41.413541")
    @pytest.mark.parametrize(
        "user_email, messages, meta_agent_chunks, expected_outputs",
        [
            (
                "user@example.com",
                [
                    MetaAgentChatMessage(
                        sent_at=datetime.datetime(2025, 4, 17, 12, 56, 41, 413541, tzinfo=datetime.timezone.utc),
                        role="USER",
                        content="Hello",
                        kind="non_specific",
                    ),
                ],
                [
                    MetaAgentOutput(
                        content="Hi there!",
                    ),
                    MetaAgentOutput(
                        content="How can I help you today?",
                    ),
                ],
                [
                    [
                        MetaAgentChatMessage(
                            sent_at=datetime.datetime(2025, 4, 17, 12, 56, 41, 413541, tzinfo=datetime.timezone.utc),
                            role="ASSISTANT",
                            content="Hi there!",
                            kind="non_specific",
                        ),
                    ],
                    [
                        MetaAgentChatMessage(
                            sent_at=datetime.datetime(2025, 4, 17, 12, 56, 41, 413541, tzinfo=datetime.timezone.utc),
                            role="ASSISTANT",
                            content="How can I help you today?",
                            kind="non_specific",
                        ),
                    ],
                ],
            ),
            (
                None,
                [
                    MetaAgentChatMessage(
                        sent_at=datetime.datetime(2025, 4, 17, 12, 56, 41, 413541, tzinfo=datetime.timezone.utc),
                        role="USER",
                        content="Help",
                        kind="non_specific",
                    ),
                ],
                [
                    MetaAgentOutput(content=None),  # Empty chunk
                    MetaAgentOutput(content="I can help with WorkflowAI!"),
                ],
                [
                    [
                        MetaAgentChatMessage(
                            sent_at=datetime.datetime(2025, 4, 17, 12, 56, 41, 413541, tzinfo=datetime.timezone.utc),
                            role="ASSISTANT",
                            content="I can help with WorkflowAI!",
                            kind="non_specific",
                        ),
                    ],
                ],
            ),
            (
                "user@example.com",
                [],  # Empty messages
                [],  # No chunks expected
                [
                    [
                        MetaAgentChatMessage(
                            sent_at=datetime.datetime(2025, 4, 17, 12, 56, 41, 413541, tzinfo=datetime.timezone.utc),
                            role="ASSISTANT",
                            content="Hi, I'm WorkflowAI's agent. How can I help you?",
                            kind="non_specific",
                        ),
                    ],
                ],
            ),
        ],
    )
    async def test_stream_meta_agent_response(
        self,
        user_email: str | None,
        messages: list[MetaAgentChatMessage],
        meta_agent_chunks: list[MetaAgentOutput],
        expected_outputs: list[list[MetaAgentChatMessage]],
    ) -> None:
        mock_storage = Mock(spec=BackendStorage)
        mock_agent = Mock(spec=SerializableTaskVariant)
        mock_agent.name = "mock agent name"
        mock_agent.task_schema_id = 0
        mock_agent.description = "mock_description"
        mock_agent.input_schema = Mock()
        mock_agent.input_schema.json_schema = {"foo": "bar"}
        mock_agent.output_schema = Mock()
        mock_agent.output_schema.json_schema = {"foo2": "bar2"}
        mock_storage.task_variant_latest_by_schema_id = AsyncMock(return_value=mock_agent)

        mock_event_router = Mock()
        mock_runs_service = Mock(spec=RunsService)
        mock_task_run = Mock(spec=AgentRun)
        mock_task_run.group = Mock(spec=TaskGroup)
        mock_task_run.group.properties = Mock(spec=TaskGroupProperties)
        mock_task_run.group.properties.model = "mock model"
        mock_task_run.task_output = {"foo": "bar"}
        mock_task_run.error = None
        mock_task_run.cost_usd = 1.0
        mock_task_run.duration_seconds = 1.0
        mock_task_run.user_review = "positive"
        mock_runs_service.run_by_id = AsyncMock(return_value=mock_task_run)
        service = MetaAgentService(
            storage=mock_storage,
            event_router=mock_event_router,
            runs_service=mock_runs_service,
            models_service=AsyncMock(),
            feedback_service=AsyncMock(),
            versions_service=AsyncMock(),
            reviews_service=AsyncMock(),
        )

        # Create a mock for _build_meta_agent_input
        mock_input = MetaAgentInput(
            current_datetime=datetime.datetime(2025, 1, 1),
            messages=[message.to_domain() for message in messages],
            company_context=MetaAgentInput.CompanyContext(),
            workflowai_documentation_sections=[
                DocumentationSection(title="Some title", content="Some content"),
            ],
            workflowai_sections=[],
            available_tools_description="Some tools description",
            playground_state=PlaygroundStateDomain(
                current_agent=PlaygroundStateDomain.Agent(
                    name="",
                    schema_id=0,
                    description="",
                    input_schema={},
                    output_schema={},
                ),
                available_models=[],
                selected_models=SelectedModels(
                    column_1=None,
                    column_2=None,
                    column_3=None,
                ),
            ),
        )

        # Create a mock for the stream response
        class MockStreamResponse(BaseModel):
            output: MetaAgentOutput
            feedback_token: str | None = None

        # Patch the _build_meta_agent_input method
        with patch.object(
            service,
            "_build_meta_agent_input",
            new_callable=AsyncMock,
            return_value=(mock_input, []),
        ) as mock_build_input:
            # Patch the meta_agent.stream function
            with patch(
                "api.services.internal_tasks.meta_agent_service.meta_agent.stream",
                return_value=mock_aiter(*[MockStreamResponse(output=chunk) for chunk in meta_agent_chunks]),
            ) as mock_stream:
                ui_state = PlaygroundState(
                    agent_instructions="some some",
                    agent_temperature=0.5,
                    agent_run_ids=["run_id_1", "run_id_2"],
                    selected_models=PlaygroundState.SelectedModels(
                        column_1=None,
                        column_2=None,
                        column_3=None,
                    ),
                )

                # Call the method and collect the results
                results = [
                    chunk
                    async for chunk in service.stream_meta_agent_response(
                        task_tuple=("mock agent name", 12345),
                        agent_schema_id=0,
                        user_email=user_email,
                        messages=messages,
                        playground_state=ui_state,
                    )
                ]

                # Verify the results match expected outputs
                assert results == expected_outputs

                # Verify _build_meta_agent_input was called or not based on messages
                if not messages:
                    mock_build_input.assert_not_called()
                    mock_stream.assert_not_called()
                else:
                    mock_build_input.assert_called_once_with(
                        ("mock agent name", 12345),
                        0,
                        user_email,
                        messages,
                        mock_agent,
                        ui_state,
                    )

    @pytest.mark.parametrize(
        "input_messages, expected_messages",
        [
            (
                [
                    MetaAgentChatMessage(role="USER", content="User0"),
                    MetaAgentChatMessage(role="ASSISTANT", content="A"),
                    MetaAgentChatMessage(role="USER", content="User1"),
                    MetaAgentChatMessage(role="USER", content="User2"),
                ],
                [
                    MetaAgentChatMessage(role="USER", content="User1"),
                    MetaAgentChatMessage(role="USER", content="User2"),
                ],
            ),
        ],
    )
    def test_dispatch_new_user_messages_event(
        self,
        input_messages: list[MetaAgentChatMessage],
        expected_messages: list[MetaAgentChatMessage],
    ) -> None:
        mock_event_router = Mock()
        mock_runs_service = Mock(spec=RunsService)

        service = MetaAgentService(
            storage=Mock(),
            event_router=mock_event_router,
            runs_service=mock_runs_service,
            models_service=AsyncMock(),
            feedback_service=AsyncMock(),
            versions_service=AsyncMock(),
            reviews_service=AsyncMock(),
        )

        service.dispatch_new_user_messages_event(input_messages)

        mock_event_router.assert_called_once_with(
            MetaAgentChatMessagesSent(messages=[message.to_domain() for message in expected_messages]),
        )

    @pytest.mark.parametrize(
        "candidate_run_id, runs_config, expected_run_id, expected_warning_calls",
        [
            # Candidate run id is present in valid runs, no warnings expected.
            (
                "run1",
                [{"id": "run1", "user_review": "positive", "task_output": {"key": "value"}}],
                "run1",
                0,
            ),
            # Valid runs is empty: returns empty string and logs one warning.
            ("runX", [], "", 1),
            # Candidate not present, negative review exists: returns that run id, one warning logged.
            (
                "runX",
                [
                    {"id": "runA", "user_review": "positive", "task_output": {"key": "value"}},
                    {"id": "runB", "user_review": "negative", "task_output": None},
                ],
                "runB",
                1,
            ),
            # Candidate not present, no negative review exists but one with task_output exists: returns that run id, one warning logged.
            (
                "runX",
                [
                    {"id": "runC", "user_review": None, "task_output": None},
                    {"id": "runD", "user_review": "positive", "task_output": {"output": "value"}},
                ],
                "runD",
                1,
            ),
            # Candidate not present, no negative and no truthful task_output: returns the first run id, two warnings logged.
            (
                "runX",
                [
                    {"id": "runE", "user_review": "positive", "task_output": None},
                    {"id": "runF", "user_review": "positive", "task_output": None},
                ],
                "runE",
                2,
            ),
        ],
    )
    def test_sanitize_agent_run_id(
        self,
        candidate_run_id: str,
        runs_config: list[dict[str, Any]],
        expected_run_id: str,
        expected_warning_calls: int,
    ) -> None:
        # Create dummy valid runs as mocks mimicking Run.
        valid_runs: list[Mock] = []
        for cfg in runs_config:
            dummy_run = Mock(spec=AgentRun)
            dummy_run.id = cfg["id"]
            dummy_run.user_review = cfg["user_review"]
            dummy_run.task_output = cfg["task_output"]
            valid_runs.append(dummy_run)

        # Instantiate the service; dependencies are not used in _sanitize_agent_run_id.
        service = MetaAgentService(
            storage=Mock(),
            event_router=Mock(),
            runs_service=Mock(),
            models_service=AsyncMock(),
            feedback_service=AsyncMock(),
            versions_service=AsyncMock(),
            reviews_service=AsyncMock(),
        )

        # Patch the service logger to count warning calls.
        with patch.object(service, "_logger") as mock_logger:
            result = service._sanitize_agent_run_id(candidate_run_id, valid_runs)  # pyright: ignore[reportPrivateUsage, reportArgumentType]
            assert result == expected_run_id
            assert mock_logger.warning.call_count == expected_warning_calls

    @pytest.mark.parametrize(
        "tool_call_type, initial_auto_run, messages, expected",
        [
            # initial_auto_run is False should always return False
            (ImprovePromptToolCall, False, [], False),
            # EditSchemaToolCall should always return False regardless of initial_auto_run
            (EditSchemaToolCall, True, [], False),
            # When initial_auto_run is True and messages do not trigger the blocking condition
            (ImprovePromptToolCall, True, [MetaAgentChatMessage(role="USER", content="test")], True),
            # Single PLAYGROUND message (not enough messages to check previous one) should return True
            (ImprovePromptToolCall, True, [MetaAgentChatMessage(role="PLAYGROUND", content="dummy")], True),
            # Condition triggered: last message is PLAYGROUND and previous is ASSISTANT with matching tool_call
            (
                ImprovePromptToolCall,
                True,
                [
                    MetaAgentChatMessage(
                        role="ASSISTANT",
                        content="assistant",
                        tool_call=ImprovePromptToolCall(run_id="id", run_feedback_message="feedback"),
                    ),
                    MetaAgentChatMessage(role="PLAYGROUND", content="dummy"),
                ],
                False,
            ),
            # For RunCurrentAgentOnModelsToolCall with matching tool_call in previous message
            (
                RunCurrentAgentOnModelsToolCall,
                True,
                [
                    MetaAgentChatMessage(
                        role="ASSISTANT",
                        content="assistant",
                        tool_call=RunCurrentAgentOnModelsToolCall(run_configs=[]),
                    ),
                    MetaAgentChatMessage(role="PLAYGROUND", content="dummy"),
                ],
                False,
            ),
            # Condition not met: last message is not PLAYGROUND
            (
                ImprovePromptToolCall,
                True,
                [
                    MetaAgentChatMessage(
                        role="ASSISTANT",
                        content="assistant",
                        tool_call=ImprovePromptToolCall(run_id="id", run_feedback_message="feedback"),
                    ),
                    MetaAgentChatMessage(role="USER", content="dummy"),
                ],
                True,
            ),
            # Condition not met: tool_call types do not match (different tool_call in message)
            (
                RunCurrentAgentOnModelsToolCall,
                True,
                [
                    MetaAgentChatMessage(
                        role="ASSISTANT",
                        content="assistant",
                        tool_call=ImprovePromptToolCall(run_id="id", run_feedback_message="feedback"),
                    ),
                    MetaAgentChatMessage(role="PLAYGROUND", content="dummy"),
                ],
                True,
            ),
        ],
    )
    def test_resolve_auto_run(
        self,
        tool_call_type: Type[MetaAgentToolCallType],
        initial_auto_run: bool,
        messages: list[MetaAgentChatMessage],
        expected: bool,
    ) -> None:
        result = MetaAgentService._resolve_auto_run(tool_call_type, initial_auto_run, messages)  # pyright: ignore[reportPrivateUsage]
        assert result == expected

    @pytest.mark.parametrize(
        "messages, expected_urls",
        [
            # Test with empty messages list
            ([], []),
            # Test with non-USER message
            ([MetaAgentChatMessage(role="ASSISTANT", content="Hello")], []),
            # Test with non-USER message
            ([MetaAgentChatMessage(role="PLAYGROUND", content="Hello")], []),
            # Test with USER message but no URLs
            ([MetaAgentChatMessage(role="USER", content="Hello")], []),
            # Test with USER message containing URLs
            (
                [MetaAgentChatMessage(role="USER", content="Check https://example.com and https://test.com")],
                ["https://example.com", "https://test.com"],
            ),
            # Test with multiple messages, only latest USER message should be considered
            (
                [
                    MetaAgentChatMessage(role="USER", content="Check https://first.com"),
                    MetaAgentChatMessage(role="ASSISTANT", content="Hello"),
                    MetaAgentChatMessage(role="USER", content="Check https://last.com"),
                ],
                ["https://last.com"],
            ),
        ],
    )
    async def test_extract_url_content_from_messages(
        self,
        messages: list[MetaAgentChatMessage],
        expected_urls: list[str],
    ) -> None:
        # Create service instance
        service = MetaAgentService(
            storage=Mock(),
            event_router=Mock(),
            runs_service=Mock(),
            versions_service=AsyncMock(),
            models_service=AsyncMock(),
            feedback_service=AsyncMock(),
            reviews_service=AsyncMock(),
        )

        # Mock extract_and_fetch_urls to return our expected URLs
        with patch(
            "api.services.internal_tasks.meta_agent_service.extract_and_fetch_urls",
            new_callable=AsyncMock,
            return_value=expected_urls,
        ) as mock_extract_urls:
            # Call the method
            result = await service._extract_url_content_from_messages(messages)  # pyright: ignore[reportPrivateUsage]

            # Verify the result
            assert result == expected_urls

            # Verify extract_and_fetch_urls was called with the correct content
            if messages and messages[-1].role == "USER":
                mock_extract_urls.assert_called_once_with(messages[-1].content)
            else:
                mock_extract_urls.assert_not_called()

    @pytest.mark.parametrize(
        "context_results, expected_context",
        [
            # All results successful
            (
                [
                    Mock(company_name="Example Corp"),  # company_description
                    ["Agent 1", "Agent 2"],  # existing_agents
                    [Mock(id="run1")],  # agent_runs
                    Mock(count=5, items=["feedback1"]),  # feedback_page
                    HasActiveRunAndDate(True, datetime.datetime(2025, 1, 1)),  # has_active_runs
                    10,  # reviewed_input_count
                ],
                MetaAgentContext(
                    company_description=Mock(company_name="Example Corp"),
                    existing_agents=["Agent 1", "Agent 2"],
                    agent_runs=[Mock(id="run1")],
                    feedback_page=Mock(count=5, items=["feedback1"]),
                    has_active_runs=HasActiveRunAndDate(True, datetime.datetime(2025, 1, 1)),
                    reviewed_input_count=10,
                ),
            ),
            # Some results failed
            (
                [
                    Exception("Failed to get company description"),  # company_description fails
                    ["Agent 1"],  # existing_agents succeeds
                    [Mock(id="run1")],  # agent_runs succeeds
                    Exception("Failed to get feedback"),  # feedback_page fails
                    HasActiveRunAndDate(True, datetime.datetime(2025, 1, 1)),  # has_active_runs succeeds
                    Exception("Failed to get reviewed input count"),  # reviewed_input_count fails
                ],
                MetaAgentContext(
                    company_description=None,
                    existing_agents=["Agent 1"],
                    agent_runs=[Mock(id="run1")],
                    feedback_page=None,
                    has_active_runs=HasActiveRunAndDate(True, datetime.datetime(2025, 1, 1)),
                    reviewed_input_count=None,
                ),
            ),
            # All results failed
            (
                [
                    Exception("Failed to get company description"),
                    Exception("Failed to get existing agents"),
                    Exception("Failed to get agent runs"),
                    Exception("Failed to get feedback"),
                    Exception("Failed to get has active runs"),
                    Exception("Failed to get reviewed input count"),
                ],
                MetaAgentContext(
                    company_description=None,
                    existing_agents=None,
                    agent_runs=None,
                    feedback_page=None,
                    has_active_runs=None,
                    reviewed_input_count=None,
                ),
            ),
        ],
    )
    async def test_fetch_meta_agent_context(
        self,
        context_results: list[Any],
        expected_context: MetaAgentContext,
    ) -> None:
        """Test that the context fetching handles exceptions properly."""
        # Create mocks
        mock_storage = Mock(spec=BackendStorage)
        mock_event_router = Mock()
        mock_runs_service = Mock(spec=RunsService)

        # Create the service with mocks
        service = MetaAgentService(
            storage=mock_storage,
            event_router=mock_event_router,
            runs_service=mock_runs_service,
            models_service=AsyncMock(),
            feedback_service=AsyncMock(),
            versions_service=AsyncMock(),
            reviews_service=AsyncMock(),
        )

        # Mock the gather call to return our test results
        with patch("asyncio.gather", AsyncMock(return_value=context_results)) as mock_gather:
            # Create test parameters
            task_tuple = ("test_task", 123)
            agent_schema_id = 456
            user_email = "test@example.com"
            playground_state = PlaygroundState(
                agent_instructions="test instructions",
                agent_temperature=0.5,
                agent_run_ids=["run1", "run2"],
                selected_models=PlaygroundState.SelectedModels(
                    column_1=None,
                    column_2=None,
                    column_3=None,
                ),
            )

            # Call the public method
            result = await service.fetch_meta_agent_context_for_testing(
                task_tuple,
                agent_schema_id,
                user_email,
                playground_state,
            )

            # Verify gather was called with the right arguments
            mock_gather.assert_called_once()

            # Compare the result with expected values
            # For company_description, we need to compare attributes since it's a Mock
            if expected_context.company_description is None:
                assert result.company_description is None
            elif result.company_description is not None:
                assert result.company_description.company_name == expected_context.company_description.company_name

            # Compare existing_agents
            assert result.existing_agents == expected_context.existing_agents

            # For agent_runs, compare the ids if not None
            if expected_context.agent_runs is None:
                assert result.agent_runs is None
            elif result.agent_runs is not None:
                assert len(result.agent_runs) == len(expected_context.agent_runs)
                for i, run in enumerate(result.agent_runs):
                    assert run.id == expected_context.agent_runs[i].id

            # For feedback_page
            if expected_context.feedback_page is None:
                assert result.feedback_page is None
            elif result.feedback_page is not None:
                assert result.feedback_page.count == expected_context.feedback_page.count
                assert result.feedback_page.items == expected_context.feedback_page.items

            # For has_active_runs
            if expected_context.has_active_runs is None:
                assert result.has_active_runs is None
            elif result.has_active_runs is not None:
                assert result.has_active_runs.has_active_runs == expected_context.has_active_runs.has_active_runs
                assert (
                    result.has_active_runs.latest_active_run_date
                    == expected_context.has_active_runs.latest_active_run_date
                )

            # For reviewed_input_count
            assert result.reviewed_input_count == expected_context.reviewed_input_count

    @patch("api.services.internal_tasks.meta_agent_service.meta_agent_user_confirmation_agent", new_callable=AsyncMock)
    async def test_sanitize_tool_call_auto_run_initially_false(
        self,
        mock_confirmation_agent: AsyncMock,
    ) -> None:
        """
        Tests that if tool_call.auto_run is initially False, the confirmation agent is not called
        and auto_run remains False.
        """
        # Create service instance with minimal dependencies
        service = MetaAgentService(
            storage=Mock(spec=BackendStorage),
            event_router=Mock(),
            runs_service=Mock(spec=RunsService),
            versions_service=Mock(),
            models_service=Mock(),
            feedback_service=Mock(),
            reviews_service=Mock(),
        )
        # Replace the logger with a mock
        with patch.object(service, "_logger", new=Mock()) as mock_logger:
            tool_call: MetaAgentToolCallType = ImprovePromptToolCall(
                run_feedback_message="Test feedback",
                auto_run=False,  # Initial state
                tool_call_id="test_improve_false_123",
                run_id="test_run_id",
                tool_name="improve_agent_instructions",
            )
            assistant_message_content = "Assistant message content"

            # Call the protected method directly in the test
            await service._sanitize_tool_call_auto_run(tool_call, assistant_message_content)  # pyright: ignore[reportPrivateUsage]

            # Verify expectations
            assert tool_call.auto_run is False  # Should remain False
            mock_confirmation_agent.assert_not_called()
            mock_logger.exception.assert_not_called()

    @pytest.mark.parametrize(
        "mock_confirmation_return, expected_final_auto_run",
        [
            # Scenario 1: Confirmation agent returns False -> auto_run remains True
            (
                Mock(requires_user_confirmation=False),
                True,
            ),
            # Scenario 2: Confirmation agent returns True -> auto_run becomes False
            (
                Mock(requires_user_confirmation=True),
                False,
            ),
            # Scenario 3: Confirmation agent raises error -> auto_run remains True (and logs)
            (
                Exception("Test Error"),
                True,
            ),
        ],
    )
    @patch("api.services.internal_tasks.meta_agent_service.meta_agent_user_confirmation_agent", new_callable=AsyncMock)
    async def test_sanitize_tool_call_auto_run_initially_true(
        self,
        mock_confirmation_agent: AsyncMock,
        mock_confirmation_return: Any,
        expected_final_auto_run: bool,
    ) -> None:
        """
        Tests that if tool_call.auto_run is initially True, the confirmation agent is called,
        and auto_run is updated based on the agent's response or exception.
        """
        # Create service instance with minimal dependencies
        service = MetaAgentService(
            storage=Mock(spec=BackendStorage),
            event_router=Mock(),
            runs_service=Mock(spec=RunsService),
            versions_service=Mock(),
            models_service=Mock(),
            feedback_service=Mock(),
            reviews_service=Mock(),
        )

        with patch.object(service, "_logger", new=Mock()) as mock_logger:
            # Setup mock confirmation agent behavior
            if isinstance(mock_confirmation_return, Exception):
                mock_confirmation_agent.side_effect = mock_confirmation_return
            else:
                mock_confirmation_agent.return_value = mock_confirmation_return

            tool_call: MetaAgentToolCallType = ImprovePromptToolCall(
                run_feedback_message="Test feedback",
                auto_run=True,  # Initial state
                tool_call_id="test_improve_true_456",
                run_id="test_run_id",
                tool_name="improve_agent_instructions",
            )
            assistant_message_content = "Relevant assistant message"

            # Call the protected method directly in the test
            await service._sanitize_tool_call_auto_run(tool_call, assistant_message_content)  # pyright: ignore[reportPrivateUsage]

            # Assertions
            assert tool_call.auto_run == expected_final_auto_run

            # Check confirmation agent call
            mock_confirmation_agent.assert_called_once()
            call_args, _ = mock_confirmation_agent.call_args
            assert len(call_args) == 1
            assert call_args[0].assistant_message_content == assistant_message_content

            # Check logger call on exception
            if isinstance(mock_confirmation_return, Exception):
                mock_logger.exception.assert_called_once_with(
                    "Error running meta agent user confirmation agent",
                    exc_info=mock_confirmation_return,
                )
            else:
                mock_logger.exception.assert_not_called()

    def test_extract_tool_call_no_tool_call(self):
        """Test when there is no tool call in the meta agent output"""
        service = MetaAgentService(
            storage=Mock(),
            event_router=Mock(),
            runs_service=Mock(),
            versions_service=Mock(),
            models_service=Mock(),
            feedback_service=Mock(),
            reviews_service=Mock(),
        )

        meta_agent_output = MetaAgentOutput(content="Just a simple response")
        result = service._extract_tool_call_from_meta_agent_output(  # pyright: ignore[reportPrivateUsage]
            meta_agent_output,
            [],
            [],
        )

        assert result is None

    def test_extract_tool_call_improve_instructions(self):
        """Test extracting an improve instructions tool call"""
        service = MetaAgentService(
            storage=Mock(),
            event_router=Mock(),
            runs_service=Mock(),
            versions_service=Mock(),
            models_service=Mock(),
            feedback_service=Mock(),
            reviews_service=Mock(),
        )

        with patch.object(service, "_sanitize_agent_run_id", return_value="run1") as mock_sanitize:
            with patch.object(service, "_resolve_auto_run", return_value=False) as mock_resolve:
                meta_agent_output = MetaAgentOutput(
                    content="Improving instructions",
                    improve_instructions_tool_call=ImprovePromptToolCallRequest(
                        agent_run_id="run1",
                        instruction_improvement_request_message="Make it better",
                        ask_user_confirmation=True,
                    ),
                )

                result = service._extract_tool_call_from_meta_agent_output(  # type: ignore[reportPrivateUsage]
                    meta_agent_output,
                    [Mock(id="run1", user_review=None, task_output={"result": "value"})],
                    [],
                )

                assert isinstance(result, ImprovePromptToolCall)
                assert result.run_id == "run1"
                assert result.run_feedback_message == "Make it better"
                assert result.auto_run is False
                mock_sanitize.assert_called_once()
                mock_resolve.assert_called_once()

    def test_extract_tool_call_edit_schema_descriptions(self):
        """Test extracting an edit schema descriptions tool call"""
        service = MetaAgentService(
            storage=Mock(),
            event_router=Mock(),
            runs_service=Mock(),
            versions_service=Mock(),
            models_service=Mock(),
            feedback_service=Mock(),
            reviews_service=Mock(),
        )

        with patch.object(service, "_resolve_auto_run", return_value=False) as mock_resolve:
            meta_agent_output = MetaAgentOutput(
                content="Editing schema descriptions",
                edit_schema_description_and_examples_tool_call=EditSchemaDescriptionAndExamplesToolCallRequest(
                    description_and_examples_edition_request_message="Better descriptions",
                    ask_user_confirmation=True,
                ),
            )

            result = service._extract_tool_call_from_meta_agent_output(  # type: ignore[reportPrivateUsage]
                meta_agent_output,
                [],
                [],
            )

            assert isinstance(result, ImprovePromptToolCall)
            assert result.run_id is None
            assert result.run_feedback_message == "Better descriptions"
            assert result.auto_run is False
            mock_resolve.assert_called_once()

    def test_extract_tool_call_edit_schema_structure(self):
        """Test extracting an edit schema structure tool call"""
        service = MetaAgentService(
            storage=Mock(),
            event_router=Mock(),
            runs_service=Mock(),
            versions_service=Mock(),
            models_service=Mock(),
            feedback_service=Mock(),
            reviews_service=Mock(),
        )

        with patch.object(service, "_resolve_auto_run", return_value=False) as mock_resolve:
            meta_agent_output = MetaAgentOutput(
                content="Editing schema structure",
                edit_schema_structure_tool_call=EditSchemaStructureToolCallRequest(
                    edition_request_message="Add a field",
                    ask_user_confirmation=False,
                ),
            )

            result = service._extract_tool_call_from_meta_agent_output(  # type: ignore[reportPrivateUsage]
                meta_agent_output,
                [],
                [],
            )

            assert isinstance(result, EditSchemaToolCall)
            assert result.edition_request_message == "Add a field"
            assert result.auto_run is False
            mock_resolve.assert_called_once()

    def test_extract_tool_call_run_on_models(self):
        """Test extracting a run on models tool call"""
        service = MetaAgentService(
            storage=Mock(),
            event_router=Mock(),
            runs_service=Mock(),
            versions_service=Mock(),
            models_service=Mock(),
            feedback_service=Mock(),
            reviews_service=Mock(),
        )

        with patch.object(service, "_resolve_auto_run", return_value=True) as mock_resolve:
            meta_agent_output = MetaAgentOutput(
                content="Running on models",
                run_current_agent_on_models_tool_call=RunCurrentAgentOnModelsToolCallRequest(
                    run_configs=[
                        RunCurrentAgentOnModelsToolCallRequest.RunConfig(
                            run_on_column="column_1",
                            model="model1",
                        ),
                    ],
                    ask_user_confirmation=False,
                ),
            )

            result = service._extract_tool_call_from_meta_agent_output(  # type: ignore[reportPrivateUsage]
                meta_agent_output,
                [],
                [],
            )

            assert isinstance(result, RunCurrentAgentOnModelsToolCall)
            assert result.run_configs is not None
            assert len(result.run_configs) == 1
            assert result.run_configs[0].run_on_column == "column_1"
            assert result.run_configs[0].model == "model1"
            assert result.auto_run is True
            mock_resolve.assert_called_once()

    def test_extract_tool_call_generate_input(self):
        """Test extracting a generate input tool call"""
        service = MetaAgentService(
            storage=Mock(),
            event_router=Mock(),
            runs_service=Mock(),
            versions_service=Mock(),
            models_service=Mock(),
            feedback_service=Mock(),
            reviews_service=Mock(),
        )

        with patch.object(service, "_resolve_auto_run", return_value=True) as mock_resolve:
            meta_agent_output = MetaAgentOutput(
                content="Generating input",
                generate_agent_input_tool_call=GenerateAgentInputToolCallRequest(
                    instructions="Generate a sample input",
                    ask_user_confirmation=False,
                ),
            )

            result = service._extract_tool_call_from_meta_agent_output(  # type: ignore[reportPrivateUsage]
                meta_agent_output,
                [],
                [],
            )

            assert isinstance(result, GenerateAgentInputToolCall)
            assert result.instructions == "Generate a sample input"
            assert result.auto_run is True
            mock_resolve.assert_called_once()

    def test_extract_tool_call_previous_message_same_type(self):
        """Test that auto_run is False when previous message has same tool call type"""
        service = MetaAgentService(
            storage=Mock(),
            event_router=Mock(),
            runs_service=Mock(),
            versions_service=Mock(),
            models_service=Mock(),
            feedback_service=Mock(),
            reviews_service=Mock(),
        )

        # Set up the previous messages with same tool call type
        messages = [
            MetaAgentChatMessage(
                role="ASSISTANT",
                content="Previous message",
                tool_call=GenerateAgentInputToolCall(instructions="Previous input generation"),
            ),
            MetaAgentChatMessage(role="PLAYGROUND", content="Playground message"),
        ]

        with patch.object(service, "_resolve_auto_run", return_value=False) as mock_resolve:
            meta_agent_output = MetaAgentOutput(
                content="Generating input again",
                generate_agent_input_tool_call=GenerateAgentInputToolCallRequest(
                    instructions="Generate another sample input",
                    ask_user_confirmation=False,
                ),
            )

            result = service._extract_tool_call_from_meta_agent_output(  # type: ignore[reportPrivateUsage]
                meta_agent_output,
                [],
                messages,
            )

            assert isinstance(result, GenerateAgentInputToolCall)
            assert result.instructions == "Generate another sample input"
            assert result.auto_run is False
            mock_resolve.assert_called_once()

    @pytest.mark.parametrize(
        "content, expected",
        [
            # No comments to remove
            ("print('hello')", "print('hello')"),
            # Single inline TypeScript style comment
            (
                "const a = 1; /* this is a comment */ const b = 2;",
                "const a = 1;  const b = 2;",
            ),
            # Comment at the beginning
            ("/* leading comment */const x = 5;", "const x = 5;"),
            # Multiple comments in one string
            (
                "const x=1;/* c1 */const y=2;/* c2 */const z=3;",
                "const x=1;const y=2;const z=3;",
            ),
        ],
    )
    def test_remove_typescript_comments(self, content: str, expected: str) -> None:
        """Verify that _remove_typescript_comments correctly strips TypeScript style block comments."""
        assert remove_ts_comments(content) == expected
