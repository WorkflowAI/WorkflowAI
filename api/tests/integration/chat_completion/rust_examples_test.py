import subprocess
from pathlib import Path

import pytest

from tests.utils import root_dir


def _rust_dir():
    return root_dir() / "integrations" / "rust"


def _all_rust_examples():
    """Returns all examples from the examples directory"""
    dirs = _rust_dir() / "src"
    for file in dirs.iterdir():
        if file.is_file() and file.suffix in [".rs"]:
            yield pytest.param(file, id=file.name)


@pytest.mark.parametrize("example", _all_rust_examples())
def test_rust_openai_example(example: Path, api_server: str):
    """Run every example in the openai_examples directory"""
    result = subprocess.run(
        ["cargo", "run", example.name.split(".")[0]],
        capture_output=True,  # Capture both stdout and stderr
        text=True,  # Return strings instead of bytes
        cwd=_rust_dir(),  # Set working directory
    )

    assert result.returncode == 0, f"Command failed with stderr: {result.stderr}\nstdout: {result.stdout}"
