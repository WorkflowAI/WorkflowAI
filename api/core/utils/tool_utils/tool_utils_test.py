from enum import StrEnum
from typing import Annotated

from core.domain.tool import Tool
from core.tools import ToolKind
from core.tools.browser_text.browser_text_tool import browser_text
from core.tools.search.run_google_search import run_google_search
from core.utils.tool_utils.tool_utils import (
    _tool_prompt,  # pyright: ignore[reportPrivateUsage]
    build_tool,
    get_tool_for_tool_kind,
    get_tools_description,
)


def test_function_with_basic_types() -> None:
    class TestMode(StrEnum):
        FAST = "fast"
        SLOW = "slow"

    def sample_func(
        name: Annotated[str, "The name parameter"],
        age: int,
        height: float,
        is_active: bool,
        mode: TestMode = TestMode.FAST,
    ) -> bool:
        """Sample function for testing"""
        return True

    schema = build_tool("sample_func", sample_func)

    expected_schema = {
        "input_json_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name parameter",
                },
                "age": {
                    "type": "number",
                },
                "height": {
                    "type": "number",
                },
                "is_active": {
                    "type": "boolean",
                },
                "mode": {
                    "type": "string",
                    "enum": ["fast", "slow"],
                },
            },
            "required": ["name", "age", "height", "is_active"],  # 'mode' is not required
        },
        "output_json_schema": {
            "type": "boolean",
        },
    }

    assert schema.input_schema == expected_schema["input_json_schema"]
    assert schema.output_schema == expected_schema["output_json_schema"]
    assert schema.description == "Sample function for testing"


def test_method_with_self() -> None:
    class TestClass:
        def sample_method(self, value: int) -> str:
            return str(value)

    schema = build_tool("sample_method", TestClass.sample_method)

    expected_schema = {
        "input_json_schema": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "number",
                },
            },
            "required": ["value"],
        },
        "output_json_schema": {
            "type": "string",
        },
    }

    assert schema.input_schema == expected_schema["input_json_schema"]
    assert schema.output_schema == expected_schema["output_json_schema"]


class TestToolPrompt:
    def test_with_description(self):
        tool = Tool(
            name="test",
            description="test",
            input_schema={"test": "test"},
            output_schema={"test": "test1"},
        )
        prompt = _tool_prompt(tool)
        assert (
            prompt
            == """
    <tool>
        <tool_name>test</tool_name>
        <tool_description>test</tool_description>
        <tool_input_schema>
        ```json
        {"test": "test"}
        ```
        </tool_input_schema>
        <tool_output_schema>
        ```json
        {"test": "test1"}
        ```
        </tool_output_schema>
    </tool>
""".strip("\n")  # removing first and last line
        )

    def test_without_description(self):
        tool = Tool(
            name="test",
            input_schema={"test": "test"},
            output_schema={"test": "test1"},
        )
        prompt = _tool_prompt(tool)
        assert (
            prompt
            == """
    <tool>
        <tool_name>test</tool_name>
        <tool_input_schema>
        ```json
        {"test": "test"}
        ```
        </tool_input_schema>
        <tool_output_schema>
        ```json
        {"test": "test1"}
        ```
        </tool_output_schema>
    </tool>
""".strip("\n")  # removing first and last line
        )


def test_build_tools_str_for_prompt() -> None:
    """Test the build_tools_str_for_prompt function with sample tools."""

    tools_str = get_tools_description(
        [
            build_tool(ToolKind.WEB_BROWSER_TEXT, browser_text),
            build_tool(ToolKind.WEB_SEARCH_GOOGLE, run_google_search),
        ],
    )

    expected_str = """<tools_list>
    <tool>
        <tool_name>@browser-text</tool_name>
        <tool_description>Extracts and converts web page content from the given URL into clean, readable markdown format. This is a text-only browser tool that cannot see images, click elements, interact with JavaScript, or perform any dynamic actions - it only parses and returns the static text content of web pages.</tool_description>
        <tool_input_schema>
        ```json
        {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}
        ```
        </tool_input_schema>
        <tool_output_schema>
        ```json
        {"type": "string"}
        ```
        </tool_output_schema>
    </tool>
    <tool>
        <tool_name>@search-google</tool_name>
        <tool_description>Performs a Google web search using Serper.dev API and returns search results including links, snippets, and related information in JSON format.</tool_description>
        <tool_input_schema>
        ```json
        {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
        ```
        </tool_input_schema>
        <tool_output_schema>
        ```json
        {"type": "string"}
        ```
        </tool_output_schema>
    </tool>
</tools_list>
""".strip("\n")

    assert tools_str == expected_str


def test_get_tool_for_tool_kind() -> None:
    """Test mapping from ToolKind to actual tool function."""
    assert get_tool_for_tool_kind(ToolKind.WEB_BROWSER_TEXT) == browser_text
    assert get_tool_for_tool_kind(ToolKind.WEB_SEARCH_GOOGLE) == run_google_search
