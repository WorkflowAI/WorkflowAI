import asyncio
import logging

from core.agents.pick_relevant_url_agent import (
    PickRelevantUrlAgentsInput,
    PickRelevantUrlAgentsOutput,
    pick_relevant_url_agents,
)
from core.domain.url_content import URLContent
from core.tools.browser_text.browser_text_tool import (
    browser_text_with_proxy_setting,
    get_sitemap,
)
from core.utils.redis_cache import redis_cached
from core.utils.token_utils import tokens_from_string

_logger = logging.getLogger(__name__)


class ScrapingService:
    """Wrapper for scraping related functions."""

    @staticmethod
    async def get_url_content(url: str, request_timeout: float | None = None) -> URLContent:
        try:
            content = await asyncio.wait_for(browser_text_with_proxy_setting(url, "stealth"), timeout=request_timeout)
            return URLContent(url=url, content=content)
        except asyncio.TimeoutError:
            _logger.warning("Timeout fetching content for URL", url, extra={"url": url})
            return URLContent(url=url, content="")
        except Exception as e:
            _logger.exception("Error getting url content", extra={"url": url}, exc_info=e)
            return URLContent(url=url, content="")

    @staticmethod
    @redis_cached(expiration_seconds=60 * 60)  # TTL=1 hour
    async def get_url_content_cached(url: str, request_timeout: float | None = None) -> URLContent:
        return await ScrapingService.get_url_content(url, request_timeout)

    @staticmethod
    async def fetch_url_contents_concurrently(
        urls_to_fetch: set[str],
        request_timeout: float,
        use_cache: bool,
    ) -> list[URLContent]:
        scraping_service = ScrapingService()

        # Selectivelly use cache or not
        if use_cache:
            fetching_function = scraping_service.get_url_content_cached
        else:
            fetching_function = scraping_service.get_url_content

        tasks = [fetching_function(link, request_timeout) for link in urls_to_fetch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful_contents: list[URLContent] = []
        url_list = list(urls_to_fetch)  # Create a list for indexing
        for i, result in enumerate(results):
            # Attempt to get the corresponding URL; handle potential index errors if lists mismatch (should not happen)
            try:
                url = url_list[i]
            except IndexError:
                _logger.error(
                    "Result index i out of bounds for url_list of length.",
                    extra={"i": i, "url_list_length": len(url_list)},
                )
                continue  # Skip this result

            if isinstance(result, URLContent):
                if result.content:  # Successfully fetched content
                    successful_contents.append(result)
                else:
                    # Content is empty, likely due to timeout or internal fetch error handled in _get_url_content
                    _logger.warning("No content retrieved for URL", extra={"url": url})
            elif isinstance(result, Exception):
                # An unexpected exception occurred during gather for this task
                _logger.warning("Error fetching content for URL", extra={"url": url}, exc_info=result)
            else:
                # Should not happen with return_exceptions=True
                _logger.error("Unexpected result type for URL", extra={"url": url, "result_type": type(result)})

        return successful_contents

    @staticmethod
    async def pick_relevant_links(site_map_links: list[str], max_links: int, purpose: str) -> set[str]:
        try:
            most_relevant_links: PickRelevantUrlAgentsOutput = await pick_relevant_url_agents(
                PickRelevantUrlAgentsInput(
                    num_urls=max_links,
                    url_contents=[
                        PickRelevantUrlAgentsInput.URL(index=index, url=link)
                        for index, link in enumerate(site_map_links)
                    ],
                    purpose=purpose,
                ),
            )
            picked_indexes: list[int] = most_relevant_links.picked_url_indexes or list(range(max_links))
            # Make sure we do not exceed the maximum number of links
            picked_indexes = picked_indexes[:max_links]
            return {link for index, link in enumerate(site_map_links) if index in picked_indexes}
        except Exception as e:
            _logger.exception("Error picking relevant urls", exc_info=e)
            # If anything goes wrong, we consider the first max_links links in the sitemap
            return set(site_map_links[:max_links])

    @staticmethod
    async def limit_url_content_size(url_contents: list[URLContent], max_tokens: int) -> list[URLContent]:
        # Assuming a default model for token counting, as tiktoken is often associated with OpenAI models.
        # Consider making the model an argument if different tokenizers are needed.
        DEFAULT_MODEL_FOR_TOKEN_COUNT = "gpt-4"

        limited_contents: list[URLContent] = []
        current_token_count = 0
        for content in url_contents:
            if not content.content:
                # Include items with empty content without counting tokens
                limited_contents.append(content)
                continue

            try:
                content_tokens = tokens_from_string(content.content, DEFAULT_MODEL_FOR_TOKEN_COUNT)
            except Exception as e:
                _logger.exception(
                    "Could not calculate tokens for content",
                    extra={"url": content.url},
                    exc_info=e,
                )
                # Skip content if token calculation fails
                continue

            if current_token_count + content_tokens <= max_tokens:
                limited_contents.append(content)
                current_token_count += content_tokens
            else:
                # Stop adding more content once the limit is exceeded
                continue

        return limited_contents

    @staticmethod
    @redis_cached(expiration_seconds=60 * 60)  # TTL=1 hour
    async def get_sitemap_links_cached(company_domain: str) -> set[str]:
        try:
            return await get_sitemap(company_domain)
        except Exception as e:
            _logger.exception("Error getting sitemap", exc_info=e)
            # If anything goes wrong, only the company domain is considered
            return {company_domain}
