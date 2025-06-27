# pyright: reportPrivateUsage=false

import json
from typing import Any, cast
from unittest.mock import patch

import pytest
from pytest import MonkeyPatch
from pytest_httpx import HTTPXMock, IteratorStream

from core.domain.fields.file import File
from core.domain.llm_usage import LLMUsage
from core.domain.message import MessageDeprecated
from core.domain.models import Model, Provider
from core.domain.structured_output import StructuredOutput
from core.domain.tool_call import ToolCall, ToolCallRequestWithID
from core.providers.base.abstract_provider import RawCompletion
from core.providers.base.httpx_provider import ParsedResponse
from core.providers.base.models import StandardMessage
from core.providers.base.provider_error import (
    FailedGenerationError,
    MaxTokensExceededError,
    ProviderBadRequestError,
    ProviderInternalError,
    UnknownProviderError,
)
from core.providers.base.provider_options import ProviderOptions
from core.providers.mistral.mistral_domain import (
    CompletionRequest,
    DeltaMessage,
    MistralToolCall,
)
from core.providers.mistral.mistral_provider import MistralAIConfig, MistralAIProvider
from tests.utils import fixture_bytes, fixtures_json


@pytest.fixture(scope="function")
def mistral_provider():
    return MistralAIProvider(
        config=MistralAIConfig(api_key="test"),
    )


class TestValues:
    def test_name(self):
        """Test the name method returns the correct Provider enum."""
        assert MistralAIProvider.name() == Provider.MISTRAL_AI

    def test_required_env_vars(self):
        """Test the required_env_vars method returns the correct environment variables."""
        expected_vars = ["MISTRAL_API_KEY"]
        assert MistralAIProvider.required_env_vars() == expected_vars

    def test_supports_model(self):
        """Test the supports_model method returns True for a supported model
        and False for an unsupported model"""
        provider = MistralAIProvider()
        assert provider.supports_model(Model.PIXTRAL_12B_2409)
        assert not provider.supports_model(Model.CLAUDE_3_OPUS_20240229)


class TestBuildRequest:
    def test_build_request(self, mistral_provider: MistralAIProvider):
        request = mistral_provider._build_request(
            messages=[
                MessageDeprecated(role=MessageDeprecated.Role.SYSTEM, content="Hello 1"),
                MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello"),
            ],
            options=ProviderOptions(model=Model.PIXTRAL_12B_2409, max_tokens=10, temperature=0),
            stream=False,
        )
        assert isinstance(request, CompletionRequest)
        request_dict = request.model_dump(exclude_none=True, by_alias=True)
        assert request_dict["messages"] == [
            {
                "role": "system",
                "content": "Hello 1",
            },
            {
                "role": "user",
                "content": "Hello",
            },
        ]
        assert request_dict["temperature"] == 0
        assert request_dict["max_tokens"] == 10
        assert request_dict["stream"] is False

    def test_build_request_with_model_mapping(self, mistral_provider: MistralAIProvider):
        request = mistral_provider._build_request(
            messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.MISTRAL_LARGE_2_2407, temperature=0),
            stream=False,
        )
        request_dict = request.model_dump()
        assert request_dict["model"] == "mistral-large-2407"

    def test_build_request_with_tools(self, mistral_provider: MistralAIProvider):
        from core.domain.tool import Tool as DomainTool

        test_tool = DomainTool(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object", "properties": {"test": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"result": {"type": "string"}}},
        )

        request = mistral_provider._build_request(
            messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
            options=ProviderOptions(
                model=Model.PIXTRAL_12B_2409,
                temperature=0,
                enabled_tools=[test_tool],
            ),
            stream=False,
        )
        request_dict = request.model_dump()
        assert request_dict["tools"] is not None
        assert len(request_dict["tools"]) == 1
        assert request_dict["tools"][0]["type"] == "function"
        assert request_dict["tools"][0]["function"]["name"] == "test_tool"
        assert request_dict["tools"][0]["function"]["description"] == "A test tool"
        assert request_dict["tools"][0]["function"]["parameters"] == {
            "type": "object",
            "properties": {"test": {"type": "string"}},
        }

    def test_build_request_without_tools(self, mistral_provider: MistralAIProvider):
        request = mistral_provider._build_request(
            messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.PIXTRAL_12B_2409, temperature=0, enabled_tools=[]),
            stream=False,
        )
        request_dict = request.model_dump()
        assert request_dict["tools"] is None

    def test_build_request_with_stream(self, mistral_provider: MistralAIProvider):
        request = mistral_provider._build_request(
            messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.PIXTRAL_12B_2409, temperature=0),
            stream=True,
        )
        request_dict = request.model_dump()
        assert request_dict["stream"] is True

    def test_build_request_without_max_tokens(self, mistral_provider: MistralAIProvider):
        request = mistral_provider._build_request(
            messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.PIXTRAL_12B_2409, temperature=0),
            stream=False,
        )
        request_dict = request.model_dump()
        assert request_dict["max_tokens"] is None

    def test_build_request_with_tool_choice(self, mistral_provider: MistralAIProvider):
        from core.domain.tool import Tool as DomainTool

        test_tool = DomainTool(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object", "properties": {"test": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"result": {"type": "string"}}},
        )
        request = mistral_provider._build_request(
            messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
            options=ProviderOptions(
                model=Model.PIXTRAL_12B_2409,
                temperature=0,
                enabled_tools=[test_tool],
                tool_choice="auto",
            ),
            stream=False,
        )
        request_dict = request.model_dump(exclude_none=True)
        assert request_dict["tool_choice"] == "auto"

    def test_build_request_multiple_tools(self, mistral_provider: MistralAIProvider):
        messages = [
            MessageDeprecated(
                role=MessageDeprecated.Role.USER,
                content="What is the weather in Tokyo and in Paris?",
            ),
            MessageDeprecated(
                role=MessageDeprecated.Role.ASSISTANT,
                content="Let me get the weather in tokyo first",
                tool_call_requests=[
                    ToolCallRequestWithID(
                        id="tool_use_01NhMGWVdTLvEuDB6Rx76hYJ",
                        tool_name="get_weather",
                        tool_input_dict={"city": "Tokyo"},
                    ),
                    ToolCallRequestWithID(
                        id="tool_use_01NhMGWVdTLvEuDB6Rx76hYK",
                        tool_name="get_weather",
                        tool_input_dict={"city": "Paris"},
                    ),
                ],
            ),
            MessageDeprecated(
                role=MessageDeprecated.Role.USER,
                content="The weather in Tokyo is sunny",
                tool_call_results=[
                    ToolCall(
                        id="tool_use_01NhMGWVdTLvEuDB6Rx76hYJ",
                        tool_name="get_weather",
                        tool_input_dict={"city": "Tokyo"},
                        result="The weather in Tokyo is sunny",
                    ),
                    ToolCall(
                        id="tool_use_01NhMGWVdTLvEuDB6Rx76hYK",
                        tool_name="get_weather",
                        tool_input_dict={"city": "Paris"},
                        result="The weather in Paris is sunny",
                    ),
                ],
            ),
        ]
        request = mistral_provider._build_request(
            messages=messages,
            options=ProviderOptions(model=Model.PIXTRAL_12B_2409, temperature=0),
            stream=False,
        )
        request = cast(CompletionRequest, request)  # noqa: F821

        assert len(request.messages) == 4
        assert request.messages[0].role == "user"
        assert request.messages[1].role == "assistant"
        assert request.messages[1].tool_calls and len(request.messages[1].tool_calls) == 2
        assert request.messages[1].tool_calls[0].id == "70b3a00ce"
        assert request.messages[1].tool_calls[1].id == "76af333cd"
        assert request.messages[2].role == "tool"
        assert request.messages[2].tool_call_id == "70b3a00ce"
        assert request.messages[2].content == '{"result": "The weather in Tokyo is sunny"}'
        assert request.messages[3].role == "tool"
        assert request.messages[3].tool_call_id == "76af333cd"
        assert request.messages[3].content == '{"result": "The weather in Paris is sunny"}'


class TestSingleStream:
    async def test_stream_data(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.mistral.ai/v1/chat/completions",
            stream=IteratorStream(
                [
                    b'data: {"id":"1","object":"chat.completion.chunk","created":1720404416,"model":"pixtral-12b-2409","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"role":"assistant","content":""},"logprobs":null,',
                    b'"finish_reason":null}]}\n\ndata: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"pixtral-12b-2409","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"content":"{\\n"},"logprobs":null,"finish_reason":null}]}\n\n',
                    b'data: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"pixtral-12b-2409","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"content":"\\"greeting\\": \\"Hello James!\\"\\n}"},"logprobs":null,"finish_reason":null}]}\n\n',
                    b"data: [DONE]\n\n",
                ],
            ),
        )

        provider = MistralAIProvider()
        raw = RawCompletion(usage=LLMUsage(), response="")

        raw_chunks = provider._single_stream(
            request={"messages": [{"role": "user", "content": "Hello"}]},
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            partial_output_factory=lambda x: StructuredOutput(x),
            raw_completion=raw,
            options=ProviderOptions(
                model=Model.PIXTRAL_12B_2409,
                max_tokens=10,
                temperature=0,
                output_schema={},
            ),
        )

        parsed_chunks = [o async for o in raw_chunks]

        assert len(parsed_chunks) == 2
        assert parsed_chunks[0][0] == {"greeting": "Hello James!"}
        assert parsed_chunks[1][0] == {"greeting": "Hello James!"}

        assert len(httpx_mock.get_requests()) == 1


class TestStream:
    # Tests overlap with single stream above but check the entire structure
    async def test_stream(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.mistral.ai/v1/chat/completions",
            stream=IteratorStream(
                [
                    b'data: {"id":"1","object":"chat.completion.chunk","created":1720404416,"model":"pixtral-12b-2409","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"role":"assistant","content":""},"logprobs":null,',
                    b'"finish_reason":null}]}\n\ndata: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"pixtral-12b-2409","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"content":"{\\n"},"logprobs":null,"finish_reason":null}]}\n\n',
                    b'data: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"pixtral-12b-2409","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"content":"\\"greeting\\": \\"Hello James!\\"\\n}"},"logprobs":null,"finish_reason":null}]}\n\n',
                    b"data: [DONE]\n\n",
                ],
            ),
        )

        provider = MistralAIProvider()

        streamer = provider.stream(
            [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
            options=ProviderOptions(
                model=Model.PIXTRAL_12B_2409,
                max_tokens=10,
                temperature=0,
                output_schema={"type": "object"},
            ),
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            partial_output_factory=lambda x: StructuredOutput(x),
        )
        chunks = [o async for o in streamer]
        assert len(chunks) == 2

        # Not sure why the pyright in the CI reports an error here
        request = httpx_mock.get_requests()[0]
        assert request.method == "POST"  # pyright: ignore reportUnknownMemberType
        body = json.loads(request.read().decode())
        assert body == {
            "max_tokens": 10,
            "model": "pixtral-12b-2409",
            "messages": [
                {
                    "content": "Hello",
                    "role": "user",
                },
            ],
            "response_format": {
                "type": "json_object",
            },
            "stream": True,
            "temperature": 0.0,
        }

    async def test_stream_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.mistral.ai/v1/chat/completions",
            status_code=400,
            json={"msg": "blabla"},
        )

        provider = MistralAIProvider()

        streamer = provider.stream(
            [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.PIXTRAL_12B_2409, max_tokens=10, temperature=0),
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            partial_output_factory=lambda x: StructuredOutput(x),
        )
        # TODO: be stricter about what error is returned here
        with pytest.raises(UnknownProviderError) as e:
            [chunk async for chunk in streamer]

        assert e.value.capture
        assert str(e.value) == "blabla"


class TestComplete:
    async def test_complete_images(self, httpx_mock: HTTPXMock, mistral_provider: MistralAIProvider):
        httpx_mock.add_response(
            url="https://api.mistral.ai/v1/chat/completions",
            json=fixtures_json("mistralai", "completion.json"),
        )

        o = await mistral_provider.complete(
            [
                MessageDeprecated(
                    role=MessageDeprecated.Role.USER,
                    content="Hello",
                    files=[
                        File(data="data", content_type="image/png"),
                    ],
                ),
            ],
            options=ProviderOptions(
                model=Model.PIXTRAL_12B_2409,
                max_tokens=10,
                temperature=0,
                output_schema={"type": "object"},
            ),
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
        )
        assert o.output
        assert o.tool_calls is None

        # Not sure why the pyright in the CI reports an error here
        request = httpx_mock.get_requests()[0]
        assert request.method == "POST"  # pyright: ignore reportUnknownMemberType
        body = json.loads(request.read().decode())
        assert body == {
            "max_tokens": 10,
            "model": "pixtral-12b-2409",
            "messages": [
                {
                    "content": [
                        {
                            "text": "Hello",
                            "type": "text",
                        },
                        {
                            "image_url": {
                                "url": "data:image/png;base64,data",
                            },
                            "type": "image_url",
                        },
                    ],
                    "role": "user",
                },
            ],
            "response_format": {
                "type": "json_object",
            },
            "stream": False,
            "temperature": 0.0,
            # "store": True,
        }

        # Tests overlap with single stream above but check the entire structure

    async def test_complete_without_max_tokens(self, httpx_mock: HTTPXMock, mistral_provider: MistralAIProvider):
        httpx_mock.add_response(
            url="https://api.mistral.ai/v1/chat/completions",
            json=fixtures_json("mistralai", "completion.json"),
        )

        o = await mistral_provider.complete(
            [
                MessageDeprecated(
                    role=MessageDeprecated.Role.USER,
                    content="Hello",
                    files=[
                        File(data="data", content_type="image/png"),
                    ],
                ),
            ],
            options=ProviderOptions(
                model=Model.PIXTRAL_12B_2409,
                temperature=0,
                output_schema={"type": "object"},
            ),
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
        )
        assert o.output
        assert o.tool_calls is None

        # Not sure why the pyright in the CI reports an error here
        request = httpx_mock.get_requests()[0]
        assert request.method == "POST"  # pyright: ignore reportUnknownMemberType
        body = json.loads(request.read().decode())
        # model_data = get_model_data(model)
        # expected_max_tokens = 0
        # if model_data.max_tokens_data.max_output_tokens:
        #     expected_max_tokens = model_data.max_tokens_data.max_output_tokens
        # else:
        #     expected_max_tokens = model_data.max_tokens_data.max_tokens
        assert body == {
            "model": "pixtral-12b-2409",
            "messages": [
                {
                    "content": [
                        {
                            "text": "Hello",
                            "type": "text",
                        },
                        {
                            "image_url": {
                                "url": "data:image/png;base64,data",
                            },
                            "type": "image_url",
                        },
                    ],
                    "role": "user",
                },
            ],
            "response_format": {
                "type": "json_object",
            },
            "stream": False,
            "temperature": 0.0,
            # "store": True,
        }

    async def test_complete_text_only(self, httpx_mock: HTTPXMock, mistral_provider: MistralAIProvider):
        httpx_mock.add_response(
            url="https://api.mistral.ai/v1/chat/completions",
            json=fixtures_json("mistralai", "completion.json"),
        )

        o = await mistral_provider.complete(
            [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.PIXTRAL_12B_2409, max_tokens=10, temperature=0),
            output_factory=lambda x, _: StructuredOutput(x),
        )
        assert o.output
        assert o.tool_calls is None

        request = httpx_mock.get_requests()[0]
        assert request.method == "POST"  # pyright: ignore reportUnknownMemberType
        body = json.loads(request.read().decode())
        assert body["response_format"]["type"] == "text"

    async def test_complete_500(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.mistral.ai/v1/chat/completions",
            status_code=500,
            text="Internal Server Error",
        )

        provider = MistralAIProvider()

        with pytest.raises(ProviderInternalError) as e:
            await provider.complete(
                [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.PIXTRAL_12B_2409, max_tokens=10, temperature=0),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            )

        details = e.value.error_response().error.details
        assert details and details.get("provider_error") == {"raw": "Internal Server Error"}

    async def test_complete_value_error(self, httpx_mock: HTTPXMock, mistral_provider: MistralAIProvider):
        httpx_mock.add_response(
            url="https://api.mistral.ai/v1/chat/completions",
            status_code=400,
            json=fixtures_json("mistralai", "error_with_details.json"),
        )

        with pytest.raises(ProviderBadRequestError) as e:
            await mistral_provider.complete(
                [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.PIXTRAL_12B_2409, max_tokens=10, temperature=0),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            )

        message = e.value.error_response().error.message
        assert message.startswith("Value error, Image content")

    async def test_max_tokens_exceeded_invalid_request(
        self,
        httpx_mock: HTTPXMock,
        mistral_provider: MistralAIProvider,
    ):
        httpx_mock.add_response(
            url="https://api.mistral.ai/v1/chat/completions",
            status_code=400,
            json={
                "message": "Prompt contains 40687 tokens and 0 draft tokens, too large for model with 32768 maximum context length",
                "type": "invalid_request_error",
            },
        )

        with pytest.raises(MaxTokensExceededError) as e:
            await mistral_provider.complete(
                [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.PIXTRAL_12B_2409, max_tokens=10, temperature=0),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            )

        assert e.value.store_task_run

    async def test_max_tokens_exceeded(self, httpx_mock: HTTPXMock, mistral_provider: MistralAIProvider):
        httpx_mock.add_response(
            url="https://api.mistral.ai/v1/chat/completions",
            status_code=400,
            json={
                "message": "Blabla",
                "type": "context_length_exceeded",
            },
        )

        with pytest.raises(MaxTokensExceededError) as e:
            await mistral_provider.complete(
                [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.PIXTRAL_12B_2409, max_tokens=10, temperature=0),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            )

        assert e.value.store_task_run

    async def test_max_tokens_in_request(self, httpx_mock: HTTPXMock, mistral_provider: MistralAIProvider):
        httpx_mock.add_response(
            url="https://api.mistral.ai/v1/chat/completions",
            json=fixtures_json("mistralai", "completion.json"),
        )
        await mistral_provider.complete(
            [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.PIXTRAL_12B_2409, max_tokens=10, temperature=0),
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
        )

        request = httpx_mock.get_requests()[0]
        body = json.loads(request.read().decode())
        assert body["max_tokens"] == 10

    async def test_max_tokens_in_request_without_max_tokens_in_options(
        self,
        httpx_mock: HTTPXMock,
        mistral_provider: MistralAIProvider,
    ):
        httpx_mock.add_response(
            url="https://api.mistral.ai/v1/chat/completions",
            json=fixtures_json("mistralai", "completion.json"),
        )
        await mistral_provider.complete(
            [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.PIXTRAL_12B_2409, temperature=0),
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
        )
        request = httpx_mock.get_requests()[0]
        body = json.loads(request.read().decode())
        assert "max_tokens" not in body
        # model_data = get_model_data(model)
        # if model_data.max_tokens_data.max_output_tokens:
        #     assert body["max_tokens"] == model_data.max_tokens_data.max_output_tokens
        # else:
        #     assert body["max_tokens"] == model_data.max_tokens_data.max_tokens


class TestCheckValid:
    async def test_valid(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.mistral.ai/v1/chat/completions",
            json={
                "id": "chatcmpl-91gL0PXUwQajck2pIp284pR9o7yVo",
                "object": "chat.completion",
                "created": 1710188102,
                "model": "gpt-4",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "index": 0,
                        "message": {"role": "assistant", "content": "{}"},
                    },
                ],
                "usage": {"prompt_tokens": 35, "completion_tokens": 109, "total_tokens": 144},
                "system_fingerprint": "fp_8abb16fa4e",
            },
        )

        provider = MistralAIProvider()
        assert await provider.check_valid()

        request = httpx_mock.get_requests()[0]
        body = json.loads(request.read().decode())
        assert body["messages"] == [{"content": "Respond with an empty json", "role": "user"}]


class TestStandardizeMessages:
    def test_standardize_messages(self) -> None:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What's in this image?"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/image1.jpg"}},
                ],
            },
            {"role": "assistant", "content": "The image shows a beautiful sunset over a beach."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Can you compare it with this one?"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/image2.jpg"}},
                ],
            },
            {"role": "assistant", "content": "The second image depicts a snowy mountain landscape."},
        ]
        expected: list[StandardMessage] = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What's in this image?"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/image1.jpg"}},
                ],
            },
            {"role": "assistant", "content": "The image shows a beautiful sunset over a beach."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Can you compare it with this one?"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/image2.jpg"}},
                ],
            },
            {"role": "assistant", "content": "The second image depicts a snowy mountain landscape."},
        ]
        assert MistralAIProvider.standardize_messages(messages) == expected


class TestExtractStreamDelta:
    def test_extract_stream_delta(self, mistral_provider: MistralAIProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        delta = mistral_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            b'{"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","usage": {"prompt_tokens": 35, "completion_tokens": 109, "total_tokens": 144},"choices":[{"index":0,"delta":{"content":"hello"},"logprobs":null,"finish_reason":null}]}',
            raw_completion,
            {},
        )
        assert delta.content == "hello"
        assert raw_completion.usage == LLMUsage(prompt_token_count=35, completion_token_count=109)

    def test_done(self, mistral_provider: MistralAIProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        delta = mistral_provider._extract_stream_delta(b"[DONE]", raw_completion, {})  # pyright: ignore[reportPrivateUsage]
        assert delta.content == ""

    def test_with_real_SSEs_and_tools(self, mistral_provider: MistralAIProvider):
        SSEs = [
            b'{"id":"fcc3f452c40749fa8f5a6e87efbf6a1a","object":"chat.completion.chunk","created":1740035502,"model":"mistral-large-2411","choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":null}]}',
            b'{"id":"fcc3f452c40749fa8f5a6e87efbf6a1a","object":"chat.completion.chunk","created":1740035502,"model":"mistral-large-2411","choices":[{"index":0,"delta":{"tool_calls":[{"id":"R5zZgxSX6","function":{"name":"get_city_internal_code","arguments":"{\\"city\\": \\"New York\\"}"},"index":0}]},"finish_reason":"tool_calls"}],"usage":{"prompt_tokens":805,"total_tokens":831,"completion_tokens":26}}',
        ]
        assert mistral_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            SSEs[0],
            RawCompletion(response="", usage=LLMUsage()),
            {},
        ) == ParsedResponse(
            content="",
            tool_calls=[],
        )

        assert mistral_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            SSEs[1],
            RawCompletion(response="", usage=LLMUsage()),
            {},
        ) == ParsedResponse(
            content="",
            tool_calls=[
                ToolCallRequestWithID(
                    tool_name="get_city_internal_code",
                    tool_input_dict={"city": "New York"},
                    id="R5zZgxSX6",
                ),
            ],
        )


class TestMaxTokensExceeded:
    async def test_max_tokens_exceeded(self, mistral_provider: MistralAIProvider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.mistral.ai/v1/chat/completions",
            json=fixtures_json("mistralai", "finish_reason_length_completion.json"),
        )
        with pytest.raises(MaxTokensExceededError) as e:
            await mistral_provider.complete(
                [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.PIXTRAL_12B_2409, max_tokens=10, temperature=0),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            )
        assert (
            e.value.args[0]
            == "Model returned a response with a LENGTH finish reason, meaning the maximum number of tokens was exceeded."
        )

    async def test_max_tokens_exceeded_stream(self, mistral_provider: MistralAIProvider, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.mistral.ai/v1/chat/completions",
            stream=IteratorStream(
                [
                    fixture_bytes("mistralai", "finish_reason_length_stream_completion.txt"),
                ],
            ),
        )
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        with pytest.raises(MaxTokensExceededError) as e:
            async for _ in mistral_provider._single_stream(  # pyright: ignore reportPrivateUsage
                request={"messages": [{"role": "user", "content": "Hello"}]},
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
                partial_output_factory=lambda x: StructuredOutput(x),
                raw_completion=raw_completion,
                options=ProviderOptions(model=Model.PIXTRAL_12B_2409, max_tokens=10, temperature=0),
            ):
                pass
        assert (
            e.value.args[0]
            == "Model returned a response with a LENGTH finish reason, meaning the maximum number of tokens was exceeded."
        )


class TestExtraStreamDeltaToolCalls:
    @pytest.fixture
    def provider(self) -> MistralAIProvider:
        # Create a provider instance with dummy configuration.
        config = MistralAIConfig(api_key="dummy")
        return MistralAIProvider(config=config)

    def test_valid_tool_call(self, provider: MistralAIProvider) -> None:
        """
        When a valid tool call is received in the SSE delta, it should be extracted.
        """
        tool_call = MistralToolCall(
            id="tcvalid12",
            function=MistralToolCall.Function(
                name="calculator",
                arguments={"operation": "multiply", "numbers": [3, 4]},
            ),
            index=1,
        )
        delta = DeltaMessage(content="partial", tool_calls=[tool_call])
        buffer: dict[int, Any] = {}
        result = provider._extra_stream_delta_tool_calls(delta, buffer)  # pyright: ignore[reportPrivateUsage]
        assert len(result) == 1
        tt = result[0]
        assert tt.id == "tcvalid12"
        # Assuming native_tool_name_to_internal acts as identity in tests.
        assert tt.tool_name == "calculator"
        assert tt.tool_input_dict == {"operation": "multiply", "numbers": [3, 4]}

    def test_no_index_raises(self, provider: MistralAIProvider) -> None:
        """
        When a tool call is missing an index, the provider should raise a FailedGenerationError.
        """
        tool_call = MistralToolCall(
            id="tc_no_index",
            function=MistralToolCall.Function(
                name="calculator",
                arguments={"operation": "subtract", "numbers": [10, 5]},
            ),
            index=None,
        )
        delta = DeltaMessage(content="ignored", tool_calls=[tool_call])
        buffer: dict[int, Any] = {}
        with pytest.raises(FailedGenerationError, match="Model returned a tool call with no index"):
            provider._extra_stream_delta_tool_calls(delta, buffer)  # pyright: ignore[reportPrivateUsage]

    def test_invalid_json_no_tool_call_added(self, provider: MistralAIProvider) -> None:
        """
        When the accumulated tool call arguments cannot be parsed as JSON,
        no tool call should be returned.
        """
        # Provide a tool call where function.arguments is a string that will not decode as valid JSON.
        tool_call = MistralToolCall(
            id="tc_invalid",
            function=MistralToolCall.Function(name="calculator", arguments="not a json"),
            index=2,
        )
        delta = DeltaMessage(content="ignored", tool_calls=[tool_call])
        buffer: dict[int, Any] = {}
        result = provider._extra_stream_delta_tool_calls(delta, buffer)  # pyright: ignore[reportPrivateUsage]
        # Expect an empty list due to JSONDecodeError.
        assert result == []


class TestComputePromptTokenCount:
    @pytest.mark.parametrize(
        "messages,model,expected_token_count",
        [
            # Test with a single user message
            (
                [{"role": "user", "content": "Hello"}],
                Model.MISTRAL_LARGE_LATEST,
                1,  # Expected tokens for "Hello"
            ),
            # Test with multiple messages
            (
                [
                    {"role": "system", "content": "Hello"},
                    {"role": "user", "content": "World"},
                ],
                Model.MISTRAL_LARGE_LATEST,
                2,  # Expected tokens for "Hellow" and "World"
            ),
            # Test with an empty message
            (
                [{"role": "user", "content": ""}],
                Model.MISTRAL_LARGE_LATEST,
                0,  # Expected tokens for empty string
            ),
            # Test with tool message
            (
                [{"role": "tool", "tool_call_id": "tc_valid", "name": "calculator", "content": "Hello"}],
                Model.MISTRAL_LARGE_LATEST,
                1,  # Expected tokens for "Hello"
            ),
        ],
    )
    def test_compute_prompt_token_count(
        self,
        mistral_provider: MistralAIProvider,
        messages: list[dict[str, Any]],
        model: Model,
        expected_token_count: int,
        monkeypatch: MonkeyPatch,
    ):
        with patch("core.utils.token_utils.tokens_from_string", return_value=1):
            # Calculate token count
            result = mistral_provider._compute_prompt_token_count(  # pyright: ignore[reportPrivateUsage]
                messages,
                model,
            )

            # This is a high-level smoke test that '_compute_prompt_token_count' does not raise and return a value
            assert result == expected_token_count
