# pyright: reportPrivateUsage=false

import copy
import json
from collections.abc import Callable
from typing import Any, cast

import pytest
from httpx import Response
from pytest_httpx import HTTPXMock, IteratorStream

from core.domain.fields.file import File
from core.domain.fields.internal_reasoning_steps import InternalReasoningStep
from core.domain.llm_usage import LLMUsage
from core.domain.message import MessageDeprecated
from core.domain.models import Model
from core.domain.structured_output import StructuredOutput
from core.providers.base.abstract_provider import RawCompletion
from core.providers.base.models import StandardMessage
from core.providers.base.provider_error import (
    ContentModerationError,
    MaxTokensExceededError,
    ModelDoesNotSupportMode,
    ProviderError,
    ProviderInternalError,
    ProviderInvalidFileError,
    StructuredGenerationError,
    UnknownProviderError,
)
from core.providers.base.provider_options import ProviderOptions
from core.providers.xai.xai_domain import CompletionRequest
from core.providers.xai.xai_provider import XAIConfig, XAIProvider
from tests import models as test_models
from tests.utils import fixture_bytes, fixtures_json, fixtures_stream


@pytest.fixture(scope="function")
def xai_provider():
    return XAIProvider(
        config=XAIConfig(api_key="test"),
    )


class TestBuildRequest:
    def test_build_request(self, xai_provider: XAIProvider):
        request = xai_provider._build_request(  # pyright: ignore [reportPrivateUsage]
            messages=[
                MessageDeprecated(role=MessageDeprecated.Role.SYSTEM, content="Hello 1"),
                MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello"),
            ],
            options=ProviderOptions(model=Model.GPT_4O_2024_11_20, max_tokens=10, temperature=0),
            stream=False,
        )
        assert isinstance(request, CompletionRequest)
        # We can exclude None values because the HTTPxProvider does the same
        assert request.model_dump(include={"messages"}, exclude_none=True)["messages"] == [
            {
                "role": "system",
                "content": "Hello 1",
            },
            {
                "role": "user",
                "content": "Hello",
            },
        ]
        assert request.temperature == 0
        assert request.max_tokens == 10

    def test_build_request_without_max_tokens(self, xai_provider: XAIProvider):
        request = xai_provider._build_request(  # pyright: ignore [reportPrivateUsage]
            messages=[
                MessageDeprecated(role=MessageDeprecated.Role.SYSTEM, content="Hello 1"),
                MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello"),
            ],
            options=ProviderOptions(model=Model.GPT_4O_2024_11_20, temperature=0),
            stream=False,
        )
        assert isinstance(request, CompletionRequest)
        # We can exclude None values because the HTTPxProvider does the same
        assert request.model_dump(include={"messages"}, exclude_none=True)["messages"] == [
            {
                "role": "system",
                "content": "Hello 1",
            },
            {
                "role": "user",
                "content": "Hello",
            },
        ]
        assert request.temperature == 0
        assert request.max_tokens is None
        # model_data = get_model_data(Model.GPT_4O_2024_11_20)
        # if model_data.max_tokens_data.max_output_tokens:
        #     assert request.max_tokens == model_data.max_tokens_data.max_output_tokens
        # else:
        #     assert request.max_tokens == model_data.max_tokens_data.max_tokens

    def test_build_request_with_reasoning_effort(self, xai_provider: XAIProvider):
        request = cast(
            CompletionRequest,
            xai_provider._build_request(  # pyright: ignore [reportPrivateUsage]
                messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(
                    model=Model.GROK_3_MINI_BETA,
                    max_tokens=10,
                    temperature=0,
                    reasoning_effort="low",
                ),
                stream=False,
            ),
        )
        # We can exclude None values because the HTTPxProvider does the same
        assert request.model_dump(include={"messages", "reasoning_effort", "model"}, exclude_none=True) == {
            "model": "grok-3-mini-beta",
            "messages": [
                {
                    "role": "user",
                    "content": "Hello",
                },
            ],
            "reasoning_effort": "low",
        }

    def test_build_request_with_reasoning_effort_medium(self, xai_provider: XAIProvider):
        request = cast(
            CompletionRequest,
            xai_provider._build_request(  # pyright: ignore [reportPrivateUsage]
                messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(
                    model=Model.GROK_3_MINI_BETA,
                    max_tokens=10,
                    temperature=0,
                    reasoning_effort="medium",
                ),
                stream=False,
            ),
        )
        # We can exclude None values because the HTTPxProvider does the same
        assert request.model_dump(include={"messages", "reasoning_effort", "model"}, exclude_none=True) == {
            "model": "grok-3-mini-beta",
            "messages": [
                {
                    "role": "user",
                    "content": "Hello",
                },
            ],
        }

    def test_build_request_with_tool_choice(self, xai_provider: XAIProvider):
        request = cast(
            CompletionRequest,
            xai_provider._build_request(  # pyright: ignore [reportPrivateUsage]
                messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(
                    model=Model.GPT_4O_2024_11_20,
                    tool_choice="auto",
                ),
                stream=False,
            ),
        )
        # We can exclude None values because the HTTPxProvider does the same
        assert request.model_dump(include={"messages", "tool_choice", "model"}, exclude_none=True) == {
            "model": "gpt-4o-2024-11-20",
            "messages": [
                {
                    "role": "user",
                    "content": "Hello",
                },
            ],
            "tool_choice": "auto",
        }


def mock_xai_stream(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://api.x.ai/v1/chat/completions",
        stream=IteratorStream(
            [
                b'data: {"id":"1","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"role":"assistant","content":""},"logprobs":null,',
                b'"finish_reason":null}]}\n\ndata: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"content":"{\\n"},"logprobs":null,"finish_reason":null}]}\n\n',
                b'data: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"content":"\\"greeting\\": \\"Hello James!\\"\\n}"},"logprobs":null,"finish_reason":null}]}\n\n',
                b"data: [DONE]\n\n",
            ],
        ),
    )


class TestSingleStream:
    async def test_stream_data(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.x.ai/v1/chat/completions",
            stream=IteratorStream(
                [
                    b'data: {"id":"1","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"role":"assistant","content":""},"logprobs":null,',
                    b'"finish_reason":null}]}\n\ndata: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"content":"{\\n"},"logprobs":null,"finish_reason":null}]}\n\n',
                    b'data: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"content":"\\"greeting\\": \\"Hello James!\\"\\n}"},"logprobs":null,"finish_reason":null}]}\n\n',
                    b"data: [DONE]\n\n",
                ],
            ),
        )

        provider = XAIProvider()
        raw = RawCompletion(usage=LLMUsage(), response="")

        raw_chunks = provider._single_stream(  # pyright: ignore [reportPrivateUsage]
            request={"messages": [{"role": "user", "content": "Hello"}]},
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            partial_output_factory=lambda x: StructuredOutput(x),
            raw_completion=raw,
            options=ProviderOptions(model=Model.GPT_3_5_TURBO_1106, max_tokens=10, temperature=0, output_schema={}),
        )

        parsed_chunks = [o async for o in raw_chunks]

        assert len(parsed_chunks) == 2
        assert parsed_chunks[0][0] == {"greeting": "Hello James!"}
        assert parsed_chunks[1][0] == {"greeting": "Hello James!"}

        assert len(httpx_mock.get_requests()) == 1

    # TODO: check for usage and add tests for error handling

    async def test_stream_data_audios(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.x.ai/v1/chat/completions",
            stream=IteratorStream(
                [
                    b'data: {"id":"1","object":"chat.completion.chunk","created":1720404416,"model":"gpt-4o-audio-preview","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"role":"assistant","content":""},"logprobs":null,',
                    b'"finish_reason":null}]}\n\ndata: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-4o-audio-preview","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"content":"{\\n"},"logprobs":null,"finish_reason":null}]}\n\n',
                    b'data: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-4o-audio-preview","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"content":"\\"answer\\": \\"Oh it has 30 words!\\"\\n}"},"logprobs":null,"finish_reason":null}]}\n\n',
                    b"data: [DONE]\n\n",
                ],
            ),
        )

        provider = XAIProvider()
        raw = RawCompletion(usage=LLMUsage(), response="")

        raw_chunks = provider._single_stream(  # pyright: ignore [reportPrivateUsage]
            request={
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Can you reply to this audio?"},
                            {"type": "audio_url", "audio_url": {"url": "data:audio/wav;base64,data234avsrtgsd"}},
                        ],
                    },
                ],
            },
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            partial_output_factory=lambda x: StructuredOutput(x),
            raw_completion=raw,
            options=ProviderOptions(
                model=Model.GROK_3_MINI_BETA,
                max_tokens=10,
                temperature=0,
                output_schema={},
            ),
        )

        parsed_chunks = [o async for o in raw_chunks]

        assert len(parsed_chunks) == 2
        assert parsed_chunks[0][0] == {"answer": "Oh it has 30 words!"}
        assert parsed_chunks[1][0] == {"answer": "Oh it has 30 words!"}

        assert len(httpx_mock.get_requests()) == 1

    async def test_stream_reasoning(self, httpx_mock: HTTPXMock, xai_provider: XAIProvider):
        httpx_mock.add_response(
            url="https://api.x.ai/v1/chat/completions",
            stream=IteratorStream(fixtures_stream("xai", "stream_reasoning.txt")),
        )
        streamer = xai_provider.stream(
            [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.GROK_3_MINI_BETA_HIGH_REASONING_EFFORT),
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            partial_output_factory=lambda x: StructuredOutput(x),
        )

        chunks = [copy.deepcopy(o) async for o in streamer]
        # assert len(chunks) == 9

        reasoning_steps = [c.reasoning_steps for c in chunks]
        assert reasoning_steps[0] == [InternalReasoningStep(explaination="First")]
        assert reasoning_steps[1] == [InternalReasoningStep(explaination="First response")]


class TestStream:
    # Tests overlap with single stream above but check the entire structure
    async def test_stream(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.x.ai/v1/chat/completions",
            stream=IteratorStream(
                [
                    b'data: {"id":"1","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"role":"assistant","content":""},"logprobs":null,',
                    b'"finish_reason":null}]}\n\ndata: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"content":"{\\n"},"logprobs":null,"finish_reason":null}]}\n\n',
                    b'data: {"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","choices":[{"index":0,"delta":{"content":"\\"greeting\\": \\"Hello James!\\"\\n}"},"logprobs":null,"finish_reason":null}]}\n\n',
                    b"data: [DONE]\n\n",
                ],
            ),
        )

        provider = XAIProvider()

        streamer = provider.stream(
            [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
            options=ProviderOptions(
                model=Model.GPT_3_5_TURBO_1106,
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
            "model": "gpt-3.5-turbo-1106",
            "messages": [
                {
                    "content": "Hello",
                    "role": "user",
                },
            ],
            # "response_format": {
            #     "type": "json_object",
            # },
            "stream": True,
            "stream_options": {
                "include_usage": True,
            },
            "temperature": 0.0,
            # "store": True,
        }

    async def test_stream_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.x.ai/v1/chat/completions",
            status_code=400,
            json={"error": "blabla"},
        )

        provider = XAIProvider()

        streamer = provider.stream(
            [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.GPT_3_5_TURBO_1106, max_tokens=10, temperature=0),
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            partial_output_factory=lambda x: StructuredOutput(x),
        )
        # TODO: be stricter about what error is returned here
        with pytest.raises(UnknownProviderError) as e:
            [chunk async for chunk in streamer]

        assert e.value.capture
        assert str(e.value) == "blabla"


class TestComplete:
    # Tests overlap with single stream above but check the entire structure
    async def test_complete_images(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.x.ai/v1/chat/completions",
            json=fixtures_json("xai", "completion.json"),
        )

        provider = XAIProvider()

        o = await provider.complete(
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
                model=Model.GPT_3_5_TURBO_1106,
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
            "model": "gpt-3.5-turbo-1106",
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
            # "response_format": {
            #     "type": "json_object",
            # },
            "stream": False,
            "temperature": 0.0,
            # "store": True,
        }

    async def test_complete_text_only(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.x.ai/v1/chat/completions",
            json=fixtures_json("xai", "completion.json"),
        )

        provider = XAIProvider()

        o = await provider.complete(
            [
                MessageDeprecated(
                    role=MessageDeprecated.Role.USER,
                    content="Hello",
                ),
            ],
            options=ProviderOptions(
                model=Model.GPT_3_5_TURBO_1106,
                max_tokens=10,
                temperature=0,
                # No output schema means the model will return a string
                output_schema=None,
            ),
            output_factory=lambda x, _: StructuredOutput(x),
        )
        assert o.output
        assert o.tool_calls is None
        # Not sure why the pyright in the CI reports an error here
        request = httpx_mock.get_requests()[0]
        assert request.method == "POST"  # pyright: ignore reportUnknownMemberType
        body = json.loads(request.read().decode())
        assert "response_format" not in body

    async def test_complete_500(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.x.ai/v1/chat/completions",
            status_code=500,
            text="Internal Server Error",
        )

        provider = XAIProvider()

        with pytest.raises(ProviderInternalError) as e:
            await provider.complete(
                [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.GPT_3_5_TURBO_1106, max_tokens=10, temperature=0),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            )

        details = e.value.error_response().error.details
        assert details and details.get("provider_error") == {"raw": "Internal Server Error"}

    async def test_complete_structured(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.x.ai/v1/chat/completions",
            json=fixtures_json("xai", "completion.json"),
        )
        provider = XAIProvider()

        o = await provider.complete(
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
                model=Model.GPT_4O_MINI_2024_07_18,
                max_tokens=10,
                temperature=0,
                task_name="hello",
                structured_generation=True,
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
            "model": "gpt-4o-mini-2024-07-18",
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
                "type": "json_schema",
                "json_schema": {
                    "name": "hello_01fc056eed58c88fe1c507fcd84dd4b7",
                    "strict": True,
                    "schema": {"type": "object"},
                },
            },
            "stream": False,
            "temperature": 0.0,
        }

    async def test_complete_refusal(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.x.ai/v1/chat/completions",
            json=fixtures_json("xai", "refusal.json"),
        )
        provider = XAIProvider()
        with pytest.raises(ContentModerationError) as e:
            await provider.complete(
                [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.GPT_4O_2024_08_06, max_tokens=10, temperature=0),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            )

        response = e.value.error_response()
        assert response.error.code == "content_moderation"
        assert response.error.status_code == 400
        assert response.error.message == "Model refused to generate a response: I'm sorry, I can't assist with that."
        assert e.value.capture is False
        assert e.value.store_task_run is True

    @pytest.mark.skip(reason="Not sure about content moderation for now")
    async def test_complete_content_moderation(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.x.ai/v1/chat/completions",
            json=fixtures_json("xai", "content_moderation.json"),
            status_code=400,
        )

        provider = XAIProvider()
        with pytest.raises(ContentModerationError) as e:
            await provider.complete(
                [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.GPT_4O_2024_08_06, max_tokens=10, temperature=0),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            )

        response = e.value.error_response()
        assert response.error.code == "content_moderation"
        assert response.error.status_code == 400
        assert response.error.message.startswith("Invalid prompt: your prompt was flagged")

    @pytest.mark.skip(reason="Not sure about max message length for now")
    async def test_max_message_length(self, httpx_mock: HTTPXMock, xai_provider: XAIProvider):
        httpx_mock.add_response(
            url="https://api.x.ai/v1/chat/completions",
            status_code=400,
            json={"error": {"code": "string_above_max_length", "message": "The string is too long"}},
        )

        with pytest.raises(MaxTokensExceededError) as e:
            await xai_provider.complete(
                [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.GPT_4O_2024_08_06, max_tokens=10, temperature=0),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            )

        assert e.value.store_task_run is False
        assert len(httpx_mock.get_requests()) == 1

    async def test_reasoning(self, httpx_mock: HTTPXMock, xai_provider: XAIProvider):
        httpx_mock.add_response(
            url="https://api.x.ai/v1/chat/completions",
            json=fixtures_json("xai", "reasoning.json"),
        )
        completion = await xai_provider.complete(
            [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.GPT_4O_2024_08_06, max_tokens=10, temperature=0),
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
        )

        assert completion.reasoning_steps and completion.reasoning_steps[0].explaination
        assert completion.reasoning_steps[0].explaination.startswith("First, the user has provided")


class TestCheckValid:
    async def test_valid(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.x.ai/v1/chat/completions",
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

        provider = XAIProvider()
        assert await provider.check_valid()

        request = httpx_mock.get_requests()[0]
        body = json.loads(request.read().decode())
        assert body["messages"] == [{"content": "Respond with an empty json", "role": "user"}]


class TestStandardizeMessages:
    def test_standardize_messages(self) -> None:
        # test is a little verbose for no reason since the standar messages are xai messages....
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
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Can you also compare it with transcription of this one?"},
                    {"type": "input_audio", "input_audio": {"data": "data", "format": "wav"}},
                ],
            },
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
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Can you also compare it with transcription of this one?"},
                    {"type": "audio_url", "audio_url": {"url": "data:audio/wav;base64,data"}},
                ],
            },
        ]
        assert XAIProvider.standardize_messages(messages) == expected


class TestExtractStreamDelta:
    def test_extract_stream_delta(self, xai_provider: XAIProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        delta = xai_provider._extract_stream_delta(  # pyright: ignore[reportPrivateUsage]
            b'{"id":"chatcmpl-9iY4Gi66tnBpsuuZ20bUxfiJmXYQC","object":"chat.completion.chunk","created":1720404416,"model":"gpt-3.5-turbo-1106","system_fingerprint":"fp_44132a4de3","usage": {"prompt_tokens": 35, "completion_tokens": 109, "total_tokens": 144},"choices":[{"index":0,"delta":{"content":"\\"greeting\\": \\"Hello James!\\"\\n}"},"logprobs":null,"finish_reason":null}]}',
            raw_completion,
            {},
        )
        assert delta.content == '"greeting": "Hello James!"\n}'
        assert raw_completion.usage == LLMUsage(prompt_token_count=35, completion_token_count=109)

    def test_done(self, xai_provider: XAIProvider):
        raw_completion = RawCompletion(response="", usage=LLMUsage())
        delta = xai_provider._extract_stream_delta(b"[DONE]", raw_completion, {})  # pyright: ignore[reportPrivateUsage]
        assert delta.content == ""


class TestMaxTokensExceededError:
    async def test_max_tokens_exceeded_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.x.ai/v1/chat/completions",
            json=fixtures_json("xai", "finish_reason_length_completion.json"),
        )

        provider = XAIProvider()
        with pytest.raises(MaxTokensExceededError) as e:
            await provider.complete(
                [MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
                options=ProviderOptions(model=Model.GPT_4O_2024_08_06, max_tokens=10, temperature=0),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
            )
        assert (
            e.value.args[0]
            == "Model returned a response with a length finish reason, meaning the maximum number of tokens was exceeded."
        )
        assert e.value.store_task_run is True
        assert len(httpx_mock.get_requests()) == 1

    async def test_max_tokens_exceeded_error_stream(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.x.ai/v1/chat/completions",
            stream=IteratorStream(
                [
                    fixture_bytes("xai", "finish_reason_length_stream_completion.txt"),
                ],
            ),
        )
        provider = XAIProvider()
        with pytest.raises(MaxTokensExceededError) as e:
            async for _ in provider._single_stream(  # pyright: ignore reportPrivateUsage
                {"messages": [{"role": "user", "content": "Hello"}]},
                options=ProviderOptions(model=Model.GPT_4O_2024_08_06, max_tokens=10, temperature=0),
                output_factory=lambda x, _: StructuredOutput(json.loads(x)),
                partial_output_factory=lambda x: StructuredOutput(x),
                raw_completion=RawCompletion(response="", usage=LLMUsage()),
            ):
                pass

        assert (
            e.value.args[0]
            == "Model returned a response with a length finish reason, meaning the maximum number of tokens was exceeded."
        )
        assert e.value.store_task_run is True
        assert len(httpx_mock.get_requests()) == 1


class TestPrepareCompletion:
    async def test_role_before_content(self, xai_provider: XAIProvider):
        """Test that the 'role' key appears before 'content' in the prepared request."""
        request, _ = await xai_provider._prepare_completion(  # pyright: ignore[reportPrivateUsage]
            messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hello")],
            options=ProviderOptions(model=Model.GPT_3_5_TURBO_1106, max_tokens=10, temperature=0),
            stream=False,
        )

        # Get the first message from the request
        message = request["messages"][0]

        # Get the actual order of keys in the message dictionary
        keys = list(message.keys())

        # Find the indices of 'role' and 'content' in the keys list
        role_index = keys.index("role")
        content_index = keys.index("content")

        assert role_index < content_index, (
            "The 'role' key must appear before the 'content' key in the message dictionary"
        )


class TestUnknownError:
    @pytest.fixture
    def unknown_error_fn(self, xai_provider: XAIProvider):
        # Wrapper to avoid having to silence the private warning
        # and instantiate the response
        def _build_unknown_error(payload: str | dict[str, Any], status_code: int = 400):
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            res = Response(status_code=status_code, text=payload)
            return xai_provider._unknown_error(res)  # pyright: ignore[reportPrivateUsage]

        return _build_unknown_error

    def test_max_tokens_error(self, unknown_error_fn: Callable[[dict[str, Any]], ProviderError]):
        payload = {
            "code": "Client specified an invalid argument",
            "error": "This model's maximum prompt length is 131072 but the request contains 144543 tokens.",
        }
        assert isinstance(unknown_error_fn(payload), MaxTokensExceededError)

    def test_model_does_not_support_mode(self, unknown_error_fn: Callable[[dict[str, Any], int], ProviderError]):
        payload = {
            "code": "The system is not in a state required for the operation's execution",
            "error": 'Unsupported content-type encountered when downloading image. The only supported content types are ["image/jpeg", "image/jpg", "image/png"]',
        }
        assert isinstance(unknown_error_fn(payload, 412), ModelDoesNotSupportMode)

    def test_wrong_content(self, unknown_error_fn: Callable[[dict[str, Any]], ProviderError]):
        payload = {
            "code": "Client specified an invalid argument",
            "error": "Downloaded response does not contain a valid JPG or PNG image",
        }
        assert isinstance(unknown_error_fn(payload), ProviderInvalidFileError)

    def test_structured_generation_error(self, unknown_error_fn: Callable[[dict[str, Any]], ProviderError]):
        payload = {
            "code": "Client specified an invalid argument",
            "error": "Invalid request content: The model does not support formatted output but some have been specified in the request.",
        }
        assert isinstance(unknown_error_fn(payload), StructuredGenerationError)


class TestResponseFormat:
    def test_response_format_structured_output_disabled(self, xai_provider: XAIProvider):
        options = ProviderOptions(
            model=Model.GPT_4O_2024_08_06,
            max_tokens=10,
            temperature=0,
            structured_generation=False,
            output_schema={"type": "object"},
        )
        model_data = test_models.model_data(supports_structured_output=True)
        response_format = xai_provider._response_format(options, model_data)
        assert response_format is None

    def test_response_format_structured_output_enabled(self, xai_provider: XAIProvider):
        options = ProviderOptions(
            model=Model.GPT_4O_2024_08_06,
            max_tokens=10,
            temperature=0,
            structured_generation=True,
            output_schema={"type": "object"},
        )
        model_data = test_models.model_data(supports_structured_output=True)
        response_format = xai_provider._response_format(options, model_data)
        assert response_format is not None
        assert response_format.type == "json_schema"
        assert response_format.json_schema.json_schema == {"type": "object"}
