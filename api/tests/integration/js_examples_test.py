"""
Tests that the JS examples are correctly supported by the API.
Node modules dependencies are required to run the tests
"""

import os
import subprocess
from pathlib import Path

import pytest

from tests.utils import root_dir


def _js_dir():
    return root_dir() / "integrations" / "js"


def _all_openai_examples():
    """Returns all examples from the examples directory"""
    dirs = _js_dir() / "openai_examples"
    for file in dirs.iterdir():
        if file.is_file() and file.suffix in [".js", ".ts"]:
            yield pytest.param(file, id=file.name)


@pytest.fixture(scope="session", autouse=True)
def install_js_dependencies():
    """Install the dependencies for the JS examples"""
    subprocess.run(["yarn", "install"], cwd=_js_dir())


@pytest.mark.parametrize("example", _all_openai_examples())
def test_js_openai_example(example: Path, api_server: str):
    """Run every example in the openai_examples directory"""
    result = subprocess.run(
        ["yarn", "tsx", f"openai_examples/{example.name}"],
        capture_output=True,  # Capture both stdout and stderr
        text=True,  # Return strings instead of bytes
        cwd=_js_dir(),  # Set working directory
        env={
            **os.environ,
            "OPENAI_API_KEY": os.environ["WORKFLOWAI_API_KEY"],
            "OPENAI_BASE_URL": f"{api_server}/v1",
        },
    )

    assert result.returncode == 0, f"Command failed with stderr: {result.stderr}\nstdout: {result.stdout}"
