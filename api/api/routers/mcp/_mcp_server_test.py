# pyright: reportPrivateUsage=false


from api.routers.mcp import mcp_server

# Note: Tests need to be updated for the new implementation
# The original tests were designed for the FastMCP 2.0 authentication system
# These tests are now placeholders that can be updated when authentication is reimplemented


async def test_mcp_server_basic_functionality():
    """Test that the MCP server is properly initialized with the official SDK."""
    # Basic test to ensure the server object exists and is properly configured
    assert mcp_server._mcp is not None
    assert hasattr(mcp_server._mcp, "name")


async def test_tools_return_appropriate_errors():
    """Test that tools return appropriate error messages when called without authentication."""
    # Test list_available_models
    result = await mcp_server.list_available_models()
    assert "error" in result
    assert "Authentication not yet implemented" in result["error"]

    # Test list_agents
    result = await mcp_server.list_agents("2024-01-01T00:00:00Z")
    assert "error" in result
    assert "Authentication not yet implemented" in result["error"]


async def test_http_app_creation():
    """Test that the HTTP app can be created."""
    app = mcp_server.mcp_http_app()
    assert app is not None


# TODO: Add proper tests once authentication is reimplemented with the official MCP SDK
# The existing authentication tests have been removed as they were specific to FastMCP 2.0
