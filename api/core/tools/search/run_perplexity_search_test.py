import json
from typing import Generator
from unittest.mock import patch

import pytest
from pytest_httpx import HTTPXMock

from core.tools.search.run_perplexity_search import (
    PerplexityModel,
    _run_perplexity_search,  # pyright: ignore[reportPrivateUsage]
    remove_citations,
)

MOCK_PERPLEXITY_RESPONSE = {
    "id": "test_id",
    "model": "sonar-pro",
    "created": 1234567890,
    "usage": {
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "total_tokens": 30,
        "citation_tokens": 5,
        "num_search_queries": 1,
    },
    "citations": ["https://example.com/1", "https://example.com/2"],
    "object": "chat.completion",
    "choices": [
        {
            "index": 0,
            "finish_reason": "stop",
            "message": {"role": "assistant", "content": "Test response content"},
            "delta": {},
        },
    ],
}


@pytest.fixture(autouse=True)
def mock_env() -> Generator[None, None, None]:
    with patch(
        "core.tools.search.run_perplexity_search.os.environ",
        {"PERPLEXITY_API_KEY": "perplexity-api-key"},
    ):
        yield


async def test_run_perplexity_search_success(httpx_mock: HTTPXMock, mock_env: None) -> None:
    """Test successful Perplexity API call."""
    httpx_mock.add_response(
        method="POST",
        url="https://api.perplexity.ai/chat/completions",
        json=MOCK_PERPLEXITY_RESPONSE,
    )

    result = await _run_perplexity_search("test query", PerplexityModel.SONAR_PRO)
    expected_result = """Test response content

Citations:
[1] https://example.com/1
[2] https://example.com/2"""
    assert result == expected_result

    # Verify the request
    request = httpx_mock.get_request()
    assert request
    assert json.loads(request.content) == {
        "model": "sonar-pro",
        "messages": [
            {
                "role": "system",
                "content": "Be precise and concise.",
            },
            {"role": "user", "content": "test query"},
        ],
    }


async def test_run_perplexity_search_validation_error(httpx_mock: HTTPXMock) -> None:
    """Test handling of invalid API response."""
    invalid_response = {"invalid": "response"}
    httpx_mock.add_response(
        method="POST",
        url="https://api.perplexity.ai/chat/completions",
        json=invalid_response,
    )

    result = await _run_perplexity_search("test query", PerplexityModel.SONAR)
    assert json.loads(result) == invalid_response


async def test_run_perplexity_search_api_error(httpx_mock: HTTPXMock) -> None:
    """Test handling of API error response."""
    error_response = {"error": "API error"}
    httpx_mock.add_response(
        method="POST",
        url="https://api.perplexity.ai/chat/completions",
        json=error_response,
        status_code=500,
    )

    result = await _run_perplexity_search("test query", PerplexityModel.SONAR)
    assert result == json.dumps(
        {
            "error": "Error running Perplexity search: Server error '500 Internal Server Error' for url 'https://api.perplexity.ai/chat/completions'\nFor more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/500",
        },
    )


async def test_run_perplexity_search_no_citations(httpx_mock: HTTPXMock) -> None:
    """Test response formatting when there are no citations."""
    response_without_citations = {**MOCK_PERPLEXITY_RESPONSE, "citations": []}
    httpx_mock.add_response(
        method="POST",
        url="https://api.perplexity.ai/chat/completions",
        json=response_without_citations,
    )

    result = await _run_perplexity_search("test query", PerplexityModel.SONAR)
    assert result == "Test response content"


@pytest.mark.parametrize(
    "input_text,expected_output",
    [
        ("This is a text without citations", "This is a text without citations"),
        ("This is a text with [1] citation", "This is a text with citation"),
        ("Multiple citations [1][2][3] in text", "Multiple citations in text"),
        ("Citation [10] with double-digit number", "Citation with double-digit number"),
        ("Mixed citations [42] and [7] in different places", "Mixed citations and in different places"),
        ("", ""),
        ("[1]", ""),
        ("[1][2][3]", ""),
        ("Double  spaces  and [1] citation", "Double spaces and citation"),
        ("Citation [1]  [2]  [3] with multiple spaces", "Citation with multiple spaces"),
        ("Citation without spaces[1].", "Citation without spaces."),
    ],
)
def test_remove_citations(input_text: str, expected_output: str) -> None:
    """Test the remove_citations function with various input patterns."""
    result = remove_citations(input_text)
    assert result == expected_output
