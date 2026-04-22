from __future__ import annotations

from pathlib import Path

from plan_cli.dag import build_graph, find_cycles
from plan_cli.planning import load_json
from plan_cli.schema import ExitCode
from plan_cli.validator import validate_plan

# Validator tests cover schema checks, cycles, and auto-fix behavior.
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_validate_valid_plan() -> None:
    response = validate_plan(FIXTURES / "valid_plan.json", strict=True)
    assert response.exit_code == ExitCode.OK
    assert response.status == "ready"
    assert response.artifacts["quality_breakdown"]["total"] == 100
    assert response.warnings


def test_validate_cycle_plan_reports_cycle() -> None:
    response = validate_plan(FIXTURES / "cycle_plan.json", strict=False)
    assert response.exit_code == ExitCode.VALIDATION_FAILED
    assert any("DAG cycle detected" in error for error in response.errors)


def test_validate_cycle_plan_auto_fix(tmp_path: Path) -> None:
    plan_path = tmp_path / "cycle.json"
    plan_path.write_text(
        (FIXTURES / "cycle_plan.json").read_text(encoding="utf-8"), encoding="utf-8"
    )

    response = validate_plan(plan_path, strict=False, auto_fix=True)
    assert response.exit_code == ExitCode.OK
    assert response.artifacts["auto_fixed"] is True

    reloaded = load_json(plan_path)
    graph, _, _ = build_graph(reloaded)
    assert find_cycles(graph) == []
