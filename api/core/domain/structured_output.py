from typing import Any, NamedTuple

from core.domain.agent_run_result import AgentRunResult
from core.domain.fields.file import File
from core.domain.fields.internal_reasoning_steps import InternalReasoningStep
from core.domain.tool_call import ToolCallRequestWithID


class StructuredOutput(NamedTuple):
    """A structured output that is when parsing the provider response"""

    output: Any
    tool_calls: list[ToolCallRequestWithID] | None = None

    # An opportunity for a LLM to decide whether the previous tool calls were successful or not
    agent_run_result: AgentRunResult | None = None

    # An opportunity for a LLM to add reasoning steps to the output
    reasoning_steps: list[InternalReasoningStep] | None = None

    files: list[File] | None = None

    delta: str | None = None

    # Whether the output is the final output, used when streaming
    final: bool = False

    @property
    def number_of_images(self) -> int:
        if not self.files:
            return 0
        return len([f for f in self.files if f.is_image])
