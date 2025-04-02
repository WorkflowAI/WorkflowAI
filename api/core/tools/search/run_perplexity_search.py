import json
import logging
import os
import re
from collections.abc import AsyncIterator
from enum import Enum
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from core.utils.redis_cache import redis_cached_generator_last_chunk
from core.utils.streams import standard_wrap_sse
from core.utils.strings import remove_empty_lines

TIMEOUT_SECONDS = 60
PERPLEXITY_API_KEY = os.environ["PERPLEXITY_API_KEY"]

_logger = logging.getLogger(__name__)


class PerplexityModel(Enum):
    SONAR_REASONING = "sonar-reasoning"
    SONAR_PRO = "sonar-pro"
    SONAR = "sonar"


class PerplexityMessage(BaseModel):
    role: str
    content: str


class PerplexityChoice(BaseModel):
    index: int
    finish_reason: str | None = None
    message: PerplexityMessage
    delta: dict[str, Any] | None = None


class PerplexityResponse(BaseModel):
    class Usage(BaseModel):
        # TODO: Implement per token pricing for Perplexity
        prompt_tokens: int | None = None
        completion_tokens: int | None = None
        total_tokens: int | None = None
        citation_tokens: int | None = None
        num_search_queries: int | None = None

    id: str | None = None
    model: str | None = None
    created: int | None = None
    usage: Usage | None = None
    citations: list[str] | None = None
    object: str | None = None
    choices: list[PerplexityChoice]

    def __str__(self) -> str:
        content = self.choices[0].message.content

        if self.citations:
            content += "\n\nCitations:"
            for index, citation in enumerate(self.citations):
                content += f"\n[{index + 1}] {citation}"

        return content


async def run_perplexity_search_default(query: str) -> str:
    return await _run_perplexity_search(query, PerplexityModel.SONAR)


async def run_perplexity_search_sonar_reasoning(query: str) -> str:
    return await _run_perplexity_search(query, PerplexityModel.SONAR_REASONING)


async def run_perplexity_search_sonar_pro(query: str) -> str:
    return await _run_perplexity_search(query, PerplexityModel.SONAR_PRO)


async def _run_perplexity_search(query: str, model: PerplexityModel) -> str:
    """Runs a Perplexity search and returns the results in JSON format."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                "accept": "application/json",
                "content-type": "application/json",
            },
            json={
                "model": model.value,
                "messages": [
                    {
                        "role": "system",
                        "content": "Be precise and concise.",  # Default system prompt from https://docs.perplexity.ai/guides/getting-started
                    },
                    {"role": "user", "content": query},
                ],
            },
            timeout=TIMEOUT_SECONDS,
        )

        try:
            response.raise_for_status()
        except Exception as e:
            _logger.exception("Error running Perplexity search", exc_info=e)
            return json.dumps({"error": f"Error running Perplexity search: {e}"})

        try:
            response_model = PerplexityResponse.model_validate(response.json())
            return str(response_model)
        except ValidationError as e:
            _logger.warning(
                "Non-parseable Perplexity response, return raw response dump",
                exc_info=e,
            )
            return response.text


def remove_citations(text: str) -> str:
    """
    Remove citations in the format [number] from the text and clean up resulting double spaces.

    Args:
        text (str): The input text.

    Returns:
        str: The text with citations removed and double spaces cleaned up.
    """
    # First remove the citations
    text_without_citations = re.sub(r"\[\d+\]", "", text)
    # Then replace any double spaces with single spaces
    return re.sub(r"  +", " ", text_without_citations)


@redis_cached_generator_last_chunk()
async def stream_perplexity_search(query: str, max_tokens: int | None = None) -> AsyncIterator[str]:
    """Runs a Perplexity search and returns the results in JSON format.

    As it's a streaming version of the Perplexity search, it's fit for use as a tool in a run.
    """

    body: dict[str, Any] = {
        "model": PerplexityModel.SONAR_PRO.value,
        "messages": [
            {
                "role": "system",
                "content": "Be precise and concise.",  # Default system prompt from https://docs.perplexity.ai/guides/getting-started
            },
            {"role": "user", "content": query},
        ],
        "web_search_options": {
            "search_context_size": "high",
        },
        "stream": True,
    }

    if max_tokens:
        body["max_tokens"] = max_tokens

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                "accept": "application/json",
                "content-type": "application/json",
            },
            json=body,
            timeout=TIMEOUT_SECONDS,
        ) as response:
            if response.status_code != 200:
                raise Exception(f"Perplexity search failed with status code {response.status_code}")

            async for chunk in standard_wrap_sse(response.aiter_bytes()):
                yield remove_empty_lines(
                    remove_citations(
                        PerplexityResponse.model_validate(json.loads(chunk.decode("utf-8"))).choices[0].message.content,
                    ),
                )
