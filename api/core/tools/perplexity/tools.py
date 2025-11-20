"""Perplexity tool definitions."""

from core.tools.base import BaseTool

from .pricing import perplexity_pricing


class PerplexitySonarTool(BaseTool):
    """Perplexity Sonar search tool definition."""

    name: str = "@perplexity-sonar"
    description: str = (
        "Performs a web search using Perplexity's Sonar model and returns comprehensive results with citations."
    )
    price: str = f"Input: ${perplexity_pricing.sonar_input_per_million}/M tokens, Output: ${perplexity_pricing.sonar_output_per_million}/M tokens, ${perplexity_pricing.sonar_per_1000_requests}/1K requests - See pricing: {perplexity_pricing.pricing_url}"


class PerplexitySonarReasoningTool(BaseTool):
    """Perplexity Sonar Reasoning search tool definition."""

    name: str = "@perplexity-sonar-reasoning"
    description: str = (
        "Performs a web search using Perplexity's Sonar Reasoning model for complex queries requiring deeper analysis."
    )
    price: str = f"Input: ${perplexity_pricing.sonar_reasoning_input_per_million}/M tokens, Output: ${perplexity_pricing.sonar_reasoning_output_per_million}/M tokens, ${perplexity_pricing.sonar_reasoning_per_1000_requests}/1K requests - See pricing: {perplexity_pricing.pricing_url}"


class PerplexitySonarProTool(BaseTool):
    """Perplexity Sonar Pro search tool definition."""

    name: str = "@perplexity-sonar-pro"
    description: str = "Performs a web search using Perplexity's Sonar Pro model for enhanced accuracy and comprehensive results with citations."
    price: str = f"Input: ${perplexity_pricing.sonar_pro_input_per_million}/M tokens, Output: ${perplexity_pricing.sonar_pro_output_per_million}/M tokens, ${perplexity_pricing.sonar_pro_per_1000_requests}/1K requests - See pricing: {perplexity_pricing.pricing_url}"


# Tool instances
perplexity_sonar_tool = PerplexitySonarTool()
perplexity_reasoning_tool = PerplexitySonarReasoningTool()
perplexity_pro_tool = PerplexitySonarProTool()

# List of all Perplexity tools
PERPLEXITY_TOOLS = [
    perplexity_sonar_tool,
    perplexity_reasoning_tool,
    perplexity_pro_tool,
]
