# pyright: reportPrivateUsage=false
from unittest.mock import Mock, patch

import pytest

from api.routers.mcp._mcp_service import MCPService


class TestMCPServiceExtractAgentIdAndRunId:
    @pytest.fixture
    def mcp_service(self):
        """Create a MCPService instance for testing."""
        # We only need to test the URL parsing method, so we can pass None for dependencies
        return MCPService(
            storage=Mock(),
            ai_engineer_service=Mock(),
            runs_service=Mock(),
            versions_service=Mock(),
            models_service=Mock(),
            task_deployments_service=Mock(),
            user_email=None,
            tenant_slug=None,
        )

    @pytest.mark.parametrize(
        "url,expected_agent,expected_run",
        [
            # Standard format from original docstring example
            (
                "https://workflowai.com/workflowai/agents/classify-email-domain/runs/019763ae-ba9f-70a9-8d44-5a626c82e888",
                "classify-email-domain",
                "019763ae-ba9f-70a9-8d44-5a626c82e888",
            ),
            # With trailing slash
            (
                "https://workflowai.com/workflowai/agents/test-agent/runs/test-run-id/",
                "test-agent",
                "test-run-id",
            ),
            # With query parameters
            (
                "https://workflowai.com/workflowai/agents/my-agent/runs/my-run?param=value&other=123",
                "my-agent",
                "my-run",
            ),
            # With fragment
            (
                "https://workflowai.com/workflowai/agents/agent-with-fragment/runs/run-with-fragment#section",
                "agent-with-fragment",
                "run-with-fragment",
            ),
            # With query and fragment
            (
                "https://workflowai.com/workflowai/agents/complex-agent/runs/complex-run?param=value#fragment",
                "complex-agent",
                "complex-run",
            ),
            # Different base path
            (
                "https://example.com/other/path/agents/different-agent/runs/different-run",
                "different-agent",
                "different-run",
            ),
            # With hyphens and underscores
            (
                "https://workflowai.com/agents/my_agent-with-special_chars/runs/run_id-with-hyphens_123",
                "my_agent-with-special_chars",
                "run_id-with-hyphens_123",
            ),
            # Different valid formats
            ("http://workflowai.com/agents/simple/runs/123", "simple", "123"),
            ("https://app.workflowai.com/org/agents/org-agent/runs/org-run", "org-agent", "org-run"),
            ("https://workflowai.com/v1/agents/versioned/runs/v1-run", "versioned", "v1-run"),
            # Complex IDs with special characters
            (
                "https://workflowai.com/agents/agent.with.dots/runs/run-with-dashes",
                "agent.with.dots",
                "run-with-dashes",
            ),
            ("https://workflowai.com/agents/agent_123/runs/run_456", "agent_123", "run_456"),
            # Long UUIDs
            (
                "https://workflowai.com/agents/my-agent/runs/01234567-89ab-cdef-0123-456789abcdef",
                "my-agent",
                "01234567-89ab-cdef-0123-456789abcdef",
            ),
            # No protocol (still valid pattern)
            ("example.com/agents/test/runs/123", "test", "123"),
            # Localhost with query parameter
            (
                "http://localhost:3000/workflowai/agents/sentiment/2/runs?page=0&taskRunId=019763a5-12a7-73b7-9b0c-e6413d2da52f",
                "sentiment",
                "019763a5-12a7-73b7-9b0c-e6413d2da52f",
            ),
        ],
    )
    def test_extract_agent_id_and_run_id_valid_cases(
        self,
        mcp_service: MCPService,
        url: str,
        expected_agent: str,
        expected_run: str,
    ):
        """Parametrized test for various valid URL formats."""
        agent_id, run_id = mcp_service._extract_agent_id_and_run_id(url)  # pyright: ignore[reportPrivateUsage]
        assert agent_id == expected_agent
        assert run_id == expected_run

    @pytest.mark.parametrize(
        "invalid_url,expected_error_pattern",
        [
            # Empty and None inputs
            ("", "run_url must be a non-empty string"),
            # Too short URLs
            ("https://example.com", "Invalid run URL format"),
            ("https://example.com/agents", "Invalid run URL format"),
            ("https://example.com/agents/test", "Invalid run URL format"),
            ("https://example.com/short", "Invalid run URL format"),
            # Missing agents keyword
            ("https://example.com/tasks/my-task/executions/run-123", "Invalid run URL format"),
            # Missing runs keyword or wrong pattern
            ("https://example.com/agents/my-agent/executions/run-123", "Invalid run URL format"),
            ("https://example.com/agents/my-agent/tasks/run-123", "Invalid run URL format"),
            ("https://example.com/agents/my-agent/settings", "Invalid run URL format"),
            # Empty components
            ("https://example.com/agents//runs/run-123", "Invalid run URL format"),
            ("https://example.com/agents/agent/runs/", "Invalid run URL format"),
            # Agents at end without proper structure
            ("https://example.com/path/agents", "Invalid run URL format"),
            # Runs at end without run ID
            ("https://example.com/agents/my-agent/runs", "Invalid run URL format"),
            # Malformed URLs
            ("not-a-url", "Invalid run URL format"),
            ("//invalid//url//format", "Invalid run URL format"),
        ],
    )
    def test_extract_agent_id_and_run_id_parametrized_invalid_cases(
        self,
        mcp_service: MCPService,
        invalid_url: str,
        expected_error_pattern: str,
    ):
        """Parametrized test for various invalid URL formats."""
        with pytest.raises(ValueError, match=expected_error_pattern):
            mcp_service._extract_agent_id_and_run_id(invalid_url)  # pyright: ignore[reportPrivateUsage]


class TestMCPServiceSendFeedback:
    @pytest.fixture
    def mcp_service(self):
        """Create a MCPService instance for testing."""
        return MCPService(
            storage=Mock(),
            ai_engineer_service=Mock(),
            runs_service=Mock(),
            versions_service=Mock(),
            models_service=Mock(),
            task_deployments_service=Mock(),
            user_email="test@example.com",
            tenant_slug="test-org",
        )

    async def test_send_feedback_success(self, mcp_service: MCPService):
        """Test successful feedback submission"""
        with patch("api.routers.mcp._mcp_service.add_background_task") as mock_add_task:
            feedback = "MCP server performed well"
            context = "Used list_agents successfully"
            user_agent = "test-user-agent"

            result = await mcp_service.send_feedback(feedback, user_agent, context)

            assert result.success is True
            assert result.data is not None
            assert "received and sent for processing" in result.data["message"]

            # Verify background task was scheduled
            mock_add_task.assert_called_once()
            # Verify the coroutine arguments
            call_args = mock_add_task.call_args[0][0]
            assert hasattr(call_args, "__name__")  # It's a coroutine

    async def test_send_feedback_without_context(self, mcp_service: MCPService):
        """Test feedback submission without context"""
        with patch("api.routers.mcp._mcp_service.add_background_task") as mock_add_task:
            feedback = "Simple feedback"
            user_agent = "test-user-agent"

            result = await mcp_service.send_feedback(feedback, user_agent, None)

            assert result.success is True
            assert result.data is not None
            assert "received and sent for processing" in result.data["message"]
            mock_add_task.assert_called_once()

    async def test_send_feedback_exception_handling(self, mcp_service: MCPService):
        """Test exception handling in send_feedback"""
        with patch("api.routers.mcp._mcp_service.add_background_task", side_effect=Exception("Background task failed")):
            feedback = "Test feedback"
            user_agent = "test-user-agent"

            result = await mcp_service.send_feedback(feedback, user_agent, None)

            assert result.success is False
            assert result.error is not None
            assert "Failed to send MCP client feedback for processing" in result.error


class TestMCPServiceProcessFeedback:
    @pytest.fixture
    def mcp_service(self):
        """Create a MCPService instance for testing."""
        return MCPService(
            storage=Mock(),
            ai_engineer_service=Mock(),
            runs_service=Mock(),
            versions_service=Mock(),
            models_service=Mock(),
            task_deployments_service=Mock(),
            user_email="test@example.com",
            tenant_slug="test-org",
        )

    async def test_process_feedback_success(self, mcp_service: MCPService):
        """Test successful feedback processing"""
        from core.agents.mcp_feedback_processing_agent import MCPFeedbackProcessingOutput

        mock_response = MCPFeedbackProcessingOutput(
            summary="Feedback processed successfully",
            sentiment="positive",
            key_themes=["performance", "tools"],
            suggested_improvements=["Improve the performance of the MCP server"],
            confidence=0.9,
        )

        with patch(
            "api.routers.mcp._mcp_service.mcp_feedback_processing_agent",
            return_value=mock_response,
        ) as mock_agent:
            with patch("api.routers.mcp._mcp_service.logger") as mock_logger:
                feedback = "Great MCP server performance"
                context = "Testing context"

                await mcp_service._process_feedback(  # pyright: ignore[reportPrivateUsage]
                    feedback,
                    context,
                    "test-user-agent",
                    "test-org",
                    "test@example.com",
                )

                # Verify agent was called with correct parameters
                mock_agent.assert_called_once_with(
                    feedback=feedback,
                    context=context,
                    user_agent="test-user-agent",
                    organization_name="test-org",
                    user_email="test@example.com",
                )

                # Verify successful processing was logged
                mock_logger.info.assert_called_once_with(
                    "MCP client feedback processed",
                    extra={
                        "organization_name": "test-org",
                        "sentiment": "positive",
                        "summary": "Feedback processed successfully",
                        "key_themes": ["performance", "tools"],
                        "confidence": 0.9,
                        "user_agent": "test-user-agent",
                    },
                )

    async def test_process_feedback_agent_returns_none(self, mcp_service: MCPService):
        """Test handling when feedback processing agent returns None"""

        with patch("api.routers.mcp._mcp_service.mcp_feedback_processing_agent", return_value=None) as mock_agent:
            with patch("api.routers.mcp._mcp_service.logger") as mock_logger:
                feedback = "Test feedback"
                context = None

                await mcp_service._process_feedback(  # pyright: ignore[reportPrivateUsage]
                    feedback,
                    context,
                    "test-user-agent",
                    "test-org",
                    "test@example.com",
                )

                # Verify agent was called
                mock_agent.assert_called_once_with(
                    feedback=feedback,
                    context=context,
                    user_agent="test-user-agent",
                    organization_name="test-org",
                    user_email="test@example.com",
                )

                # Verify error was logged when no response received
                mock_logger.error.assert_called_once_with(
                    "MCP client feedback processing agent returned no response",
                    extra={
                        "organization_name": "test-org",
                        "user_email": "test@example.com",
                        "feedback": feedback,
                        "context": context,
                        "user_agent": "test-user-agent",
                    },
                )

    async def test_process_feedback_exception_handling(self, mcp_service: MCPService):
        """Test exception handling in _process_feedback"""

        with patch(
            "api.routers.mcp._mcp_service.mcp_feedback_processing_agent",
            side_effect=Exception("Agent failed"),
        ) as mock_agent:
            with patch("api.routers.mcp._mcp_service.logger") as mock_logger:
                feedback = "Test feedback"
                context = "Test context"

                await mcp_service._process_feedback(  # pyright: ignore[reportPrivateUsage]
                    feedback,
                    context,
                    "test-user-agent",
                    "test-org",
                    "test@example.com",
                )

                # Verify agent was called
                mock_agent.assert_called_once()

                # Verify exception was logged
                mock_logger.exception.assert_called_once_with(
                    "Error processing MCP client feedback",
                    exc_info=mock_agent.side_effect,
                )

    async def test_process_feedback_with_minimal_parameters(self, mcp_service: MCPService):
        """Test _process_feedback with minimal parameters (None values)"""
        from core.agents.mcp_feedback_processing_agent import MCPFeedbackProcessingOutput

        mock_response = MCPFeedbackProcessingOutput(
            summary="Minimal feedback processed",
            sentiment="neutral",
            key_themes=[],
            suggested_improvements=[],
            confidence=0.5,
        )

        with patch(
            "api.routers.mcp._mcp_service.mcp_feedback_processing_agent",
            return_value=mock_response,
        ) as mock_agent:
            with patch("api.routers.mcp._mcp_service.logger") as mock_logger:
                feedback = "Minimal feedback"

                await mcp_service._process_feedback(  # pyright: ignore[reportPrivateUsage]
                    feedback,
                    None,
                    "test-user-agent",
                    None,
                    None,
                )

                # Verify agent was called with None values
                mock_agent.assert_called_once_with(
                    feedback=feedback,
                    context=None,
                    user_agent="test-user-agent",
                    organization_name=None,
                    user_email=None,
                )

                # Verify logging included None organization name
                mock_logger.info.assert_called_once()
                log_call = mock_logger.info.call_args
                assert log_call[1]["extra"]["organization_name"] is None
