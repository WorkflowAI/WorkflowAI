import re
from typing import Any, cast

from api.routers.mcp._mcp_errors import MCPError


def extract_agent_id_and_run_id(run_url: str) -> tuple[str, str]:
    """Extract the agent ID and run ID from the run URL.

    Supports multiple URL formats:
    1. https://workflowai.com/workflowai/agents/classify-email-domain/runs/019763ae-ba9f-70a9-8d44-5a626c82e888
    2. http://localhost:3000/workflowai/agents/sentiment/2/runs?taskRunId=019763a5-12a7-73b7-9b0c-e6413d2da52f

    Args:
        run_url: The run URL to parse

    Returns:
        A tuple of (agent_id, run_id)

    Raises:
        ValueError: If the URL format is invalid or doesn't match the expected pattern
    """
    if not run_url:
        raise ValueError("run_url must be a non-empty string")

    regexps = [
        r"^.*/agents/([^/]+)/runs/([-_a-zA-Z0-9]+)",
        r"^.*/agents/([^/]+)/\d+/runs?.*runId=([-_a-zA-Z0-9]+).*$",
    ]

    for regexp in regexps:
        match = re.match(regexp, run_url, re.IGNORECASE)
        if match:
            return match.group(1), match.group(2)
    raise MCPError(
        "Invalid run URL, must be in the format 'https://workflowai.com/workflowai/agents/agent-id/runs/run-id', or you must pass 'agent_id' and 'run_id'",
    )


def truncate_field(field: str, max_length: int) -> str:
    if len(field) > max_length:
        return f"{field[:max_length]}...Truncated"
    return field


def truncate_obj(obj: Any, max_field_length: int = 1000) -> Any:
    if obj is None:
        return None
    if isinstance(obj, str):
        return truncate_field(obj, max_field_length)

    if isinstance(obj, dict):
        return {k: truncate_obj(v, max_field_length) for k, v in cast(dict[str, Any], obj).items()}
    if isinstance(obj, list):
        return [truncate_obj(v, max_field_length) for v in cast(list[Any], obj)]
    return obj
