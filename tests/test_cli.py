from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from plan_cli.cli import app

# Integration tests exercise the public CLI entrypoints.
FIXTURES = Path(__file__).resolve().parent / "fixtures"
runner = CliRunner()


def parse_json_output(output: str) -> dict[str, Any]:
    start = output.find("{")
    if start == -1:
        raise AssertionError(f"JSON output not found: {output!r}")
    return json.loads(output[start:])


def test_init_validate_and_schema(tmp_path: Path) -> None:
    out = tmp_path / "plan.json"

    result = runner.invoke(app, ["init", "--template", "enterprise", "--out", str(out)])
    assert result.exit_code == 0
    payload = parse_json_output(result.stdout)
    assert payload["status"] == "initialized"
    assert out.exists()

    result = runner.invoke(app, ["validate", str(FIXTURES / "valid_plan.json"), "--strict"])
    assert result.exit_code == 0
    payload = parse_json_output(result.stdout)
    assert payload["status"] == "ready"
    assert payload["exit_code"] == 0

    result = runner.invoke(app, ["schema", "--target", "plan"])
    assert result.exit_code == 0
    schema = parse_json_output(result.stdout)
    assert "mode" in schema["properties"]


def test_execute_audit_and_rollback(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        (FIXTURES / "valid_plan.json").read_text(encoding="utf-8"), encoding="utf-8"
    )

    result = runner.invoke(app, ["execute", str(plan_path), "--mode", "plan-and-execute"])
    assert result.exit_code == 3
    approval_payload = parse_json_output(result.stdout)
    assert approval_payload["status"] == "approval_required"

    result = runner.invoke(
        app,
        ["approve", str(plan_path), "--role", "tech-lead", "--reviewer", "qa"],
    )
    assert result.exit_code == 0
    approve_payload = parse_json_output(result.stdout)
    assert approve_payload["status"] == "approval_recorded"

    result = runner.invoke(app, ["execute", str(plan_path), "--mode", "plan-and-execute"])
    assert result.exit_code == 0
    execute_payload = parse_json_output(result.stdout)
    assert execute_payload["status"] == "executed"
    assert (tmp_path / ".plan" / "state.json").exists()
    assert (tmp_path / ".plan" / "snapshots").exists()

    result = runner.invoke(app, ["audit", str(plan_path), "--format", "json"])
    assert result.exit_code == 0
    audit_payload = parse_json_output(result.stdout)
    assert audit_payload["status"] == "audit_generated"
    assert audit_payload["artifacts"]["summary"]["count"] >= 1

    result = runner.invoke(app, ["rollback", str(plan_path), "--dry-run"])
    assert result.exit_code == 0
    rollback_payload = parse_json_output(result.stdout)
    assert rollback_payload["status"] == "rollback_dry_run"
