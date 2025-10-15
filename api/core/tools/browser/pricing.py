"""Browser text extraction (ScrapingBee) pricing configuration."""

from pydantic import BaseModel


class BrowserTextPricing(BaseModel):
    """Browser text extraction pricing model based on ScrapingBee pricing.

    Assumes stealth proxy usage for better success rates.
    Based on Business+ plan: $599/month for 8M credits.
    """

    # ScrapingBee credit usage (with stealth proxy)
    credits_per_request: int = 25  # Stealth proxy uses 25 credits per request

    # Business+ plan: $599 for 8M credits
    monthly_cost: float = 599.0
    monthly_credits: int = 8_000_000

    @property
    def price_per_credit(self) -> float:
        """Calculate price per credit based on Business+ plan."""
        return self.monthly_cost / self.monthly_credits  # $0.000074875 per credit

    @property
    def price_per_request(self) -> float:
        """Calculate price per request based on credits used."""
        return self.price_per_credit * self.credits_per_request  # $0.001871875 per request

    @property
    def pricing_url(self) -> str:
        """URL to ScrapingBee pricing page."""
        return "https://www.scrapingbee.com/#pricing"


# Global pricing instance
browser_text_pricing = BrowserTextPricing()
