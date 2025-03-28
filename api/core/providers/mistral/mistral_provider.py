import json
from typing import Any, Literal

from httpx import Response
from pydantic import BaseModel, ValidationError
from typing_extensions import override

from core.domain.errors import FailedGenerationError, MaxTokensExceededError, UnknownProviderError
from core.domain.llm_usage import LLMUsage
from core.domain.message import Message
from core.domain.models import Model, Provider
from core.domain.tool_call import ToolCallRequestWithID
from core.providers.base.abstract_provider import RawCompletion
from core.providers.base.httpx_provider import HTTPXProvider, ParsedResponse
from core.providers.base.models import StandardMessage
from core.providers.base.provider_options import ProviderOptions
from core.providers.base.streaming_context import ToolCallRequestBuffer
from core.providers.base.utils import get_provider_config_env
from core.providers.google.google_provider_domain import (
    internal_tool_name_to_native_tool_call,
    native_tool_name_to_internal,
)
from core.utils.json_utils import safe_extract_dict_from_json

from .mistral_domain import (
    CompletionChunk,
    CompletionRequest,
    CompletionResponse,
    DeltaMessage,
    FunctionParameters,
    MistralAIMessage,
    MistralError,
    MistralToolMessage,
    ResponseFormat,
    Tool,
)


class MistralAIConfig(BaseModel):
    provider: Literal[Provider.MISTRAL_AI] = Provider.MISTRAL_AI

    url: str = "https://api.mistral.ai/v1/chat/completions"
    api_key: str

    def __str__(self):
        return f"MistralAIConfig(url={self.url}, api_key={self.api_key[:4]}****)"


MODEL_MAP = {
    Model.MISTRAL_LARGE_2_2407: "mistral-large-2407",
}


class MistralAIProvider(HTTPXProvider[MistralAIConfig, CompletionResponse]):
    @override
    def _build_request(self, messages: list[Message], options: ProviderOptions, stream: bool) -> BaseModel:
        domain_messages: list[MistralAIMessage | MistralToolMessage] = []
        for m in messages:
            if m.tool_call_results:
                domain_messages.extend(MistralToolMessage.from_domain(m))
            else:
                domain_messages.append(MistralAIMessage.from_domain(m))

        request = CompletionRequest(
            messages=domain_messages,
            model=MODEL_MAP.get(options.model, options.model),
            temperature=options.temperature,
            # TODO[max-tokens]: Set the max token from the context data
            max_tokens=options.max_tokens,
            stream=stream,
        )

        if options.enabled_tools is not None and options.enabled_tools != []:
            # Can't use json_object with tools
            # 400 from Mistral AI when doing so: "Cannot use json response type with tools","type":"invalid_request_error"
            request.response_format = ResponseFormat(type="text")
            request.tools = [
                Tool(
                    type="function",
                    function=FunctionParameters(
                        name=internal_tool_name_to_native_tool_call(tool.name),
                        description=tool.description,
                        parameters=tool.input_schema,
                    ),
                )
                for tool in options.enabled_tools
            ]

        return request

    @classmethod
    def mistral_message_or_tool_message(cls, messag_dict: dict[str, Any]) -> MistralAIMessage | MistralToolMessage:
        try:
            return MistralToolMessage.model_validate(messag_dict)
        except ValidationError:
            return MistralAIMessage.model_validate(messag_dict)

    @classmethod
    def standardize_messages(cls, messages: list[dict[str, Any]]) -> list[StandardMessage]:
        result: list[StandardMessage] = []
        current_tool_messages: list[MistralToolMessage] = []

        for message in (cls.mistral_message_or_tool_message(m) for m in messages):
            if isinstance(message, MistralToolMessage):
                current_tool_messages.append(message)
            else:
                # Process any accumulated tool messages before adding the non-tool message
                if current_tool_messages:
                    if tool_message := MistralToolMessage.to_standard(current_tool_messages):
                        result.append(tool_message)
                    current_tool_messages = []

                # Add the non-tool message
                result.append(message.to_standard())

        # Handle any remaining tool messages at the end
        if current_tool_messages:
            if tool_message := MistralToolMessage.to_standard(current_tool_messages):
                result.append(tool_message)

        return result

    @override
    async def _request_headers(self, request: dict[str, Any], url: str, model: Model) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
        }

    @override
    def _request_url(self, model: Model, stream: bool) -> str:
        return self.config.url

    @override
    def _response_model_cls(self) -> type[CompletionResponse]:
        return CompletionResponse

    @override
    def _extract_content_str(self, response: CompletionResponse) -> str:
        # TODO: handle finish reasons
        for choice in response.choices:
            if choice.finish_reason == "length":
                raise MaxTokensExceededError(
                    msg="Model returned a response with a LENGTH finish reason, meaning the maximum number of tokens was exceeded.",
                    raw_completion=str(response.choices),
                )
        message = response.choices[0].message
        content = message.content
        if content is None and not message.tool_calls:
            # We only raise an error if there are no tool calls
            raise FailedGenerationError(
                msg="Model did not generate a response content",
                capture=True,
            )

        return content or ""

    @override
    def _invalid_json_error(self, response: Response, exception: Exception, content_str: str):
        # Sometimes MistralAI returns a non-JSON response that contains an excuse
        if "sorry" in content_str.lower():
            return FailedGenerationError(
                msg=f"Model refused to generate a response: {content_str}",
                response=response,
            )
        return super()._invalid_json_error(response, exception=exception, content_str=content_str)

    @override
    def _extract_usage(self, response: CompletionResponse) -> LLMUsage | None:
        return response.usage.to_domain()

    @override
    def _unknown_error(self, response: Response):
        try:
            payload = MistralError.model_validate_json(response.text)
        except Exception:
            self.logger.exception("failed to parse MistralAI error response", extra={"response": response.text})
            return super()._unknown_error(response)

        if payload.type == "invalid_request_error":
            if payload.message and "too large for model" in payload.message:
                return MaxTokensExceededError(msg=payload.message, response=response, store_task_run=False)
        elif payload.type == "context_length_exceeded":
            # Here the task run is stored because the error might
            # have occurred during the generation
            return MaxTokensExceededError(
                msg=payload.message or "Context length exceeded",
                response=response,
            )

        return UnknownProviderError(payload.message, response=response)

    @override
    @classmethod
    def required_env_vars(cls) -> list[str]:
        return ["MISTRAL_API_KEY"]

    @override
    @classmethod
    def name(cls) -> Provider:
        return Provider.MISTRAL_AI

    @override
    @classmethod
    def _default_config(cls, index: int):
        return MistralAIConfig(
            api_key=get_provider_config_env("MISTRAL_API_KEY", index),
            url=get_provider_config_env("MISTRAL_API_URL", index, "https://api.mistral.ai/v1/chat/completions"),
        )

    @override
    def default_model(self) -> Model:
        return Model.PIXTRAL_12B_2409

    def _extra_stream_delta_tool_calls(
        self,
        delta: DeltaMessage,
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer],
    ) -> list[ToolCallRequestWithID]:
        tool_calls: list[ToolCallRequestWithID] = []
        for tool_call in delta.tool_calls or []:
            if tool_call.index is None:
                raise FailedGenerationError(
                    msg=f"Model returned a tool call with no index: {tool_call}",
                    capture=True,
                )
            if tool_call.index not in tool_call_request_buffer:
                tool_call_request_buffer[tool_call.index] = ToolCallRequestBuffer(
                    id=tool_call.id,
                    tool_name=native_tool_name_to_internal(tool_call.function.name)
                    if tool_call.function.name
                    else None,
                    tool_input=json.dumps(tool_call.function.arguments)
                    if isinstance(tool_call.function.arguments, dict)
                    else tool_call.function.arguments,
                )
            else:
                arg_delta = (
                    json.dumps(tool_call.function.arguments)
                    if isinstance(tool_call.function.arguments, dict)
                    else tool_call.function.arguments
                )
                tool_call_request_buffer[tool_call.index].tool_input += arg_delta

            candidate_tool_call = tool_call_request_buffer[tool_call.index]
            if (
                candidate_tool_call.id is not None
                and candidate_tool_call.tool_name is not None
                and candidate_tool_call.tool_input != ""
            ):
                try:
                    tool_calls.append(
                        ToolCallRequestWithID(
                            id=candidate_tool_call.id,
                            tool_name=native_tool_name_to_internal(candidate_tool_call.tool_name),
                            tool_input_dict=json.loads(candidate_tool_call.tool_input),
                        ),
                    )
                except json.JSONDecodeError:
                    # That means the tool call was not finalized
                    pass

        return tool_calls

    @override
    def _extract_stream_delta(
        self,
        sse_event: bytes,
        raw_completion: RawCompletion,
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer],
    ):
        if sse_event == b"[DONE]":
            return ParsedResponse("")
        raw = CompletionChunk.model_validate_json(sse_event)
        if raw.choices:
            for choice in raw.choices:
                if choice.finish_reason == "length":
                    raise MaxTokensExceededError(
                        msg="Model returned a response with a LENGTH finish reason, meaning the maximum number of tokens was exceeded.",
                        raw_completion=str(raw.choices),
                    )
        if raw.usage:
            raw_completion.usage = raw.usage.to_domain()
        if raw.choices and raw.choices[0].delta:
            tool_calls = self._extra_stream_delta_tool_calls(raw.choices[0].delta, tool_call_request_buffer)

            return ParsedResponse(raw.choices[0].delta.content or "", tool_calls=tool_calls)

        return ParsedResponse("")

    def _compute_prompt_token_count(
        self,
        messages: list[dict[str, Any]],
        model: Model,
    ) -> float:
        # For now, we just estimate tokens by counting the number of characters the same way OpenAI does
        # this is not super accurate -> https://github.com/mistralai/mistral-common/blob/main/src/mistral_common/tokens/tokenizers/tekken.py
        # and https://docs.mistral.ai/guides/tokenization/
        # But since we should get the usage from the requests, there is not really a need to be accurate
        num_tokens = 0

        for message in messages:
            domain_message = MistralAIProvider.mistral_message_or_tool_message(message)
            num_tokens += domain_message.token_count(model)

        return num_tokens

    def _compute_prompt_image_count(
        self,
        messages: list[dict[str, Any]],
    ) -> int:
        # MistralAI includes image usage in the prompt token count, so we do not need to add those separately
        return 0

    @override
    async def _compute_prompt_audio_token_count(
        self,
        messages: list[dict[str, Any]],
    ):
        return 0, None

    @classmethod
    def _extract_native_tool_calls(cls, response: CompletionResponse) -> list[ToolCallRequestWithID]:
        choice = response.choices[0]

        tool_calls: list[ToolCallRequestWithID] = []

        for tool_call in choice.message.tool_calls or []:
            args = safe_extract_dict_from_json(tool_call.function.arguments)
            if not args:
                raise FailedGenerationError(
                    msg=f"Model returned a tool call with unparseable arguments: {tool_call.function.arguments}",
                    capture=True,
                )
            tool_calls.append(
                ToolCallRequestWithID(
                    id=tool_call.id or "",
                    tool_name=native_tool_name_to_internal(tool_call.function.name),
                    tool_input_dict=args,
                ),
            )

        return tool_calls

    async def _extract_and_log_rate_limits(self, response: Response, model: Model):
        # Mistral also has a per second request rate limit
        # But it does not seem to be exposed
        # https://admin.mistral.ai/plateforme/limits

        await self._log_rate_limit_remaining(
            "tokens",
            remaining=response.headers.get("x-ratelimitbysize-remaining-minute"),
            total=response.headers.get("x-ratelimitbysize-limit-minute"),
            model=model,
        )

        await self._log_rate_limit_remaining(
            "tokens_by_month",
            remaining=response.headers.get("x-ratelimitbysize-remaining-month"),
            total=response.headers.get("x-ratelimitbysize-limit-month"),
            model=model,
        )
