import logging
from datetime import datetime
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field

from core.domain.fields.file import File
from core.domain.llm_completion import LLMCompletion
from core.domain.llm_usage import LLMUsage
from core.domain.message import Message, MessageContent, MessageDeprecated
from core.domain.tool_call import ToolCall, ToolCallRequestWithID
from core.utils.fields import datetime_factory


class RawCompletion(BaseModel):
    response: str | None
    usage: LLMUsage
    finish_reason: str | None = None

    start_time: datetime = Field(default_factory=datetime_factory)

    model_config = ConfigDict(extra="allow")

    def apply_to(self, llm_completion: LLMCompletion):
        if self.usage.completion_image_count is not None:
            llm_completion.usage.completion_image_count = self.usage.completion_image_count
        if self.usage.completion_token_count is not None:
            llm_completion.usage.completion_token_count = self.usage.completion_token_count
        if self.usage.completion_cost_usd is not None:
            llm_completion.usage.completion_cost_usd = self.usage.completion_cost_usd
        if self.usage.prompt_token_count is not None:
            llm_completion.usage.prompt_token_count = self.usage.prompt_token_count
        if self.usage.prompt_cost_usd is not None:
            llm_completion.usage.prompt_cost_usd = self.usage.prompt_cost_usd
        if self.usage.prompt_token_count_cached is not None:
            llm_completion.usage.prompt_token_count_cached = self.usage.prompt_token_count_cached
        if self.usage.model_context_window_size is not None:
            llm_completion.usage.model_context_window_size = self.usage.model_context_window_size
        if self.usage.reasoning_token_count is not None:
            llm_completion.usage.reasoning_token_count = self.usage.reasoning_token_count


class TextContentDict(TypedDict):
    type: Literal["text"]
    text: str


class DocumentURLDict(TypedDict):
    url: str


class DocumentContentDict(TypedDict):
    type: Literal["document_url"]
    source: DocumentURLDict


class ImageURLDict(TypedDict):
    url: str


class AudioURLDict(TypedDict):
    url: str


class ImageContentDict(TypedDict):
    type: Literal["image_url"]
    image_url: ImageURLDict


class AudioContentDict(TypedDict):
    type: Literal["audio_url"]
    audio_url: AudioURLDict


class ToolCallRequestDict(TypedDict):
    type: Literal["tool_call_request"]
    id: str | None
    tool_name: str
    tool_input_dict: dict[str, Any] | None


class ToolCallResultDict(TypedDict):
    type: Literal["tool_call_result"]
    id: str | None
    tool_name: str | None
    tool_input_dict: dict[str, Any] | None
    result: Any | None
    error: str | None


class StandardMessage(TypedDict):
    # NOTE: The structure is standard for all providers.
    # So keep consistent with client side as well.
    role: Literal["system", "user", "assistant"] | None
    content: (
        str
        | list[
            TextContentDict
            | ImageContentDict
            | AudioContentDict
            | DocumentContentDict
            | ToolCallRequestDict
            | ToolCallResultDict
        ]
    )


_logger = logging.getLogger(__name__)


def role_standard_to_domain(role: Literal["system", "user", "assistant"] | None) -> MessageDeprecated.Role:
    if not role:
        _logger.warning("No role provided, using default role")
        # TODO: Using a default role, not the best solution
        return MessageDeprecated.Role.USER
    return MessageDeprecated.Role(role)


def role_domain_to_standard(role: MessageDeprecated.Role) -> Literal["system", "user", "assistant"]:
    return role.value  # type: ignore


def message_standard_to_domain_deprecated(message: StandardMessage):
    role = role_standard_to_domain(message["role"])
    raw = message["content"]
    if isinstance(raw, str):
        return MessageDeprecated(role=role, content=raw)

    content: list[str] = []
    files: list[File] = []
    tool_call_requests: list[ToolCallRequestWithID] = []
    tool_call_results: list[ToolCall] = []

    for item in raw:
        try:
            match item["type"]:
                case "text":
                    content.append(item["text"])
                case "image_url":
                    files.append(File(url=item["image_url"]["url"]))
                case "document_url":
                    files.append(File(url=item["source"]["url"]))
                case "audio_url":
                    files.append(File(url=item["audio_url"]["url"]))
                case "tool_call_request":
                    tool_call_requests.append(
                        ToolCallRequestWithID(
                            id=item["id"] or "",
                            tool_name=item["tool_name"],
                            tool_input_dict=item["tool_input_dict"] or {},
                        ),
                    )
                case "tool_call_result":
                    tool_call_results.append(
                        ToolCall(
                            id=item["id"] or "",
                            tool_name=item["tool_name"] or "",
                            tool_input_dict=item["tool_input_dict"] or {},
                            result=item["result"],
                            error=item["error"],
                        ),
                    )
                case _:  # pyright: ignore[reportUnnecessaryComparison]
                    _logger.exception("Unsupported content type: %s", item["type"])
        except KeyError:
            _logger.exception("Key error while parsing content", extra={"raw": message})

    return MessageDeprecated(
        role=role,
        content="\n".join(content),
        files=files or None,
        tool_call_requests=tool_call_requests or None,
        tool_call_results=tool_call_results or None,
    )


def _standard_content_to_domain(
    content: TextContentDict
    | ImageContentDict
    | AudioContentDict
    | DocumentContentDict
    | ToolCallRequestDict
    | ToolCallResultDict,
):
    match content["type"]:
        case "text":
            return MessageContent(text=content["text"])
        case "image_url":
            return MessageContent(file=File(url=content["image_url"]["url"]))
        case "document_url":
            return MessageContent(file=File(url=content["source"]["url"]))
        case "audio_url":
            return MessageContent(file=File(url=content["audio_url"]["url"]))
        case "tool_call_request":
            return MessageContent(
                tool_call_request=ToolCallRequestWithID(
                    id=content["id"] or "",
                    tool_name=content["tool_name"],
                    tool_input_dict=content["tool_input_dict"] or {},
                ),
            )
        case "tool_call_result":
            return MessageContent(
                tool_call_result=ToolCall(
                    id=content["id"] or "",
                    tool_name=content["tool_name"] or "",
                    tool_input_dict=content["tool_input_dict"] or {},
                    result=content["result"],
                    error=content["error"],
                ),
            )


def message_standard_to_domain(message: StandardMessage):
    if isinstance(message["content"], str):
        content = [MessageContent(text=message["content"])]
    else:
        content = [_standard_content_to_domain(item) for item in message["content"]]

    return Message(
        role=message["role"] or "user",
        content=content,
    )
