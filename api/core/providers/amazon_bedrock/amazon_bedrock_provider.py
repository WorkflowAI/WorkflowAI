import json
import logging
import re
from typing import Any, AsyncIterator

import httpx
from pydantic import BaseModel
from typing_extensions import override

from core.domain.errors import (
    MaxTokensExceededError,
    ModelDoesNotSupportMode,
    ProviderBadRequestError,
    ProviderInternalError,
    UnknownProviderError,
)
from core.domain.llm_usage import LLMUsage
from core.domain.message import Message
from core.domain.models import Model, Provider
from core.domain.tool import Tool
from core.domain.tool_call import ToolCallRequestWithID
from core.providers.amazon_bedrock.amazon_bedrock_auth import get_auth_headers
from core.providers.amazon_bedrock.amazon_bedrock_config import AmazonBedrockConfig
from core.providers.amazon_bedrock.amazon_bedrock_domain import (
    AmazonBedrockMessage,
    AmazonBedrockSystemMessage,
    BedrockError,
    BedrockTool,
    BedrockToolConfig,
    BedrockToolInputSchema,
    BedrockToolSpec,
    CompletionRequest,
    CompletionResponse,
    StreamedResponse,
    message_or_system,
)
from core.providers.base.abstract_provider import RawCompletion
from core.providers.base.httpx_provider import HTTPXProvider, ParsedResponse
from core.providers.base.models import StandardMessage
from core.providers.base.provider_options import ProviderOptions
from core.providers.base.streaming_context import ToolCallRequestBuffer
from core.providers.google.google_provider_domain import (
    internal_tool_name_to_native_tool_call,
    native_tool_name_to_internal,
)
from core.runners.workflowai.utils import FileWithKeyPath

logger = logging.getLogger(__name__)


# The models below do not support streaming when tools are enabled
_NON_STREAMING_WITH_TOOLS_MODELS = {
    Model.MISTRAL_LARGE_2_2407,
}


class AmazonBedrockProvider(HTTPXProvider[AmazonBedrockConfig, CompletionResponse]):
    @override
    def _build_request(self, messages: list[Message], options: ProviderOptions, stream: bool) -> BaseModel:
        system_message: AmazonBedrockSystemMessage | None = None
        user_messages: list[AmazonBedrockMessage] = []

        for message in messages:
            if message.role == Message.Role.USER:
                user_messages.append(AmazonBedrockMessage.from_domain(message))
            if message.role == Message.Role.ASSISTANT:
                user_messages.append(AmazonBedrockMessage.from_domain(message))
            if message.role == Message.Role.SYSTEM:
                if system_message is not None:
                    logger.warning(
                        "Only one system message is allowed in Amazon Bedrock",
                        extra={
                            "system_message": system_message.text,
                            "new_system_message": message.content,
                        },
                    )
                    system_message.text += message.content
                system_message = AmazonBedrockSystemMessage.from_domain(message)
        request = CompletionRequest(
            system=[system_message] if system_message else [],
            messages=user_messages,
            inferenceConfig=CompletionRequest.InferenceConfig(
                temperature=options.temperature,
                # TODO[max_tokens]: Add max tokens from model data when we have e2e tests
                maxTokens=options.max_tokens,
            ),
        )

        if options.enabled_tools is not None and options.enabled_tools != []:
            request.toolConfig = BedrockToolConfig(
                tools=[
                    BedrockTool(
                        toolSpec=BedrockToolSpec(
                            name=internal_tool_name_to_native_tool_call(tool.name),
                            # Bedrock requires a description to be at least 1 character
                            description=tool.description if len(tool.description) > 1 else None,
                            inputSchema=BedrockToolInputSchema(json=tool.input_schema),
                        ),
                    )
                    for tool in options.enabled_tools
                ],
            )

        return request

    @classmethod
    @override
    def requires_downloading_file(cls, file: FileWithKeyPath, model: Model) -> bool:
        return True

    def _raw_prompt(self, request_json: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract the raw prompt from the request JSON"""
        return request_json["system"] + request_json["messages"]

    @override
    async def _request_headers(self, request: dict[str, Any], url: str, model: Model) -> dict[str, str]:
        return get_auth_headers(
            method="POST",
            url=url,
            headers=httpx.Headers(),
            aws_access_key=self.config.aws_bedrock_access_key,
            aws_secret_key=self.config.aws_bedrock_secret_key,
            aws_session_token=None,
            region=self.config.region_for_model(model),
            data=json.dumps(request),
        )

    @override
    def _request_url(self, model: Model, stream: bool) -> str:
        suffix = "converse-stream" if stream else "converse"
        region = self.config.region_for_model(model)
        url_model = self.config.id_for_model(model)

        return f"https://bedrock-runtime.{region}.amazonaws.com/model/{url_model}/{suffix}"

    @override
    def _response_model_cls(self) -> type[CompletionResponse]:
        return CompletionResponse

    @override
    def _extract_content_str(self, response: CompletionResponse) -> str:
        try:
            content = response.output.message.content[0]
            content_str = content.text
        except IndexError as e:
            self.logger.warning("Empty content found in response", extra={"response": response.model_dump()})
            raise e
        if not content_str:
            if not content.toolUse:
                self.logger.warning("Empty content found in response", extra={"response": response.model_dump()})
            return ""
        return content_str

    @override
    def _extract_usage(self, response: CompletionResponse) -> LLMUsage | None:
        return response.usage.to_domain()

    @override
    @classmethod
    def required_env_vars(cls) -> list[str]:
        return ["AWS_BEDROCK_ACCESS_KEY", "AWS_BEDROCK_SECRET_KEY"]

    @override
    @classmethod
    def name(cls) -> Provider:
        return Provider.AMAZON_BEDROCK

    @override
    @classmethod
    def _default_config(cls, index: int) -> AmazonBedrockConfig:
        return AmazonBedrockConfig.from_env(index)

    @override
    def default_model(self) -> Model:
        return Model.CLAUDE_3_5_SONNET_20240620

    def _raise_for_message_if_needed(self, raw: str, response: httpx.Response | None = None):
        try:
            bedrock_error = BedrockError.model_validate_json(raw)
        except Exception:
            logger.warning("Failed to validate Bedrock error", extra={"raw": raw}, exc_info=True)
            return

        if not bedrock_error.message:
            return

        lower_msg = bedrock_error.message.lower()

        capture: bool | None = None
        match lower_msg:
            case lower_msg if "input is too long for requested model" in lower_msg or re.search(
                r"too large for model with \d+ maximum context length",
                lower_msg,
            ):
                error_cls = MaxTokensExceededError

            case lower_msg if "bedrock is unable to process your request" in lower_msg:
                error_cls = ProviderInternalError
            case lower_msg if "unexpected error" in lower_msg:
                error_cls = ProviderInternalError
            case lower_msg if "image exceeds max pixels allowed" in lower_msg:
                error_cls = ProviderBadRequestError
            case lower_msg if "provided image does not match the specified image format" in lower_msg:
                error_cls = ProviderBadRequestError
                # Capturing for now, this could happen if we do not properly detect the image format
                capture = True
            case lower_msg if "too many images and documents" in lower_msg:
                error_cls = ProviderBadRequestError
            case lower_msg if re.search(r"model does( not|n't) support tool use", lower_msg):
                error_cls = ModelDoesNotSupportMode
                capture = True
            case _:
                return
        prefix = "The model returned the following errors: "
        raise error_cls(msg=bedrock_error.message.removeprefix(prefix), response=response, capture=capture)

    async def wrap_sse(self, raw: AsyncIterator[bytes], termination_chars: bytes = b""):
        from botocore.eventstream import EventStreamBuffer  # pyright: ignore [reportMissingTypeStubs]

        event_stream_buffer = EventStreamBuffer()
        async for chunk in raw:
            event_stream_buffer.add_data(chunk)  # pyright: ignore [reportUnknownMemberType]
            for event in event_stream_buffer:
                if header := event.headers.get(":exception-type", None):  # pyright: ignore [reportUnknownMemberType, reportUnknownVariableType]
                    raw_msg = event.payload.decode("utf-8")
                    self._raise_for_message_if_needed(raw_msg)
                    raise UnknownProviderError(msg=raw_msg, extra={"header": header})
                yield event.payload

    @override
    def _extract_stream_delta(
        self,
        sse_event: bytes,
        raw_completion: RawCompletion,
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer],
    ) -> ParsedResponse:
        raw = StreamedResponse.model_validate_json(sse_event)
        completion_text = raw.delta.text if (raw.delta and raw.delta.text) else ""

        if raw.usage:
            raw_completion.usage = raw.usage.to_domain()

        if raw.start and raw.start.toolUse:
            if raw.contentBlockIndex is None:
                raise ValueError("Can't parse tool call input without a content block index")
            self._handle_tool_start(raw.start.toolUse, raw.contentBlockIndex, tool_call_request_buffer)

        tool_calls: list[ToolCallRequestWithID] = []
        if raw.delta and raw.delta.toolUse:
            if raw.contentBlockIndex is None:
                raise ValueError("Can't parse tool call input without a content block index")
            tool_calls = self._handle_tool_input(raw.delta.toolUse, raw.contentBlockIndex, tool_call_request_buffer)

        return ParsedResponse(completion_text, tool_calls=tool_calls)

    def _handle_tool_start(
        self,
        tool_use: StreamedResponse.Start.ToolUse,
        content_block_index: int,
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer],
    ) -> None:
        tool_call_request_buffer[content_block_index] = ToolCallRequestBuffer(
            id=tool_use.toolUseId,
            tool_name=tool_use.name,
            tool_input="",
        )

    def _handle_tool_input(
        self,
        tool_use: StreamedResponse.Delta.ToolUseBlockDelta,
        content_block_index: int,
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer],
    ) -> list[ToolCallRequestWithID]:
        if content_block_index not in tool_call_request_buffer:
            raise ValueError(f"Can't find tool call request buffer for content block index {content_block_index}")
        tool_call_request_buffer[content_block_index].tool_input += tool_use.input
        candidate_tool_call = tool_call_request_buffer[content_block_index]
        tool_calls: list[ToolCallRequestWithID] = []
        if candidate_tool_call.id and candidate_tool_call.tool_name:
            try:
                tool_input_dict = json.loads(candidate_tool_call.tool_input)
                tool_calls.append(
                    ToolCallRequestWithID(
                        id=candidate_tool_call.id,
                        tool_name=native_tool_name_to_internal(candidate_tool_call.tool_name),
                        tool_input_dict=tool_input_dict,
                    ),
                )
            except json.JSONDecodeError:
                # That means the tool call is not fully streamed yet
                pass
        return tool_calls

    def supports_model(self, model: Model) -> bool:
        try:
            # Can vary based on the models declared in 'AWS_BEDROCK_MODEL_REGION_MAP
            if model not in self.config.available_model_x_region_map.keys():
                return False

            return True
        except ValueError:
            return False

    @override
    def _unknown_error_message(self, response: httpx.Response):
        return response.text

    def _handle_error_status_code(self, response: httpx.Response):
        self._raise_for_message_if_needed(response.text, response)

        super()._handle_error_status_code(response)

    def _compute_prompt_token_count(
        self,
        messages: list[dict[str, Any]],
        model: Model,
    ) -> float:
        # TODO: Double check the truthfulness of those boilerplates token counts
        # Those are based on OpenAI's ones
        # See: https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
        BOILERPLATE_TOKENS: int = 3
        PER_MESSAGE_BOILERPLATE_TOKENS: int = 4

        token_count: int = BOILERPLATE_TOKENS

        for message in messages:
            token_count += PER_MESSAGE_BOILERPLATE_TOKENS

            domain_message = message_or_system(message)
            message_token_count = domain_message.token_count(model)
            token_count += message_token_count

        return token_count

    def _compute_prompt_image_count(
        self,
        messages: list[dict[str, Any]],
    ) -> int:
        # Amazon Bedrock includes image usage in the prompt token count, so we do not need to add those separately
        return 0

    @override
    async def _compute_prompt_audio_token_count(
        self,
        messages: list[dict[str, Any]],
    ):
        return 0, None

    @override
    @classmethod
    def standardize_messages(cls, messages: list[dict[str, Any]]) -> list[StandardMessage]:
        return [message_or_system(message).to_standard() for message in messages]

    @classmethod
    def _extract_native_tool_calls(cls, response: CompletionResponse) -> list[ToolCallRequestWithID]:
        choice = response.output.message

        tool_calls: list[ToolCallRequestWithID] = [
            ToolCallRequestWithID(
                id=content.toolUse.toolUseId,
                tool_name=native_tool_name_to_internal(content.toolUse.name),
                tool_input_dict=content.toolUse.input,
            )
            for content in choice.content or []
            if content.toolUse
        ]
        return tool_calls

    def is_streamable(self, model: Model, enabled_tools: list[Tool] | None = None) -> bool:
        if enabled_tools and model in _NON_STREAMING_WITH_TOOLS_MODELS:
            return False
        return True

    # Bedrock does not expose rate limits
