import os

import httpx

TIMEOUT_SECONDS = 30


# NOTE: This function's docstring is exposed as public API documentation
# via the GET /v1/tools/hosted endpoint. Changes to the docstring will
# be reflected in external documentation.
async def run_google_search(query: str) -> str:
    """Performs a Google web search using Serper.dev API and returns search results including links, snippets, and related information in JSON format."""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": os.environ["SERPER_API_KEY"], "Content-Type": "application/json"},
            json={"q": query},
            timeout=TIMEOUT_SECONDS,
        )
        return response.text
