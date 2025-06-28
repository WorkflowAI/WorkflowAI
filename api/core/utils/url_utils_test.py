from unittest.mock import AsyncMock, patch

import pytest

from core.domain.url_content import URLContent, URLStatus
from core.utils.url_utils import extract_and_fetch_urls, fetch_urls_content, find_urls_in_text


@pytest.mark.parametrize(
    "text,expected",
    [
        (
            "Check this website http://example.com and this one https://test.org/page?query=123",
            ["http://example.com", "https://test.org/page?query=123"],
        ),
        (
            "No URLs here",
            [],
        ),
        (
            "",
            [],
        ),
        (
            "Multiple same URLs: https://duplicate.com https://duplicate.com",
            ["https://duplicate.com", "https://duplicate.com"],
        ),
        (
            "Visit example.com for more information",
            ["https://example.com"],
        ),
        (
            "My website is www.mysite.org",
            ["https://www.mysite.org"],
        ),
        (
            "Contact us at support@company.io or visit company.io/contact",
            ["https://company.io/contact"],
        ),
        (
            "Email me at user@domain.com but check out domain.co.uk",
            ["https://domain.co.uk"],
        ),
        (
            "Multiple formats: github.com, https://gitlab.com, and www.bitbucket.org",
            ["https://github.com", "https://gitlab.com", "https://www.bitbucket.org"],
        ),
        (
            "I want to scrape from https://www.agriaffaires.co.uk/used/2/farm-tractor.html",
            ["https://www.agriaffaires.co.uk/used/2/farm-tractor.html"],
        ),
        (  # With trailing quote
            "I want to scrape from https://www.agriaffaires.co.uk/used/2/farm-tractor.html'",
            ["https://www.agriaffaires.co.uk/used/2/farm-tractor.html"],
        ),
        (  # With default no-url-fetch tags
            "Check https://example.com and <no-url-fetch>ignore https://ignored.com</no-url-fetch> but include https://included.com",
            ["https://example.com", "https://included.com"],
        ),
        (  # Multiple no-url-fetch regions
            "Visit example.com <no-url-fetch>skip github.com and gitlab.com</no-url-fetch> also check bitbucket.org <no-url-fetch>ignore stackoverflow.com</no-url-fetch>",
            ["https://example.com", "https://bitbucket.org"],
        ),
        (  # Nested content in no-url-fetch tags
            "Here's a URL: example.com <no-url-fetch>This text contains test.com and other-site.org that should be ignored</no-url-fetch> end with final.com",
            ["https://example.com", "https://final.com"],
        ),
    ],
)
def test_find_urls_in_text(text: str, expected: list[str]) -> None:
    """Test that URLs are correctly extracted from text."""
    result = find_urls_in_text(text)
    assert result == expected


@pytest.mark.parametrize(
    "text,ignore_tag,expected",
    [
        (
            "Check https://example.com and <custom-ignore>ignore https://ignored.com</custom-ignore> but include https://included.com",
            "custom-ignore",
            ["https://example.com", "https://included.com"],
        ),
        (
            "Visit example.com <skip-url>skip github.com</skip-url> and bitbucket.org",
            "skip-url",
            ["https://example.com", "https://bitbucket.org"],
        ),
        (
            "All URLs should be found: example.com github.com",
            "non-existent-tag",
            ["https://example.com", "https://github.com"],
        ),
    ],
)
def test_find_urls_in_text_custom_ignore_tag(text: str, ignore_tag: str, expected: list[str]) -> None:
    """Test that URLs are correctly extracted with custom ignore tags."""
    result = find_urls_in_text(text, ignore_tag=ignore_tag)
    assert result == expected


@pytest.mark.asyncio
async def test_fetch_urls_content_empty_list() -> None:
    """Test that fetch_urls_content returns an empty list when given an empty list."""
    result = await fetch_urls_content([])
    assert result == []


@pytest.mark.asyncio
# pyright: ignore[reportPrivateUsage]
@patch("core.utils.url_utils._fetch_single_url_content")
async def test_fetch_urls_content_success(mock_fetch: AsyncMock) -> None:
    """Test that fetch_urls_content returns the expected URLContent objects."""
    # Set the return values for the mock
    mock_fetch.side_effect = [
        URLContent(
            url="https://example.com",
            content="Content from https://example.com",
            status=URLStatus.REACHABLE,
        ),
        URLContent(
            url="https://test.org",
            content="Content from https://test.org",
            status=URLStatus.REACHABLE,
        ),
    ]

    urls = ["https://example.com", "https://test.org"]
    result = await fetch_urls_content(urls)

    # Verify _fetch_single_url_content was called for each URL
    assert mock_fetch.call_count == 2
    mock_fetch.assert_any_call("https://example.com")
    mock_fetch.assert_any_call("https://test.org")

    # Verify the result contains the expected URLContent objects
    assert len(result) == 2
    assert result[0] == URLContent(
        url="https://example.com",
        content="Content from https://example.com",
        status=URLStatus.REACHABLE,
    )
    assert result[1] == URLContent(
        url="https://test.org",
        content="Content from https://test.org",
        status=URLStatus.REACHABLE,
    )


@pytest.mark.asyncio
# pyright: ignore[reportPrivateUsage]
@patch("core.utils.url_utils._fetch_single_url_content")
async def test_fetch_urls_content_with_exception(mock_fetch: AsyncMock) -> None:
    """Test that fetch_urls_content handles exceptions properly."""
    # Set a successful return and an exception
    mock_fetch.side_effect = [
        URLContent(
            url="https://example.com",
            content="Content from https://example.com",
            status=URLStatus.REACHABLE,
        ),
        Exception("Failed to fetch content"),
    ]

    urls = ["https://example.com", "https://error.org"]

    # Patch the logger to avoid printing exceptions during the test
    with patch("core.utils.url_utils.logger.exception"):
        result = await fetch_urls_content(urls)

    # Verify _fetch_single_url_content was called for each URL
    assert mock_fetch.call_count == 2

    # Verify the result contains both URLs, one reachable and one unreachable
    assert len(result) == 2
    assert result[0] == URLContent(
        url="https://example.com",
        content="Content from https://example.com",
        status=URLStatus.REACHABLE,
    )
    assert result[1] == URLContent(
        url="https://error.org",
        content=None,
        status=URLStatus.UNREACHABLE,
    )


@pytest.mark.asyncio
@patch("core.utils.url_utils.browser_text_with_proxy_setting", new_callable=AsyncMock)
async def test_fetch_single_url_content_success(mock_browser_text: AsyncMock) -> None:
    """Test that _fetch_single_url_content returns URLContent with the right status."""
    from core.utils.url_utils import _fetch_single_url_content  # pyright: ignore[reportPrivateUsage]

    # Test successful content fetch
    mock_browser_text.return_value = "Content from https://example.com"

    result = await _fetch_single_url_content("https://example.com")

    assert result == URLContent(
        url="https://example.com",
        content="Content from https://example.com",
        status=URLStatus.REACHABLE,
    )

    # Test empty content case
    mock_browser_text.return_value = ""

    result = await _fetch_single_url_content("https://empty.org")

    assert result == URLContent(
        url="https://empty.org",
        content=None,
        status=URLStatus.UNREACHABLE,
    )

    # Test exception case
    mock_browser_text.side_effect = Exception("Failed to fetch")

    with patch("core.utils.url_utils.logger.exception"):
        result = await _fetch_single_url_content("https://error.org")

    assert result == URLContent(
        url="https://error.org",
        content=None,
        status=URLStatus.UNREACHABLE,
    )


@pytest.mark.asyncio
@patch("core.utils.url_utils.find_urls_in_text")
@patch("core.utils.url_utils.fetch_urls_content")
async def test_extract_and_fetch_urls(mock_fetch_urls: AsyncMock, mock_find_urls: AsyncMock) -> None:
    """Test that extract_and_fetch_urls combines URL extraction and content fetching."""
    # Set up mocks
    mock_find_urls.return_value = ["https://example.com", "https://test.org"]
    mock_fetch_urls.return_value = [
        URLContent(
            url="https://example.com",
            content="Content from https://example.com",
            status=URLStatus.REACHABLE,
        ),
        URLContent(
            url="https://test.org",
            content="Content from https://test.org",
            status=URLStatus.REACHABLE,
        ),
    ]

    # Call the function with some text
    result = await extract_and_fetch_urls("Check these sites: example.com test.org")

    # Verify find_urls_in_text was called with the input text and default ignore_tag
    mock_find_urls.assert_called_once_with("Check these sites: example.com test.org", ignore_tag="no-url-fetch")

    # Verify fetch_urls_content was called with the URLs returned by find_urls_in_text
    mock_fetch_urls.assert_called_once_with(["https://example.com", "https://test.org"])

    # Verify the result contains the expected URLContent objects
    assert len(result) == 2
    assert result[0] == URLContent(
        url="https://example.com",
        content="Content from https://example.com",
        status=URLStatus.REACHABLE,
    )
    assert result[1] == URLContent(
        url="https://test.org",
        content="Content from https://test.org",
        status=URLStatus.REACHABLE,
    )


@pytest.mark.asyncio
@patch("core.utils.url_utils.find_urls_in_text")
@patch("core.utils.url_utils.fetch_urls_content")
async def test_extract_and_fetch_urls_custom_ignore_tag(mock_fetch_urls: AsyncMock, mock_find_urls: AsyncMock) -> None:
    """Test that extract_and_fetch_urls passes through custom ignore_tag parameter."""
    # Set up mocks
    mock_find_urls.return_value = ["https://example.com"]
    mock_fetch_urls.return_value = [
        URLContent(
            url="https://example.com",
            content="Content from https://example.com",
            status=URLStatus.REACHABLE,
        ),
    ]

    # Call the function with a custom ignore_tag
    result = await extract_and_fetch_urls("Check example.com <custom>ignore test.org</custom>", ignore_tag="custom")

    # Verify find_urls_in_text was called with the custom ignore_tag
    mock_find_urls.assert_called_once_with("Check example.com <custom>ignore test.org</custom>", ignore_tag="custom")

    # Verify fetch_urls_content was called with the URLs returned by find_urls_in_text
    mock_fetch_urls.assert_called_once_with(["https://example.com"])

    # Verify the result contains the expected URLContent objects
    assert len(result) == 1
    assert result[0] == URLContent(
        url="https://example.com",
        content="Content from https://example.com",
        status=URLStatus.REACHABLE,
    )
