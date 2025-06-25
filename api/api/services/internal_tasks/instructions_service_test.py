from unittest.mock import patch

import pytest

from api.services.internal_tasks.instructions_service import InstructionsService
from core.agents.task_instruction_tool_update_task import (
    TaskInstructionsToolUpdateTaskInput,
    TaskInstructionsToolUpdateTaskOutput,
)
from core.domain.task_io import SerializableTaskIO
from core.domain.task_variant import SerializableTaskVariant
from core.domain.tool import Tool
from core.tools import ToolKind
from tests.utils import mock_aiter


@pytest.fixture
def service() -> InstructionsService:
    return InstructionsService()


def test_get_tool_to_remove() -> None:
    instructions = "Use @search and @browser-text to perform the task"
    selected_tools = [ToolKind.WEB_SEARCH_GOOGLE]

    to_remove = InstructionsService.get_tools_to_remove(instructions, selected_tools)

    assert "@browser-text" in to_remove
    assert "@search-google" not in to_remove


def test_get_tools_to_remove_no_matches() -> None:
    instructions = "Use @tool to perform the task"
    selected_tools = [ToolKind.WEB_SEARCH_GOOGLE]

    to_remove = InstructionsService.get_tools_to_remove(instructions, selected_tools)

    assert to_remove == []


def test_complex_case() -> None:
    """
    Check this former bug:
    - search already enabled -> enable browser = search is replaced by browser
    From [WOR-3791: Investigate weird tool addition behaviour in playground](https://linear.app/workflowai/issue/WOR-3791/investigate-weird-tool-addition-behaviour-in-playground)
    """
    instructions = "Answer solely based on the URL content. Provide the URL as input to retrieve the content for analysis.\nYou can use the @perplexity-sonar-pro tool to perform a query-based analysis. Provide a query as input to retrieve relevant insights in string format, which can assist in answering the question."
    selected_tools = [ToolKind.WEB_SEARCH_PERPLEXITY_SONAR_PRO, ToolKind.WEB_BROWSER_TEXT]

    to_remove = InstructionsService.get_tools_to_remove(instructions, selected_tools)
    to_add = InstructionsService.get_tools_to_add(instructions, selected_tools)

    assert to_remove == []
    assert len(to_add) == 1
    assert to_add[0].name == "@browser-text"


def test_complex_case_2() -> None:
    """
    Solve this former bug:
    - search and browser enabled -> disable browser = both search and browser are disabled
    From [WOR-3791: Investigate weird tool addition behaviour in playground](https://linear.app/workflowai/issue/WOR-3791/investigate-weird-tool-addition-behaviour-in-playground)
    """

    instructions = "Answer solely based on the URL content. Use @browser-text. Provide the URL as input to retrieve the content for analysis.\nYou can use the @perplexity-sonar-pro tool to perform a query-based analysis. Provide a query as input to retrieve relevant insights in string format, which can assist in answering the question."
    selected_tools = [ToolKind.WEB_SEARCH_PERPLEXITY_SONAR_PRO]

    to_remove = InstructionsService.get_tools_to_remove(instructions, selected_tools)
    to_add = InstructionsService.get_tools_to_add(instructions, selected_tools)

    assert to_remove == [ToolKind.WEB_BROWSER_TEXT]
    assert len(to_add) == 0


def test_get_tools_to_add_nothing_to_add() -> None:
    instructions = "Use @search-google to perform the task"
    selected_tools = [ToolKind.WEB_SEARCH_GOOGLE]

    to_add = InstructionsService.get_tools_to_add(instructions, selected_tools)

    assert to_add == []


def _google_docstring():
    from core.tools.search.run_google_search import run_google_search

    return run_google_search.__doc__


def test_get_tools_to_add_search() -> None:
    instructions = "hello !"
    selected_tools = [ToolKind.WEB_SEARCH_GOOGLE]

    to_add = InstructionsService.get_tools_to_add(instructions, selected_tools)

    assert to_add == [
        Tool(
            name="@search-google",
            description=_google_docstring(),
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            output_schema={"type": "string"},
        ),
    ]


async def test_update_task_instructions(service: InstructionsService) -> None:
    task_variant = SerializableTaskVariant(
        id="test_task",
        task_schema_id=1,
        name="test_task",
        input_schema=SerializableTaskIO(
            json_schema={"type": "object", "properties": {}},  # pyright: ignore[reportGeneralTypeIssues]
            version="1",
        ),
        output_schema=SerializableTaskIO(
            json_schema={"type": "object", "properties": {}},  # pyright: ignore[reportGeneralTypeIssues]
            version="1",
        ),
    )
    instructions = "Use @tool1 to perform the task"
    selected_tools = [ToolKind.WEB_SEARCH_GOOGLE]

    expected_output = TaskInstructionsToolUpdateTaskOutput(
        updated_task_instructions="Use @tool1 and @tool2 to perform the task",
    )

    with patch(
        "api.services.internal_tasks.instructions_service.stream_task_instruction_tool_update",
        return_value=mock_aiter(expected_output),
    ) as mock_stream:
        result = service.update_task_instructions(task_variant, instructions, selected_tools)
        outputs: list[TaskInstructionsToolUpdateTaskOutput] = [output async for output in await result]

        assert len(outputs) == 1
        assert outputs[0] == expected_output

        mock_stream.assert_called_once_with(
            TaskInstructionsToolUpdateTaskInput(
                task=TaskInstructionsToolUpdateTaskInput.Task(
                    name="test_task",
                    input_json_schema={"type": "object", "properties": {}},
                    output_json_schema={"type": "object", "properties": {}},
                ),
                initial_task_instructions=instructions,
                tools_to_remove=[],
                tools_to_add=[
                    TaskInstructionsToolUpdateTaskInput.Tool(
                        handle="@search-google",
                        description="Performs a Google web search using Serper.dev API and returns search results including links, snippets, and related information in JSON format.",
                        input_json_schema={
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                            "required": ["query"],
                        },
                        output_json_schema={"type": "string"},
                    ),
                ],
            ),
            use_cache="always",
        )
