from typing import Any
from unittest.mock import Mock, patch

from pydantic import BaseModel

from api.services.internal_tasks.custom_tool_creation_service import CustomToolService
from core.domain.fields.custom_tool_creation_chat_message import CustomToolCreationChatMessage
from tests.utils import mock_aiter


async def test_stream_creation_agent_with_dict_answer() -> None:
    """Test that stream_creation_agent validates dict answers correctly."""

    class DummyOutput(BaseModel):
        answer: Any

    dummy_output = DummyOutput(answer={"role": "ASSISTANT", "content": "dummy response"})

    # Patch the agent function that yields the agent outputs
    with patch(
        "api.services.internal_tasks.custom_tool_creation_service.stream_custom_tool_creation_agent",
        return_value=mock_aiter(dummy_output),
    ):
        # Create a valid CustomToolCreationChatMessage as input
        input_message = CustomToolCreationChatMessage.model_construct(role="user", content="Test")
        messages = [input_message]
        results = [msg async for msg in CustomToolService.stream_creation_agent(messages)]
        # The returned message should be a validated CustomToolCreationChatMessage
        assert results, "No output received"
        validated = results[0]
        assert validated.role == "ASSISTANT", f"Expected role 'ASSISTANT', got {validated.role}"
        assert validated.content == "dummy response", f"Expected content 'dummy response', got {validated.content}"


async def test_stream_creation_agent_with_non_dict_answer() -> None:
    """Test that stream_creation_agent yields non-dict answers as-is."""

    class DummyOutputNested(BaseModel):
        field: str

    class DummyOutput(BaseModel):
        answer: Any

    dummy_output = DummyOutput(answer=DummyOutputNested(field="value"))

    with patch(
        "api.services.internal_tasks.custom_tool_creation_service.stream_custom_tool_creation_agent",
        return_value=mock_aiter(dummy_output),
    ):
        input_message = CustomToolCreationChatMessage.model_construct(role="user", content="Test")
        messages = [input_message]
        results = [msg async for msg in CustomToolService.stream_creation_agent(messages)]
        assert results, "No output received"
        # Since answer was not a dict, it should be yielded as-is
        assert results[0] == DummyOutputNested(field="value")


async def test_stream_example_input() -> None:
    """Test that stream_example_input yields the example input from the agent."""

    class DummyInputOutput:
        example_tool_input: Any

    dummy_output = DummyInputOutput()
    dummy_output.example_tool_input = {"sample": "input"}

    with patch(
        "api.services.internal_tasks.custom_tool_creation_service.tool_input_example_agent",
        return_value=mock_aiter(dummy_output),
    ):
        results = [output async for output in CustomToolService.stream_example_input("ToolName", "ToolDescription", {})]
        assert results, "No output received"
        # The service should yield the example input
        assert results[0] == {"sample": "input"}


async def test_stream_example_output() -> None:
    """Test that stream_example_output yields the agent output correctly."""

    class DummyOutput(BaseModel):
        example_tool_output_string: str
        example_tool_output_json: dict[str, Any]

    dummy_output = DummyOutput(example_tool_output_string="Output string", example_tool_output_json={"key": "value"})
    dummy_run = Mock(id="test_run_id", output=dummy_output)

    with patch(
        "api.services.internal_tasks.custom_tool_creation_service.tool_output_example_agent.stream",
        return_value=mock_aiter(dummy_run),
    ):
        results = [
            output
            async for output in CustomToolService.stream_example_output(
                "ToolName",
                "ToolDescription",
                {"input": "x"},
                previous_run_id=None,
                new_user_message=None,
            )
        ]
        assert results, "No output received"
        output = results[0]
        assert output.example_tool_output_string == "Output string", (
            f"Expected 'Output string', got {output.example_tool_output_string}"
        )
        assert output.example_tool_output_json == {
            "key": "value",
        }, f"Expected output json {{'key': 'value'}}, got {output.example_tool_output_json}"


async def test_stream_example_output_with_follow_up_request() -> None:
    """Test that stream_example_output yields the agent output correctly."""

    class DummyOutput(BaseModel):
        example_tool_output_string: str
        example_tool_output_json: dict[str, Any]

    dummy_output = DummyOutput(example_tool_output_string="Output string", example_tool_output_json={"key": "value"})
    dummy_run = Mock(id="test_run_id", output=dummy_output)

    with patch(
        "api.services.internal_tasks.custom_tool_creation_service.tool_output_example_agent.reply",
        return_value=dummy_run,
    ) as mock_reply:
        results = [
            output
            async for output in CustomToolService.stream_example_output(
                "ToolName",
                "ToolDescription",
                {"input": "x"},
                previous_run_id="test_run_id",
                new_user_message="Test",
            )
        ]
        assert results, "No output received"
        output = results[0]
        assert output.example_tool_output_string == "Output string", (
            f"Expected 'Output string', got {output.example_tool_output_string}"
        )
        assert output.example_tool_output_json == {
            "key": "value",
        }, f"Expected output json {{'key': 'value'}}, got {output.example_tool_output_json}"
        mock_reply.assert_called_once_with("test_run_id", "Test")
