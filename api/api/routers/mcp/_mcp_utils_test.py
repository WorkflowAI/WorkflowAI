import pytest

from api.routers.mcp._mcp_utils import extract_agent_id_and_run_id, truncate_obj


class TestMCPServiceExtractAgentIdAndRunId:
    @pytest.mark.parametrize(
        "url,expected_agent,expected_run",
        [
            # Standard format from original docstring example
            pytest.param(
                "https://workflowai.com/workflowai/agents/classify-email-domain/runs/019763ae-ba9f-70a9-8d44-5a626c82e888",
                "classify-email-domain",
                "019763ae-ba9f-70a9-8d44-5a626c82e888",
                id="standard-format",
            ),
            # With trailing slash
            pytest.param(
                "https://workflowai.com/workflowai/agents/test-agent/runs/test-run-id/",
                "test-agent",
                "test-run-id",
                id="with-trailing-slash",
            ),
            # With query parameters
            pytest.param(
                "https://workflowai.com/workflowai/agents/my-agent/runs/my-run?param=value&other=123",
                "my-agent",
                "my-run",
                id="with-query-parameters",
            ),
            # With fragment
            pytest.param(
                "https://workflowai.com/workflowai/agents/agent-with-fragment/runs/run-with-fragment#section",
                "agent-with-fragment",
                "run-with-fragment",
                id="with-fragment",
            ),
            # With query and fragment
            pytest.param(
                "https://workflowai.com/workflowai/agents/complex-agent/runs/complex-run?param=value#fragment",
                "complex-agent",
                "complex-run",
                id="with-query-and-fragment",
            ),
            # Different base path
            pytest.param(
                "https://example.com/other/path/agents/different-agent/runs/different-run",
                "different-agent",
                "different-run",
                id="different-base-path",
            ),
            # With hyphens and underscores
            pytest.param(
                "https://workflowai.com/agents/my_agent-with-special_chars/runs/run_id-with-hyphens_123",
                "my_agent-with-special_chars",
                "run_id-with-hyphens_123",
                id="with-hyphens-and-underscores",
            ),
            # Different valid formats
            ("http://workflowai.com/agents/simple/runs/123", "simple", "123"),
            ("https://app.workflowai.com/org/agents/org-agent/runs/org-run", "org-agent", "org-run"),
            ("https://workflowai.com/v1/agents/versioned/runs/v1-run", "versioned", "v1-run"),
            # Complex IDs with special characters
            pytest.param(
                "https://workflowai.com/agents/agent.with.dots/runs/run-with-dashes",
                "agent.with.dots",
                "run-with-dashes",
                id="with-dots",
            ),
            pytest.param(
                "https://workflowai.com/agents/agent_123/runs/run_456",
                "agent_123",
                "run_456",
                id="with-underscores",
            ),
            # Long UUIDs
            pytest.param(
                "https://workflowai.com/agents/my-agent/runs/01234567-89ab-cdef-0123-456789abcdef",
                "my-agent",
                "01234567-89ab-cdef-0123-456789abcdef",
                id="with-long-uuid",
            ),
            # No protocol (still valid pattern)
            pytest.param(
                "example.com/agents/test/runs/123",
                "test",
                "123",
                id="no-protocol",
            ),
            # Localhost with query parameter
            pytest.param(
                "http://localhost:3000/workflowai/agents/sentiment/2/runs?page=0&runId=019763a5-12a7-73b7-9b0c-e6413d2da52f",
                "sentiment",
                "019763a5-12a7-73b7-9b0c-e6413d2da52f",
                id="with-query-parameter",
            ),
        ],
    )
    def test_extract_agent_id_and_run_id_valid_cases(
        self,
        url: str,
        expected_agent: str,
        expected_run: str,
    ):
        """Parametrized test for various valid URL formats."""
        agent_id, run_id = extract_agent_id_and_run_id(url)  # pyright: ignore[reportPrivateUsage]
        assert agent_id == expected_agent
        assert run_id == expected_run


class TestTruncateObj:
    def test_truncate_obj(self):
        obj = {"a": "1234567890"}
        max_field_length = 5
        expected = {"a": "12345...Truncated"}
        assert truncate_obj(obj, max_field_length) == expected

    def test_truncate_obj_list(self):
        obj = ["1234567890"]
        max_field_length = 5
        expected = ["12345...Truncated"]
        assert truncate_obj(obj, max_field_length) == expected

    def test_truncate_obj_nested(self):
        obj = {
            "a": [
                "1234567890",
                {"b": "1234567890"},
            ],
            "c": "1234567890",
        }
        max_field_length = 5
        expected = {
            "a": ["12345...Truncated", {"b": "12345...Truncated"}],
            "c": "12345...Truncated",
        }
        assert truncate_obj(obj, max_field_length) == expected
