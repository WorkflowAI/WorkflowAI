import json

import pytest
from httpx_mock import HTTPXMock

from core.domain.message import MessageDeprecated
from core.domain.models import Model
from core.providers.base.provider_options import ProviderOptions
from core.providers.base.structured_output import StructuredOutput
from core.providers.mistral.mistral_provider import MistralAIProvider


class TestMistralStructuredOutput:
    async def test_structured_output_request_format(self, httpx_mock: HTTPXMock):
        """Test that structured output generates the correct request format."""
        httpx_mock.add_response(
            url="https://api.mistral.ai/v1/chat/completions",
            json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "mistral-large-latest",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '{"name": "John", "age": 30}',
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                },
            },
        )

        provider = MistralAIProvider()

        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name", "age"],
        }

        await provider.complete(
            [
                MessageDeprecated(
                    role=MessageDeprecated.Role.USER,
                    content="Extract name and age from: John is 30 years old",
                ),
            ],
            options=ProviderOptions(
                model=Model.MISTRAL_LARGE_2411,
                max_tokens=100,
                temperature=0,
                task_name="test_task",
                structured_generation=True,
                output_schema=schema,
            ),
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
        )

        # Verify the request was made with structured output format
        request = httpx_mock.get_requests()[0]
        assert request.method == "POST"
        body = json.loads(request.read().decode())
        
        # Check that response_format is json_schema
        assert body["response_format"]["type"] == "json_schema"
        assert "json_schema" in body["response_format"]
        
        # Check the json_schema structure
        json_schema = body["response_format"]["json_schema"]
        assert json_schema["strict"] is True
        assert "test_task" in json_schema["name"]
        assert "schema" in json_schema
        
        # Verify the schema has been processed
        processed_schema = json_schema["schema"]
        assert processed_schema["type"] == "object"
        assert "additionalProperties" in processed_schema
        assert processed_schema["additionalProperties"] is False

    async def test_fallback_to_json_object_when_structured_disabled(self, httpx_mock: HTTPXMock):
        """Test that it falls back to json_object when structured_generation is disabled."""
        httpx_mock.add_response(
            url="https://api.mistral.ai/v1/chat/completions",
            json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "mistral-large-latest",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '{"name": "John", "age": 30}',
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                },
            },
        )

        provider = MistralAIProvider()

        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name", "age"],
        }

        await provider.complete(
            [
                MessageDeprecated(
                    role=MessageDeprecated.Role.USER,
                    content="Extract name and age from: John is 30 years old",
                ),
            ],
            options=ProviderOptions(
                model=Model.MISTRAL_LARGE_2411,
                max_tokens=100,
                temperature=0,
                structured_generation=False,  # Disabled
                output_schema=schema,
            ),
            output_factory=lambda x, _: StructuredOutput(json.loads(x)),
        )

        # Verify the request was made with json_object format
        request = httpx_mock.get_requests()[0]
        assert request.method == "POST"
        body = json.loads(request.read().decode())
        
        # Check that response_format is json_object (fallback)
        assert body["response_format"]["type"] == "json_object"

    async def test_text_format_when_no_schema(self, httpx_mock: HTTPXMock):
        """Test that it uses text format when no output schema is provided."""
        httpx_mock.add_response(
            url="https://api.mistral.ai/v1/chat/completions",
            json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "mistral-large-latest",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Hello, how can I help you?",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                },
            },
        )

        provider = MistralAIProvider()

        await provider.complete(
            [
                MessageDeprecated(
                    role=MessageDeprecated.Role.USER,
                    content="Hello",
                ),
            ],
            options=ProviderOptions(
                model=Model.MISTRAL_LARGE_2411,
                max_tokens=100,
                temperature=0,
                # No output_schema provided
            ),
            output_factory=lambda x, _: x,
        )

        # Verify the request was made with text format
        request = httpx_mock.get_requests()[0]
        assert request.method == "POST"
        body = json.loads(request.read().decode())
        
        # Check that response_format is text
        assert body["response_format"]["type"] == "text"