import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from tests.integration.mcp._mcp_test_utils import ClaudeSteps, Evaluator, EvaluatorDefinition
from tests.utils import root_dir

_MCP_NAME = "workflowai_test"


@pytest.fixture(scope="session", autouse=True)
def install_js_dependencies(workflowai_api_key: str, api_server: str):
    """Install the node dependencies since Claude CLI is a node dependency
    Also set up the mcp server in claude"""
    subprocess.run(["yarn", "install"], cwd=root_dir())

    # Add the mcp server to claude
    subprocess.run(
        [
            "yarn",
            "run",
            "claude",
            "mcp",
            "add",
            _MCP_NAME,
            f"{api_server}/mcp/",
            "-H",
            f"Authorization: Bearer {workflowai_api_key}",
            "--transport",
            "http",
        ],
        cwd=root_dir(),
    )


def _cur_dir():
    return Path(__file__).parent


def _list_cases():
    """List the test cases in the cases directory"""
    names = [f.name for f in (_cur_dir() / "cases").iterdir() if f.is_dir() and not f.name.startswith("_")]
    names.sort(key=lambda n: int(n.split("_")[0]))
    return names


# For now, it looks like passing a wildcard `mcp__{_MCP_NAME}__` in allowed tools
# does not work so we need to manually list the tools...
_WAI_TOOLS = [
    "list_available_models",
    "list_agents",
    "fetch_run_details",
    "get_agent_versions",
    "ask_ai_engineer",
    "deploy_agent_version",
    "create_api_key",
]


def base_allowed_tools():
    return [
        "Read(./*)",
        "Write(./*)",
        *[f"mcp__{_MCP_NAME}__{tool}" for tool in _WAI_TOOLS],
        "MultiEdit",
        "Write",
        "Edit",
    ]


def base_denied_tools():
    return ["Read(../*)"]


# Typing for claude output, does not need to be exhaustive, just here to provide an idea of what is expected
# and potentially check for possible errors


@pytest.mark.parametrize("case", _list_cases())
def test_mcp_cases(case: str):
    case_dir_path = _cur_dir() / "cases" / case
    initial_state_dir = case_dir_path / "initial_state"

    if case_dir_path / "FAILURE.md" and os.getenv("MCP_TEST_IGNORE_FAILURES") != "true":
        pytest.skip("Skipping for expected failure")

    # RM the claude_steps if exists
    # The claude steps file will contain the steps for the actual execution of the agent
    # that is being tested
    claude_steps_file = initial_state_dir / "claude_steps.json"
    if claude_steps_file.exists():
        claude_steps_file.unlink()

    # Make sure there is a .claude_steps directory and that it's empty
    # The claude steps directory will contain other claude steps files
    # for example the logs of evaluations
    claude_steps_dir = case_dir_path / ".claude_steps"
    if claude_steps_dir.exists():
        shutil.rmtree(claude_steps_dir)
    claude_steps_dir.mkdir(parents=True, exist_ok=True)

    # Add the CLAUDE.md file to the initial state directory
    shutil.copy(case_dir_path.parent / "_CLAUDE.md", initial_state_dir / "CLAUDE.md")

    # TODO: assert no git changes in the initial_state directory

    allowed_tools = " ".join(f'"{tool}"' for tool in base_allowed_tools())
    denied_tools = " ".join(f'"{tool}"' for tool in base_denied_tools())

    cmd = f'cat "../PROMPT.md" | yarn run claude --verbose --allowedTools {allowed_tools} --disallowedTools {denied_tools} --output-format json -p'

    print(cmd)

    # Write the output directly to the claude_steps.json file
    with open(claude_steps_file, "w") as f:
        result = subprocess.run(
            cmd,
            cwd=initial_state_dir,
            stdout=f,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,
        )
    assert result.returncode == 0, f"Failed to run claude: {result.stderr}"

    # Read the file back to parse the JSON
    with open(claude_steps_file, "r") as f:
        steps = ClaudeSteps.validate_python(json.load(f))

    with open(case_dir_path / "evaluator.yaml", "r") as f:
        evaluator = EvaluatorDefinition.model_validate(yaml.safe_load(f))

    evaluator = Evaluator(definition=evaluator, mcp_name=_MCP_NAME, claude_steps_dir=claude_steps_dir)
    failed_assertions = evaluator.evaluate(case_dir_path, steps)
    assert not failed_assertions, f"Failed assertions:{'\n------\n'.join(failed_assertions)}"
