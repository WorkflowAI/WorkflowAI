from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from pytest import LogCaptureFixture

from api.services.scraping_service import ScrapingService
from core.agents.pick_relevant_url_agent import PickRelevantUrlAgentsOutput
from core.domain.url_content import URLContent


@pytest.fixture
def scraping_service() -> ScrapingService:
    return ScrapingService()


class TestGetSitemapLinks:
    async def test_get_sitemap_links_success(self, scraping_service: ScrapingService):
        company_domain = "example.com"
        expected_links = {"http://example.com", "http://example.com/page1"}

        with patch("api.services.scraping_service.get_sitemap", new_callable=AsyncMock) as mock_get_sitemap:
            mock_get_sitemap.return_value = expected_links
            actual_links = await scraping_service.get_sitemap_links_cached(company_domain)  # pyright: ignore[reportPrivateUsage]
            assert actual_links == expected_links
            mock_get_sitemap.assert_awaited_once_with(company_domain)

    async def test_get_sitemap_links_failure(self, scraping_service: ScrapingService, caplog: LogCaptureFixture):
        company_domain = "example.com"
        expected_links = {company_domain}  # Fallback

        with patch("api.services.scraping_service.get_sitemap", new_callable=AsyncMock) as mock_get_sitemap:
            mock_get_sitemap.side_effect = Exception("Sitemap fetch failed")
            actual_links = await scraping_service.get_sitemap_links_cached(company_domain)  # pyright: ignore[reportPrivateUsage]
            assert actual_links == expected_links
            mock_get_sitemap.assert_awaited_once_with(company_domain)
            assert "Error getting sitemap" in caplog.text


class TestPickRelevantLinks:
    @pytest.mark.parametrize(
        "sitemap_links, max_links, agent_output, expected_links",
        [
            (
                ["a.com", "b.com", "c.com", "d.com"],
                2,
                PickRelevantUrlAgentsOutput(picked_url_indexes=[0, 2]),
                {"a.com", "c.com"},
            ),
            (
                ["a.com", "b.com", "c.com"],
                5,  # More than available links
                PickRelevantUrlAgentsOutput(picked_url_indexes=[0, 1, 2]),
                {"a.com", "b.com", "c.com"},
            ),
            (
                ["a.com", "b.com", "c.com", "d.com", "e.com"],
                3,
                PickRelevantUrlAgentsOutput(picked_url_indexes=[0, 1, 2, 3, 4]),  # Agent returns more than max_links
                {"a.com", "b.com", "c.com"},  # Should be truncated
            ),
            (
                ["a.com", "b.com", "c.com"],
                2,
                PickRelevantUrlAgentsOutput(picked_url_indexes=None),  # Agent returns None
                {"a.com", "b.com"},  # Fallback to first max_links
            ),
        ],
    )
    async def test_pick_relevant_links_success(
        self,
        scraping_service: ScrapingService,
        sitemap_links: set[str],
        max_links: int,
        agent_output: PickRelevantUrlAgentsOutput,
        expected_links: set[str],
    ):
        with patch("api.services.scraping_service.pick_relevant_url_agents", new_callable=AsyncMock) as mock_pick_agent:
            mock_pick_agent.return_value = agent_output
            actual_links = await scraping_service.pick_relevant_links(list(sitemap_links), max_links, "test")  # pyright: ignore[reportPrivateUsage]
            # Convert sitemap_links to list for consistent ordering in assertion check if needed, but set comparison is fine
            assert actual_links == expected_links
            mock_pick_agent.assert_awaited_once()
            # We can add more specific checks on the input to the agent if necessary

    async def test_pick_relevant_links_failure(self, scraping_service: ScrapingService, caplog: LogCaptureFixture):
        sitemap_links = ["a.com", "b.com", "c.com", "d.com"]
        max_links = 2
        # Fallback: first max_links from the input set (order might vary, so convert to list first)
        expected_links = set(list(sitemap_links)[:max_links])

        with patch("api.services.scraping_service.pick_relevant_url_agents", new_callable=AsyncMock) as mock_pick_agent:
            mock_pick_agent.side_effect = Exception("Agent failed")
            actual_links = await scraping_service.pick_relevant_links(sitemap_links, max_links, "test")  # pyright: ignore[reportPrivateUsage]
            assert actual_links == expected_links
            mock_pick_agent.assert_awaited_once()
            assert "Error picking relevant urls" in caplog.text


class TestFetchUrlContentsConcurrently:
    @patch("api.services.scraping_service.ScrapingService.get_url_content")
    async def test_fetch_contents_success(self, mock_get_content: AsyncMock, scraping_service: ScrapingService):
        urls_to_fetch = {"a.com", "b.com", "c.com"}
        timeout = 60.0
        expected_contents = [
            URLContent(url="a.com", content="Content A"),
            URLContent(url="b.com", content="Content B"),
            URLContent(url="c.com", content="Content C"),
        ]

        # Configure mock to return different values based on URL
        async def mock_content_side_effect(url: str, request_timeout: float | None = None) -> URLContent:
            if url == "a.com":
                return URLContent(url=url, content="Content A")
            if url == "b.com":
                return URLContent(url=url, content="Content B")
            if url == "c.com":
                return URLContent(url=url, content="Content C")
            return URLContent(url=url, content="")  # Default empty

        mock_get_content.side_effect = mock_content_side_effect

        actual_contents = await scraping_service.fetch_url_contents_concurrently(urls_to_fetch, timeout, False)

        # Order might not be guaranteed by gather, so compare sets of results
        assert set(actual_contents) == set(expected_contents)
        assert mock_get_content.call_count == len(urls_to_fetch)
        for url in urls_to_fetch:
            # Check if called with correct args (any order)
            mock_get_content.assert_any_call(url, timeout)

    @patch("api.services.scraping_service.ScrapingService.get_url_content")
    async def test_fetch_contents_partial_failure(
        self,
        mock_get_content: MagicMock,
        scraping_service: ScrapingService,
        caplog: LogCaptureFixture,
    ):
        urls_to_fetch = {"good.com", "timeout.com", "error.com", "empty.com"}
        timeout = 10.0
        expected_successful = [URLContent(url="good.com", content="Good Content")]

        # Patch gather directly to simulate mixed results including exceptions
        mock_results: list[URLContent | Exception] = []
        url_list = list(urls_to_fetch)  # Need a fixed order to map results
        for url in url_list:
            if url == "good.com":
                mock_results.append(URLContent(url=url, content="Good Content"))
            elif url == "timeout.com":
                # Simulate _get_url_content returning empty on timeout
                mock_results.append(URLContent(url=url, content=""))
            elif url == "error.com":
                # Simulate gather returning an exception caught *during* gather
                mock_results.append(ValueError("Simulated gather error"))
            elif url == "empty.com":
                mock_results.append(URLContent(url=url, content=""))

        with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
            mock_gather.return_value = mock_results
            actual_contents = await scraping_service.fetch_url_contents_concurrently(urls_to_fetch, timeout, False)

            assert set(actual_contents) == set(expected_successful)  # Only good.com should remain
            assert mock_get_content.call_count == len(urls_to_fetch)  # Ensure tasks were created
            mock_gather.assert_awaited_once()  # Ensure gather was called


@pytest.mark.asyncio
class TestLimiteURLContentSize:
    scraping_service = ScrapingService()

    @pytest.mark.parametrize(
        "url_contents, max_tokens, expected_token_counts, mock_tokens_from_string_side_effect, expected_result_indices",
        [
            # Test case 1: Empty input list
            ([], 100, [], [], []),
            # Test case 2: All content fits
            (
                [URLContent(url="url1", content="Hello"), URLContent(url="url2", content="World")],
                100,
                [1, 1],  # Assuming each word is 1 token
                [1, 1],
                [0, 1],
            ),
            # Test case 3: Only some content fits
            (
                [
                    URLContent(url="url1", content="This is long"),
                    URLContent(url="url2", content="This is also quite long"),
                ],
                5,  # Limit
                [3, 5],  # Token counts
                [3, 5],
                [0],  # Only the first item should fit
            ),
            # Test case 4: Exact limit match
            (
                [URLContent(url="url1", content="Fit"), URLContent(url="url2", content="Exactly")],
                6,  # Limit
                [1, 5],  # Token counts
                [1, 5],
                [0, 1],  # Both should fit
            ),
            # Test case 5: First item exceeds limit
            (
                [URLContent(url="url1", content="Too long right away"), URLContent(url="url2", content="Short")],
                5,  # Limit
                [6, 1],  # Token counts
                [6, 1],
                [1],  # Only the second item should fit
            ),
            # Test case 6: Item with empty content
            (
                [
                    URLContent(url="url1", content="Some"),
                    URLContent(url="url2", content=""),
                    URLContent(url="url3", content="Content"),
                ],
                10,
                [1, 4],  # Token counts (empty string has 0)
                [1, 4],  # Mock side effect only called for non-empty
                [0, 1, 2],  # All should be included
            ),
            # Test case 7: Item with None content
            (
                [
                    URLContent(url="url1", content="Some"),
                    URLContent(url="url2", content=None),
                    URLContent(url="url3", content="Content"),
                ],
                10,
                [1, 4],  # Token counts (None content has 0)
                [1, 4],  # Mock side effect only called for non-empty
                [0, 1, 2],  # All should be included
            ),
            # Test case 8: Max tokens is 0
            (
                [URLContent(url="url1", content="Hello"), URLContent(url="url2", content="World")],
                0,
                [],  # Should not be called
                [],
                [],  # No content fits
            ),
            # Test case 9: Token calculation error
            (
                [
                    URLContent(url="url1", content="Good"),
                    URLContent(url="url2", content="Bad Content"),
                    URLContent(url="url3", content="More Good"),
                ],
                10,
                [1, Exception("Tiktoken error!"), 2],
                [1, Exception("Tiktoken error!"), 2],
                [0, 2],  # Should include only the first one before the error
            ),
        ],
    )
    @patch("api.services.scraping_service.tokens_from_string")
    async def test_limit_url_content_size(
        self,
        mock_tokens_from_string: Mock,
        url_contents: list[URLContent],
        max_tokens: int,
        expected_token_counts: list[int | Exception],
        mock_tokens_from_string_side_effect: list[int | Exception],
        expected_result_indices: list[int],
    ):
        mock_tokens_from_string.side_effect = mock_tokens_from_string_side_effect

        result = await self.scraping_service.limit_url_content_size(url_contents, max_tokens)  # pyright: ignore[reportPrivateUsage]

        expected_result = [url_contents[i] for i in expected_result_indices]
        assert result == expected_result

        call_index = 0
        total_tokens_added = 0
        for i, content in enumerate(url_contents):
            if i in expected_result_indices and content.content:
                # Check if tokens_from_string was called for content that was added and non-empty
                assert mock_tokens_from_string.call_count > call_index
                args, _ = mock_tokens_from_string.call_args_list[call_index]  # Ignore kwargs
                assert args[0] == content.content
                assert args[1] == "gpt-4"  # Check the model used
                # Sum tokens only if the mock didn't raise an exception for this call
                effect = mock_tokens_from_string_side_effect[call_index]
                if not isinstance(effect, Exception):
                    assert isinstance(effect, int)  # Add assertion for type checker
                    total_tokens_added += effect
                call_index += 1
            elif content.content and i not in expected_result_indices:
                # Check if tokens_from_string was called for content that was *not* added (if it was the one exceeding the limit)
                if mock_tokens_from_string.call_count > call_index:
                    args, _ = mock_tokens_from_string.call_args_list[call_index]  # Ignore kwargs
                    if args[0] == content.content:
                        call_index += 1  # Count the call even if not added

        assert total_tokens_added <= max_tokens
