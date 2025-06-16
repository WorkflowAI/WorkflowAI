import os

import pytest
from pytest_httpx import IteratorStream

from core.domain.models import Model
from core.domain.models.providers import Provider
from tests.component.common import (
    IntegrationTestClient,
    mock_gemini_call,
)
from tests.utils import approx, fixture_bytes, fixtures_json


@pytest.mark.skip(reason="Google no longer returns the thinking mode")
async def test_gemini_thinking_streaming(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    test_client.httpx_mock.add_response(
        url=f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-thinking-exp-01-21:streamGenerateContent?key={os.environ.get('GEMINI_API_KEY')}&alt=sse",
        stream=IteratorStream(fixture_bytes("gemini", "streamed_response_thoughts.txt").splitlines(keepends=True)),
    )
    chunks = [c async for c in test_client.stream_run_task_v1(task, model=Model.GEMINI_2_0_FLASH_THINKING_EXP_0121)]
    assert chunks

    assert chunks[1]["reasoning_steps"] == [
        {
            "step": 'The request asks for a greeting and a JSON response with "greeting" as the key.  This',
        },
    ]
    assert chunks[2]["reasoning_steps"] == [
        {
            "step": 'The request asks for a greeting and a JSON response with "greeting" as the key.  This is straightforward.\n\n1. **Greeting:**  Choose a friendly and common greeting.',
        },
    ]

    assert len(chunks[-1]["reasoning_steps"]) == 1
    assert len(chunks[-1]["reasoning_steps"][0]["step"]) == 608
    assert chunks[-1]["task_output"]["greeting"] == "Hello there!"


@pytest.mark.skip(reason="Google no longer returns the thinking mode")
async def test_thinking_mode_model(test_client: IntegrationTestClient):
    task = await test_client.create_task()

    test_client.httpx_mock.add_response(
        url=f"https://generativelanguage.googleapis.com/v1alpha/models/gemini-2.0-flash-thinking-exp-01-21:generateContent?key={os.environ.get('GEMINI_API_KEY')}",
        json=fixtures_json("gemini", "completion_thoughts_gemini_2.0_flash_thinking_mode.json"),
    )

    run = await test_client.run_task_v1(
        task,
        model=Model.GEMINI_2_0_FLASH_THINKING_EXP_0121,
    )

    assert (
        run["task_output"]["greeting"]
        == "Explaining how AI works is a bit like explaining how a human brain works – it's incredibly complex and the exact mechanisms are still being researched. While the underlying mechanisms can be complex, the fundamental principles of data-driven learning and pattern recognition remain central.\n"
    )

    assert (
        run["reasoning_steps"][0]["step"]
        == 'My thinking process for generating the explanation of how AI works went something like this:\n\n1. **Deconstruct the Request:** The user asked "Explain how AI works." This is a broad question, so a comprehensive yet accessible explanation is needed. I need to cover the core principles without getting bogged down in overly technical jargon.\n\n2. **Identify Key Concepts:**  I immediately thought of the fundamental building blocks of AI. This led to the identification of:\n'
    )


async def test_prompt_cached_tokens(test_client: IntegrationTestClient):
    """Check that price is calculated correctly for cached tokens"""
    task = await test_client.create_task()

    mock_gemini_call(
        httpx_mock=test_client.httpx_mock,
        model=Model.GEMINI_2_5_PRO_PREVIEW_0605,
        usage={
            "promptTokenCount": 1_000,
            "candidatesTokenCount": 2_000,
            "cachedContentTokenCount": 750,
        },
    )

    run = await test_client.run_task_v1(task, model=Model.GEMINI_2_5_PRO_PREVIEW_0605, provider=Provider.GOOGLE_GEMINI)

    assert run["cost_usd"] == approx(
        (250 * 1.25 / 1_000_000) + (750 * 0.25 * 1.25 / 1_000_000) + (2_000 * 10 / 1_000_000),
    )
