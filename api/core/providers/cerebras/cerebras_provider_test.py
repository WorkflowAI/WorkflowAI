import json
import unittest

import pytest
from pytest_httpx import HTTPXMock, IteratorStream

from core.domain.message import MessageDeprecated
from core.domain.models import Model, Provider
from core.domain.structured_output import StructuredOutput
from core.providers.base.provider_options import ProviderOptions
from core.providers.cerebras.cerebras_domain import Choice, ChoiceMessage, CompletionResponse, Usage
from core.providers.cerebras.cerebras_provider import CerebrasConfig, CerebrasProvider


class TestCerebrasProvider(unittest.TestCase):
    def test_name(self):
        self.assertEqual(CerebrasProvider.name(), Provider.CEREBRAS)

    def test_required_env_vars(self):
        self.assertEqual(CerebrasProvider.required_env_vars(), ["CEREBRAS_API_KEY"])


@pytest.fixture(scope="function")
def cerebras_provider():
    return CerebrasProvider(config=CerebrasConfig(api_key="token"))


class TestBuildRequest:
    def test_build_request(self, cerebras_provider: CerebrasProvider):
        request = cerebras_provider._build_request(  # pyright: ignore [reportPrivateUsage]
            messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Hi")],
            options=ProviderOptions(model=Model.LLAMA_3_1_8B, max_tokens=5, temperature=0),
            stream=False,
        )
        dumped = request.model_dump()
        assert dumped["messages"][0]["role"] == "user"
        assert dumped["messages"][0]["content"] == "Hi"
        assert dumped["max_tokens"] == 5
        assert dumped["model"] == "llama3.1-8b"


class TestComplete:
    async def test_complete(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.cerebras.ai/v1/chat/completions",
            json=CompletionResponse(
                id="1",
                choices=[Choice(message=ChoiceMessage(content="hello"))],
                usage=Usage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            ).model_dump(),
        )

        provider = CerebrasProvider()

        out = await provider.complete(
            [MessageDeprecated(role=MessageDeprecated.Role.USER, content="hi")],
            options=ProviderOptions(model=Model.LLAMA_3_1_8B, max_tokens=5, temperature=0),
            output_factory=lambda x, _: StructuredOutput(x),
        )

        assert out.output == "hello"
        request = httpx_mock.get_requests()[0]
        body = json.loads(request.read().decode())
        assert body["stream"] is False

    async def test_stream(self, httpx_mock: HTTPXMock):
        stream_events = [
            b'data: {"id":"1","choices":[{"delta":{"content":"he"}}]}\n\n',
            b'data: {"id":"1","choices":[{"delta":{"content":"llo"},"finish_reason":"stop"}]}\n\n',
            b"data: [DONE]",
        ]
        httpx_mock.add_response(
            url="https://api.cerebras.ai/v1/chat/completions",
            stream=IteratorStream(stream_events),
        )

        provider = CerebrasProvider()
        streamer = provider.stream(
            [MessageDeprecated(role=MessageDeprecated.Role.USER, content="hi")],
            options=ProviderOptions(model=Model.LLAMA_3_1_8B, max_tokens=5, temperature=0),
            output_factory=lambda x, _: StructuredOutput(x),
            partial_output_factory=lambda x: StructuredOutput(x),
        )
        chunks = [c async for c in streamer]
        assert chunks[-1].output == "hello"


class TestListModels:
    async def test_list_models(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.cerebras.ai/v1/models",
            json={"data": [
                {"id": "llama3.1-8b"},
                {"id": "llama-3.3-70b"},
                {"id": "llama-4-scout-17b-16e-instruct"},
                {"id": "qwen-3-32b"},
            ]},
        )

        provider = CerebrasProvider()
        models = await provider.list_models()
        assert models == [
            "llama3.1-8b",
            "llama-3.3-70b",
            "llama-4-scout-17b-16e-instruct",
            "qwen-3-32b",
        ]
