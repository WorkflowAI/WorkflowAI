"""
Simple Pydantic-based tool definitions for WorkflowAI.
Each tool inherits from BaseTool and defines name, description, and price.
"""

from core.tools.base import BaseTool
from core.tools.browser.tool import browser_tool
from core.tools.google.tool import google_tool
from core.tools.perplexity.tools import PERPLEXITY_TOOLS

# Manual assembly of tools list
AVAILABLE_TOOLS: list[BaseTool] = [
    google_tool,
    browser_tool,
    *PERPLEXITY_TOOLS,  # Unpack all Perplexity tools
]
