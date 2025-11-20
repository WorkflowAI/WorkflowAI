"""Perplexity API pricing configuration."""

from pydantic import BaseModel


class PerplexityPricing(BaseModel):
    """Perplexity API pricing model based on https://perplexity.ai/pricing.

    Assumes high context level for all pricing.
    """

    # Sonar pricing (high context)
    sonar_input_per_million: float = 1.0  # $1 per 1M input tokens
    sonar_output_per_million: float = 1.0  # $1 per 1M output tokens
    sonar_per_1000_requests: float = 12.0  # $12 per 1000 requests

    # Sonar Pro pricing (high context)
    sonar_pro_input_per_million: float = 3.0  # $3 per 1M input tokens
    sonar_pro_output_per_million: float = 15.0  # $15 per 1M output tokens
    sonar_pro_per_1000_requests: float = 14.0  # $14 per 1000 requests

    # Sonar Reasoning pricing (high context)
    sonar_reasoning_input_per_million: float = 1.0  # $1 per 1M input tokens
    sonar_reasoning_output_per_million: float = 5.0  # $5 per 1M output tokens
    sonar_reasoning_per_1000_requests: float = 12.0  # $12 per 1000 requests

    # Sonar Reasoning Pro pricing (high context)
    sonar_reasoning_pro_input_per_million: float = 2.0  # $2 per 1M input tokens
    sonar_reasoning_pro_output_per_million: float = 8.0  # $8 per 1M output tokens
    sonar_reasoning_pro_per_1000_requests: float = 14.0  # $14 per 1000 requests

    @property
    def pricing_url(self) -> str:
        """URL to Perplexity's pricing page."""
        return "https://docs.perplexity.ai/guides/pricing"


# Global pricing instance
perplexity_pricing = PerplexityPricing()
