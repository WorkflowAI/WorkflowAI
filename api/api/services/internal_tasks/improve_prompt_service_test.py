from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, Mock, patch

import pytest
from workflowai import Run

from api.services.internal_tasks.improve_prompt_service import ImprovePromptService
from core.agents.chat_task_schema_generation.apply_field_updates import InputFieldUpdate, OutputFieldUpdate
from core.agents.improve_prompt import ImprovePromptAgentOutput
from core.domain.task_group import TaskGroup
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_variant import SerializableTaskVariant
from tests import models
from tests.utils import mock_aiter


def _improve_task_output(
    improved_prompt: str = "This is an improved prompt",
    field_updates: list[OutputFieldUpdate] | None = None,
    input_field_updates: list[InputFieldUpdate] | None = None,
):
    return ImprovePromptAgentOutput(
        improved_prompt=improved_prompt,
        changelog=["Minor tweaks"],
        output_field_updates=field_updates,
        input_field_updates=input_field_updates,
    )


def _run(output: ImprovePromptAgentOutput):
    return Run(
        id="1",
        agent_id="1",
        schema_id=1,
        output=output,
    )


@pytest.fixture
def improve_prompt_service(mock_storage: Mock):
    return ImprovePromptService(mock_storage)


@pytest.fixture
def patched_logger(improve_prompt_service: ImprovePromptService):
    with patch.object(improve_prompt_service, "_logger") as mock:
        yield mock


@pytest.fixture
def patched_improve_prompt_run():
    with patch(
        "api.services.internal_tasks.improve_prompt_service.run_improve_prompt_agent",
        new_callable=AsyncMock,
    ) as mock:
        yield mock


@pytest.fixture
def patched_improve_prompt_stream():
    with patch("api.services.internal_tasks.improve_prompt_service.run_improve_prompt_agent", autospec=True) as mock:
        mock.stream = Mock()
        yield mock.stream


class TestImprovePrompt:
    @pytest.fixture(autouse=True)
    def fetched_properties(self, mock_storage: Mock):
        properties = TaskGroupProperties.model_validate(
            {
                "model": "model",
                "instructions": "You are a helpful assistant.",
                "task_variant_id": "1",
            },
        )
        mock_storage.task_groups.get_task_group_by_id.return_value = TaskGroup(
            properties=properties,
        )
        return properties

    @pytest.fixture(autouse=True)
    def fetched_variant(self, mock_storage: Mock):
        task_variant = models.task_variant(
            input_schema={
                "type": "object",
                "properties": {
                    "input_field": {"type": "string"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "result": {"type": "string"},
                },
            },
        )
        mock_storage.task_version_resource_by_id.return_value = task_variant
        return task_variant

    @pytest.fixture(autouse=True)
    def fetched_run(self, mock_storage: Mock):
        task_run = models.task_run_ser(
            task_input={"input_field": "test"},
            task_output={"result": "test"},
        )
        mock_storage.task_runs.fetch_task_run_resource.return_value = task_run
        return task_run

    async def test_run_schema_updated(
        self,
        patched_improve_prompt_run: Mock,
        improve_prompt_service: ImprovePromptService,
        mock_storage: Mock,
        fetched_variant: SerializableTaskVariant,
    ):
        patched_improve_prompt_run.return_value = _improve_task_output(
            field_updates=[
                OutputFieldUpdate(
                    keypath="result",
                    updated_description="A test string field",
                    updated_examples=["example1", "example2"],
                ),
            ],
            input_field_updates=[
                InputFieldUpdate(
                    keypath="input_field",
                    updated_description="A test input field",
                ),
            ],
        )

        mock_storage.store_task_resource.return_value = fetched_variant.model_copy(update={"id": "new_id"}), True

        # Act
        result = await improve_prompt_service.run(("", 1), "1", None, None, "This is a user evaluation.")

        # Assert
        # Test that we stored a new task variant, since there are schema updates
        mock_storage.store_task_resource.assert_awaited_once()
        created_variant: SerializableTaskVariant = mock_storage.store_task_resource.call_args.args[0]
        assert created_variant.input_schema.json_schema == {
            "type": "object",
            "properties": {
                "input_field": {
                    "type": "string",
                    "description": "A test input field",
                },
            },
        }
        assert created_variant.output_schema.json_schema == {
            "type": "object",
            "properties": {
                "result": {
                    "type": "string",
                    "description": "A test string field",
                    "examples": [
                        "example1",
                        "example2",
                    ],
                },
            },
        }

        assert result == (
            TaskGroupProperties.model_validate(
                {
                    "model": "model",
                    "instructions": "This is an improved prompt",
                    "task_variant_id": "new_id",
                },
            ),
            ["Minor tweaks"],
        )
        # Check that the improve prompt task was called with the correct input
        patched_improve_prompt_run.assert_awaited_once()
        task_input = patched_improve_prompt_run.call_args.args[0]
        assert task_input.user_evaluation == "This is a user evaluation."

    async def test_run_no_field_updates(
        self,
        patched_improve_prompt_run: Mock,
        improve_prompt_service: ImprovePromptService,
        mock_storage: Mock,
    ):
        patched_improve_prompt_run.return_value = _improve_task_output()

        # Act
        result = await improve_prompt_service.run(("", 1), "1", None, None, "This is a user evaluation.")

        # Assert
        # Test that we did not store a new task variant, since there is no 'improved_output_schema'
        mock_storage.store_task_resource.assert_not_called()
        assert result == (
            TaskGroupProperties.model_validate(
                {
                    "model": "model",
                    "instructions": "This is an improved prompt",
                    "task_variant_id": "1",
                },
            ),
            ["Minor tweaks"],
        )

        mock_storage.store_task_resource.assert_not_called()

    async def test_stream_schema_updated(
        self,
        patched_improve_prompt_stream: Mock,
        improve_prompt_service: ImprovePromptService,
        mock_storage: Mock,
        fetched_variant: SerializableTaskVariant,
    ):
        patched_improve_prompt_stream.return_value = mock_aiter(
            _run(_improve_task_output(improved_prompt="This is an")),
            _run(_improve_task_output(improved_prompt="This is an improved prompt")),
            _run(
                _improve_task_output(
                    improved_prompt="This is an improved prompt",
                    field_updates=[],
                    input_field_updates=[],
                ),
            ),
            _run(
                _improve_task_output(
                    improved_prompt="This is an improved prompt",
                    field_updates=[
                        OutputFieldUpdate(
                            keypath="result",
                        ),
                    ],
                    input_field_updates=[
                        InputFieldUpdate(
                            keypath="input_field",
                        ),
                    ],
                ),
            ),
            _run(
                _improve_task_output(
                    improved_prompt="This is an improved prompt",
                    field_updates=[
                        OutputFieldUpdate(
                            keypath="result",
                            updated_description="A test string field",
                            updated_examples=["example1", "example2"],
                        ),
                    ],
                    input_field_updates=[
                        InputFieldUpdate(
                            keypath="input_field",
                            updated_description="A test input field",
                        ),
                    ],
                ),
            ),
        )

        mock_storage.store_task_resource.return_value = fetched_variant.model_copy(update={"id": "new_id"}), True

        # Act

        chunks = [
            c
            async for c in improve_prompt_service.stream(
                task_tuple=("", 1),
                run_id="1",
                variant_id=None,
                instructions=None,
                user_evaluation="This is a user evaluation.",
            )
        ]
        assert len(chunks) == 6  # 5 + 1 when the task variant is updated

        assert chunks[0][0].instructions == "This is an"
        assert chunks[0][0] != "new_id", "sanity"
        assert chunks[-1][0].task_variant_id == "new_id"

        # Test that we stored a new task variant, since there are schema updates
        mock_storage.store_task_resource.assert_awaited_once()
        created_variant: SerializableTaskVariant = mock_storage.store_task_resource.call_args.args[0]
        assert created_variant.input_schema.json_schema == {
            "type": "object",
            "properties": {
                "input_field": {
                    "type": "string",
                    "description": "A test input field",
                },
            },
        }
        assert created_variant.output_schema.json_schema == {
            "type": "object",
            "properties": {
                "result": {
                    "type": "string",
                    "description": "A test string field",
                    "examples": [
                        "example1",
                        "example2",
                    ],
                },
            },
        }

    async def test_stream_no_field_updates(
        self,
        patched_improve_prompt_stream: Mock,
        improve_prompt_service: ImprovePromptService,
        mock_storage: Mock,
    ):
        patched_improve_prompt_stream.return_value = mock_aiter(
            _run(_improve_task_output(improved_prompt="This is an")),
            _run(_improve_task_output(improved_prompt="This is an improved prompt")),
        )

        # Act

        chunks = [
            c
            async for c in improve_prompt_service.stream(
                task_tuple=("", 1),
                run_id="1",
                variant_id=None,
                instructions=None,
                user_evaluation="This is a user evaluation.",
            )
        ]
        assert len(chunks) == 2

        # Assert
        mock_storage.store_task_resource.assert_not_called()
        patched_improve_prompt_stream.assert_called_once()

    async def test_run_invalid_field_updates(
        self,
        improve_prompt_service: ImprovePromptService,
        mock_storage: Mock,
        patched_improve_prompt_run: Mock,
        patched_logger: Mock,
        fetched_properties: TaskGroupProperties,
    ):
        """Test that we fail silently when the updated fields do not exist in the task variant"""
        # The field updates are not valid since the fields do not exist
        patched_improve_prompt_run.return_value = _improve_task_output(
            field_updates=[
                OutputFieldUpdate(
                    keypath="result1",
                    updated_description="A test string field",
                    updated_examples=["example1", "example2"],
                ),
            ],
            input_field_updates=[
                InputFieldUpdate(
                    keypath="input_field1",
                    updated_description="A test input field",
                ),
            ],
        )

        # In which case the run should succeed but a new task variant should not be created
        result = await improve_prompt_service.run(
            task_tuple=("", 1),
            run_id="1",
            variant_id=None,
            instructions=None,
            user_evaluation="This is a user evaluation.",
        )

        assert result == (
            fetched_properties.model_copy(update={"instructions": "This is an improved prompt"}),
            ["Minor tweaks"],
        )

        mock_storage.store_task_resource.assert_not_called()
        patched_logger.exception.assert_called_once()
        assert patched_logger.exception.call_args.args[0] == "Error handling improved output schema"

    async def test_stream_invalid_field_updates(
        self,
        improve_prompt_service: ImprovePromptService,
        mock_storage: Mock,
        patched_improve_prompt_stream: Mock,
        patched_logger: Mock,
    ):
        """Test that we fail silently on streams when the updated fields do not exist in the task variant"""
        # The field updates are not valid since the fields do not exist
        patched_improve_prompt_stream.return_value = mock_aiter(
            _run(_improve_task_output(improved_prompt="This is an")),
            _run(_improve_task_output(improved_prompt="This is an improved prompt")),
            _run(
                _improve_task_output(
                    improved_prompt="This is an improved prompt",
                    field_updates=[],
                    input_field_updates=[],
                ),
            ),
            _run(
                _improve_task_output(
                    improved_prompt="This is an improved prompt",
                    field_updates=[
                        OutputFieldUpdate(
                            keypath="result1",
                        ),
                    ],
                    input_field_updates=[
                        InputFieldUpdate(
                            keypath="input_field1",
                            updated_description="A test input field",
                        ),
                    ],
                ),
            ),
            _run(
                _improve_task_output(
                    improved_prompt="This is an improved prompt",
                    field_updates=[
                        OutputFieldUpdate(
                            keypath="result1",
                            updated_description="A test string field",
                            updated_examples=["example1", "example2"],
                        ),
                    ],
                    input_field_updates=[
                        InputFieldUpdate(
                            keypath="input_field1",
                            updated_description="A test input field",
                        ),
                    ],
                ),
            ),
        )

        # In which case the run should succeed but a new task variant should not be created

        chunks = [
            c
            async for c in improve_prompt_service.stream(
                task_tuple=("", 1),
                run_id="1",
                variant_id=None,
                instructions=None,
                user_evaluation="This is a user evaluation.",
            )
        ]
        assert len(chunks) == 5

        mock_storage.store_task_resource.assert_not_called()
        patched_logger.exception.assert_called_once()
        assert patched_logger.exception.call_args.args[0] == "Error handling improved output schema"

    @pytest.mark.parametrize(
        "model_responses,expected_result",
        [
            (
                [
                    _improve_task_output(improved_prompt="First model success"),
                    None,  # Second model not called
                    None,  # Third model not called
                ],
                ("First model success", ["Minor tweaks"]),
            ),
            (
                [
                    Exception("First model failed"),
                    _improve_task_output(improved_prompt="Second model success"),
                    None,  # Third model not called
                ],
                ("Second model success", ["Minor tweaks"]),
            ),
            (
                [
                    Exception("First model failed"),
                    Exception("Second model failed"),
                    _improve_task_output(improved_prompt="Third model success"),
                ],
                ("Third model success", ["Minor tweaks"]),
            ),
            (
                [
                    Exception("All models failed"),
                    Exception("All models failed"),
                    Exception("All models failed"),
                ],
                ("You are a helpful assistant.", ["Failed to improve prompt"]),
            ),
        ],
    )
    async def test_model_fallback_behavior(
        self,
        improve_prompt_service: ImprovePromptService,
        patched_improve_prompt_run: Mock,
        model_responses: list[ImprovePromptAgentOutput | Exception | None],
        expected_result: tuple[str, list[str]],
    ) -> None:
        """Test that we try multiple models in sequence and fall back appropriately"""
        # Setup the mock to return different responses for each model
        patched_improve_prompt_run.side_effect = model_responses

        # Act
        result = await improve_prompt_service.run(
            task_tuple=("", 1),
            run_id="1",
            variant_id=None,
            instructions=None,
            user_evaluation="This is a user evaluation.",
        )

        # Assert
        assert result[0].instructions == expected_result[0]
        assert result[1] == expected_result[1]
        assert patched_improve_prompt_run.call_count == len([r for r in model_responses if r is not None])

    @pytest.mark.parametrize(
        "model_responses,expected_chunks",
        [
            (
                [
                    mock_aiter(
                        _run(_improve_task_output(improved_prompt="First model success")),
                    ),
                    None,  # Second model not called
                    None,  # Third model not called
                ],
                [("First model success", ["Minor tweaks"])],
            ),
            (
                [
                    Exception("First model failed"),
                    mock_aiter(
                        _run(_improve_task_output(improved_prompt="Second model success")),
                    ),
                    None,  # Third model not called
                ],
                [("Second model success", ["Minor tweaks"])],
            ),
            (
                [
                    Exception("First model failed"),
                    Exception("Second model failed"),
                    mock_aiter(
                        _run(_improve_task_output(improved_prompt="Third model success")),
                    ),
                ],
                [("Third model success", ["Minor tweaks"])],
            ),
            (
                [
                    Exception("All models failed"),
                    Exception("All models failed"),
                    Exception("All models failed"),
                ],
                [("You are a helpful assistant.", ["Failed to improve prompt"])],
            ),
        ],
    )
    async def test_stream_model_fallback_behavior(
        self,
        improve_prompt_service: ImprovePromptService,
        patched_improve_prompt_stream: Mock,
        model_responses: list[AsyncIterator[Run[Any]] | Exception | None],
        expected_chunks: list[tuple[str, list[str]]],
    ) -> None:
        """Test that we try multiple models in sequence and fall back appropriately in stream mode"""
        # Setup the mock to return different responses for each model
        patched_improve_prompt_stream.side_effect = model_responses

        # Act
        chunks = [
            c
            async for c in improve_prompt_service.stream(
                task_tuple=("", 1),
                run_id="1",
                variant_id=None,
                instructions=None,
                user_evaluation="This is a user evaluation.",
            )
        ]

        # Assert
        assert len(chunks) == len(expected_chunks)
        for chunk, expected in zip(chunks, expected_chunks):
            assert chunk[0].instructions == expected[0]
            assert chunk[1] == expected[1]
        assert patched_improve_prompt_stream.call_count == len([r for r in model_responses if r is not None])

    async def test_run_new_input_variables_added_returns_original_properties(
        self,
        improve_prompt_service: ImprovePromptService,
        mock_storage: Mock,
        patched_improve_prompt_run: Mock,
        patched_logger: Mock,
        fetched_properties: TaskGroupProperties,
    ):
        """Test that when new input variables are added, we return original properties and log warning"""
        # Mock the improved prompt to have new variables
        patched_improve_prompt_run.return_value = _improve_task_output(
            improved_prompt="Hello {{name}}, please process {{new_variable}} and return the result.",
        )

        # Mock the original instructions to have fewer variables
        with patch.object(
            improve_prompt_service,
            "_ensure_no_new_input_variables_added",
            return_value=False,
        ) as mock_check:
            result = await improve_prompt_service.run(
                task_tuple=("", 1),
                run_id="1",
                variant_id=None,
                instructions="Hello {{name}}, please process the input.",
                user_evaluation="This is a user evaluation.",
            )

            # Assert that the check was called
            mock_check.assert_called_once_with(
                "Hello {{name}}, please process the input.",
                "Hello {{name}}, please process {{new_variable}} and return the result.",
            )

        # Should return original properties, not the improved ones
        assert result == (
            fetched_properties,  # Original properties unchanged
            ["Failed to improve prompt"],
        )

        # Should log a warning
        patched_logger.warning.assert_called_once_with(
            "New input variables were added by improve prompt agent",
            extra={
                "original_instructions": "Hello {{name}}, please process the input.",
                "improved_instructions": "Hello {{name}}, please process {{new_variable}} and return the result.",
            },
        )

        # Should not store a new task variant
        mock_storage.store_task_resource.assert_not_called()

    async def test_run_no_new_input_variables_proceeds_normally(
        self,
        improve_prompt_service: ImprovePromptService,
        mock_storage: Mock,
        patched_improve_prompt_run: Mock,
        patched_logger: Mock,
        fetched_properties: TaskGroupProperties,
    ):
        """Test that when no new input variables are added, processing continues normally"""
        patched_improve_prompt_run.return_value = _improve_task_output(
            improved_prompt="Hello {{name}}, please process the input with better clarity.",
        )

        with patch.object(
            improve_prompt_service,
            "_ensure_no_new_input_variables_added",
            return_value=True,
        ) as mock_check:
            result = await improve_prompt_service.run(
                task_tuple=("", 1),
                run_id="1",
                variant_id=None,
                instructions="Hello {{name}}, please process the input.",
                user_evaluation="This is a user evaluation.",
            )

            mock_check.assert_called_once_with(
                "Hello {{name}}, please process the input.",
                "Hello {{name}}, please process the input with better clarity.",
            )

        # Should return improved properties
        assert result == (
            fetched_properties.model_copy(
                update={"instructions": "Hello {{name}}, please process the input with better clarity."},
            ),
            ["Minor tweaks"],
        )

        # Should not log a warning
        patched_logger.warning.assert_not_called()

    async def test_stream_new_input_variables_added_returns_original_and_stops(
        self,
        improve_prompt_service: ImprovePromptService,
        mock_storage: Mock,
        patched_improve_prompt_stream: Mock,
        patched_logger: Mock,
        fetched_properties: TaskGroupProperties,
    ):
        """Test that in stream mode, when new input variables are detected, we return original instructions and stop"""
        patched_improve_prompt_stream.return_value = mock_aiter(
            _run(_improve_task_output(improved_prompt="Hello {{name}}")),
            _run(_improve_task_output(improved_prompt="Hello {{name}}, process {{new_var}}")),
        )

        with patch.object(
            improve_prompt_service,
            "_ensure_no_new_input_variables_added",
            return_value=False,  # Return False to indicate new variables were added
        ) as mock_check:
            chunks = [
                c
                async for c in improve_prompt_service.stream(
                    task_tuple=("", 1),
                    run_id="1",
                    variant_id=None,
                    instructions="Hello {{name}}",
                    user_evaluation="This is a user evaluation.",
                )
            ]

        # Should have 3 chunks: 2 from streaming + 1 final chunk with original instructions
        assert len(chunks) == 3

        # First chunk should have the first improved prompt
        assert chunks[0][0].instructions == "Hello {{name}}"
        assert chunks[0][1] == ["Minor tweaks"]

        # Second chunk should have the second improved prompt
        assert chunks[1][0].instructions == "Hello {{name}}, process {{new_var}}"
        assert chunks[1][1] == ["Minor tweaks"]

        # Final chunk should revert to original instructions with empty changelog
        assert chunks[2][0].instructions == "Hello {{name}}"
        assert chunks[2][1] == []

        # Should be called once with the final improved prompt
        mock_check.assert_called_once_with(
            "Hello {{name}}",
            "Hello {{name}}, process {{new_var}}",
        )

        # Should log a warning
        patched_logger.warning.assert_called_once_with(
            "New input variables were added by improve prompt agent",
            extra={
                "original_instructions": "Hello {{name}}",
                "improved_instructions": "Hello {{name}}, process {{new_var}}",
            },
        )

        # Should not store a new task variant
        mock_storage.store_task_resource.assert_not_called()

    async def test_stream_no_new_input_variables_proceeds_normally(
        self,
        improve_prompt_service: ImprovePromptService,
        mock_storage: Mock,
        patched_improve_prompt_stream: Mock,
        patched_logger: Mock,
    ):
        """Test that in stream mode, when no new input variables are detected, processing continues normally"""
        patched_improve_prompt_stream.return_value = mock_aiter(
            _run(_improve_task_output(improved_prompt="Hello {{name}}")),
            _run(_improve_task_output(improved_prompt="Hello {{name}}, with improvements")),
        )

        with patch.object(
            improve_prompt_service,
            "_ensure_no_new_input_variables_added",
            return_value=True,
        ):
            chunks = [
                c
                async for c in improve_prompt_service.stream(
                    task_tuple=("", 1),
                    run_id="1",
                    variant_id=None,
                    instructions="Hello {{name}}",
                    user_evaluation="This is a user evaluation.",
                )
            ]

        # Should have 2 chunks from normal streaming
        assert len(chunks) == 2

        assert chunks[0][0].instructions == "Hello {{name}}"
        assert chunks[1][0].instructions == "Hello {{name}}, with improvements"

        # Should not log a warning
        patched_logger.warning.assert_not_called()

    async def test_run_with_variable_validation_integration(
        self,
        improve_prompt_service: ImprovePromptService,
        mock_storage: Mock,
        patched_improve_prompt_run: Mock,
        patched_logger: Mock,
        fetched_properties: TaskGroupProperties,
    ):
        """Integration test for variable validation with real extract_variable_schema"""
        # Test case where improved prompt adds new variables
        patched_improve_prompt_run.return_value = _improve_task_output(
            improved_prompt="Hello {{name}}, process {{input}} and also handle {{new_variable}}",
        )

        result = await improve_prompt_service.run(
            task_tuple=("", 1),
            run_id="1",
            variant_id=None,
            instructions="Hello {{name}}, process {{input}}",
            user_evaluation="This is a user evaluation.",
        )

        # Should return original properties due to new variable detection
        assert result == (
            fetched_properties,
            ["Failed to improve prompt"],
        )

        # Should log a warning
        patched_logger.warning.assert_called_once_with(
            "New input variables were added by improve prompt agent",
            extra={
                "original_instructions": "Hello {{name}}, process {{input}}",
                "improved_instructions": "Hello {{name}}, process {{input}} and also handle {{new_variable}}",
            },
        )

    async def test_run_with_same_variables_integration(
        self,
        improve_prompt_service: ImprovePromptService,
        mock_storage: Mock,
        patched_improve_prompt_run: Mock,
        patched_logger: Mock,
        fetched_properties: TaskGroupProperties,
    ):
        """Integration test for variable validation when variables remain the same"""
        # Test case where improved prompt keeps same variables
        patched_improve_prompt_run.return_value = _improve_task_output(
            improved_prompt="Hello {{name}}, please carefully process {{input}} with attention to detail",
        )

        result = await improve_prompt_service.run(
            task_tuple=("", 1),
            run_id="1",
            variant_id=None,
            instructions="Hello {{name}}, process {{input}}",
            user_evaluation="This is a user evaluation.",
        )

        # Should return improved properties since variables are the same
        assert result == (
            fetched_properties.model_copy(
                update={
                    "instructions": "Hello {{name}}, please carefully process {{input}} with attention to detail",
                },
            ),
            ["Minor tweaks"],
        )

        # Should not log a warning
        patched_logger.warning.assert_not_called()

    async def test_stream_with_variable_validation_integration(
        self,
        improve_prompt_service: ImprovePromptService,
        mock_storage: Mock,
        patched_improve_prompt_stream: Mock,
        patched_logger: Mock,
        fetched_properties: TaskGroupProperties,
    ):
        """Integration test for variable validation in stream mode"""
        # Stream that eventually adds new variables
        patched_improve_prompt_stream.return_value = mock_aiter(
            _run(_improve_task_output(improved_prompt="Hello {{name}}, process {{input}}")),
            _run(_improve_task_output(improved_prompt="Hello {{name}}, process {{input}} carefully")),
            _run(_improve_task_output(improved_prompt="Hello {{name}}, process {{input}} and {{new_var}}")),
        )

        chunks = [
            c
            async for c in improve_prompt_service.stream(
                task_tuple=("", 1),
                run_id="1",
                variant_id=None,
                instructions="Hello {{name}}, process {{input}}",
                user_evaluation="This is a user evaluation.",
            )
        ]

        # Should have 4 chunks: 3 from streaming + 1 final chunk reverting to original
        assert len(chunks) == 4

        # First two chunks should proceed normally
        assert chunks[0][0].instructions == "Hello {{name}}, process {{input}}"
        assert chunks[1][0].instructions == "Hello {{name}}, process {{input}} carefully"
        assert chunks[2][0].instructions == "Hello {{name}}, process {{input}} and {{new_var}}"

        # Final chunk should revert to original instructions
        assert chunks[3][0].instructions == "Hello {{name}}, process {{input}}"
        assert chunks[3][1] == []

        # Should log a warning
        patched_logger.warning.assert_called_once_with(
            "New input variables were added by improve prompt agent",
            extra={
                "original_instructions": "Hello {{name}}, process {{input}}",
                "improved_instructions": "Hello {{name}}, process {{input}} and {{new_var}}",
            },
        )
