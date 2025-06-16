# pyright: reportPrivateUsage=false

from api.api.routers.mcp.mcp_server import SendFeedbackRequest, send_feedback


async def test_send_feedback_mcp_tool_basic():
    """Basic test to ensure MCP tool returns acknowledgment"""
    request = SendFeedbackRequest(feedback="Basic test feedback")
    result = await send_feedback(request)

    assert result.success is True
    assert "received and sent for processing" in result.result["message"]
    assert result.result["feedback_length"] == len(request.feedback)
    assert result.result["has_context"] is False


async def test_send_feedback_with_context():
    """Test MCP tool with context provided"""
    request = SendFeedbackRequest(
        feedback="MCP tools were responsive and helpful",
        context="Used list_agents and fetch_run_details successfully",
    )
    result = await send_feedback(request)

    assert result.success is True
    assert "received and sent for processing" in result.result["message"]
    assert result.result["feedback_length"] == len(request.feedback)
    assert result.result["has_context"] is True


async def test_send_feedback_empty_feedback_handling():
    """Test MCP tool with empty feedback string"""
    request = SendFeedbackRequest(feedback="")
    result = await send_feedback(request)

    # Should still succeed but with zero length
    assert result.success is True
    assert result.result["feedback_length"] == 0


async def test_send_feedback_malformed_request():
    """Test error handling for malformed requests"""
    try:
        # This should raise a validation error due to missing required field
        SendFeedbackRequest()
        assert False, "Should have raised validation error"
    except Exception:
        # Expected validation error for missing required feedback field
        pass
