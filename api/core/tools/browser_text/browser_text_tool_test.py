import json
import os
import re
from pathlib import Path
from unittest.mock import patch

from pytest_httpx import HTTPXMock

from core.tools.browser_text.browser_text_tool import (
    FetchUrlContentResult,
    _fetch_url_content_firecrawl,  # pyright: ignore[reportPrivateUsage]
    browser_text,
    fetch_url_content_scrapingbee,  # pyright: ignore[reportPrivateUsage]
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SCRAPINGBEE_API_KEY = os.getenv("SCRAPINGBEE_API_KEY")


async def test_fetch_url_content_firecrawl_success(httpx_mock: HTTPXMock) -> None:
    """Test successful content fetch from FireCrawl."""
    url = "https://example.com"
    mock_response = {
        "success": True,
        "data": {
            "markdown": "# Test Content\nThis is test content",
            "metadata": {"statusCode": 200},
        },
    }

    httpx_mock.add_response(
        method="POST",
        url="https://api.firecrawl.dev/v1/scrape",
        json=mock_response,
    )

    result = await _fetch_url_content_firecrawl(url)
    assert isinstance(result, FetchUrlContentResult)
    assert result.error is None
    assert result.content
    assert json.loads(result.content) == mock_response
    req = httpx_mock.get_request()
    assert req
    assert req.method == "POST"
    assert req.url == "https://api.firecrawl.dev/v1/scrape"
    assert json.loads(req.content) == {"url": url, "formats": ["markdown"], "onlyMainContent": False}


async def test_fetch_url_content_firecrawl_failure(httpx_mock: HTTPXMock) -> None:
    """Test FireCrawl returning success: false."""
    url = "https://example.com"

    with open(FIXTURES_DIR / "firecrawl_refusal.json", "r") as f:  # noqa
        mock_response = json.load(f)

    httpx_mock.add_response(
        method="POST",
        url="https://api.firecrawl.dev/v1/scrape",
        json=mock_response,
    )

    result = await _fetch_url_content_firecrawl(url)
    assert isinstance(result, FetchUrlContentResult)
    assert result.error == "content_not_reachable"
    assert (
        result.content
        == "This website is no longer supported, please reach out to help@firecrawl.com for more info on how to activate it on your account."
    )


async def test_fetch_url_content_firecrawl_403(httpx_mock: HTTPXMock) -> None:
    """Test FireCrawl returning a 403 status code."""
    url = "https://example.com"

    with open(FIXTURES_DIR / "firecrawl_403.json", "r") as f:  # noqa
        mock_response = json.load(f)

    httpx_mock.add_response(
        method="POST",
        url="https://api.firecrawl.dev/v1/scrape",
        json=mock_response,
    )

    result = await _fetch_url_content_firecrawl(url)
    assert isinstance(result, FetchUrlContentResult)
    assert result.error == "content_not_reachable"
    assert result.content is None


async def test_fetch_url_content_firecrawl_unknown_error(httpx_mock: HTTPXMock) -> None:
    """Test FireCrawl returning an unknown error status code."""
    url = "https://example.com"
    mock_response = {
        "success": True,
        "data": {
            "markdown": "Error content",
            "metadata": {"statusCode": 500},
        },
    }

    httpx_mock.add_response(
        method="POST",
        url="https://api.firecrawl.dev/v1/scrape",
        json=mock_response,
    )

    result = await _fetch_url_content_firecrawl(url)
    assert isinstance(result, FetchUrlContentResult)
    assert result.error == "unknown_error"
    assert result.content is not None


async def test_fetch_url_content_scrapingbee_success(httpx_mock: HTTPXMock) -> None:
    """Test successful content fetch from ScrapingBee."""
    url = "https://example.com"
    mock_content = "<p>Hello, <a href='https://www.google.com/earth/'>world</a>!</p>"

    httpx_mock.add_response(
        method="GET",
        url=f"https://app.scrapingbee.com/api/v1?api_key={SCRAPINGBEE_API_KEY}&url={url}&stealth_proxy=true",
        text=mock_content,
        status_code=200,
    )

    result = await fetch_url_content_scrapingbee(url)
    assert isinstance(result, FetchUrlContentResult)
    assert result.error is None
    assert (
        result.content
        == """Hello, [world](https://www.google.com/earth/)!

"""
    )


async def test_fetch_url_content_scrapingbee_internal_error(httpx_mock: HTTPXMock) -> None:
    """Test ScrapingBee returning a 500 internal error."""
    url = "https://example.com"

    httpx_mock.add_response(
        method="GET",
        url=f"https://app.scrapingbee.com/api/v1?api_key={SCRAPINGBEE_API_KEY}&url={url}&stealth_proxy=true",
        status_code=500,
    )

    result = await fetch_url_content_scrapingbee(url)
    assert isinstance(result, FetchUrlContentResult)
    assert result.error == "internal_tool_error"
    assert result.content is None


async def test_fetch_url_content_scrapingbee_unknown_error(httpx_mock: HTTPXMock) -> None:
    """Test ScrapingBee returning an unknown error status code."""
    url = "https://example.com"

    httpx_mock.add_response(
        method="GET",
        url=f"https://app.scrapingbee.com/api/v1?api_key={SCRAPINGBEE_API_KEY}&url={url}&stealth_proxy=true",
        status_code=400,
        text="Error content",
    )

    result = await fetch_url_content_scrapingbee(url)
    assert isinstance(result, FetchUrlContentResult)
    assert result.error == "unknown_error"
    assert result.content == "Error content"


async def test_browser_text_success_firecrawl(httpx_mock: HTTPXMock) -> None:
    """Test browser_text successfully getting content from FireCrawl."""
    url = "https://example.com"
    mock_content = "# Test Content\nThis is test content"
    mock_response = {
        "success": True,
        "data": {
            "markdown": mock_content,
            "metadata": {"statusCode": 200},
        },
    }

    httpx_mock.add_response(
        url=re.compile(r"^https://app\.scrapingbee\.com.*"),
        status_code=400,
    )

    httpx_mock.add_response(
        method="POST",
        url="https://api.firecrawl.dev/v1/scrape",
        json=mock_response,
    )

    result = await browser_text(url)
    assert json.loads(result) == mock_response


async def test_browser_text_fallback_to_firecrawl(httpx_mock: HTTPXMock) -> None:
    """Test browser_text falling back to FireCrawl when ScrapingBee fails."""
    url = "https://example.com"
    mock_content = {
        "success": True,
        "data": {"markdown": "# Test Content", "metadata": {"statusCode": 200}},
    }

    # ScrapingBee fails
    httpx_mock.add_response(
        method="GET",
        url=f"https://app.scrapingbee.com/api/v1?api_key={SCRAPINGBEE_API_KEY}&url={url}&stealth_proxy=true",
        status_code=403,
        text="Error content",
    )

    httpx_mock.add_response(
        method="POST",
        url="https://api.firecrawl.dev/v1/scrape",
        json=mock_content,
    )

    result = await browser_text(url)
    assert json.loads(result) == mock_content


async def test_browser_text_all_services_fail(httpx_mock: HTTPXMock) -> None:
    """Test browser_text when all services fail."""
    url = "https://example.com"

    # FireCrawl fails with 403
    with open(FIXTURES_DIR / "firecrawl_403.json", "r") as f:  # noqa
        firecrawl_response = json.load(f)

    httpx_mock.add_response(
        method="POST",
        url="https://api.firecrawl.dev/v1/scrape",
        json=firecrawl_response,
    )

    # ScrapingBee fails with 500
    httpx_mock.add_response(
        method="GET",
        url=f"https://app.scrapingbee.com/api/v1?api_key={SCRAPINGBEE_API_KEY}&url={url}&stealth_proxy=true",
        status_code=500,
    )

    result = await browser_text(url)
    assert (
        result
        == "error fetching url content: https://example.com, no scraping service succeeded, latest error is:  content_not_reachable"
    )


async def test_tolerance_to_exceptions() -> None:
    """Test browser_text tolerating exceptions."""

    with (
        patch(
            "core.tools.browser_text.browser_text_tool._fetch_url_content_firecrawl",
            side_effect=Exception("Test exception"),
        ),
        patch(
            "core.tools.browser_text.browser_text_tool.fetch_url_content_scrapingbee",
            side_effect=Exception("Test exception"),
        ),
    ):
        url = "https://example.com"
        result = await browser_text(url)
        assert (
            result
            == "error fetching url content: https://example.com, no scraping service succeeded, latest error is: Test exception"
        )
