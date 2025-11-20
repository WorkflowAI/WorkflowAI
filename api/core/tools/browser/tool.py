"""Browser text extraction tool definition."""

from core.tools.base import BaseTool

from .pricing import browser_text_pricing


class BrowserTextTool(BaseTool):
    """Browser text extraction tool definition."""

    name: str = "@browser-text"
    description: str = (
        "Extracts web page content from URL as clean, readable markdown. "
        "Useful for reading articles, documentation, and gathering information from web pages."
    )
    price: str = f"${browser_text_pricing.price_per_request:.6f} per page (stealth proxy) - See pricing: {browser_text_pricing.pricing_url}"


# Tool instance
browser_tool = BrowserTextTool()
