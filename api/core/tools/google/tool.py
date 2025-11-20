"""Google search tool definition."""

from core.tools.base import BaseTool

from .pricing import google_search_pricing


class GoogleSearchTool(BaseTool):
    """Google search tool definition."""

    name: str = "@search-google"
    description: str = (
        "Performs a Google web search using Serper.dev API and returns search results "
        "including links, snippets, and related information in JSON format."
    )
    price: str = (
        f"${google_search_pricing.price_per_search} per search - See pricing: {google_search_pricing.pricing_url}"
    )


# Tool instance
google_tool = GoogleSearchTool()
