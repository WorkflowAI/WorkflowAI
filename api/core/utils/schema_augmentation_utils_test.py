import logging
from typing import Any
from unittest import mock
from unittest.mock import patch

from core.utils.schema_augmentation_utils import (
    add_agent_run_result_to_schema,
    add_reasoning_steps_to_schema,
)


class TestAddReasoningSteps:
    def test_add_reasoning_steps_to_empty_schema(self):
        """Test adding reasoning steps to an empty schema with no properties"""
        output_schema: dict[str, Any] = {}

        with patch.object(logging.getLogger("core.utils.schema_augmentation_utils"), "exception") as mock_logger:
            add_reasoning_steps_to_schema(output_schema)  # pyright: ignore[reportPrivateUsage]

        assert output_schema == {}
        mock_logger.assert_called_once_with(
            "Output schema has no properties, skipping schema addition",
            extra={"output_schema": {}},
        )

    def test_add_reasoning_steps_to_object_schema(self):
        """Test adding reasoning steps to a non-object schema"""
        output_schema: dict[str, Any] = {"type": "object"}

        add_reasoning_steps_to_schema(output_schema)  # pyright: ignore[reportPrivateUsage]
        assert output_schema == {
            "type": "object",
            "properties": {
                "internal_reasoning_steps": mock.ANY,
            },
        }

    def test_add_reasoning_steps_when_already_present(self):
        """Test adding reasoning steps when they already exist in schema"""
        output_schema = {
            "properties": {
                "internal_reasoning_steps": {"type": "array"},
            },
        }

        # with patch.object(logging.getLogger("core.utils.schema_augmentation_utils"), "warning") as mock_logger:
        add_reasoning_steps_to_schema(output_schema)  # pyright: ignore[reportPrivateUsage]

        assert output_schema == {
            "properties": {
                "internal_reasoning_steps": {"type": "array"},
            },
        }
        # mock_logger.assert_called_once_with(
        #     "Property already in output schema, skipping",
        #     extra={"property_name": "internal_reasoning_steps"},
        # )

    def test_add_reasoning_steps_with_existing_properties(self):
        """Test adding reasoning steps to schema with existing properties"""
        output_schema = {
            "properties": {
                "existing_field": {"type": "string"},
            },
        }

        with patch.object(logging.getLogger("core.utils.schema_augmentation_utils"), "exception") as mock_logger:
            add_reasoning_steps_to_schema(output_schema)  # pyright: ignore[reportPrivateUsage]

        # Check that both original and new properties exist
        assert "existing_field" in output_schema["properties"]
        assert "internal_reasoning_steps" in output_schema["properties"]

        # Check that reasoning steps schema was properly merged
        assert output_schema == {
            "properties": {
                "internal_reasoning_steps": {
                    "description": "An array of reasoning steps",
                    "items": {
                        "type": "object",
                        "properties": {
                            "explaination": {
                                "description": "The explanation for this step of reasoning",
                                "type": "string",
                            },
                            "output": {
                                "description": "The output or conclusion from this step",
                                "type": "string",
                            },
                            "title": {
                                "description": "A brief title for this step (maximum a few words)",
                                "type": "string",
                            },
                        },
                    },
                    "type": "array",
                },
                "existing_field": {"type": "string"},
            },
        }

        # Verify logger was not called
        mock_logger.assert_not_called()

    def test_add_reasoning_steps_with_existing_defs(self):
        """Test adding reasoning steps to schema with existing $defs"""
        output_schema = {
            "properties": {},
            "$defs": {
                "existing_def": {"type": "string"},
            },
        }

        with patch.object(logging.getLogger("core.utils.schema_augmentation_utils"), "exception") as mock_logger:
            add_reasoning_steps_to_schema(output_schema)  # pyright: ignore[reportPrivateUsage]

        assert output_schema == {
            "properties": {
                "internal_reasoning_steps": {
                    "description": "An array of reasoning steps",
                    "items": {
                        "type": "object",
                        "properties": {
                            "explaination": {
                                "description": "The explanation for this step of reasoning",
                                "type": "string",
                            },
                            "output": {
                                "description": "The output or conclusion from this step",
                                "type": "string",
                            },
                            "title": {
                                "description": "A brief title for this step (maximum a few words)",
                                "type": "string",
                            },
                        },
                    },
                    "type": "array",
                },
            },
            "$defs": {
                "existing_def": {"type": "string"},
            },
        }

        # Verify logger was not called
        mock_logger.assert_not_called()


class TestAddAgentRunResult:
    def test_add_agent_run_result_to_empty_schema(self):
        """Test adding agent run result to an empty schema with no properties"""
        output_schema: dict[str, Any] = {}

        with patch.object(logging.getLogger("core.utils.schema_augmentation_utils"), "exception") as mock_logger:
            add_agent_run_result_to_schema(output_schema)  # pyright: ignore[reportPrivateUsage]

        assert output_schema == {}
        mock_logger.assert_called_once_with(
            "Output schema has no properties, skipping schema addition",
            extra={"output_schema": {}},
        )

    def test_add_agent_run_result_when_already_present(self):
        """Test adding agent run result when it already exists in schema"""
        output_schema = {
            "properties": {
                "internal_agent_run_result": {"type": "object"},
            },
        }

        # with patch.object(logging.getLogger("core.utils.schema_augmentation_utils"), "warning") as mock_logge:
        add_agent_run_result_to_schema(output_schema)  # pyright: ignore[reportPrivateUsage]

        assert output_schema == {
            "properties": {
                "internal_agent_run_result": {"type": "object"},
            },
        }
        # mock_logger.assert_called_once_with(
        #     "Property already in output schema, skipping",
        #     extra={"property_name": "internal_agent_run_result"},
        # )

    def test_add_agent_run_result_with_existing_properties(self):
        """Test adding agent run result to schema with existing properties"""
        output_schema = {
            "properties": {
                "existing_field": {"type": "string"},
            },
        }

        with patch.object(logging.getLogger("core.utils.schema_augmentation_utils"), "exception") as mock_logger:
            add_agent_run_result_to_schema(output_schema)  # pyright: ignore[reportPrivateUsage]

        # Check that both original and new properties exist
        assert "existing_field" in output_schema["properties"]
        assert "internal_agent_run_result" in output_schema["properties"]
        # Check that agent run result schema was properly merged

        assert output_schema == {
            "properties": {
                "existing_field": {
                    "type": "string",
                },
                "internal_agent_run_result": {
                    "type": "object",
                    "description": "The status of the agent run, needs to be filled whether the run was successful or not",
                    "properties": {
                        "error": {
                            "description": "The error that occurred during the agent run, to fill in case of status='failure'",
                            "properties": {
                                "error_code": {
                                    "description": "The type of error that occurred during the agent "
                                    "run, 'tool_call_error' if an error occurred "
                                    "during a tool call, 'missing_tool' if the agent "
                                    "is missing a tool in order to complete the run, "
                                    "'other' for any other error",
                                    "enum": [
                                        "tool_call_error",
                                        "missing_tool",
                                        "other",
                                    ],
                                    "type": "string",
                                },
                                "error_message": {
                                    "description": "A summary of the error that occurred during the agent run",
                                    "type": "string",
                                },
                            },
                            "type": "object",
                        },
                        "status": {
                            "description": "Whether the agent run was successful or not",
                            "enum": [
                                "success",
                                "failure",
                            ],
                            "type": "string",
                        },
                    },
                },
            },
        }

        # Verify logger was not called
        mock_logger.assert_not_called()
