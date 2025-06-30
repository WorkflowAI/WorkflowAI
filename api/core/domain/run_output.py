from collections.abc import Sequence
from typing import Any, NamedTuple

from core.domain.agent_run import AgentRun
from core.domain.fields.internal_reasoning_steps import InternalReasoningStep
from core.domain.tool_call import ToolCall, ToolCallRequestWithID


class RunOutput(NamedTuple):
    task_output: Any
    tool_calls: Sequence[ToolCall] | None = None
    tool_call_requests: Sequence[ToolCallRequestWithID] | None = None
    reasoning_steps: list[InternalReasoningStep] | None = None
    delta: str | None = None

    # Whether the output is the final output, used when streaming
    final: bool = False

    @classmethod
    def from_run(cls, run: AgentRun, delta: str | None = None):
        return cls(
            task_output=run.task_output,
            tool_calls=run.tool_calls,
            tool_call_requests=run.tool_call_requests,
            reasoning_steps=run.reasoning_steps,
            delta=delta,
        )
