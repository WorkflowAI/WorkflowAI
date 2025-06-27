"""
Simple Pydantic-based tool definitions for WorkflowAI.
Each tool inherits from BaseTool and defines name, description, and price.
"""

from abc import ABC

from pydantic import BaseModel, Field


class BaseTool(BaseModel, ABC):
    """Base class for all WorkflowAI tools."""

    name: str = Field(description="Tool handle (e.g., '@search-google')")
    description: str = Field(description="Human-readable description of what the tool does")
    price: str = Field(description="Pricing information for the tool")


class GoogleSearchTool(BaseTool):
    """Google search tool definition."""

    name: str = "@google-search"
    description: str = (
        "Performs a Google web search using Serper.dev API and returns search results "
        "including links, snippets, and related information in JSON format."
    )
    price: str = "$TODO per call (search)"


class BrowserTextTool(BaseTool):
    """Browser text extraction tool definition."""

    name: str = "@browser-text"
    description: str = (
        "Extracts web page content from URL as clean, readable markdown. "
        "Useful for reading articles, documentation, and gathering information from web pages."
    )
    price: str = "$TODO per call (page)"


class PerplexitySonarTool(BaseTool):
    """Perplexity Sonar search tool definition."""

    name: str = "@perplexity-sonar"
    description: str = (
        "Performs a web search using Perplexity's Sonar model and returns comprehensive results with citations."
    )
    price: str = "$TODO per call (search)"


class PerplexitySonarReasoningTool(BaseTool):
    """Perplexity Sonar Reasoning search tool definition."""

    name: str = "@perplexity-sonar-reasoning"
    description: str = (
        "Performs a web search using Perplexity's Sonar Reasoning model for complex queries requiring deeper analysis."
    )
    price: str = "$TODO per call (search)"


class PerplexitySonarProTool(BaseTool):
    """Perplexity Sonar Pro search tool definition."""

    name: str = "@perplexity-sonar-pro"
    description: str = "Performs a web search using Perplexity's Sonar Pro model for enhanced accuracy and comprehensive results with citations."
    price: str = "$TODO per call (search)"


# Tool instances
google_tool = GoogleSearchTool()
browser_tool = BrowserTextTool()
perplexity_sonar_tool = PerplexitySonarTool()
perplexity_reasoning_tool = PerplexitySonarReasoningTool()
perplexity_pro_tool = PerplexitySonarProTool()

# Manual assembly of tools list
AVAILABLE_TOOLS: list[BaseTool] = [
    google_tool,
    browser_tool,
    perplexity_sonar_tool,
    perplexity_reasoning_tool,
    perplexity_pro_tool,
]
