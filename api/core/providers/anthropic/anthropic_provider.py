import json
import logging
from typing import Any, AsyncIterator, Literal

from httpx import Response
from pydantic import BaseModel
from typing_extensions import override

from core.domain.errors import UnpriceableRunError
from core.domain.fields.file import File
from core.domain.fields.internal_reasoning_steps import InternalReasoningStep
from core.domain.llm_usage import LLMUsage
from core.domain.message import MessageDeprecated
from core.domain.models import Model, Provider
from core.domain.models.model_data import FinalModelData
from core.domain.models.utils import get_model_data
from core.domain.tool_call import ToolCallRequestWithID
from core.providers.anthropic.anthropic_domain import (
    AnthropicErrorResponse,
    AnthropicMessage,
    AntToolChoice,
    CompletionChunk,
    CompletionRequest,
    CompletionResponse,
    ContentBlock,
    StopReasonDelta,
    TextContent,
    ThinkingContent,
    ToolUseContent,
    Usage,
)
from core.providers.base.httpx_provider import HTTPXProvider
from core.providers.base.models import RawCompletion, StandardMessage
from core.providers.base.provider_error import (
    FailedGenerationError,
    MaxTokensExceededError,
    ProviderError,
    ProviderInternalError,
    UnknownProviderError,
)
from core.providers.base.provider_options import ProviderOptions
from core.providers.base.streaming_context import ParsedResponse, ToolCallRequestBuffer
from core.providers.base.utils import get_provider_config_env
from core.providers.google.google_provider_domain import (
    native_tool_name_to_internal,
)

DEFAULT_MAX_TOKENS = 8192

ANTHROPIC_VERSION = "2023-06-01"

ANTHROPIC_PDF_BETA = "pdfs-2024-09-25"


class AnthropicConfig(BaseModel):
    provider: Literal[Provider.ANTHROPIC] = Provider.ANTHROPIC
    api_key: str
    url: str = "https://api.anthropic.com/v1/messages"

    def __str__(self):
        return f"AnthropicConfig(url={self.url}, api_key={self.api_key[:4]}****)"


class AnthropicProvider(HTTPXProvider[AnthropicConfig, CompletionResponse]):
    @classmethod
    def _max_tokens(cls, model_data: FinalModelData, requested_max_tokens: int | None) -> int:
        model_max_output_tokens = model_data.max_tokens_data.max_output_tokens
        if not model_max_output_tokens:
            logging.warning(
                "Max tokens not set for Anthropic",
                extra={"model": model_data.model},
            )
            model_max_output_tokens = DEFAULT_MAX_TOKENS
        return min(requested_max_tokens or DEFAULT_MAX_TOKENS, model_max_output_tokens)

    @override
    def _build_request(self, messages: list[MessageDeprecated], options: ProviderOptions, stream: bool) -> BaseModel:
        model_data = get_model_data(options.model)
        # Anthropic requires the max tokens to be set to the max generated tokens for the model
        # https://docs.anthropic.com/en/api/messages#body-max-tokens

        if messages[0].role == MessageDeprecated.Role.SYSTEM:
            system_message = messages[0].content
            messages = messages[1:]
        else:
            system_message = None

        thinking_budget = options.final_reasoning_budget(model_data.reasoning)
        thinking_config = (
            None
            if thinking_budget is None
            else CompletionRequest.Thinking(
                type="enabled",
                budget_tokens=thinking_budget,
            )
        )

        request = CompletionRequest(
            # Anthropic requires at least one message
            # So if we have no messages, we add a user message with a dash
            messages=[AnthropicMessage.from_domain(m) for m in messages]
            if messages
            else [
                AnthropicMessage(role="user", content=[TextContent(text="-")]),
            ],
            model=options.model,
            temperature=options.temperature,
            max_tokens=self._max_tokens(model_data, options.max_tokens) + (thinking_budget or 0),
            stream=stream,
            tool_choice=AntToolChoice.from_domain(options.tool_choice),
            top_p=options.top_p,
            system=system_message,
            thinking=thinking_config,
            # Presence and frequency penalties are not yet supported by Anthropic
        )

        if options.enabled_tools is not None and options.enabled_tools != []:
            request.tools = [CompletionRequest.Tool.from_domain(tool) for tool in options.enabled_tools]

        return request

    @override
    async def _request_headers(self, request: dict[str, Any], url: str, model: Model) -> dict[str, str]:
        return {
            "x-api-key": self._config.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "anthropic-beta": ANTHROPIC_PDF_BETA,
        }

    @override
    def _request_url(self, model: Model, stream: bool) -> str:
        return self._config.url

    @override
    def _response_model_cls(self) -> type[CompletionResponse]:
        return CompletionResponse

    @override
    def _extract_content_str(self, response: CompletionResponse) -> str:
        """Extract the text content from the first content block in the response"""
        if not response.content or len(response.content) == 0:
            raise ProviderInternalError("No content in response")
        if response.stop_reason == "max_tokens":
            raise MaxTokensExceededError(
                msg="Model returned MAX_TOKENS stop reason, the max tokens limit was exceeded.",
                raw_completion=str(response.content),
            )

        for block in response.content:
            if isinstance(block, ContentBlock):
                return block.text

        return ""

    @override
    def _extract_usage(self, response: CompletionResponse) -> LLMUsage | None:
        # Implement if Anthropic provides usage metrics
        return response.usage.to_domain()

    @override
    def _extract_reasoning_steps(self, response: CompletionResponse) -> list[InternalReasoningStep] | None:
        """Extract reasoning steps from thinking content blocks in the response"""
        reasoning_steps = [
            InternalReasoningStep(
                explaination=content_block.thinking,
                # TODO: We could potentially use the signature field for validation
                # but for now we'll just include the thinking text
            )
            for content_block in response.content
            if isinstance(content_block, ThinkingContent)
        ]

        return reasoning_steps if reasoning_steps else None

    @override
    @classmethod
    def required_env_vars(cls) -> list[str]:
        return ["ANTHROPIC_API_KEY"]

    @override
    @classmethod
    def name(cls) -> Provider:
        return Provider.ANTHROPIC

    @override
    @classmethod
    def _default_config(cls, index: int) -> AnthropicConfig:
        return AnthropicConfig(
            api_key=get_provider_config_env("ANTHROPIC_API_KEY", index),
            url=get_provider_config_env("ANTHROPIC_API_URL", index, "https://api.anthropic.com/v1/messages"),
        )

    @override
    def _raw_prompt(self, request_json: dict[str, Any]) -> list[dict[str, Any]]:
        messages = request_json.get("messages", [])
        if "system" in request_json:
            return [{"role": "system", "content": request_json["system"]}, *messages]
        return messages

    async def wrap_sse(self, raw: AsyncIterator[bytes], termination_chars: bytes = b""):
        """Custom SSE wrapper for Anthropic's event stream format"""
        acc = b""
        async for chunk in raw:
            acc += chunk
            lines = acc.split(b"\n")
            include_last = chunk.endswith(b"\n")
            if not include_last:
                acc = lines[-1]
                lines = lines[:-1]
            else:
                acc = b""

            for line in lines:
                if line.startswith(b"data: "):
                    yield line[6:]  # Strip "data: " prefix
                elif line.startswith(b"event: "):
                    continue  # Skip event lines
                elif not line.strip():
                    continue  # Skip
                else:
                    self.logger.error("Unexpected line in SSE stream", extra={"line": line, "acc": acc})

    def _handle_message_delta(self, chunk: CompletionChunk, raw_completion: RawCompletion):
        if chunk.usage:
            if raw_completion.usage:
                # Update only completion tokens as input tokens were set in message_start
                if chunk.usage.output_tokens is not None:
                    raw_completion.usage.completion_token_count = chunk.usage.output_tokens
            else:
                raw_completion.usage = chunk.usage.to_domain()

        if chunk.delta and isinstance(chunk.delta, StopReasonDelta) and chunk.delta.stop_reason:
            raw_completion.finish_reason = chunk.delta.stop_reason
            if chunk.delta.stop_reason == "max_tokens":
                raise MaxTokensExceededError(
                    msg="Model returned MAX_TOKENS stop reason, the max tokens limit was exceeded.",
                    raw_completion=raw_completion.response,
                )

        return ""

    @override
    def _extract_stream_delta(
        self,
        sse_event: bytes,
        raw_completion: RawCompletion,
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer],
    ) -> ParsedResponse:
        try:
            chunk = CompletionChunk.model_validate_json(sse_event)

            match chunk.type:
                case "message_start":
                    return self._handle_message_start(chunk, raw_completion)
                case "message_delta":
                    return ParsedResponse(self._handle_message_delta(chunk, raw_completion))
                case "content_block_start":
                    return self._handle_content_block_start(chunk, tool_call_request_buffer)
                case "content_block_delta":
                    return self._handle_content_block_delta(chunk, tool_call_request_buffer)
                case "ping" | "message_stop" | "content_block_stop":
                    return ParsedResponse("")
                case "error":
                    if chunk.error:
                        raise chunk.error.to_domain(response=None)
                    raise UnknownProviderError("Anthropic error response with no error details")

        except ProviderError as e:
            raise e
        except Exception:
            self.logger.exception(
                "Failed to parse SSE event",
                extra={"event": str(sse_event)},
            )
            return ParsedResponse("")

    def _handle_message_start(self, chunk: CompletionChunk, raw_completion: RawCompletion) -> ParsedResponse:
        """Handle message_start event type."""
        if chunk.message and "usage" in chunk.message:
            usage = Usage.model_validate(chunk.message["usage"])
            raw_completion.usage = usage.to_domain()
        return ParsedResponse("")

    def _handle_content_block_start(
        self,
        chunk: CompletionChunk,
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer],
    ) -> ParsedResponse:
        """Handle content_block_start event type."""
        tool_calls: list[ToolCallRequestWithID] = []
        if chunk.content_block and chunk.content_block.type == "tool_use":
            if chunk.index is None:
                raise FailedGenerationError(
                    f"Missing required fields in content block start, index, id or name: {chunk}",
                )

            tool_call_request_buffer[chunk.index] = ToolCallRequestBuffer(
                id=chunk.content_block.id,
                tool_name=native_tool_name_to_internal(chunk.content_block.name),
                tool_input="",
            )

        # For thinking content blocks, we don't need to buffer anything at start
        # The thinking content will be streamed via content_block_delta events
        return ParsedResponse("", tool_calls=tool_calls)

    def _handle_content_block_delta(
        self,
        chunk: CompletionChunk,
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer],
    ) -> ParsedResponse:
        """Handle content_block_delta event type."""
        tool_calls: list[ToolCallRequestWithID] = []
        reasoning_steps: str | None = None

        if chunk.delta and chunk.delta.type == "input_json_delta":
            if chunk.index not in tool_call_request_buffer:
                raise FailedGenerationError(
                    f"Received content block delta for unknown tool call, index: {chunk.index}  ",
                )

            tool_call_request_buffer[chunk.index].tool_input += chunk.delta.partial_json

            candidate_tool_call = tool_call_request_buffer[chunk.index]

            if candidate_tool_call.id is not None and candidate_tool_call.tool_name is not None:
                try:
                    tool_calls.append(
                        ToolCallRequestWithID(
                            id=candidate_tool_call.id,
                            tool_name=native_tool_name_to_internal(candidate_tool_call.tool_name),
                            tool_input_dict=json.loads(candidate_tool_call.tool_input),
                        ),
                    )
                except json.JSONDecodeError:
                    # That means the tool call is not fully streamed yet
                    pass

        # Handle thinking deltas for reasoning steps
        elif chunk.delta and chunk.delta.type == "thinking_delta":
            reasoning_steps = chunk.delta.thinking

        return ParsedResponse(chunk.extract_delta(), tool_calls=tool_calls, reasoning_steps=reasoning_steps)

    def _compute_prompt_token_count(
        self,
        messages: list[dict[str, Any]],
        model: Model,
    ) -> float:
        # Token count is already included in the usage
        raise UnpriceableRunError("Token counting is not implemented yet for Anthropic")

    def _compute_prompt_image_count(self, messages: list[dict[str, Any]]) -> int:
        # Anthropic includes images in the prompt token count, so we do not need to add those separately
        raise UnpriceableRunError("Token counting is not implemented yet for Anthropic")

    async def _compute_prompt_audio_token_count(self, messages: list[dict[str, Any]]) -> tuple[float, float | None]:
        raise UnpriceableRunError("Token counting is not implemented yet for Anthropic")

    @override
    @classmethod
    def standardize_messages(cls, messages: list[dict[str, Any]]) -> list[StandardMessage]:
        def _to_msg(m: dict[str, Any]) -> StandardMessage:
            if m.get("role") == "system":
                return {"role": "assistant", "content": m["content"]}
            return AnthropicMessage.model_validate(m).to_standard()

        return [_to_msg(m) for m in messages]

    @override
    @classmethod
    def requires_downloading_file(cls, file: File, model: Model) -> bool:
        return True

    @override
    def _unknown_error(self, response: Response) -> ProviderError:
        try:
            payload = AnthropicErrorResponse.model_validate_json(response.text)
        except Exception:
            self.logger.exception("failed to parse Anthropic error response", extra={"response": response.text})
            return UnknownProviderError(response.text, response=response)

        if payload.error:
            return payload.error.to_domain(response)
        raise UnknownProviderError("Anthropic error response with no error details", response=response)

    @override
    @classmethod
    def _extract_native_tool_calls(cls, response: CompletionResponse) -> list[ToolCallRequestWithID]:
        return [
            ToolCallRequestWithID(
                id=c.id,
                tool_name=native_tool_name_to_internal(c.name),
                tool_input_dict=c.input,
            )
            for c in response.content
            if isinstance(c, ToolUseContent)
        ]

    @override
    async def _extract_and_log_rate_limits(self, response: Response, options: ProviderOptions):
        await self._log_rate_limit_remaining(
            "requests",
            remaining=response.headers.get("anthropic-ratelimit-requests-remaining"),
            total=response.headers.get("anthropic-ratelimit-requests-limit"),
            options=options,
        )
        await self._log_rate_limit_remaining(
            "tokens",
            remaining=response.headers.get("anthropic-ratelimit-tokens-remaining"),
            total=response.headers.get("anthropic-ratelimit-tokens-limit"),
            options=options,
        )
        await self._log_rate_limit_remaining(
            "input_tokens",
            remaining=response.headers.get("anthropic-ratelimit-input-tokens-remaining"),
            total=response.headers.get("anthropic-ratelimit-input-tokens-limit"),
            options=options,
        )
        await self._log_rate_limit_remaining(
            "output_tokens",
            remaining=response.headers.get("anthropic-ratelimit-output-tokens-remaining"),
            total=response.headers.get("anthropic-ratelimit-output-tokens-limit"),
            options=options,
        )

    @override
    def default_model(self) -> Model:
        return Model.CLAUDE_3_7_SONNET_20250219
