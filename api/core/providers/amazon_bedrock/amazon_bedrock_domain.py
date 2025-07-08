import hashlib
import re
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, BeforeValidator, Field, ValidationError

from core.domain.errors import InternalError, InvalidRunOptionsError, UnpriceableRunError
from core.domain.fields.file import File as DomainImage
from core.domain.llm_usage import LLMUsage
from core.domain.message import MessageDeprecated
from core.domain.models import Model
from core.domain.task_group_properties import ToolChoice as DomainToolChoice
from core.domain.tool import Tool as DomainTool
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
from core.providers.google.google_provider_domain import (
    internal_tool_name_to_native_tool_call,
    native_tool_name_to_internal,
)
from core.utils.dicts import TwoWayDict
from core.utils.json_utils import safe_extract_dict_from_json
from core.utils.token_utils import tokens_from_string

AmazonBedrockRole = Literal["system", "user", "assistant"]

AnthropicImageFormat = Literal["png", "jpeg", "gif", "webp"]


MESSAGE_ROLE_X_ROLE_MAP: dict[MessageDeprecated.Role, AmazonBedrockRole] = {
    MessageDeprecated.Role.SYSTEM: "assistant",
    MessageDeprecated.Role.USER: "user",
    MessageDeprecated.Role.ASSISTANT: "assistant",
}


MIME_TO_FORMAT_MAP = TwoWayDict[str, AnthropicImageFormat](
    ("image/png", "png"),
    ("image/jpeg", "jpeg"),
    ("image/gif", "gif"),
    ("image/webp", "webp"),
)


def _sanitize_tool_id(tool_id: str) -> str:
    """
    Sanitize the tool id to be a valid Amazon Bedrock tool id
    """
    if not re.match(r"^[a-zA-Z0-9_-]+$", tool_id):
        return hashlib.sha256(tool_id.encode()).hexdigest()
    return tool_id


_ToolUseID = Annotated[str, BeforeValidator(_sanitize_tool_id)]


# https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ContentBlock.html
class ContentBlock(BaseModel):
    text: str | None = None

    class Image(BaseModel):
        format: AnthropicImageFormat

        class Source(BaseModel):
            bytes: str

        source: Source

        def to_url(self) -> str:
            return f"data:{MIME_TO_FORMAT_MAP.backward(self.format)};base64,{self.source.bytes}"

        @classmethod
        def from_domain(cls, image: DomainImage):
            if not image.data or not image.content_type:
                raise InternalError("Image data and content type are required", extras={"image": image.model_dump()})
            try:
                image_format = MIME_TO_FORMAT_MAP[image.content_type]
            except KeyError:
                raise ModelDoesNotSupportMode(
                    f"Unsupported image format: {image.content_type}, only PNG, JPEG, GIF, and WEBP are supported",
                )

            return cls(format=image_format, source=ContentBlock.Image.Source(bytes=image.data))

    image: Image | None = None

    class ThinkingContent(BaseModel):
        thinking: str
        signature: str | None = None

        def to_standard(self) -> TextContentDict:
            return {"type": "text", "text": self.thinking}

    thinking: ThinkingContent | None = None

    def to_standard(
        self,
    ) -> list[TextContentDict | ImageContentDict | AudioContentDict | ToolCallRequestDict | ToolCallResultDict]:
        out: list[TextContentDict | ImageContentDict | AudioContentDict | ToolCallRequestDict | ToolCallResultDict] = []
        if self.text:
            out.append({"text": self.text, "type": "text"})
        if self.image:
            out.append({"image_url": {"url": self.image.to_url()}, "type": "image_url"})
        if self.thinking:
            out.append(self.thinking.to_standard())
        if self.toolUse:
            out.append(
                {
                    "id": self.toolUse.toolUseId,
                    "tool_name": native_tool_name_to_internal(self.toolUse.name),
                    "tool_input_dict": self.toolUse.input,
                    "type": "tool_call_request",
                },
            )
        if self.toolResult:
            out.extend(
                [
                    {
                        "id": self.toolResult.toolUseId,
                        "tool_name": None,
                        "tool_input_dict": None,
                        "result": tool_result_content.json_content,
                        "error": None if self.toolResult.status == "success" else "error",
                        "type": "tool_call_result",
                    }
                    for tool_result_content in self.toolResult.content
                ],
            )
        return out

    class ToolUse(BaseModel):
        toolUseId: _ToolUseID
        name: str
        input: dict[str, Any]

    toolUse: ToolUse | None = None

    class ToolResult(BaseModel):
        toolUseId: _ToolUseID

        class ToolResultContentBlock(BaseModel):
            json_content: dict[str, Any] | None = Field(default=None, alias="json")
            # ToolResultContentBlock also supports image, video, document content blocks, but we stick for now to the JSON
            # https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ToolResultContentBlock.html

        content: list[ToolResultContentBlock]
        status: Literal["success", "error"] = "success"

    toolResult: ToolResult | None = None


class AmazonBedrockMessage(BaseModel):
    role: AmazonBedrockRole | None = None
    content: list[ContentBlock]

    @classmethod
    def from_domain(cls, message: MessageDeprecated) -> Self:
        role = MESSAGE_ROLE_X_ROLE_MAP[message.role]
        content: list[ContentBlock] = []

        if message.content:
            content.append(ContentBlock(text=message.content))

        content.extend([ContentBlock(image=ContentBlock.Image.from_domain(image)) for image in message.files or []])

        content.extend(
            [
                ContentBlock(
                    toolUse=ContentBlock.ToolUse(
                        toolUseId=tool_call_request.id,
                        name=internal_tool_name_to_native_tool_call(tool_call_request.tool_name),
                        input=tool_call_request.tool_input_dict,
                    ),
                )
                for tool_call_request in message.tool_call_requests or []
            ],
        )

        for tool_call_result in message.tool_call_results or []:
            dict_result = safe_extract_dict_from_json(tool_call_result.result)
            if dict_result:
                result = dict_result
            else:
                result = {"result": str(tool_call_result.result)}

            content.append(
                ContentBlock(
                    toolResult=ContentBlock.ToolResult(
                        toolUseId=tool_call_result.id,
                        content=[
                            ContentBlock.ToolResult.ToolResultContentBlock(
                                json=result,
                            ),
                        ],
                    ),
                ),
            )

        return cls(content=content, role=role)

    def token_count(self, model: Model) -> int:
        token_count = 0
        for block in self.content:
            if block.text:
                token_count += tokens_from_string(block.text, model)
            if block.image:
                raise UnpriceableRunError("Token counting for images is not implemented")
        return token_count

    def to_standard(self) -> StandardMessage:
        content: list[
            TextContentDict
            | ImageContentDict
            | AudioContentDict
            | DocumentContentDict
            | ToolCallRequestDict
            | ToolCallResultDict
        ] = []
        for block in self.content:
            content.extend(block.to_standard())
        if len(content) == 1 and content[0]["type"] == "text":
            return {"role": self.role, "content": content[0]["text"]}

        return {"role": self.role, "content": content}


class AmazonBedrockSystemMessage(BaseModel):
    text: str

    @classmethod
    def from_domain(cls, message: MessageDeprecated) -> Self:
        if message.files:
            raise InvalidRunOptionsError("System messages cannot contain images")

        return cls(text=message.content)

    def token_count(self, model: Model) -> int:
        return tokens_from_string(self.text, model)

    def to_standard(self) -> StandardMessage:
        return {"role": "system", "content": self.text}


class BedrockToolInputSchema(BaseModel):
    json_schema: dict[str, Any] | None = Field(
        default=None,
        description="A plain JSON schema",
        alias="json",  # json is a reserved word in Pydantic
    )


# https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ToolSpecification.html
# Bedrock does not support strict yet
class BedrockToolSpec(BaseModel):
    name: str
    description: str | None
    inputSchema: BedrockToolInputSchema


class BedrockTool(BaseModel):
    toolSpec: BedrockToolSpec

    @classmethod
    def from_domain(cls, tool: DomainTool) -> Self:
        return cls(
            toolSpec=BedrockToolSpec(
                name=internal_tool_name_to_native_tool_call(tool.name),
                # Bedrock requires a description to be at least 1 character
                description=tool.description if tool.description and len(tool.description) > 1 else None,
                inputSchema=BedrockToolInputSchema(json=tool.input_schema),
            ),
        )


class BedrockToolConfig(BaseModel):
    tools: list[BedrockTool]

    class ToolChoice(BaseModel):
        # only one field should be set
        # any and auto should be set to {} if used
        any: dict[str, Any] | None = None
        auto: dict[str, Any] | None = None
        # tool should be set to the name of the tool
        tool: dict[str, Any] | None = None

        @classmethod
        def from_domain(cls, tool_choice: DomainToolChoice | None) -> Self | None:
            if not tool_choice:
                return None
            if isinstance(tool_choice, str):
                match tool_choice:
                    case "auto":
                        return cls(auto={})
                    case "required":
                        return cls(any={})
                    case "none":
                        # Not sure what to return here
                        return None
            return cls(tool={"name": tool_choice.name})

    toolChoice: ToolChoice | None = None

    @classmethod
    def from_domain(cls, tools: list[DomainTool] | None, tool_choice: DomainToolChoice | None):
        if not tools:
            return None
        return cls(
            tools=[BedrockTool.from_domain(tool) for tool in tools],
            toolChoice=cls.ToolChoice.from_domain(tool_choice),
        )


# https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html#API_runtime_Converse_RequestBody
class CompletionRequest(BaseModel):
    system: list[AmazonBedrockSystemMessage]
    messages: list[AmazonBedrockMessage]
    toolConfig: BedrockToolConfig | None = None

    # https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_InferenceConfiguration.html
    class InferenceConfig(BaseModel):
        maxTokens: int | None = None
        temperature: float | None = None
        topP: float | None = None

    inferenceConfig: InferenceConfig

    class Thinking(BaseModel):
        type: Literal["enabled"]  # 'disabled' is never used
        budget_tokens: int

    thinking: Thinking | None = None


class Usage(BaseModel):
    inputTokens: int = 0
    outputTokens: int = 0
    totalTokens: int = 0

    def to_domain(self) -> LLMUsage:
        return LLMUsage(
            prompt_token_count=self.inputTokens,
            completion_token_count=self.outputTokens,
        )


class CompletionResponse(BaseModel):
    stopReason: str

    class Output(BaseModel):
        class Message(BaseModel):
            role: AmazonBedrockRole | None = None
            content: list[ContentBlock]

        message: Message

    output: Output
    usage: Usage


class StreamedResponse(BaseModel):
    contentBlockIndex: int | None = None

    class Delta(BaseModel):
        text: str | None = None

        class ToolUseBlockDelta(BaseModel):
            input: str

        toolUse: ToolUseBlockDelta | None = None

        class ThinkingDelta(BaseModel):
            thinking: str

        thinking: ThinkingDelta | None = None

    delta: Delta | None = None

    class Start(BaseModel):
        class ToolUse(BaseModel):
            name: str
            toolUseId: _ToolUseID

        toolUse: ToolUse | None = None

        class ThinkingBlock(BaseModel):
            thinking: str | None = None

        thinking: ThinkingBlock | None = None

    start: Start | None = None

    usage: Usage | None = None


def message_or_system(message: dict[str, Any]) -> AmazonBedrockMessage | AmazonBedrockSystemMessage:
    try:
        return AmazonBedrockMessage.model_validate(message)
    except ValidationError:
        return AmazonBedrockSystemMessage.model_validate(message)


class BedrockError(BaseModel):
    message: str | None = None
