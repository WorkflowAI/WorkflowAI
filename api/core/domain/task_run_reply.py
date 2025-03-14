from typing import NamedTuple

from core.domain.message import Message
from core.domain.tool_call import ToolCall


# using NamedTuple here since it's immutable
class RunReply(NamedTuple):
    # Data about the previous run
    previous_run_id: str
    previous_messages: list[Message]

    # Newly provided data
    user_message: str | None = None
    tool_calls: list[ToolCall] | None = None
