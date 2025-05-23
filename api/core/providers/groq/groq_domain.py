import json
from typing import Any, Literal

from pydantic import BaseModel, Field
from typing_extensions import Annotated

from core.domain.errors import UnpriceableRunError
from core.domain.fields.file import File
from core.domain.llm_usage import LLMUsage
from core.domain.message import MessageDeprecated
from core.domain.models import Model
from core.domain.tool import Tool
from core.domain.tool_call import ToolCall, ToolCallRequestWithID
from core.providers.base.models import (
    AudioContentDict,
    DocumentContentDict,
    ImageContentDict,
    StandardMessage,
    TextContentDict,
    ToolCallRequestDict,
    ToolCallResultDict,
)
from core.providers.base.provider_error import ModelDoesNotSupportMode
from core.providers.google.google_provider_domain import native_tool_name_to_internal
from core.providers.openai.openai_domain import parse_tool_call_or_raise
from core.utils.token_utils import tokens_from_string

GroqRole = Literal["system", "user", "assistant", "tool"]


role_to_groq_map: dict[MessageDeprecated.Role, Literal["system", "user", "assistant"]] = {
    MessageDeprecated.Role.SYSTEM: "system",
    MessageDeprecated.Role.USER: "user",
    MessageDeprecated.Role.ASSISTANT: "assistant",
}

groq_to_role_map: dict[GroqRole, Literal["system", "user", "assistant"] | None] = {
    "system": "system",
    "user": "user",
    "assistant": "assistant",
    "tool": "user",
}


class _TextContent(BaseModel):
    type: Literal["text"] = "text"
    text: str

    def to_standard(self) -> TextContentDict:
        return {"type": "text", "text": self.text}


class _ImageContent(BaseModel):
    type: Literal["image_url"] = "image_url"

    class URL(BaseModel):
        url: str

    image_url: URL

    def to_standard(self) -> ImageContentDict:
        return {"type": "image_url", "image_url": {"url": self.image_url.url}}

    @classmethod
    def from_file(cls, file: File):
        return cls(image_url=cls.URL(url=file.to_url(default_content_type="image/*")))


class GroqToolDescription(BaseModel):
    type: Literal["function"] = "function"

    class Function(BaseModel):
        name: str
        description: str | None = None
        parameters: dict[str, Any] | None = None
        # strict is not supported by Groq

    function: Function

    @classmethod
    def from_domain(cls, tool: Tool):
        return cls(
            type="function",
            function=cls.Function(
                name=tool.name,
                description=tool.description,
                parameters=tool.input_schema,
            ),
        )


class _ToolCall(BaseModel):
    id: str | None = None
    type: Literal["function"] = "function"

    class Function(BaseModel):
        name: str | None = None
        arguments: str | None = None

    function: Function

    @classmethod
    def from_domain(cls, tool_call: ToolCallRequestWithID):
        return cls(
            id=tool_call.id,
            function=cls.Function(name=tool_call.tool_name, arguments=json.dumps(tool_call.tool_input_dict)),
        )

    def to_standard(self) -> ToolCallRequestDict:
        return ToolCallRequestDict(
            type="tool_call_request",
            id=self.id,
            tool_name=native_tool_name_to_internal(self.function.name or ""),
            tool_input_dict=json.loads(self.function.arguments or "{}"),
        )


class GroqMessage(BaseModel):
    role: GroqRole | None = None
    content: str | list[_TextContent | _ImageContent] | None = None
    # Tool calls generated by the model
    tool_calls: list[_ToolCall] | None = None
    # Only set for role = "tool"
    tool_call_id: str | None = None

    def token_count(self, model: Model) -> int:
        if isinstance(self.content, str):
            return tokens_from_string(self.content, model)

        raise UnpriceableRunError("Groq does not support token counting for non-text content")

    @classmethod
    def _from_tool_call_result(cls, result: ToolCall):
        return cls(
            role="tool",
            content=result.stringified_result(),
            tool_call_id=result.id,
        )

    @classmethod
    def from_domain(cls, message: MessageDeprecated):
        out: list[cls] = []

        role = role_to_groq_map[message.role]

        if message.content and not message.files and not message.tool_call_requests:
            out.append(cls(role=role, content=message.content))
            return out

        content: list[_TextContent | _ImageContent] = []

        if message.content:
            content.append(_TextContent(text=message.content))
        for file in message.files or []:
            if file.is_image:
                content.append(_ImageContent.from_file(file))
            else:
                raise ModelDoesNotSupportMode("Groq only supports image files in messages")

        if content or message.tool_call_requests:
            out.append(
                cls(
                    role=role,
                    content=content or None,
                    tool_calls=[_ToolCall.from_domain(tool_call) for tool_call in message.tool_call_requests]
                    if message.tool_call_requests
                    else None,
                ),
            )

        if message.tool_call_results:
            out.extend(cls._from_tool_call_result(result) for result in message.tool_call_results)
        return out

    def to_standard(self):
        # This is not great, we should really remove the need for this conversion entirely
        # See https://linear.app/workflowai/issue/WOR-3957/we-should-store-the-completion-as-our-internal-model-and-the-raw
        # Storing the domain message format directly instead of the raw provider message would likely solve our issues

        content: list[
            TextContentDict
            | ImageContentDict
            | AudioContentDict
            | DocumentContentDict
            | ToolCallRequestDict
            | ToolCallResultDict
        ] = []
        if self.content:
            if self.role == "tool":
                content.append(
                    ToolCallResultDict(
                        type="tool_call_result",
                        id=self.tool_call_id,
                        result=self.content,
                        tool_input_dict=None,
                        tool_name=None,
                        error=None,
                    ),
                )
            elif isinstance(self.content, str):
                content.append(TextContentDict(type="text", text=self.content))
            else:
                content.extend(item.to_standard() for item in self.content)

        if self.tool_calls:
            content.extend(
                ToolCallRequestDict(
                    type="tool_call_request",
                    id=item.id,
                    tool_name=native_tool_name_to_internal(item.function.name or ""),
                    tool_input_dict=parse_tool_call_or_raise(item.function.arguments or "{}"),
                )
                for item in self.tool_calls
            )

        return StandardMessage(role=groq_to_role_map.get(self.role) if self.role else None, content=content)


class JSONResponseFormat(BaseModel):
    type: Literal["json_object"] = "json_object"


class TextResponseFormat(BaseModel):
    type: Literal["text"] = "text"


ResponseFormat = Annotated[
    JSONResponseFormat | TextResponseFormat,
    Field(discriminator="type"),
]


class CompletionRequest(BaseModel):
    # https://console.groq.com/docs/api-reference#chat
    temperature: float
    max_tokens: int | None
    model: str
    messages: list[GroqMessage]
    stream: bool
    response_format: ResponseFormat

    tools_choice: Literal["auto", "none", "required"] | None = None
    tools: list[GroqToolDescription] | None = None
    top_p: float | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    parallel_tool_calls: bool | None = None


class _BaseChoice(BaseModel):
    index: int | None = None
    finish_reason: str | None = None


class Choice(_BaseChoice):
    message: GroqMessage


class StreamedToolCall(BaseModel):
    index: int
    id: str | None = None
    type: Literal["function"] | None = None

    class Function(BaseModel):
        name: str | None = None
        arguments: str | None = None

    function: Function


class ChoiceDelta(_BaseChoice):
    class MessageDelta(BaseModel):
        content: str | None = None
        tool_calls: list[StreamedToolCall] | None = None

    delta: MessageDelta


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def to_domain(self) -> LLMUsage:
        return LLMUsage(
            prompt_token_count=self.prompt_tokens,
            completion_token_count=self.completion_tokens,
        )


class CompletionResponse(BaseModel):
    id: str
    choices: list[Choice]
    usage: Usage


class StreamedResponse(BaseModel):
    id: str
    choices: list[ChoiceDelta]
    usage: Usage | None = None

    class XGroq(BaseModel):
        usage: Usage | None = None
        error: str | None = None

    x_groq: XGroq | None = None


class GroqError(BaseModel):
    class Payload(BaseModel):
        message: str | None = None
        type: str | None = None
        param: str | None = None
        code: str = "unknown"
        failed_generation: str | None = None

    error: Payload
