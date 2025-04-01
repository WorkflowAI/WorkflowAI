import datetime
from asyncio import TaskGroup
from typing import Any, Type
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import BaseModel

from api.services.documentation_service import DocumentationService
from api.services.internal_tasks.meta_agent_service import (
    EditSchemaToolCall,
    ImprovePromptToolCall,
    MetaAgentChatMessage,
    MetaAgentService,
    MetaAgentToolCallType,
    PlaygroundState,
    RunCurrentAgentOnModelsToolCall,
)
from api.services.runs import RunsService
from api.tasks.extract_company_info_from_domain_task import Product
from api.tasks.meta_agent import MetaAgentInput, MetaAgentOutput
from api.tasks.meta_agent import PlaygroundState as PlaygroundStateDomain
from core.domain.documentation_section import DocumentationSection
from core.domain.events import MetaAgentChatMessagesSent
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_run import SerializableTaskRun
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
                        selected_models=PlaygroundStateDomain.SelectedModels(
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
                        selected_models=PlaygroundStateDomain.SelectedModels(
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
        mock_task_run = Mock(spec=SerializableTaskRun)
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

    @pytest.mark.parametrize(
        "user_email, messages, meta_agent_chunks, expected_outputs",
        [
            (
                "user@example.com",
                [MetaAgentChatMessage(role="USER", content="Hello")],
                [
                    MetaAgentOutput(
                        content="Hi there!",
                    ),
                    MetaAgentOutput(
                        content="How can I help you today?",
                    ),
                ],
                [
                    [MetaAgentChatMessage(role="ASSISTANT", content="Hi there!")],
                    [MetaAgentChatMessage(role="ASSISTANT", content="How can I help you today?")],
                ],
            ),
            (
                None,
                [MetaAgentChatMessage(role="USER", content="Help")],
                [
                    MetaAgentOutput(content=None),  # Empty chunk
                    MetaAgentOutput(content="I can help with WorkflowAI!"),
                ],
                [
                    [MetaAgentChatMessage(role="ASSISTANT", content="I can help with WorkflowAI!")],
                ],
            ),
            (
                "user@example.com",
                [],  # Empty messages
                [],  # No chunks expected
                [
                    [
                        MetaAgentChatMessage(
                            role="ASSISTANT",
                            content="Hi, I'm WorkflowAI's agent. How can I help you?",
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
        mock_task_run = Mock(spec=SerializableTaskRun)
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
                selected_models=PlaygroundStateDomain.SelectedModels(
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
        # Create dummy valid runs as mocks mimicking SerializableTaskRun.
        valid_runs: list[Mock] = []
        for cfg in runs_config:
            dummy_run = Mock(spec=SerializableTaskRun)
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
