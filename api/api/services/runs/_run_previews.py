import logging
from typing import Any, Sequence, cast

from pydantic import ValidationError

from core.domain.agent_run import AgentRun
from core.domain.consts import INPUT_KEY_MESSAGES
from core.domain.message import Messages
from core.domain.task_io import RawMessagesSchema, SerializableTaskIO
from core.domain.task_variant import SerializableTaskVariant
from core.domain.tool_call import ToolCallRequest
from core.utils.models.previews import DEFAULT_PREVIEW_MAX_LEN, compute_preview


def _messages_preview(payload: Any, include_roles: set[str] = {"user"}, max_len: int = DEFAULT_PREVIEW_MAX_LEN):
    try:
        validated = Messages.model_validate(payload)
    except ValidationError:
        logging.getLogger("RunsService").warning("Error validating messages", exc_info=True)
        return None

    if not validated.messages:
        return None

    first_user_message = next((m for m in validated.messages if m.role in include_roles), validated.messages[0])

    if not first_user_message.content:
        return None

    content = first_user_message.content[0]
    if content.file:
        return compute_preview(content.file, max_len=max_len)

    if content.text:
        return compute_preview(content.text)

    return None


def _compute_preview(payload: Any, agent_io: SerializableTaskIO):
    if agent_io.version == RawMessagesSchema.version:
        # Then we try and preview the first user message
        if preview := _messages_preview(payload):
            return preview

    if agent_io.uses_messages and isinstance(payload, dict) and INPUT_KEY_MESSAGES in payload:
        # That means we are in the case of an input schema in the case of a proxy task
        # In which case we preview the input, and then the messages in the reply
        without_messages = {k: v for k, v in cast(dict[str, Any], payload).items() if k != INPUT_KEY_MESSAGES}
        first_preview = compute_preview(without_messages)
        if len(first_preview) < DEFAULT_PREVIEW_MAX_LEN:
            if second_preview := _messages_preview(
                {"messages": payload[INPUT_KEY_MESSAGES]},
                include_roles={"user", "assistant"},
                max_len=DEFAULT_PREVIEW_MAX_LEN - len(first_preview),
            ):
                first_preview += f" | messages: {second_preview}"
        return first_preview

    return compute_preview(payload)


def _tool_call_request_preview(tool_call_requests: Sequence[ToolCallRequest]):
    if len(tool_call_requests) == 1:
        return f"tool: {tool_call_requests[0].preview}"

    return f"tools: [{', '.join([t.preview for t in tool_call_requests])}]"


def assign_run_previews(run: AgentRun, variant: SerializableTaskVariant):
    if not run.task_input_preview:
        run.task_input_preview = _compute_preview(run.task_input, variant.input_schema)
    if not run.task_output_preview:
        if run.task_output:
            run.task_output_preview = _compute_preview(run.task_output, variant.output_schema)
        elif run.tool_call_requests:
            run.task_output_preview = _tool_call_request_preview(run.tool_call_requests)
