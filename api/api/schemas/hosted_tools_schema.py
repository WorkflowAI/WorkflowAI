from pydantic import BaseModel, Field


class HostedToolResponse(BaseModel):
    """Response model for a single hosted tool."""

    name: str = Field(description="The tool handle/name (e.g., '@search-google')")
    description: str = Field(description="Description of what the tool does")


# Type alias for the list response - just a simple array of tools
HostedToolsListResponse = list[HostedToolResponse]
