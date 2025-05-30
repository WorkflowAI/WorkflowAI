import json
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.domain.errors import UnpriceableRunError
from core.domain.fields.file import File
from core.domain.llm_usage import LLMUsage
from core.domain.message import MessageDeprecated
from core.domain.models import Model
from core.providers.base.models import (
    AudioContentDict,
    DocumentContentDict,
    ImageContentDict,
    StandardMessage,
    TextContentDict,
    ToolCallRequestDict,
    ToolCallResultDict,
)
from core.providers.google.google_provider_domain import (
    internal_tool_name_to_native_tool_call,
    native_tool_name_to_internal,
)
from core.providers.openai.openai_domain import parse_tool_call_or_raise
from core.utils.token_utils import tokens_from_string

FireworksAIRole = Literal["system", "user", "assistant"]


class TextContent(BaseModel):
    type: Literal["text"] = "text"
    text: str

    def to_standard(self) -> TextContentDict:
        return {"type": "text", "text": self.text}


class ImageContent(BaseModel):
    type: Literal["image_url"] = "image_url"

    class URL(BaseModel):
        url: str

    image_url: URL

    def to_standard(self) -> ImageContentDict:
        return {"type": "image_url", "image_url": {"url": self.image_url.url}}

    @classmethod
    def from_file(cls, file: File, inline: bool = True) -> Self:
        url = file.to_url(default_content_type="image/*")
        if inline:
            url += "#transform=inline"
        return cls(image_url=ImageContent.URL(url=url))


role_to_fireworks_map: dict[MessageDeprecated.Role, FireworksAIRole] = {
    MessageDeprecated.Role.SYSTEM: "system",
    MessageDeprecated.Role.USER: "user",
    MessageDeprecated.Role.ASSISTANT: "assistant",
}


class FireworksToolMessage(BaseModel):
    role: Literal["tool"]
    tool_call_id: str
    content: Any

    @classmethod
    def from_domain(cls, message: MessageDeprecated) -> list[Self]:
        if not message.tool_call_results:
            return []

        return [
            cls(
                tool_call_id=result.id,
                content=str(result.result),  # OpenAI expects a string or array of string here.
                role="tool",
            )
            for result in message.tool_call_results
        ]

    @classmethod
    def to_standard(cls, messages: list[Self]) -> StandardMessage:
        return StandardMessage(
            role="user",
            content=[
                ToolCallResultDict(
                    type="tool_call_result",
                    id=item.tool_call_id,
                    tool_name="",
                    tool_input_dict=None,
                    result={"result": item.content},
                    error=None,
                )
                for item in messages
            ],
        )


class FireworksToolCallFunction(BaseModel):
    name: str
    arguments: str


class FireworksToolCall(BaseModel):
    id: str
    type: Literal["function"]
    function: FireworksToolCallFunction


class FireworksMessage(BaseModel):
    role: FireworksAIRole
    content: str | list[TextContent | ImageContent]
    tool_calls: list[FireworksToolCall] | None = None

    @classmethod
    def from_domain(cls, message: MessageDeprecated):
        role = role_to_fireworks_map[message.role]

        if not message.files and not message.tool_call_requests:
            return cls(content=message.content, role=role)

        content: list[TextContent | ImageContent] = []

        if message.content:
            content.append(TextContent(text=message.content))
        if message.files:
            content.extend((ImageContent.from_file(file) for file in message.files))

        tool_calls: list[FireworksToolCall] | None = None
        if message.tool_call_requests:
            tool_calls = [
                FireworksToolCall(
                    id=request.id,
                    type="function",
                    function=FireworksToolCallFunction(
                        name=internal_tool_name_to_native_tool_call(request.tool_name),
                        arguments=json.dumps(request.tool_input_dict),
                    ),
                )
                for request in message.tool_call_requests
            ]
        return cls(content=content, role=role, tool_calls=tool_calls)

    def to_standard(self) -> StandardMessage:
        tool_calls_content: list[ToolCallRequestDict] = []
        if self.tool_calls:
            tool_calls_content = [
                ToolCallRequestDict(
                    type="tool_call_request",
                    id=item.id,
                    tool_name=native_tool_name_to_internal(item.function.name),
                    tool_input_dict=parse_tool_call_or_raise(item.function.arguments),
                )
                for item in self.tool_calls
            ]

        if isinstance(self.content, str):
            return StandardMessage(
                role=self.role,
                content=(
                    self.content
                    if not tool_calls_content
                    else [TextContentDict(type="text", text=self.content), *tool_calls_content]
                ),
            )

        content: list[
            TextContentDict
            | ImageContentDict
            | AudioContentDict
            | DocumentContentDict
            | ToolCallRequestDict
            | ToolCallResultDict
        ] = [item.to_standard() for item in self.content]
        content.extend(tool_calls_content)

        return StandardMessage(
            role=self.role,
            content=content,
        )

    def token_count(self, model: Model) -> int:
        token_count = 0

        if isinstance(self.content, str):
            return tokens_from_string(self.content, model)

        for block in self.content:
            if isinstance(block, TextContent):
                token_count += tokens_from_string(block.text, model)
            else:
                raise UnpriceableRunError("Token counting for files is not implemented")

        return token_count


class TextResponseFormat(BaseModel):
    type: Literal["text"] = "text"


class JSONResponseFormat(BaseModel):
    type: Literal["json_object"] = "json_object"
    json_schema: dict[str, Any] | None = Field(serialization_alias="schema")


class FireworksToolFunction(BaseModel):
    name: str
    description: str | None = None
    parameters: dict[str, Any]


class FireworksTool(BaseModel):
    type: Literal["function"]
    function: FireworksToolFunction


class CompletionRequest(BaseModel):
    temperature: float
    # The max tokens to be generated
    # https://docs.fireworks.ai/api-reference/post-completions#body-max-tokens
    max_tokens: int | None
    model: str
    messages: list[FireworksMessage | FireworksToolMessage]
    response_format: TextResponseFormat | JSONResponseFormat | None
    stream: bool
    # https://docs.fireworks.ai/api-reference/post-completions#body-context-length-exceeded-behavior
    # Setting to truncate allows us to set the max_tokens to whatever value we want
    # and fireworks will limit the max_tokens to the "model context window - prompt token count"
    context_length_exceeded_behavior: Literal["truncate", "error"] = "truncate"
    user: str | None = None
    tools: list[FireworksTool] | None = None
    # tool_choice is not supported
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    top_p: float | None = None
    # Not supported by Fireworks
    # parallel_tool_calls: bool | None = None


ResponseFormat = Annotated[
    JSONResponseFormat,
    Field(discriminator="type"),
]


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def to_domain(self) -> LLMUsage:
        return LLMUsage(
            prompt_token_count=self.prompt_tokens,
            completion_token_count=self.completion_tokens,
        )


class _BaseChoice(BaseModel):
    index: int | None = None
    finish_reason: Literal["stop", "length", "tool_calls"] | None = None
    usage: Usage | None = None


class ChoiceMessage(BaseModel):
    role: FireworksAIRole | None = None
    content: None | str | list[TextContent | ImageContent] = None
    tool_calls: list[FireworksToolCall] | None = None


class Choice(_BaseChoice):
    message: ChoiceMessage


class CompletionResponse(BaseModel):
    id: str
    choices: list[Choice]
    usage: Usage


class StreamedToolCallFunction(BaseModel):
    name: str | None = None
    arguments: str | None = None


class StreamedToolCall(BaseModel):
    index: int
    id: str | None = None
    type: Literal["function"] | None = None
    function: StreamedToolCallFunction


class ChoiceDelta(_BaseChoice):
    class MessageDelta(BaseModel):
        content: str | None = ""
        tool_calls: list[StreamedToolCall] | None = None

    delta: MessageDelta


class StreamedResponse(BaseModel):
    id: str
    choices: list[ChoiceDelta]
    usage: Usage | None = None


class FireworksAIError(BaseModel):
    class Payload(BaseModel):
        code: str | None = None
        message: str | None = None
        type: str | None = None

        model_config = ConfigDict(extra="allow")

    error: Payload

    @field_validator("error", mode="before")
    def validate_error(cls, v: Any) -> Any:
        # Sometimes, fireworks returns a string instead of a dict
        if isinstance(v, str):
            return cls.Payload(message=v)
        return v
