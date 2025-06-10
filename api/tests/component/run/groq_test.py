from typing import Any

from pytest_httpx import IteratorStream

from tests.component.common import IntegrationTestClient


async def test_invalid_json_response(test_client: IntegrationTestClient):
    """Groq uses text mode since the JSON mode often fails. this test checks that text mode is handled correctly"""
    task = await test_client.create_agent_v1(output_schema={})

    test_client.httpx_mock.add_response(
        url="https://api.groq.com/openai/v1/chat/completions",
        stream=IteratorStream(
            [
                b'data: {"id":"chatcmpl-96c29a0b-2a71-46fd-af4d-62d783cfc693","object":"chat.completion.chunk","created":1722540285,"model":"llama-3.1-70b-versatile","system_fingerprint":null,"choices":[{"index":0,"delta":{"role":"assistant","content":""},"logprobs":null,"finish_reason":null}],"x_groq":{"id":"req_01j47pdq9cerqbp0w6bzqwmytq","queue_length":1}}\n\ndata: {"id":"chatcmpl-96c29a0b-2a71-46fd-af4d-62d783cfc693","object":"chat.completion.chunk","created":1722540285,"model":"llama-3.1-70b-versatile","system_fingerprint":"fp_b3ae7e594e","choices":[{"index":0,"delta":{"content":"```"},"logprobs":null,"finish_reason":null}]}\n\n',
                b'data: {"id":"chatcmpl-96c29a0b-2a71-46fd-af4d-62d783cfc693","object":"chat.completion.chunk","created":1722540285,"model":"llama-3.1-70b-versatile","system_fingerprint":"fp_b3ae7e594e","choices":[{"index":0,"delta":{"content":"json"},"logprobs":null,"finish_reason":null}]}\n\n',
                b'data: {"id":"chatcmpl-96c29a0b-2a71-46fd-af4d-62d783cfc693","object":"chat.completion.chunk","created":1722540285,"model":"llama-3.1-70b-versatile","system_fingerprint":"fp_b3ae7e594e","choices":[{"index":0,"delta":{"content":" {"},"logprobs":null,"finish_reason":null}]}\n\n',
                b'data: {"id":"chatcmpl-96c29a0b-2a71-46fd-af4d-62d783cfc693","object":"chat.completion.chunk","created":1722540285,"model":'
                b'"llama-3.1-70b-versatile","system_fingerprint":"fp_b3ae7e594e","choices":[{"index":0,"delta":{"content":" \\""},"logprobs":null,"finish_reason":null}]}\n\n',
                b'data: {"id":"chatcmpl-96c29a0b-2a71-46fd-af4d-62d783cfc693","object":"chat.completion.chunk","created":1722540285,"model":"llama-3.1-70b-versatile","system_fingerprint":"fp_b3ae7e594e","choices":[{"index":0,"delta":{"content":"sent"},"logprobs":null,"finish_reason":null}]}\n\n',
                b'data: {"id":"chatcmpl-96c29a0b-2a71-46fd-af4d-62d783cfc693","object":"chat.completion.chunk","created":1722540285,"model":"llama-3.1-70b-versatile","system_fingerprint":"fp_b3ae7e594e","choices":[{"index":0,"delta":{"content":"iment"},"logprobs":null,"finish_reason":null}]}\n\n',
                b'data: {"id":"chatcmpl-96c29a0b-2a71-46fd-af4d-62d783cfc693","object":"chat.completion.chunk","created":1722540285,"model":"llama-3.1-70b-versatile","system_fingerprint":"fp_b3ae7e594e","choices":[{"index":0,"delta":{"content":"\\":"},"logprobs":null,"finish_reason":null}]}\n\n',
                b'data: {"id":"chatcmpl-96c29a0b-2a71-46fd-af4d-62d783cfc693","object":"chat.completion.chunk","created":1722540285,"model":"llama-3.1-70b-versatile","system_fingerprint":"fp_b3ae7e594e","choices":[{"index":0,"delta":{"content":" \\""},"logprobs":null,"finish_reason":null}]}\n\n',
                b'data: {"id":"chatcmpl-96c29a0b-2a71-46fd-af4d-62d783cfc693","object":"chat.completion.chunk","created":1722540285,"model":"llama-3.1-70b-versatile","system_fingerprint":"fp_b3ae7e594e","choices":[{"index":0,"delta":{"content":"positive\\""},"logprobs":null,"finish_reason":null}]}\n\n',
                b'data: {"id":"chatcmpl-96c29a0b-2a71-46fd-af4d-62d783cfc693","object":"chat.completion.chunk","created":1722540285,"model":"llama-3.1-70b-versatile","system_fingerprint":"fp_b3ae7e594e","choices":[{"index":0,"delta":{"content":"}```"},"logprobs":null,"finish_reason":null}]}\n\n',
                b'data: {"id":"chatcmpl-96c29a0b-2a71-46fd-af4d-62d783cfc693","object":"chat.completion.chunk","created":1722540285,"model":"llama-3.1-70b-versatile","system_fingerprint":"fp_b3ae7e594e","choices":[{"index":0,"delta":{},"logprobs":null,"finish_reason":"stop"}],"x_groq":{"id":"req_01j47pdq9cerqbp0w6bzqwmytq","usage":{"queue_time":0.019005437000000007,"prompt_tokens":244,"prompt_time":0.058400983,"completion_tokens":15,"completion_time":0.06,"total_tokens":259,"total_time":0.11840098299999999}}}\n\n',
                b"data: [DONE]",
            ],
        ),
    )

    chunk: Any = None
    async for chunk in test_client.stream_run_task_v1(
        task,
        version={"model": "llama4-scout-instruct-fast", "provider": "groq"},
    ):
        assert chunk
        assert "error" not in chunk

    assert chunk["task_output"] == {"sentiment": "positive"}
