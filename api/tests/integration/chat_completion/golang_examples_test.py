import os
import subprocess
from pathlib import Path

import pytest

from tests.utils import root_dir


def _golang_dir():
    return root_dir() / "integrations" / "golang"


def _all_golang_examples():
    dirs = _golang_dir()
    for dir in dirs.iterdir():
        # Golang tests are one level deep
        if dir.is_dir():
            for file in dir.iterdir():
                if file.is_file() and file.name == "main.go":
                    # The name of the test is the name of the directory
                    yield pytest.param(file, id=dir.name)


@pytest.mark.parametrize("example", _all_golang_examples())
def test_golang_example(example: Path, api_server: str):
    result = subprocess.run(
        ["go", "run", example],
        capture_output=True,
        cwd=_golang_dir(),
        env={
            **os.environ,
            "OPENAI_API_KEY": os.environ["WORKFLOWAI_API_KEY"],
            "OPENAI_BASE_URL": f"{api_server}/v1",
        },
    )
    assert result.returncode == 0, f"Command failed with stderr: {result.stderr}\nstdout: {result.stdout}"
