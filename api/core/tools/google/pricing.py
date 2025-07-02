"""Google search (Serper.dev) pricing configuration."""

from pydantic import BaseModel


class GoogleSearchPricing(BaseModel):
    """Google search pricing model for Serper.dev API."""

    # Constant price per search
    price_per_search: float = 0.0005  # $0.0005 per search

    @property
    def pricing_url(self) -> str:
        """URL to Serper.dev pricing page."""
        return "https://serper.dev"


# Global pricing instance
google_search_pricing = GoogleSearchPricing()
