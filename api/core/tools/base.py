"""Base class for all WorkflowAI tools."""

from abc import ABC

from pydantic import BaseModel, Field


class BaseTool(BaseModel, ABC):
    """Base class for all WorkflowAI tools."""

    name: str = Field(description="Tool handle (e.g., '@search-google')")
    description: str = Field(description="Human-readable description of what the tool does")
    price: str = Field(description="Pricing information for the tool")
