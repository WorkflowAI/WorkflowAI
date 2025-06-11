from typing import Any, NamedTuple

from pydantic import BaseModel

from core.domain.fields.internal_reasoning_steps import InternalReasoningStep
from core.domain.tool_call import ToolCallRequestWithID
from core.providers.base.models import RawCompletion
from core.utils.streams import JSONStreamParser, RawStreamParser


class ToolCallRequestBuffer(BaseModel):
    id: str | None = None
    tool_name: str | None = None
    tool_input: str = ""


class ParsedResponse(NamedTuple):
    content: str
    reasoning_steps: str | None = None
    thoughts: str | None = None
    # TODO: switch to tool call request
    tool_calls: list[ToolCallRequestWithID] | None = None


class StreamingContext:
    def __init__(self, raw_completion: RawCompletion, json: bool, stream_deltas: bool = False):
        self.json = json
        self.streamer = JSONStreamParser() if json else RawStreamParser()
        self.agg_output: dict[str, Any] = {}
        self.reasoning_steps: list[InternalReasoningStep] | None = None
        self.thoughts: str | None = None
        self.raw_completion = raw_completion

        self.tool_call_request_buffer: dict[int, ToolCallRequestBuffer] = {}
        self.tool_calls: list[ToolCallRequestWithID] | None = None

        self.last_chunk: ParsedResponse | None = None
        self.stream_deltas = stream_deltas
