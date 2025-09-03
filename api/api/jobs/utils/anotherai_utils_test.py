# pyright: reportPrivateUsage=false

from typing import Any
from unittest.mock import Mock

import pytest

from api.jobs.utils.anotherai_utils import AnotherAIService, _Message
from api.services.runs.runs_service import RunsService
from core.domain.error_response import ErrorResponse
from core.domain.task_io import SerializableTaskIO
from core.domain.tool_call import ToolCallRequestWithID
from core.storage.backend_storage import BackendStorage
from tests import models as test_models


@pytest.fixture
def mock_storage():
    return Mock(spec=BackendStorage)


@pytest.fixture
def mock_runs_service():
    return Mock(spec=RunsService)


@pytest.fixture
def anotherai_service(mock_storage: Mock, mock_runs_service: Mock):
    return AnotherAIService(storage=mock_storage, runs_service=mock_runs_service)


class TestCompletionFromDomain:
    async def test_basic_completion_with_string_output(self, anotherai_service: AnotherAIService):
        """Test basic completion with string task output."""
        run = test_models.task_run_ser(
            id="test_run_id",
            task_id="test_task_id",
            task_output="Hello, world!",
            cost_usd=0.05,
            duration_seconds=2.5,
        )
        task_variant = test_models.task_variant()

        completion = await anotherai_service._convert_run(run, task_variant)

        assert completion.id == "test_run_id"
        assert completion.agent_id == "test_task_id"
        assert completion.cost_usd == 0.05
        assert completion.duration_seconds == 2.5
        assert completion.output.messages is not None
        assert len(completion.output.messages) == 1
        assert completion.output.messages[0].role == "assistant"
        assert len(completion.output.messages[0].content) == 1
        assert isinstance(completion.output.messages[0].content, list)
        assert completion.output.messages[0].content[0].text == "Hello, world!"
        assert completion.output.error is None
        assert completion.messages == []  # TODO: handle completions

    async def test_completion_with_dict_output(self, anotherai_service: AnotherAIService):
        """Test completion with dictionary task output."""
        task_output = {"result": "success", "value": 42}
        run = test_models.task_run_ser(
            task_output=task_output,
            cost_usd=0.03,
        )
        task_variant = test_models.task_variant()

        completion = await anotherai_service._convert_run(run, task_variant)

        assert completion.output.messages is not None
        assert len(completion.output.messages) == 1
        assert isinstance(completion.output.messages[0].content, list)
        assert completion.output.messages[0].content[0].object == task_output
        assert completion.output.messages[0].content[0].text is None
        assert completion.cost_usd == 0.03

    async def test_completion_with_list_output(self, anotherai_service: AnotherAIService):
        """Test completion with list task output."""
        task_output = ["item1", "item2", "item3"]
        run = test_models.task_run_ser(
            task_output=task_output,
            cost_usd=0.02,
        )
        task_variant = test_models.task_variant()

        completion = await anotherai_service._convert_run(run, task_variant)

        assert completion.output.messages is not None
        assert len(completion.output.messages) == 1
        assert isinstance(completion.output.messages[0].content, list)
        assert completion.output.messages[0].content[0].object == task_output
        assert completion.output.messages[0].content[0].text is None

    async def test_completion_with_tool_call_requests(self, anotherai_service: AnotherAIService):
        """Test completion with tool call requests."""
        tool_call_requests = [
            ToolCallRequestWithID(
                id="tool_call_1",
                tool_name="calculator",
                tool_input_dict={"expression": "2 + 2"},
            ),
            ToolCallRequestWithID(
                id="tool_call_2",
                tool_name="search",
                tool_input_dict={"query": "python testing"},
            ),
        ]
        run = test_models.task_run_ser(
            task_output="Calculation complete",
            tool_call_requests=tool_call_requests,
        )
        task_variant = test_models.task_variant()

        completion = await anotherai_service._convert_run(run, task_variant)

        assert completion.output.messages is not None
        assert len(completion.output.messages) == 1
        # Should have 1 text content + 2 tool call requests = 3 content items
        assert len(completion.output.messages[0].content) == 3

        # Check text content
        assert isinstance(completion.output.messages[0].content, list)
        text_content = completion.output.messages[0].content[0]
        assert text_content.text == "Calculation complete"

        # Check tool call requests
        tool_call_content_1 = completion.output.messages[0].content[1]
        assert tool_call_content_1.tool_call_request is not None
        assert tool_call_content_1.tool_call_request.id == "tool_call_1"
        assert tool_call_content_1.tool_call_request.name == "calculator"
        assert tool_call_content_1.tool_call_request.arguments == {"expression": "2 + 2"}

        tool_call_content_2 = completion.output.messages[0].content[2]
        assert tool_call_content_2.tool_call_request is not None
        assert tool_call_content_2.tool_call_request.id == "tool_call_2"
        assert tool_call_content_2.tool_call_request.name == "search"
        assert tool_call_content_2.tool_call_request.arguments == {"query": "python testing"}

    async def test_completion_with_error(self, anotherai_service: AnotherAIService):
        """Test completion with error response."""
        error = ErrorResponse.Error(message="Something went wrong", code="TEST_ERROR")
        run = test_models.task_run_ser(
            task_output=None,
            error=error,
            cost_usd=0.01,
        )
        run.task_output = None
        task_variant = test_models.task_variant()

        completion = await anotherai_service._convert_run(run, task_variant)

        assert completion.output.messages is None
        assert completion.output.error is not None
        assert completion.output.error.error == "Something went wrong"
        assert completion.cost_usd == 0.01

    async def test_completion_with_none_cost(self, anotherai_service: AnotherAIService):
        """Test completion when cost_usd is None."""
        run = test_models.task_run_ser(
            task_output="Test output",
            cost_usd=None,
        )
        task_variant = test_models.task_variant()

        completion = await anotherai_service._convert_run(run, task_variant)

        assert completion.cost_usd == 0  # Should default to 0 when None

    async def test_completion_with_none_duration(self, anotherai_service: AnotherAIService):
        """Test completion when duration_seconds is None."""
        run = test_models.task_run_ser(
            task_output="Test output",
            duration_seconds=None,
        )
        task_variant = test_models.task_variant()

        completion = await anotherai_service._convert_run(run, task_variant)

        assert completion.duration_seconds is None

    async def test_completion_with_complex_task_input(self, anotherai_service: AnotherAIService):
        """Test completion with complex task input containing variables."""
        complex_input = {
            "messages": [{"role": "user", "content": "Hello"}],
            "variables": {"name": "Alice", "age": 30},
        }
        run = test_models.task_run_ser(
            task_input=complex_input,
            task_output="Response generated",
        )
        task_variant = test_models.task_variant()

        completion = await anotherai_service._convert_run(run, task_variant)

        # The input should be processed by _Input.from_raw_input
        assert completion.input is not None
        # Detailed input testing should be covered in _Input tests

    async def test_completion_with_empty_task_output(self, anotherai_service: AnotherAIService):
        """Test completion with empty/None task output and no tool calls."""
        run = test_models.task_run_ser(
            task_output=None,
            tool_call_requests=None,
        )
        run.task_output = None
        task_variant = test_models.task_variant()

        completion = await anotherai_service._convert_run(run, task_variant)

        assert completion.output.messages is None
        assert completion.output.error is None

    async def test_completion_preserves_all_run_fields(self, anotherai_service: AnotherAIService):
        """Test that all relevant fields from AgentRun are preserved in completion."""
        run = test_models.task_run_ser(
            id="unique_run_id",
            task_id="unique_task_id",
            task_output="Test response",
            cost_usd=1.23,
            duration_seconds=45.67,
        )
        task_variant = test_models.task_variant(
            id="test_variant_id",
            task_id="unique_task_id",
            task_schema_id=5,
        )

        completion = await anotherai_service._convert_run(run, task_variant)

        assert completion.id == "unique_run_id"
        assert completion.agent_id == "unique_task_id"
        assert completion.cost_usd == 1.23
        assert completion.duration_seconds == 45.67
        assert completion.version is not None  # Should be created by _Version.from_domain
        assert completion.input is not None  # Should be created by _Input.from_raw_input
        assert completion.output is not None  # Should be created by _Output.from_domain

    @pytest.mark.parametrize(
        "task_output,expected_content_count",
        [
            ("string output", 1),
            ({"key": "value"}, 1),
            ([1, 2, 3], 1),
        ],
    )
    async def test_completion_content_count_by_output_type(
        self,
        anotherai_service: AnotherAIService,
        task_output: Any,
        expected_content_count: int,
    ):
        """Test that different output types create the expected number of content items."""
        run = test_models.task_run_ser(
            task_output=task_output,
            tool_call_requests=None,
        )
        task_variant = test_models.task_variant()

        completion = await anotherai_service._convert_run(run, task_variant)

        if expected_content_count == 0:
            assert completion.output.messages is None
        else:
            assert completion.output.messages is not None
            assert len(completion.output.messages) == 1
            assert len(completion.output.messages[0].content) == expected_content_count

    async def test_prompt_from_instructions_no_variables(self, anotherai_service: AnotherAIService):
        run = test_models.task_run_ser(task_input={"input": "world"})
        run.group.properties.instructions = "You are a helpful assistant."
        task_variant = test_models.task_variant()

        completion = await anotherai_service._convert_run(run, task_variant)
        assert completion.input.messages is None
        assert completion.input.variables == {"input": "world"}

        assert completion.version.input_variables_schema == {
            "properties": {
                "input": {
                    "type": "string",
                },
            },
            "required": [
                "input",
            ],
            "type": "object",
        }

        assert completion.version.prompt == [
            _Message(role="system", content="You are a helpful assistant."),
            _Message(role="user", content="input: {{input}}"),
        ]

    async def test_prompt_from_templated_instructions(self, anotherai_service: AnotherAIService):
        run = test_models.task_run_ser(task_input={"input": "world", "hello": "world"})
        run.group.properties.instructions = "You are a helpful assistant. {{input}}"
        task_variant = test_models.task_variant(
            input_schema={
                "properties": {"input": {"type": "string"}, "hello": {"type": "string"}},
                "required": ["input", "hello"],
            },
        )

        completion = await anotherai_service._convert_run(run, task_variant)
        assert completion.input.messages is None
        assert completion.input.variables == {"input": "world", "hello": "world"}

        assert completion.version.prompt == [
            _Message(role="system", content="You are a helpful assistant. {{input}}"),
            _Message(role="user", content="hello: {{hello}}"),
        ]

        assert completion.version.input_variables_schema == task_variant.input_schema.json_schema

    async def test_prompt_with_files(self, anotherai_service: AnotherAIService):
        run = test_models.task_run_ser(task_input={"file": {"url": "https://blabla/file.png"}})
        run.group.properties.instructions = "You are a helpful assistant"
        task_variant = test_models.task_variant(
            input_io=SerializableTaskIO.from_json_schema(
                {
                    "properties": {"file": {"$ref": "#/$defs/File"}},
                },
                streamline=True,
            ),
        )

        completion = await anotherai_service._convert_run(run, task_variant)
        assert completion.input.messages == [
            _Message(role="user", content=[_Message.Content(image_url="https://blabla/file.png")]),
        ]
        assert completion.input.variables is None

        assert completion.version.prompt == [
            _Message(role="system", content="You are a helpful assistant"),
        ]

        assert completion.version.input_variables_schema is None
