import logging
import os
from typing import Literal, NamedTuple, TypeAlias

import html2text
import httpx

TIMEOUT_SECONDS = 60

logger = logging.getLogger(__name__)


class FetchUrlContentResult(NamedTuple):
    content: str | None
    error: Literal["content_not_reachable", "internal_tool_error", "unknown_error"] | None


# Stealth is more "solid" but much slower, use "premium" if you want a good balance between speed and reliability
ProxySetting: TypeAlias = Literal["classic", "premium", "stealth"]


async def _fetch_url_content_firecrawl(url: str, proxy_setting: ProxySetting = "stealth") -> FetchUrlContentResult:
    """Browses the URL passed as argument and extracts the web page content in markdown format."""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {os.environ['FIRECRAWL_API_KEY']}"},
            json={"url": url, "formats": ["markdown"], "onlyMainContent": False},
            timeout=TIMEOUT_SECONDS,
        )
    reponse_json = response.json()

    if not reponse_json.get("success", False):
        return FetchUrlContentResult(content=reponse_json.get("error", None), error="content_not_reachable")

    status_code = reponse_json.get("data", {}).get("metadata", {}).get("statusCode", 200)
    if status_code == 200:
        return FetchUrlContentResult(content=response.text, error=None)

    if status_code == 403:
        return FetchUrlContentResult(content=None, error="content_not_reachable")

    return FetchUrlContentResult(content=response.text, error="unknown_error")


async def fetch_url_content_scrapingbee(
    url: str,
    proxy_setting: ProxySetting = "stealth",
) -> FetchUrlContentResult:
    """Browses the URL passed as argument and extracts the web page content in markdown format."""

    body_params = {
        "api_key": os.environ["SCRAPINGBEE_API_KEY"],
        "url": url,
    }

    if proxy_setting == "stealth":
        # this proxy is required to have a better rate of success, without it around 15% of scraping request fail.
        body_params["stealth_proxy"] = "true"
    elif proxy_setting == "premium":
        body_params["premium_proxy"] = "true"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://app.scrapingbee.com/api/v1",
            params=body_params,
            timeout=TIMEOUT_SECONDS,
        )
    if response.status_code == 200:
        raw_html = response.text
        clean_text = ""
        try:
            html_converter = html2text.HTML2Text()
            clean_text = html_converter.handle(raw_html)
        except Exception:
            logger.exception("Error converting HTML to text", extra={"url": url})
        return FetchUrlContentResult(content=clean_text, error=None)
    if response.status_code == 500:
        return FetchUrlContentResult(content=None, error="internal_tool_error")
    return FetchUrlContentResult(content=response.text, error="unknown_error")


async def browser_text_with_proxy_setting(url: str, proxy_setting: ProxySetting = "stealth") -> str:
    """Browses the URL passed as argument and extracts the web page content in markdown format.

    Not DRY at all from the browser_text above, but we wan to keep  "browser_text" untouched because it's an internal tool for agents.
    """

    pipeline = [
        fetch_url_content_scrapingbee,  # ScrapingBee is first because we have less failed request with ScrapingBee.
        _fetch_url_content_firecrawl,
    ]

    result = None
    error_details: str | None = None

    for func in pipeline:
        try:
            result = await func(url, proxy_setting)
            if result.error:
                error_details = f"{result.content if result and result.content else ''} {result.error if result and result.error else ''}"
                logger.warning(
                    "Error fetching url content",
                    extra={"url": url, "error": error_details},
                )
                continue
            if result.content:
                return result.content
        except Exception as e:
            error_details = str(e)
            logger.exception(
                "Error fetching url content",
                extra={"url": url},
            )
            continue

    return f"error fetching url content: {url}, no scraping service succeeded, latest error is: {error_details}"


# WARNING update this function's name and signature with caution since it's an internal tool for agent.
# NOTE: Tool descriptions are now defined in api/core/tools/tool_definitions.py
# This docstring is for internal documentation only.
async def browser_text(url: str) -> str:
    """Extracts and converts web page content from the given URL into clean, readable markdown format. This is a text-only browser tool that cannot see images, click elements, interact with JavaScript, or perform any dynamic actions - it only parses and returns the static text content of web pages."""

    return await browser_text_with_proxy_setting(url, proxy_setting="stealth")


async def get_sitemap(url: str, limit: int = 50) -> set[str]:
    """Get the sitemap of the URL passed as argument."""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.firecrawl.dev/v1/map",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {os.environ['FIRECRAWL_API_KEY']}"},
            json={"url": url, "includeSubdomains": True, "limit": limit},
            timeout=TIMEOUT_SECONDS,
        )
        reponse_json = response.json()

        if not reponse_json.get("success", False):
            logger.warning(
                "Failed to fetch sitemap for url",
                extra={"url": url},
            )
            return set()

        links = reponse_json.get("links", [])
        if not links:
            logger.warning(
                "No links found in sitemap for url",
                extra={"url": url},
            )
            return set()

        return set(str(link) for link in links)
