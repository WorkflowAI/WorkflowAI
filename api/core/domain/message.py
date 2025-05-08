from collections.abc import Sequence
from enum import StrEnum, auto
from typing import Literal

from pydantic import BaseModel

from core.domain.errors import InternalError
from core.domain.fields.file import File
from core.domain.fields.image_options import ImageOptions
from core.domain.tool_call import ToolCall, ToolCallRequestWithID


class MessageDeprecated(BaseModel):
    class Role(StrEnum):
        SYSTEM = auto()
        USER = auto()
        ASSISTANT = auto()

    role: Role
    content: str
    files: Sequence[File] | None = None

    tool_call_requests: list[ToolCallRequestWithID] | None = None
    tool_call_results: list[ToolCall] | None = None

    image_options: ImageOptions | None = None


class MessageContent(BaseModel):
    text: str | None = None
    file: File | None = None
    tool_call_request: ToolCallRequestWithID | None = None
    tool_call_result: ToolCall | None = None


class Message(BaseModel):
    # It would be nice to use strict validation since we know that certain roles are not allowed to
    # have certain content. Unfortunately it would mean that we would have oneOfs in the schema which
    # we currently do not handle client side
    role: Literal["system", "user", "assistant"]
    content: list[MessageContent]
    image_options: ImageOptions | None = None

    def to_deprecated(self) -> MessageDeprecated:
        # TODO: remove this method
        content = "\n\n".join([c.text for c in self.content if c.text])
        files = [c.file for c in self.content if c.file]
        tool_call_requests = [c.tool_call_request for c in self.content if c.tool_call_request]
        tool_call_results = [c.tool_call_result for c in self.content if c.tool_call_result]
        match self.role:
            case "system":
                return MessageDeprecated(role=MessageDeprecated.Role.SYSTEM, content=content)
            case "user":
                return MessageDeprecated(
                    role=MessageDeprecated.Role.USER,
                    content=content,
                    files=files,
                    tool_call_requests=tool_call_requests,
                    tool_call_results=tool_call_results,
                )
            case "assistant":
                return MessageDeprecated(
                    role=MessageDeprecated.Role.ASSISTANT,
                    content=content,
                    files=files,
                    tool_call_requests=tool_call_requests,
                )
        # We should never reach this point
        raise InternalError("Unexpected message type")


class Messages(BaseModel):
    messages: list[Message]

    def to_deprecated(self) -> list[MessageDeprecated]:
        return [m.to_deprecated() for m in self.messages]

    def to_input_dict(self):
        return self.model_dump(exclude_none=True)
