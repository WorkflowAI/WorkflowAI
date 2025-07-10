import json
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field

from core.domain.errors import (
    InvalidRunOptionsError,
)
from core.domain.llm_usage import LLMUsage
from core.domain.message import MessageDeprecated
from core.domain.models import Model
from core.domain.task_group_properties import ToolChoice, ToolChoiceFunction
from core.providers.base.models import (
    AudioContentDict,
    DocumentContentDict,
    ImageContentDict,
    StandardMessage,
    TextContentDict,
    ToolCallRequestDict,
    ToolCallResultDict,
)
from core.providers.base.provider_error import FailedGenerationError
from core.providers.google.google_provider_domain import (
    native_tool_name_to_internal,
)
from core.utils.json_utils import safe_extract_dict_from_json
from core.utils.token_utils import tokens_from_string

CerebrasRole = Literal["system", "user", "assistant"]


class TextContent(BaseModel):
    type: Literal["text"] = "text"
    text: str

    def to_standard(self) -> TextContentDict:
        return {"type": "text", "text": self.text}


def parse_tool_call_or_raise(arguments: str) -> dict[str, Any] | None:
    if arguments == "{}":
        return None
    try:
        args_dict = safe_extract_dict_from_json(arguments)
        if args_dict is None:
            raise ValueError("Can't parse dictionary from tool call arguments")
        return args_dict
    except (ValueError, json.JSONDecodeError):
        raise FailedGenerationError(
            f"Failed to parse tool call arguments: {arguments}",
            code="failed_to_parse_tool_call_arguments",
        )


role_to_cerebras_map: dict[MessageDeprecated.Role, CerebrasRole] = {
    MessageDeprecated.Role.SYSTEM: "system",
    MessageDeprecated.Role.USER: "user",
    MessageDeprecated.Role.ASSISTANT: "assistant",
}

cerebras_to_role_map: dict[CerebrasRole, Literal["system", "user", "assistant"] | None] = {
    "system": "system",
    "user": "user",
    "assistant": "assistant",
}


class ToolCallFunction(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    id: str
    type: Literal["function"]
    function: ToolCallFunction


class ToolFunction(BaseModel):
    name: str
    description: str | None = None
    parameters: dict[str, Any] | None = None
    strict: bool = False


class Tool(BaseModel):
    type: Literal["function"]
    function: ToolFunction


class CerebrasToolChoice(BaseModel):
    type: Literal["function"]

    class Function(BaseModel):
        name: str

    function: Function


class CerebrasToolMessage(BaseModel):
    role: Literal["tool"]
    tool_call_id: str
    content: str

    @classmethod
    def from_domain(cls, message: MessageDeprecated) -> list[Self]:
        if not message.tool_call_results:
            return []

        return [
            cls(
                tool_call_id=result.id,
                # Cerebras expects a string or array of string here,
                # but we stringify everything to simplify and align behavior with other providers.
                content=str(
                    result.result,
                ),
                role="tool",
            )
            for result in message.tool_call_results
        ]

    @classmethod
    def to_standard(cls, messages: list[Self]) -> StandardMessage:
        contents: list[
            TextContentDict
            | ImageContentDict
            | AudioContentDict
            | DocumentContentDict
            | ToolCallRequestDict
            | ToolCallResultDict
        ] = []

        for message in messages:
            try:
                result_dict = safe_extract_dict_from_json(message.content)
                if result_dict is None:
                    raise ValueError("Can't parse dictionary from result")
                contents.append(
                    ToolCallResultDict(
                        type="tool_call_result",
                        id=message.tool_call_id,
                        tool_name=None,
                        tool_input_dict=None,
                        result=result_dict,
                        error=None,
                    ),
                )
            except (ValueError, json.JSONDecodeError):
                contents.append(
                    ToolCallResultDict(
                        type="tool_call_result",
                        id=message.tool_call_id,
                        tool_name=None,
                        tool_input_dict=None,
                        result={"result": message.content},
                        error=None,
                    ),
                )

        return StandardMessage(
            role="user",
            content=contents,
        )

    def token_count(self, model: Model) -> int:
        # Very basic implementation of the pricing of tool calls messages.
        # We'll need to double check the pricing rules for every provider
        # When working on https://linear.app/workflowai/issue/WOR-3730
        return tokens_from_string(self.content, model)


class CerebrasMessage(BaseModel):
    role: CerebrasRole | None = None
    content: str | list[TextContent]
    tool_calls: list[ToolCall] | None = None

    @classmethod
    def from_domain(cls, message: MessageDeprecated, model: str | None = None):
        role = role_to_cerebras_map[message.role]

        # Check if files are passed and raise error
        if message.files:
            raise InvalidRunOptionsError("Cerebras provider does not support files. Only text content is supported.")

        if not message.tool_call_requests:
            return cls(content=message.content, role=role)

        tool_calls: list[ToolCall] | None = None
        if message.tool_call_requests:
            # use empty tool_calls array to avoid errors
            # see https://inference-docs.cerebras.ai/capabilities/tool-use#current-limitations-of-multi-turn-tool-use
            tool_calls = []

        # If there are tool calls (or empty tool_calls for non-qwen models), content should be a string
        if tool_calls is not None:
            return cls(content=message.content or "", role=role, tool_calls=tool_calls)

        # Only support text content
        content: list[TextContent] = []
        if message.content:
            content.append(TextContent(text=message.content))

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
                role=cerebras_to_role_map.get(self.role) if self.role else None,
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
            role=cerebras_to_role_map.get(self.role) if self.role else None,
            content=content,
        )

    def token_count(self, model: Model) -> int:
        if isinstance(self.content, str):
            return tokens_from_string(self.content, model)

        token_count = 0
        for block in self.content:
            # Since we only support TextContent now, we can directly use it
            token_count += tokens_from_string(block.text, model)

        return token_count


class TextResponseFormat(BaseModel):
    type: Literal["text"] = "text"


class JSONResponseFormat(BaseModel):
    type: Literal["json_object"] = "json_object"


class CerebrasSchema(BaseModel):
    strict: bool = True
    name: str
    json_schema: Annotated[dict[str, Any], Field(serialization_alias="schema")]


class JSONSchemaResponseFormat(BaseModel):
    type: Literal["json_schema"] = "json_schema"
    json_schema: CerebrasSchema


class StreamOptions(BaseModel):
    include_usage: bool


ResponseFormat = Annotated[
    JSONResponseFormat | TextResponseFormat | JSONSchemaResponseFormat,
    Field(discriminator="type"),
]


class CompletionRequest(BaseModel):
    temperature: float | None
    max_completion_tokens: int | None
    model: str
    messages: list[CerebrasMessage | CerebrasToolMessage]
    response_format: ResponseFormat | None = JSONResponseFormat()
    stream: bool
    tools: list[Tool] | None = None
    tool_choice: CerebrasToolChoice | Literal["none", "auto", "required"] | None = None
    top_p: float | None = None
    seed: int | None = None
    stop: list[str] | None = None

    @classmethod
    def tool_choice_from_domain(
        cls,
        tool_choice: ToolChoice | None,
    ) -> CerebrasToolChoice | Literal["none", "auto", "required"] | None:
        if tool_choice is None:
            return None
        if isinstance(tool_choice, ToolChoiceFunction):
            return CerebrasToolChoice(type="function", function=CerebrasToolChoice.Function(name=tool_choice.name))
        return tool_choice


class _BaseChoice(BaseModel):
    index: int | None = None
    finish_reason: str | None = None


class ChoiceMessage(BaseModel):
    role: CerebrasRole | None = None
    content: None | str | list[TextContent] = None
    refusal: str | None = None
    finish_reason: str | None = None
    tool_calls: list[ToolCall] | None = None


class Choice(_BaseChoice):
    message: ChoiceMessage


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
        content: str | None = None
        tool_calls: list[StreamedToolCall] | None = None

    delta: MessageDelta


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    class PromptTokensDetails(BaseModel):
        audio_tokens: int = 0
        cached_tokens: int = 0

    prompt_tokens_details: PromptTokensDetails | None = None

    class CompletionTokensDetails(BaseModel):
        audio_tokens: int = 0

    completion_tokens_details: CompletionTokensDetails | None = None

    def to_domain(self) -> LLMUsage:
        return LLMUsage(
            prompt_token_count=self.prompt_tokens,
            prompt_token_count_cached=self.prompt_tokens_details.cached_tokens if self.prompt_tokens_details else None,
            prompt_audio_token_count=self.prompt_tokens_details.audio_tokens if self.prompt_tokens_details else None,
            completion_token_count=self.completion_tokens,
        )


class CompletionResponse(BaseModel):
    id: str | None = None
    choices: list[Choice] = Field(default_factory=list)
    usage: Usage | None = None


class StreamedResponse(BaseModel):
    id: str | None = None
    choices: list[ChoiceDelta] = Field(default_factory=list)
    usage: Usage | None = None


class CerebrasError(BaseModel):
    message: str
    type: str | None = None
    param: str | None = None
    code: str | None = None

    model_config = ConfigDict(extra="allow")
