"""
Tests that provider models are correctly supported by the API.
The tests require realistic API keys since they require a call to the provider API.
To avoid having to trigger an inference for every model, we check that models returned by the provider
are within the MODEL_ALIASES mapping. (the fact that MODEL_ALIASES are correctly used is covered by
unit and component tests)
"""

import os
from typing import Any

import httpx

from core.domain.models.model_datas_mapping import MODEL_ALIASES
from core.domain.models.models import Model


async def test_exhaustive_openai():
    async with httpx.AsyncClient() as client:
        res = await client.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        )
    res.raise_for_status()
    models: list[dict[str, Any]] = res.json()["data"]
    bypassed_keywords = [
        "dall-e",
        "whisper",
        "babbage",
        "text-embedding",
        "gpt-4o-realtime",
        "transcribe",
        "computer-use",
        "tts-",
        "codex-",
        "ft:",
        "search-preview",
        "davinci",
        "-tts",
        "chatgpt-",
        "-realtime-",
        "gpt-4o-mini-audio-preview",
        "o1-pro",
        "omni-",
        "o3-pro",
        "gpt-4.5-preview",
    ]
    model_ids = [model["id"] for model in models if not any(keyword in model["id"] for keyword in bypassed_keywords)]

    missing_models = [m for m in model_ids if m not in MODEL_ALIASES and m not in Model]
    assert not missing_models


async def test_exhaustive_anthropic():
    async with httpx.AsyncClient() as client:
        res = await client.get(
            "https://api.anthropic.com/v1/models",
            headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
        )
    res.raise_for_status()
    models: list[dict[str, Any]] = res.json()["data"]
    bypassed_keywords = ["claude-2.1", "claude-2.0"]

    model_ids = [model["id"] for model in models if not any(keyword in model["id"] for keyword in bypassed_keywords)]

    missing_models = [m for m in model_ids if m not in MODEL_ALIASES and m not in Model]
    assert not missing_models
