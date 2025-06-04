from typing import Sequence

from api.services.runs._stored_message import StoredMessage, StoredMessages
from core.domain.agent_run import AgentRun
from core.domain.tool_call import ToolCallRequest
from core.utils.models.previews import DEFAULT_PREVIEW_MAX_LEN, compute_preview


def _last_message_idx_with_run_id(messages: Sequence[StoredMessage]) -> int | None:
    for i, m in enumerate(reversed(messages)):
        if m.run_id:
            return len(messages) - i - 1
    return None


def _message_preview(message: StoredMessage, max_len: int):
    if not message.content:
        return None

    content = message.content[0]
    if content.file:
        return "User: " + compute_preview(content.file, max_len=max_len)

    if content.text:
        return "User: " + compute_preview(content.text, max_len=max_len)

    if content.tool_call_result:
        return "Tool: " + compute_preview(content.tool_call_result.result, max_len=max_len)

    return None


def _messages_list_preview(
    messages: Sequence[StoredMessage],
    include_roles: set[str] = {"user"},
    max_len: int = DEFAULT_PREVIEW_MAX_LEN,
):
    if not messages:
        return None

    # Trying to find the number of messages that were added
    # This means finding the number of messages after the last run that has a "run_id"

    first_response_idx = _last_message_idx_with_run_id(messages)
    if first_response_idx is None:
        first_msg_idx = 0
        prefix = ""
    else:
        first_msg_idx = first_response_idx + 1
        prefix = f"💬 {first_msg_idx} msg{'s' if first_msg_idx > 1 else ''}..."

    max_len -= len(prefix)
    first_message = next((m for m in messages[first_msg_idx:] if m.role in include_roles), messages[0])
    if preview := _message_preview(first_message, max_len):
        return f"{prefix}{preview}"
    return None


def _tool_call_request_preview(tool_call_requests: Sequence[ToolCallRequest]):
    if len(tool_call_requests) == 1:
        return f"tool: {tool_call_requests[0].preview}"

    return f"tools: [{', '.join([t.preview for t in tool_call_requests])}]"


def _messages_preview(messages: StoredMessages):
    if extra := messages.model_extra:
        first_preview = compute_preview(extra)
        if len(first_preview) < DEFAULT_PREVIEW_MAX_LEN:
            if second_preview := _messages_list_preview(
                messages.messages,
                include_roles={"user", "assistant"},
                max_len=DEFAULT_PREVIEW_MAX_LEN - len(first_preview),
            ):
                first_preview += f" | {second_preview}"
        return first_preview
    return _messages_list_preview(messages.messages) or ""


def assign_run_previews(run: AgentRun, messages: StoredMessages | None):
    if not run.task_input_preview:
        run.task_input_preview = _messages_preview(messages) if messages else compute_preview(run.task_input)
    if not run.task_output_preview:
        if run.task_output:
            run.task_output_preview = compute_preview(run.task_output)
        elif run.tool_call_requests:
            run.task_output_preview = _tool_call_request_preview(run.tool_call_requests)
