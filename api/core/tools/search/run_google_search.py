import os

import httpx

TIMEOUT_SECONDS = 30


# NOTE: Tool descriptions are now defined in api/core/tools/tool_definitions.py
# This docstring is for internal documentation only.
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
