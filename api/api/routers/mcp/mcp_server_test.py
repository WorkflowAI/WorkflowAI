# pyright: reportPrivateUsage=false
# pyright: reportMissingImports=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false

import pytest

from api.api.routers.mcp.mcp_server import SendFeedbackRequest, send_feedback


async def test_send_feedback_mcp_tool_basic() -> None:
    """Basic test to ensure MCP tool returns acknowledgment"""
    request = SendFeedbackRequest(feedback="Basic test feedback")
    result = await send_feedback(request)

    assert result.success is True
    assert "received and sent for processing" in result.data["message"]
    assert result.data["feedback_length"] == len(request.feedback)
    assert result.data["has_context"] is False


async def test_send_feedback_with_context() -> None:
    """Test MCP tool with context provided"""
    request = SendFeedbackRequest(
        feedback="MCP tools were responsive and helpful",
        context="Used list_agents and fetch_run_details successfully",
    )
    result = await send_feedback(request)

    assert result.success is True
    assert "received and sent for processing" in result.data["message"]
    assert result.data["feedback_length"] == len(request.feedback)
    assert result.data["has_context"] is True


async def test_send_feedback_empty_feedback_handling() -> None:
    """Test MCP tool with empty feedback string"""
    request = SendFeedbackRequest(feedback="")
    result = await send_feedback(request)

    # Should still succeed but with zero length
    assert result.success is True
    assert result.data["feedback_length"] == 0


async def test_send_feedback_malformed_request() -> None:
    """Test error handling for malformed requests"""
    with pytest.raises(Exception):
        # This should raise a validation error due to missing required field
        SendFeedbackRequest()  # type: ignore
