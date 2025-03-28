import copy
import json
from contextvars import ContextVar
from json import JSONDecodeError
from typing import Any, AsyncIterator, Literal, override

from httpx import Response
from pydantic import BaseModel, ValidationError

from core.domain.errors import (
    FailedGenerationError,
    InvalidGenerationError,
    MaxTokensExceededError,
    UnknownProviderError,
)
from core.domain.fields.internal_reasoning_steps import InternalReasoningStep
from core.domain.llm_usage import LLMUsage
from core.domain.message import Message
from core.domain.models import Model, Provider
from core.domain.models.model_data import ModelData
from core.domain.models.utils import get_model_data
from core.domain.structured_output import StructuredOutput
from core.domain.tool_call import ToolCallRequestWithID
from core.providers.base.httpx_provider import HTTPXProvider, ParsedResponse
from core.providers.base.models import RawCompletion, StandardMessage
from core.providers.base.provider_options import ProviderOptions
from core.providers.base.streaming_context import ToolCallRequestBuffer
from core.providers.base.utils import get_provider_config_env
from core.providers.fireworks.fireworks_domain import (
    CompletionRequest,
    CompletionResponse,
    FireworksAIError,
    FireworksMessage,
    FireworksTool,
    FireworksToolFunction,
    FireworksToolMessage,
    JSONResponseFormat,
    StreamedResponse,
)
from core.providers.google.google_provider_domain import (
    internal_tool_name_to_native_tool_call,
    native_tool_name_to_internal,
)
from core.providers.openai.openai_domain import parse_tool_call_or_raise
from core.runners.workflowai.templates import TemplateName
from core.runners.workflowai.utils import FileWithKeyPath
from core.utils.redis_cache import redis_cached

_NAME_OVERRIDE_MAP = {
    Model.LLAMA_3_3_70B: "accounts/fireworks/models/llama-v3p3-70b-instruct",
    Model.LLAMA_3_2_3B_PREVIEW: "accounts/fireworks/models/llama-v3p2-3b-instruct",
    Model.LLAMA_3_2_3B: "accounts/fireworks/models/llama-v3p2-3b-instruct",
    Model.LLAMA_3_2_11B_VISION: "accounts/fireworks/models/llama-v3p2-11b-vision-instruct",
    Model.LLAMA_3_2_90B_VISION_PREVIEW: "accounts/fireworks/models/llama-v3p2-90b-vision-instruct",
    Model.LLAMA_3_1_8B: "accounts/fireworks/models/llama-v3p1-8b-instruct",
    Model.QWEN_QWQ_32B_PREVIEW: "accounts/fireworks/models/qwen-qwq-32b-preview",
    Model.MIXTRAL_8X7B_32768: "accounts/fireworks/models/mixtral-8x7b-instruct",
    Model.LLAMA3_70B_8192: "accounts/fireworks/models/llama-v3-70b-instruct",
    Model.LLAMA3_8B_8192: "accounts/fireworks/models/llama-v3-8b-instruct",
    Model.LLAMA_3_1_8B: "accounts/fireworks/models/llama-v3p1-8b-instruct",
    Model.LLAMA_3_1_70B: "accounts/fireworks/models/llama-v3p1-70b-instruct",
    Model.LLAMA_3_1_405B: "accounts/fireworks/models/llama-v3p1-405b-instruct",
    Model.DEEPSEEK_V3_2412: "accounts/fireworks/models/deepseek-v3",
    Model.DEEPSEEK_V3_0324: "accounts/fireworks/models/deepseek-v3-0324",
    Model.DEEPSEEK_R1_2501: "accounts/fireworks/models/deepseek-r1",
    Model.DEEPSEEK_R1_2501_BASIC: "accounts/fireworks/models/deepseek-r1-basic",
}


class FireworksConfig(BaseModel):
    provider: Literal[Provider.FIREWORKS] = Provider.FIREWORKS

    url: str = "https://api.fireworks.ai/inference/v1/chat/completions"
    api_key: str

    def __str__(self):
        return f"FireworksConfig(url={self.url}, api_key={self.api_key[:4]}****)"


class FireworksAIProvider(HTTPXProvider[FireworksConfig, CompletionResponse]):
    # A context var to track if we are in a thinking tag
    _thinking_tag_context = ContextVar[bool | None]("_thinking_tag_context", default=None)
    _models_not_supporting_structured_gen = {Model.DEEPSEEK_R1_2501}

    def _response_format(self, options: ProviderOptions, is_preview_model: bool):
        schema = copy.deepcopy(options.output_schema)
        return JSONResponseFormat(json_schema=schema)

    def model_str(self, model: Model) -> str:
        return _NAME_OVERRIDE_MAP.get(model, model.value)

    @override
    def _build_request(self, messages: list[Message], options: ProviderOptions, stream: bool) -> BaseModel:
        # Clearing the buffer before building the request
        domain_messages: list[FireworksMessage | FireworksToolMessage] = []
        for m in messages:
            if m.tool_call_results:
                domain_messages.extend(FireworksToolMessage.from_domain(m))
            else:
                domain_messages.append(FireworksMessage.from_domain(m))

        tool_call_activated = options.enabled_tools is not None and options.enabled_tools != []

        data = get_model_data(options.model)

        request = CompletionRequest(
            messages=domain_messages,
            model=self.model_str(Model(options.model)),
            temperature=options.temperature,
            # Setting the max generation tokens to the max possible value
            # Setting the context length exceeded behavior to truncate will ensure that no error
            # is raised when prompt token + max_tokens > model context window
            #
            # We fallback to the full context window if no max_output_tokens is set since some models do not have
            # an explicit generation limit
            max_tokens=options.max_tokens or data.max_tokens_data.max_output_tokens or data.max_tokens_data.max_tokens,
            context_length_exceeded_behavior="truncate",
            stream=stream,
            response_format=self._response_format(options, False)
            if options.model not in self._models_not_supporting_structured_gen and not tool_call_activated
            else None,
        )

        # Add native tool calls if enabled
        if tool_call_activated:
            request.tools = [
                FireworksTool(
                    type="function",
                    function=FireworksToolFunction(
                        name=internal_tool_name_to_native_tool_call(tool.name),
                        description=tool.description,
                        parameters=tool.input_schema,
                    ),
                )
                for tool in options.enabled_tools or []
            ]
        return request

    @override
    def _response_model_cls(self) -> type[CompletionResponse]:
        return CompletionResponse

    @classmethod
    def fireworks_message_or_tool_message(cls, messag_dict: dict[str, Any]) -> FireworksToolMessage | FireworksMessage:
        try:
            return FireworksToolMessage.model_validate(messag_dict)
        except ValidationError:
            return FireworksMessage.model_validate(messag_dict)

    @classmethod
    def standardize_messages(cls, messages: list[dict[str, Any]]) -> list[StandardMessage]:
        result: list[StandardMessage] = []
        current_tool_messages: list[FireworksToolMessage] = []

        for message in (cls.fireworks_message_or_tool_message(m) for m in messages):
            if isinstance(message, FireworksToolMessage):
                current_tool_messages.append(message)
            else:
                # Process any accumulated tool messages before adding the non-tool message
                if current_tool_messages:
                    if tool_message := FireworksToolMessage.to_standard(current_tool_messages):
                        result.append(tool_message)
                    current_tool_messages = []

                # Add the non-tool message
                result.append(message.to_standard())

        # Handle any remaining tool messages at the end
        if current_tool_messages:
            if tool_message := FireworksToolMessage.to_standard(current_tool_messages):
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
    def _extract_reasoning_steps(self, response: CompletionResponse) -> list[InternalReasoningStep] | None:
        response_text = response.choices[0].message.content
        if response_text and "<think>" in response_text and isinstance(response_text, str):
            if "</think>" in response_text:
                return [
                    InternalReasoningStep(
                        explaination=response_text[
                            response_text.index("<think>") + len("<think>") : response_text.index("</think>")
                        ],
                    ),
                ]

            raise InvalidGenerationError(
                msg="Model returned a response without a closing THINK tag, meaning the model failed to complete generation.",
                raw_completion=str(response.choices),
            )
        return None

    @override
    def _extract_content_str(self, response: CompletionResponse) -> str:  # noqa: C901
        message = response.choices[0].message
        content = message.content
        for choice in response.choices:
            if choice.finish_reason == "length":
                raise MaxTokensExceededError(
                    msg="Model returned a response with a LENGTH finish reason, meaning the maximum number of tokens was exceeded.",
                    raw_completion=str(response.choices),
                )

        if content is None:
            if not message.tool_calls:
                raise FailedGenerationError(
                    msg="Model did not generate a response content",
                    capture=True,
                )
            return ""

        if isinstance(content, str):
            if "<think>" in content:
                if "</think>" in content:
                    return content[content.index("</think>") + len("</think>") :]
                raise InvalidGenerationError(
                    msg="Model returned a response without a closing THINK tag, meaning the model failed to complete generation.",
                    raw_completion=str(response.choices),
                )
            return content
        if len(content) > 1:
            self.logger.warning("Multiple content items found in response", extra={"response": response.model_dump()})
        for item in content:
            if item.type == "text":
                return item.text
        self.logger.warning("No content found in response", extra={"response": response.model_dump()})
        return ""

    @override
    def _invalid_json_error(self, response: Response, exception: Exception, content_str: str):
        # TODO: check if this is needed
        if "sorry" in content_str.lower():
            return FailedGenerationError(
                msg=f"Model refused to generate a response: {content_str}",
                response=response,
            )
        return super()._invalid_json_error(response, exception, content_str)

    @override
    def _extract_usage(self, response: CompletionResponse) -> LLMUsage | None:
        return response.usage.to_domain()

    def _invalid_request_error(self, payload: FireworksAIError, response: Response):
        if not payload.error.message:
            return None
        lower_msg = payload.error.message.lower()
        if "prompt is too long" in lower_msg:
            return MaxTokensExceededError(
                msg=payload.error.message,
                response=response,
                store_task_run=False,
            )
        return False

    @override
    def _unknown_error(self, response: Response):
        try:
            payload = FireworksAIError.model_validate_json(response.text)
        except Exception:
            self.logger.exception("failed to parse Fireworks AI error response", extra={"response": response.text})
            return UnknownProviderError(
                msg=f"Unknown error status {response.status_code}",
                response=response,
            )

        store_task_run: bool | None = None
        error_cls = UnknownProviderError
        match payload.error.code:
            case "string_above_max_length" | "context_length_exceeded":
                # In this case we do not want to store the task run because it is a request error that
                # does not incur cost
                # We still bin with max tokens exceeded since it is related
                error_cls = MaxTokensExceededError
                store_task_run = False

            case None:
                if err := self._invalid_request_error(payload, response):
                    return err

            case _:
                pass

        return error_cls(
            msg=payload.error.message or "Unknown error",
            response=response,
            store_task_run=store_task_run,
        )

    @override
    def _unknown_error_message(self, response: Response):
        try:
            payload = FireworksAIError.model_validate_json(response.text)
            return payload.error.message or "Unknown error"
        except Exception:
            self.logger.exception("failed to parse Fireworks AI error response", extra={"response": response.text})
            return super()._unknown_error_message(response)

    @override
    @classmethod
    def requires_downloading_file(cls, file: FileWithKeyPath, model: Model) -> bool:
        return True

    @override
    @classmethod
    def required_env_vars(cls) -> list[str]:
        return ["FIREWORKS_API_KEY"]

    @override
    @classmethod
    def name(cls) -> Provider:
        return Provider.FIREWORKS

    @override
    @classmethod
    def _default_config(cls, index: int) -> FireworksConfig:
        return FireworksConfig(
            api_key=get_provider_config_env("FIREWORKS_API_KEY", index),
            url=get_provider_config_env(
                "FIREWORKS_URL",
                index,
                "https://api.fireworks.ai/inference/v1/chat/completions",
            ),
        )

    @override
    def default_model(self) -> Model:
        return Model.LLAMA_3_3_70B

    @property
    def is_structured_generation_supported(self) -> bool:
        return True

    @override
    async def wrap_sse(self, raw: AsyncIterator[bytes], termination_chars: bytes = b"\n\n"):
        self._thinking_tag_context.set(None)

        # Call parent's wrap_sse implementation
        async for chunk in super().wrap_sse(raw, termination_chars):
            yield chunk

    def _check_for_closing_thinking_tag(self, content: str, tool_calls: list[ToolCallRequestWithID] | None):
        index = content.find("</think>")
        if index == -1:
            return ParsedResponse("", content, tool_calls=tool_calls)

        self._thinking_tag_context.set(False)
        return ParsedResponse(content[index + len("</think>") :], content[:index], tool_calls=tool_calls)

    def _check_for_thinking_tag(self, content: str, tool_calls: list[ToolCallRequestWithID] | None):
        # We only consider full tags in streams for now
        index = content.find("<think>")
        if index == -1:
            return ParsedResponse(content, tool_calls=tool_calls)

        self._thinking_tag_context.set(True)
        thinking_content = content[index + len("<think>") :]
        return self._check_for_closing_thinking_tag(thinking_content, tool_calls)

    def _process_tool_call(
        self,
        tool_call: Any,
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer],
    ) -> ToolCallRequestWithID | None:
        # Check if a tool call at that index is already in the buffer
        if tool_call.index not in tool_call_request_buffer:
            tool_call_request_buffer[tool_call.index] = ToolCallRequestBuffer()

        buffered_tool_call = tool_call_request_buffer[tool_call.index]

        if tool_call.id and not buffered_tool_call.id:
            buffered_tool_call.id = tool_call.id

        if tool_call.function.name and not buffered_tool_call.tool_name:
            buffered_tool_call.tool_name = tool_call.function.name

        if tool_call.function.arguments:
            buffered_tool_call.tool_input += tool_call.function.arguments

        if buffered_tool_call.id and buffered_tool_call.tool_name and buffered_tool_call.tool_input:
            try:
                tool_input_dict = json.loads(buffered_tool_call.tool_input)
            except JSONDecodeError:
                # That means the tool call is not full streamed yet
                return None

            return ToolCallRequestWithID(
                id=buffered_tool_call.id,
                tool_name=native_tool_name_to_internal(buffered_tool_call.tool_name),
                tool_input_dict=tool_input_dict,
            )
        return None

    def _process_tool_calls(
        self,
        delta_tool_calls: list[Any] | None,
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer],
    ) -> list[ToolCallRequestWithID]:
        if not delta_tool_calls:
            return []

        return [
            call
            for tool_call in delta_tool_calls
            if (call := self._process_tool_call(tool_call, tool_call_request_buffer))
        ]

    def _handle_thinking_context(
        self,
        content: str,
        tool_calls: list[ToolCallRequestWithID] | None,
    ) -> ParsedResponse:
        match self._thinking_tag_context.get():
            case False:
                return ParsedResponse(content, tool_calls=tool_calls)
            case None:
                return self._check_for_thinking_tag(content, tool_calls)
            case True:
                return self._check_for_closing_thinking_tag(content, tool_calls)

        # We should never be here
        self.logger.error("Unexpected thinking tag context", extra={"context": self._thinking_tag_context.get()})
        return ParsedResponse("")

    @override
    def _extract_stream_delta(
        self,
        sse_event: bytes,
        raw_completion: RawCompletion,
        tool_call_request_buffer: dict[int, ToolCallRequestBuffer],
    ):
        if sse_event == b"[DONE]":
            return ParsedResponse("")

        raw = StreamedResponse.model_validate_json(sse_event)
        for choice in raw.choices:
            if choice.finish_reason == "length":
                raise MaxTokensExceededError(
                    msg="Model returned a response with a LENGTH finish reason, meaning the maximum number of tokens was exceeded.",
                    raw_completion=str(raw.choices),
                )
        if raw.usage:
            raw_completion.usage = raw.usage.to_domain()

        if not raw.choices or not raw.choices[0]:
            return ParsedResponse("")

        tools_calls = self._process_tool_calls(raw.choices[0].delta.tool_calls, tool_call_request_buffer)
        content = raw.choices[0].delta.content or ""

        return self._handle_thinking_context(content, tools_calls)

    def _compute_prompt_token_count(
        self,
        messages: list[dict[str, Any]],
        model: Model,
    ) -> float:
        # NOTE: FireworksAI similar to OpenAI
        FIREWORKS_BOILERPLATE_TOKENS = 3
        FIREWORKS_MESSAGE_BOILERPLATE_TOKENS = 4

        num_tokens = FIREWORKS_BOILERPLATE_TOKENS

        for message in messages:
            domain_message = FireworksMessage.model_validate(message)
            num_tokens += domain_message.token_count(model)
            num_tokens += FIREWORKS_MESSAGE_BOILERPLATE_TOKENS

        return num_tokens

    def _compute_prompt_image_count(
        self,
        messages: list[dict[str, Any]],
    ) -> int:
        # Fireworks includes image usage in the prompt token count, so we do not need to add those separately
        return 0

    @override
    async def _compute_prompt_audio_token_count(
        self,
        messages: list[dict[str, Any]],
    ):
        return 0, None

    @redis_cached()
    async def is_schema_supported_for_structured_generation(
        self,
        task_name: str,
        model: Model,
        schema: dict[str, Any],
    ) -> bool:
        # Check if the task schema is actually supported by the FireworksAI's implementation of structured generation
        try:
            options = ProviderOptions(
                task_name=task_name,
                model=model,
                output_schema=schema,
                structured_generation=True,  # We are forcing structured generation to be used
            )

            request, llm_completion = await self._prepare_completion(
                messages=[Message(content="Generate a test output", role=Message.Role.USER)],
                options=options,
                stream=False,
            )
            raw_completion = RawCompletion(response="", usage=llm_completion.usage)
            await self._single_complete(request, lambda x, _: StructuredOutput(json.loads(x)), raw_completion, options)
        except Exception:
            # Caught exception is wide because we do not want to impact group creation in any way, and the error is logged.
            self.logger.exception(
                "Schema is not supported for structured generation",
                extra={"schema": schema},
            )
            return False
        return True

    @override
    def sanitize_template(self, template: TemplateName):
        # being exhaustive to make sure we don't forget any template
        # Firework recommends keeping the output schema in the system message, even when using structured generation
        # Source: https://docs.fireworks.ai/structured-responses/structured-response-formatting#structured-response-modes
        match template:
            case (
                TemplateName.V2_STRUCTURED_GENERATION_AND_TOOL_USE_NO_INPUT_SCHEMA
                | TemplateName.V2_STRUCTURED_GENERATION_AND_NATIVE_TOOL_USE_NO_INPUT_SCHEMA
            ):
                return TemplateName.V2_NATIVE_TOOL_USE_NO_INPUT_SCHEMA
            case TemplateName.V2_STRUCTURED_GENERATION_NO_INPUT_SCHEMA:
                return TemplateName.V2_DEFAULT_NO_INPUT_SCHEMA
            case (
                TemplateName.V2_STRUCTURED_GENERATION_AND_TOOL_USE
                | TemplateName.V2_STRUCTURED_GENERATION_AND_NATIVE_TOOL_USE
            ):
                return TemplateName.V2_NATIVE_TOOL_USE
            case TemplateName.V2_STRUCTURED_GENERATION:
                return TemplateName.V2_DEFAULT
            case (
                TemplateName.V1
                | TemplateName.NO_OUTPUT_SCHEMA
                | TemplateName.WITH_TOOL_USE
                | TemplateName.WITH_TOOL_USE_AND_NO_OUTPUT_SCHEMA
                | TemplateName.V2_DEFAULT
                | TemplateName.V2_TOOL_USE
                | TemplateName.V2_DEFAULT_NO_INPUT_SCHEMA
                | TemplateName.V2_TOOL_USE_NO_INPUT_SCHEMA
                | TemplateName.V2_NATIVE_TOOL_USE
                | TemplateName.V2_NATIVE_TOOL_USE_NO_INPUT_SCHEMA
            ):
                return template

    @override
    def sanitize_model_data(self, model_data: ModelData):
        model_data.supports_input_image = True
        model_data.supports_multiple_images_in_input = True
        model_data.supports_input_pdf = True

    @classmethod
    def _extract_native_tool_calls(cls, response: CompletionResponse) -> list[ToolCallRequestWithID]:
        choice = response.choices[0]

        tool_calls: list[ToolCallRequestWithID] = [
            ToolCallRequestWithID(
                id=tool_call.id,
                tool_name=native_tool_name_to_internal(tool_call.function.name),
                # Fireworks returns the tool call arguments as a string, so we need to parse it
                tool_input_dict=parse_tool_call_or_raise(tool_call.function.arguments) or {},
            )
            for tool_call in choice.message.tool_calls or []
        ]
        return tool_calls

    @override
    async def _extract_and_log_rate_limits(self, response: Response, model: Model):
        await self._log_rate_limit_remaining(
            "requests",
            remaining=response.headers.get("x-ratelimit-remaining-requests"),
            total=response.headers.get("x-ratelimit-limit-requests"),
            model=model,
        )
        await self._log_rate_limit_remaining(
            "input_tokens",
            remaining=response.headers.get("x-ratelimit-remaining-tokens-prompt"),
            total=response.headers.get("x-ratelimit-limit-tokens-prompt"),
            model=model,
        )
        await self._log_rate_limit_remaining(
            "output_tokens",
            remaining=response.headers.get("x-ratelimit-remaining-tokens-generated"),
            total=response.headers.get("x-ratelimit-limit-tokens-generated"),
            model=model,
        )
