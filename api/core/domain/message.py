import asyncio
from collections.abc import Sequence
from enum import StrEnum, auto
from typing import Literal

from pydantic import BaseModel

from core.domain.fields.file import File
from core.domain.fields.image_options import ImageOptions
from core.domain.tool_call import ToolCall, ToolCallRequestWithID
from core.domain.types import TemplateRenderer


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

    async def templated(self, renderer: TemplateRenderer):
        try:
            async with asyncio.TaskGroup() as tg:
                text_task = tg.create_task(renderer(self.text)) if self.text else None
                file_task = tg.create_task(self.file.templated(renderer)) if self.file else None
        except ExceptionGroup as e:
            # Raising the first exception, to avoid having a special kind of exception to handle
            # This is not great and we should return a compound instead
            raise e.exceptions[0]

        return MessageContent(
            text=text_task.result() if text_task else None,
            file=file_task.result() if file_task else None,
            tool_call_request=self.tool_call_request,
        )


class Message(BaseModel):
    # It would be nice to use strict validation since we know that certain roles are not allowed to
    # have certain content. Unfortunately it would mean that we would have oneOfs in the schema which
    # we currently do not handle client side
    role: Literal["system", "user", "assistant"]
    content: list[MessageContent]
    image_options: ImageOptions | None = None

    async def templated(self, renderer: TemplateRenderer):
        try:
            contents = await asyncio.gather(*[c.templated(renderer) for c in self.content])
        except ExceptionGroup as e:
            # Raising the first exception, to avoid having a special kind of exception to handle
            # This is not great and we should return a compound instead
            raise e.exceptions[0]
        return Message(
            role=self.role,
            content=contents,
            image_options=self.image_options,
            tool_call=self.tool_call,
        )

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


class Messages(BaseModel):
    messages: list[Message]

    async def templated(self, renderer: TemplateRenderer):
        try:
            messages = await asyncio.gather(*[m.templated(renderer) for m in self.messages])
        except ExceptionGroup as e:
            # Raising the first exception, to avoid having a special kind of exception to handle
            # This is not great and we should return a compound instead
            raise e.exceptions[0]
        return Messages(messages=messages)

    def to_deprecated(self) -> list[MessageDeprecated]:
        return [m.to_deprecated() for m in self.messages]

    def to_input_dict(self):
        return self.model_dump(exclude_none=True)
