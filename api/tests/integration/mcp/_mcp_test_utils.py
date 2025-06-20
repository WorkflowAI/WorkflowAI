import json
import subprocess
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter


class EvaluatorDefinition(BaseModel):
    """Base definition for an evaluator description
    This is the format that should be matched by evaluate.yaml files"""

    class RequiredTool(BaseModel):
        name: str
        input: dict[str, Any] | None = None

    required_tools: list[RequiredTool] = Field(default_factory=list)

    class Assertions(BaseModel):
        final_response: list[str] = Field(default_factory=list)
        code: list[str] = Field(default_factory=list)

    assertions: Assertions


class ClaudeMessage(BaseModel):
    role: str
    content: list[dict[str, Any]]


class _ClaudeStepSystem(BaseModel):
    type: Literal["system"]
    subtype: str | None = None
    session_id: str

    class MCPServer(BaseModel):
        name: str
        status: str

    mcp_servers: list[MCPServer] | None = None


class _ClaudeContentToolUse(BaseModel):
    type: Literal["tool_use"]
    id: str
    name: str
    input: dict[str, Any]


class _ClaudeContentToolResult(BaseModel):
    type: Literal["tool_result"]
    is_error: bool | None = None
    content: Any
    tool_use_id: str


class _ClaudeContentText(BaseModel):
    type: Literal["text"]
    text: str


_ClaudeContent = Annotated[
    _ClaudeContentToolUse | _ClaudeContentToolResult | _ClaudeContentText,
    Field(discriminator="type"),
]


class _ClaudeStepMessage(BaseModel):
    type: Literal["assistant", "user"]

    class Message(BaseModel):
        content: list[_ClaudeContent]

    message: Message


class _ClaudeStepResult(BaseModel):
    type: Literal["result"]
    subtype: str
    is_error: bool
    result: str


ClaudeStep = Annotated[
    _ClaudeStepSystem | _ClaudeStepMessage | _ClaudeStepResult,
    Field(discriminator="type"),
]

ClaudeSteps = TypeAdapter(list[ClaudeStep])


def _find_tool_use(step: ClaudeStep, tool_name: str) -> _ClaudeContentToolUse | None:
    if not isinstance(step, _ClaudeStepMessage):
        return None

    try:
        return next(
            tool_use for tool_use in step.message.content if tool_use.type == "tool_use" and tool_use.name == tool_name
        )
    except StopIteration:
        return None


def _result(claude_steps: list[ClaudeStep]):
    return next(step for step in reversed(claude_steps) if step.type == "result")


class Evaluator:
    def __init__(self, definition: EvaluatorDefinition, mcp_name: str, claude_steps_dir: Path):
        self.definition = definition
        self.mcp_name = mcp_name
        self.claude_steps_dir = claude_steps_dir

    def _full_tool_name(self, tool_name: str) -> str:
        return f"mcp__{self.mcp_name}__{tool_name}"

    def _wai_tool_name(self, tool_name: str) -> str | None:
        if not tool_name.startswith(f"mcp__{self.mcp_name}__"):
            return None

        return tool_name.split("__")[-1]

    def _check_required_tools(self, claude_steps: list[ClaudeStep]):
        return [
            f"Missing {tool.name}"
            for tool in self.definition.required_tools
            if not any(_find_tool_use(step, self._full_tool_name(tool.name)) for step in claude_steps)
        ]

    def _check_all_tool_success(self, claude_steps: list[ClaudeStep]):
        def _tool_failures_iter():
            for step in claude_steps:
                if not isinstance(step, _ClaudeStepMessage):
                    continue

                for content in step.message.content:
                    if content.type == "tool_result" and content.is_error:
                        yield content

        return [
            f"Tool {self._wai_tool_name(failure.tool_use_id)} failed: {failure.content}"
            for failure in _tool_failures_iter()
        ]

    def _run_claude_evaluation(self, prompt: str, cwd: Path, name: str) -> list[str]:
        # TODO: This could probably be a workflowai agent instead ?
        final_prompt = f"{prompt}\n\nRespond either with a list of failed assertions that failed or only 'PASS' if all the assertions are met."
        cmd = [
            "echo",
            f'"{final_prompt}"',
            "|",
            "yarn",
            "run",
            "claude",
            "--verbose",
            "--output-format",
            "json",
            "-p",
        ]
        result = subprocess.run(
            " ".join(cmd),
            cwd=cwd,
            capture_output=True,
            text=True,
            shell=True,
        )
        assert result.returncode == 0, f"Failed to run claude: {result.stderr}"
        with open(self.claude_steps_dir / f"{name}.json", "w") as f:
            f.write(result.stdout)

        steps = ClaudeSteps.validate_python(json.loads(result.stdout))

        result = _result(steps)
        assert not result.is_error, f"Final result failed: {result.result}"

        if result.result == "PASS":
            return []

        return [result.result]

    def _run_final_response_assertion(self, code_dir: Path, claude_steps: list[ClaudeStep]) -> list[str]:
        final_result = _result(claude_steps)

        if final_result.is_error:
            return [f"Final result failed: {final_result.result}"]

        if not self.definition.assertions.final_response:
            return []

        asserts = "\n".join(f"- {assertion}" for assertion in self.definition.assertions.final_response)
        prompt = f"""Evaluate that the final result meets the following assertions:

{asserts}

The final result is:
{final_result.result}
"""

        return self._run_claude_evaluation(prompt, code_dir, "final_response")

    def _run_code_assertion(self, code_dir: Path) -> list[str]:
        if not self.definition.assertions.code:
            return []

        asserts = "\n".join(f"- {assertion}" for assertion in self.definition.assertions.code)
        prompt = f"""Check that the current code directory meets the following assertions:

        {asserts}
        """

        return self._run_claude_evaluation(prompt, code_dir, "code")

    def evaluate(self, code_dir: Path, claude_steps: list[ClaudeStep]):
        """Evaluates the result and returns a list of failed assertions"""

        failed_assertions: list[str] = []
        failed_assertions.extend(self._check_required_tools(claude_steps))
        failed_assertions.extend(self._check_all_tool_success(claude_steps))
        failed_assertions.extend(self._run_final_response_assertion(code_dir, claude_steps))
        failed_assertions.extend(self._run_code_assertion(code_dir))

        return failed_assertions
