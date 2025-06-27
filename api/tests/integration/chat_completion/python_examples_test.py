import os
import subprocess

import pytest

from tests.utils import root_dir


def _python_dir():
    return root_dir() / "integrations" / "python"


@pytest.mark.parametrize("model", ["gemini-2.5-flash", "gpt-4.1-nano"])
def test_search_documentation_agent(
    model: str,
    api_server: str,
    workflowai_api_key: str,
):
    result = subprocess.run(
        ["python", "pydantic_output.py"],
        capture_output=True,  # Capture both stdout and stderr
        text=True,  # Return strings instead of bytes
        cwd=_python_dir(),  # Set working directory
        env={
            **os.environ,
            "WORKFLOWAI_TEST_MODEL": model,
            "WORKFLOWAI_API_KEY": workflowai_api_key,
            "WORKFLOWAI_API_URL": api_server,
        },
    )
    assert result.returncode == 0, f"Command failed with stderr: {result.stderr}\nstdout: {result.stdout}"
