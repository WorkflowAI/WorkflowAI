from collections.abc import Sequence
from enum import StrEnum, auto
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field

from core.domain.consts import INPUT_KEY_MESSAGES, INPUT_KEY_MESSAGES_DEPRECATED
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


MessageRole = Literal["system", "user", "assistant"]


class Message(BaseModel):
    # It would be nice to use strict validation since we know that certain roles are not allowed to
    # have certain content. Unfortunately it would mean that we would have oneOfs in the schema which
    # we currently do not handle client side
    role: MessageRole
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
        from core.domain.errors import InternalError

        raise InternalError("Unexpected message type")

    @classmethod
    def with_text(cls, text: str, role: MessageRole = "user"):
        return cls(role=role, content=[MessageContent(text=text)])

    @classmethod
    def with_file_url(cls, url: str, role: MessageRole = "user"):
        return cls(role=role, content=[MessageContent(file=File(url=url))])


class Messages(BaseModel):
    messages: list[Message] = Field(
        default_factory=list,
        serialization_alias=INPUT_KEY_MESSAGES,
        validation_alias=AliasChoices(INPUT_KEY_MESSAGES, "messages", INPUT_KEY_MESSAGES_DEPRECATED),
    )

    def to_deprecated(self) -> list[MessageDeprecated]:
        return [m.to_deprecated() for m in self.messages]

    def to_input_dict(self):
        return self.model_dump(exclude_none=True)
