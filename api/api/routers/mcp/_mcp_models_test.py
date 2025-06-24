# pyright: reportPrivateUsage=false
from datetime import date, datetime
from typing import Any
from unittest.mock import Mock

import pytest

from api.routers.mcp._mcp_models import ConciseModelResponse, MCPRun
from core.domain.error_response import ErrorResponse
from core.domain.models import Provider
from core.domain.models.model_provider_data import ModelProviderData, TextPricePerToken
from tests import models as test_models


@pytest.fixture
def mock_text_price() -> TextPricePerToken:
    """Create a mock TextPricePerToken for testing"""
    return TextPricePerToken(
        prompt_cost_per_token=0.001,
        completion_cost_per_token=0.002,
        source="test-source",
    )


@pytest.fixture
def mock_provider_data(mock_text_price: TextPricePerToken) -> ModelProviderData:
    """Create a mock ModelProviderData for testing"""
    return ModelProviderData(text_price=mock_text_price)


@pytest.fixture
def mock_final_model_data(mock_provider_data: ModelProviderData) -> Any:
    """Create a mock FinalModelData for testing"""
    model_data = Mock()
    model_data.providers = [(Provider.OPEN_AI, mock_provider_data)]
    model_data.provider_name = "OpenAI"
    model_data.display_name = "GPT-4"
    model_data.release_date = date(2024, 1, 15)
    model_data.quality_index = 100

    # Mock model_dump to return supports fields - only whitelisted ones will be included
    model_data.model_dump.return_value = {
        "supports_tool_calling": True,
        "supports_input_image": True,
        "supports_input_pdf": True,
        "supports_input_audio": True,
        "supports_audio_only": False,  # False value should be ignored
        "supports_json_mode": True,  # Not in whitelist, should be ignored
        "supports_structured_output": True,  # Not in whitelist, should be ignored
        "support_system_messages": True,  # Not in whitelist, should be ignored
        "supports_parallel_tool_calls": True,  # Not in whitelist, should be ignored
        "other_field": "value",  # Should be ignored
    }

    return model_data


class TestConciseModelResponseFromModelData:
    def test_basic_functionality(self, mock_final_model_data: Any, mock_provider_data: ModelProviderData):
        """Test basic functionality with typical model data"""
        result = ConciseModelResponse.from_model_data("test-model-id", mock_final_model_data)

        assert result.id == "test-model-id"
        assert result.display_name == "GPT-4"
        assert result.cost_per_input_token_usd == 0.001
        assert result.cost_per_output_token_usd == 0.002
        assert result.release_date == "2024-01-15"

        # Check supports filtering - only whitelisted fields that are True should be included
        expected_supports = ["tool_calling", "input_image", "input_pdf", "input_audio"]
        assert sorted(result.supports) == sorted(expected_supports)

    def test_only_whitelisted_supports_included(self, mock_final_model_data: Any):
        """Test that only whitelisted supports are included"""
        result = ConciseModelResponse.from_model_data("test-id", mock_final_model_data)

        # These should NOT be in the result because they're not in the whitelist
        assert "json_mode" not in result.supports
        assert "structured_output" not in result.supports
        assert "system_messages" not in result.supports
        assert "parallel_tool_calls" not in result.supports

        # Only whitelisted ones should be included
        for support in result.supports:
            assert support in ["tool_calling", "input_image", "input_pdf", "input_audio", "audio_only"]

    def test_empty_supports_when_none_whitelisted(self, mock_provider_data: ModelProviderData):
        """Test when model has no whitelisted supports"""
        model_data = Mock()
        model_data.providers = [(Provider.ANTHROPIC, mock_provider_data)]
        model_data.provider_name = "Anthropic"
        model_data.display_name = "Claude"
        model_data.release_date = date(2023, 5, 10)
        model_data.quality_index = 95

        # Only non-whitelisted supports
        model_data.model_dump.return_value = {
            "supports_json_mode": True,  # Not in whitelist
            "supports_structured_output": True,  # Not in whitelist
            "supports_parallel_tool_calls": True,  # Not in whitelist
            "other_field": True,  # Doesn't match whitelist pattern
        }

        result = ConciseModelResponse.from_model_data("claude-id", model_data)

        # Should be empty since no whitelisted supports are present
        assert result.supports == []

    def test_all_whitelisted_supports(self, mock_provider_data: ModelProviderData):
        """Test model with all whitelisted supports enabled"""
        model_data = Mock()
        model_data.providers = [(Provider.FIREWORKS, mock_provider_data)]
        model_data.provider_name = "Fireworks"
        model_data.display_name = "Llama 3.1"
        model_data.release_date = date(2024, 7, 23)
        model_data.quality_index = 85

        # All whitelisted supports set to True
        model_data.model_dump.return_value = {
            "supports_tool_calling": True,
            "supports_input_image": True,
            "supports_input_audio": True,
            "supports_input_pdf": True,
            "supports_audio_only": True,
            # Add some non-whitelisted ones to ensure they're ignored
            "supports_output_image": True,
            "supports_json_mode": True,
        }

        result = ConciseModelResponse.from_model_data("llama-id", model_data)

        expected_supports = [
            "tool_calling",
            "input_image",
            "input_audio",
            "input_pdf",
            "audio_only",
        ]
        assert sorted(result.supports) == sorted(expected_supports)

    def test_false_values_ignored(self, mock_provider_data: ModelProviderData):
        """Test that False values are ignored even if whitelisted"""
        model_data = Mock()
        model_data.providers = [(Provider.OPEN_AI, mock_provider_data)]
        model_data.provider_name = "Test Provider"
        model_data.display_name = "Test Model"
        model_data.release_date = date(2024, 1, 1)
        model_data.quality_index = 90

        model_data.model_dump.return_value = {
            "supports_tool_calling": True,  # Should be included
            "supports_input_image": False,  # Should be ignored (False)
            "supports_input_audio": True,  # Should be included
            "supports_input_pdf": False,  # Should be ignored (False)
            "supports_audio_only": True,  # Should be included
        }

        result = ConciseModelResponse.from_model_data("test", model_data)

        expected_supports = ["tool_calling", "input_audio", "audio_only"]
        assert sorted(result.supports) == sorted(expected_supports)

    def test_different_provider_costs(self, mock_final_model_data: Any):
        """Test with different provider cost structure"""
        # Create provider data with different costs
        expensive_price = TextPricePerToken(
            prompt_cost_per_token=0.05,
            completion_cost_per_token=0.15,
            source="expensive-provider",
        )
        expensive_provider_data = ModelProviderData(text_price=expensive_price)

        # Update the first provider data
        mock_final_model_data.providers = [(Provider.AZURE_OPEN_AI, expensive_provider_data)]

        result = ConciseModelResponse.from_model_data("expensive-model", mock_final_model_data)

        assert result.cost_per_input_token_usd == 0.05
        assert result.cost_per_output_token_usd == 0.15

    @pytest.mark.parametrize(
        "test_date,expected_iso",
        [
            (date(2024, 1, 1), "2024-01-01"),
            (date(2023, 12, 31), "2023-12-31"),
            (date(2025, 6, 15), "2025-06-15"),
        ],
    )
    def test_date_formatting(self, mock_final_model_data: Any, test_date: date, expected_iso: str):
        """Test that dates are properly formatted to ISO format"""
        mock_final_model_data.release_date = test_date

        result = ConciseModelResponse.from_model_data("date-test", mock_final_model_data)

        assert result.release_date == expected_iso

    def test_uses_first_provider_for_pricing(self, mock_final_model_data: Any):
        """Test that it uses the first provider in the list for pricing"""
        # Create a second provider with different pricing
        second_price = TextPricePerToken(
            prompt_cost_per_token=0.999,
            completion_cost_per_token=0.888,
            source="second-provider",
        )
        second_provider_data = ModelProviderData(text_price=second_price)

        # Add second provider to the list
        first_provider_data: ModelProviderData = mock_final_model_data.providers[0][1]
        mock_final_model_data.providers = [
            (Provider.OPEN_AI, first_provider_data),
            (Provider.ANTHROPIC, second_provider_data),
        ]

        result = ConciseModelResponse.from_model_data("multi-provider", mock_final_model_data)

        # Should use first provider's pricing
        assert result.cost_per_input_token_usd == 0.001  # From first provider
        assert result.cost_per_output_token_usd == 0.002  # From first provider

    def test_supports_prefix_removal(self, mock_provider_data: ModelProviderData):
        """Test that 'supports_' prefix is properly removed from whitelisted field names"""
        model_data = Mock()
        model_data.providers = [(Provider.OPEN_AI, mock_provider_data)]
        model_data.provider_name = "Test Provider"
        model_data.display_name = "Test Model"
        model_data.release_date = date(2024, 1, 1)
        model_data.quality_index = 90

        model_data.model_dump.return_value = {
            "supports_tool_calling": True,  # Whitelisted - should be included as "tool_calling"
            "supports_input_image": True,  # Whitelisted - should be included as "input_image"
            "supports_custom_feature": True,  # Not whitelisted - should be ignored
        }

        result = ConciseModelResponse.from_model_data("test", model_data)

        expected_supports = ["tool_calling", "input_image"]
        assert sorted(result.supports) == sorted(expected_supports)

    def test_whitelist_exact_matching(self, mock_provider_data: ModelProviderData):
        """Test that whitelist matching is exact (no partial matches)"""
        model_data = Mock()
        model_data.providers = [(Provider.OPEN_AI, mock_provider_data)]
        model_data.provider_name = "Test Provider"
        model_data.display_name = "Test Model"
        model_data.release_date = date(2024, 1, 1)
        model_data.quality_index = 75

        model_data.model_dump.return_value = {
            "supports_tool": True,  # Similar but not exact match to "supports_tool_calling"
            "supports_tool_calling_advanced": True,  # Similar but not exact match
            "supports_tool_calling": True,  # Exact match - should be included
            "tool_calling": True,  # Missing prefix - should be ignored
        }

        result = ConciseModelResponse.from_model_data("test", model_data)

        # Only the exact whitelist match should be included
        assert result.supports == ["tool_calling"]


class TestMCPRunFromDomain:
    def test_successful_run_with_version(self):
        """Test MCPRun.from_domain with a successful run and explicit version"""
        # Create a task group for the version
        version_group = test_models.task_group(
            group_id="version-group",
            properties={
                "model": "gpt-4-turbo",
                "temperature": 0.3,
                "instructions": "Version instructions",
                "messages": [],
                "top_p": 0.8,
                "max_tokens": 2000,
                "frequency_penalty": 0.1,
                "presence_penalty": 0.2,
            },
            semver=[2, 0],
        )

        # Create an agent run using the generator
        agent_run = test_models.task_run_ser(
            id="run-123",
            task_id="task-789",
            task_schema_id=42,
            task_input={"param1": "value1", "param2": "value2"},
            task_output={"result": "success"},
            model="gpt-4",
            status="success",
            duration_seconds=2.5,
            cost_usd=0.05,
            created_at=datetime(2024, 1, 15, 10, 30, 0),
            metadata={"key": "metadata_value"},
            conversation_id="conv-456",
        )

        output_schema = {"type": "object", "properties": {"result": {"type": "string"}}}

        result = MCPRun.from_domain(agent_run, version_group, output_schema, "")

        assert result.id == "run-123"
        assert result.conversation_id == "conv-456"
        assert result.agent_id == "task-789"
        assert result.agent_schema_id == 42
        assert result.status == "success"
        assert result.agent_input == {"param1": "value1", "param2": "value2"}
        # The messages property computes messages from task output, not input messages
        assert len(result.messages) == 1
        assert result.messages[0].role == "assistant"
        assert result.duration_seconds == 2.5
        assert result.cost_usd == 0.05
        assert result.created_at == datetime(2024, 1, 15, 10, 30, 0)
        assert result.metadata == {"key": "metadata_value"}
        assert result.response_json_schema == output_schema
        assert result.error is None

        # Check that agent_version is created from the provided version
        assert result.agent_version.id == "2.0"
        assert result.agent_version.model == "gpt-4-turbo"
        assert result.agent_version.temperature == 0.3

    def test_successful_run_without_version(self):
        """Test MCPRun.from_domain with a successful run but no explicit version (uses run.group)"""
        agent_run = test_models.task_run_ser(
            id="run-456",
            task_id="task-123",
            task_schema_id=99,
            model="gpt-4",
            status="success",
        )

        result = MCPRun.from_domain(agent_run, None, None, "")

        assert result.id == "run-456"
        assert result.status == "success"
        assert result.agent_id == "task-123"
        assert result.agent_schema_id == 99

        # Check that agent_version is created from run.group since version is None
        assert result.agent_version.model == "gpt-4"

    def test_error_run(self):
        """Test MCPRun.from_domain with a failed run"""
        # Create an error response
        error = ErrorResponse.Error(code="test_error", message="Test error message", details={"key": "value"})

        agent_run = test_models.task_run_ser(
            id="run-error-123",
            task_id="task-error-789",
            task_schema_id=99,
            status="failure",  # Use "failure" not "failed"
            task_input={"error_param": "error_value"},
            duration_seconds=1.0,
            cost_usd=0.02,
            created_at=datetime(2024, 1, 16, 14, 45, 0),
            metadata={"error_key": "error_metadata"},
            conversation_id="conv-error-456",
            error=error,
        )

        result = MCPRun.from_domain(agent_run, None, None, "")

        assert result.id == "run-error-123"
        assert result.status == "error"  # Non-success status should map to "error"
        assert result.error is not None
        assert result.error.code == "test_error"
        assert result.error.message == "Test error message"
        assert result.error.details == {"key": "value"}

    def test_none_conversation_id(self):
        """Test MCPRun.from_domain when conversation_id is None"""
        agent_run = test_models.task_run_ser(
            id="run-no-conv",
            conversation_id=None,
        )

        result = MCPRun.from_domain(agent_run, None, None, "")

        # conversation_id should default to empty string when None
        assert result.conversation_id == ""

    def test_none_task_input(self):
        """Test MCPRun.from_domain when task_input is None"""
        # The generator sets default task_input, so we need to override after creation
        agent_run = test_models.task_run_ser(id="run-no-input")
        agent_run.task_input = None

        result = MCPRun.from_domain(agent_run, None, None, "")

        assert result.agent_input is None

    def test_task_input_filtering_workflowai_messages(self):
        """Test that 'workflowai.messages' key is filtered out from task_input"""
        agent_run = test_models.task_run_ser(
            id="run-filtered",
            task_input={
                "param1": "value1",
                "workflowai.messages": [{"role": "user", "content": "should be filtered"}],
                "param2": "value2",
            },
        )

        result = MCPRun.from_domain(agent_run, None, None, "")

        # 'workflowai.messages' should be filtered out
        expected_input = {"param1": "value1", "param2": "value2"}
        assert result.agent_input == expected_input

    def test_task_input_only_workflowai_messages(self):
        """Test when task_input only contains 'workflowai.messages'"""
        agent_run = test_models.task_run_ser(
            id="run-only-filtered",
            task_input={
                "workflowai.messages": [{"role": "user", "content": "only filtered content"}],
            },
        )

        result = MCPRun.from_domain(agent_run, None, None, "")

        # Should result in empty dict, not None
        assert result.agent_input == {}

    def test_empty_task_input(self):
        """Test when task_input is empty"""
        agent_run = test_models.task_run_ser(
            id="run-empty-input",
            task_input={},
        )

        result = MCPRun.from_domain(agent_run, None, None, "")

        # Empty dict is falsy, so the conditional evaluates to None
        assert result.agent_input is None

    def test_status_mapping(self):
        """Test status mapping for different run statuses"""
        # Test success status
        success_run = test_models.task_run_ser(id="success-run", status="success")
        result = MCPRun.from_domain(success_run, None, None, "")
        assert result.status == "success"

        # Test failure status maps to "error"
        failure_run = test_models.task_run_ser(id="failure-run", status="failure")
        result = MCPRun.from_domain(failure_run, None, None, "")
        assert result.status == "error"

    def test_none_values_handling(self):
        """Test handling of None values in optional fields"""
        agent_run = test_models.task_run_ser(
            id="run-none-values",
            duration_seconds=None,
            cost_usd=None,
            metadata=None,
        )

        result = MCPRun.from_domain(agent_run, None, None, "")

        assert result.duration_seconds is None
        assert result.cost_usd is None
        assert result.metadata is None

    def test_with_output_schema(self):
        """Test MCPRun.from_domain with various output schema configurations"""
        agent_run = test_models.task_run_ser(id="schema-test")

        # Test with complex schema
        complex_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "items": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["name"],
        }

        result = MCPRun.from_domain(agent_run, None, complex_schema, "")
        assert result.response_json_schema == complex_schema

        # Test with None schema
        result = MCPRun.from_domain(agent_run, None, None, "")
        assert result.response_json_schema is None

    @pytest.mark.parametrize(
        "created_at,expected_created_at",
        [
            (datetime(2024, 1, 1, 0, 0, 0), datetime(2024, 1, 1, 0, 0, 0)),
            (datetime(2023, 12, 25, 15, 30, 45), datetime(2023, 12, 25, 15, 30, 45)),
            (datetime(2025, 6, 15, 9, 15, 30), datetime(2025, 6, 15, 9, 15, 30)),
        ],
    )
    def test_datetime_handling(self, created_at: datetime, expected_created_at: datetime):
        """Test that datetime values are properly handled"""
        agent_run = test_models.task_run_ser(
            id="datetime-test",
            created_at=created_at,
        )

        result = MCPRun.from_domain(agent_run, None, None, "")

        assert result.created_at == expected_created_at
