import json
from pathlib import Path

import pytest
import yaml

from tests.integration.mcp._mcp_test_utils import ClaudeSteps, EvaluatorDefinition


def test_claude_step_deser():
    """Check that we can deserialize the claude outputs from the json file"""
    fixture_path = Path(__file__).parent / "fixtures" / "claude_steps.json"
    with open(fixture_path, "r") as f:
        ClaudeSteps.validate_python(json.load(f))


def _evaluator_fixtures():
    cases_dir = Path(__file__).parent / "cases"
    paths = [evaluator_path for evaluator_path in cases_dir.glob("**/evaluator.yaml")]
    paths.sort(key=lambda p: int(p.parent.name.split("_")[0]))
    for evaluator_path in paths:
        yield pytest.param(evaluator_path, id=str(evaluator_path.relative_to(cases_dir)).split("/")[-2])


@pytest.mark.parametrize("evaluator_path", _evaluator_fixtures())
def test_evaluator_deser(evaluator_path: Path):
    with open(evaluator_path, "r") as f:
        EvaluatorDefinition.model_validate(yaml.safe_load(f))
