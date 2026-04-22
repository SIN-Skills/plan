from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from .planning import dump_json, load_json, state_dir
from .schema import AgentHint, ExitCode, PlanResponse
from .utils import hash_file

# Governance helpers for approvals, audit trails, and rollback snapshots.


def approval_dir(plan_path: Path) -> Path:
    return state_dir(plan_path) / "approvals"


def audit_dir(plan_path: Path) -> Path:
    return state_dir(plan_path) / "audit"


def snapshot_dir(plan_path: Path) -> Path:
    return state_dir(plan_path) / "snapshots"


def approval_path(plan_path: Path) -> Path:
    return approval_dir(plan_path) / f"{hash_file(plan_path)}.json"


def check_approval(plan_path: Path) -> bool:
    path = approval_path(plan_path)
    if not path.exists():
        return False
    try:
        payload = load_json(path)
    except Exception:
        return False
    return payload.get("approved", False) is True


def record_approval(
    plan_path: Path,
    role: str,
    reviewer: str,
    notes: str = "",
    approved: bool = True,
) -> PlanResponse:
    target = approval_path(plan_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "approved": approved,
        "role": role,
        "reviewer": reviewer,
        "notes": notes,
        "timestamp": int(time.time()),
        "plan_hash": hash_file(plan_path),
    }
    dump_json(target, payload)
    return PlanResponse(
        status="approval_recorded",
        exit_code=ExitCode.OK,
        artifacts={"approval_file": str(target), "approval": payload},
        agent_hint=AgentHint(
            next_command="opencode-plan execute plan.json --mode plan-and-execute",
            context="Approval stored. Execution is now allowed for this plan hash.",
        ),
    )


def capture_snapshot(plan_path: Path) -> Path:
    source = plan_path.expanduser().resolve()
    target_dir = snapshot_dir(plan_path)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{hash_file(plan_path)}.json"
    if not target.exists():
        shutil.copy2(source, target)
    return target


def write_audit(plan_path: Path, response: PlanResponse, event: str = "run") -> Path:
    directory = audit_dir(plan_path)
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    payload = {
        "timestamp": timestamp,
        "event": event,
        "plan_hash": hash_file(plan_path),
        "status": response.status,
        "exit_code": int(response.exit_code),
        "errors": response.errors,
        "warnings": response.warnings,
        "artifacts": response.artifacts,
    }
    path = directory / f"audit_{timestamp}.json"
    dump_json(path, payload)
    return path


def _summarize_audits(entries: list[dict[str, Any]]) -> dict[str, Any]:
    exit_code_counts: dict[str, int] = {}
    for entry in entries:
        exit_code = str(entry.get("exit_code", "unknown"))
        exit_code_counts[exit_code] = exit_code_counts.get(exit_code, 0) + 1
    return {"count": len(entries), "exit_code_counts": exit_code_counts}


def generate_audit(plan_path: Path, fmt: str = "json") -> PlanResponse:
    directory = audit_dir(plan_path)
    directory.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    for path in sorted(directory.glob("audit_*.json")):
        try:
            entries.append(load_json(path))
        except Exception:
            continue

    summary = _summarize_audits(entries)
    artifacts: dict[str, Any] = {"entries": entries, "summary": summary, "format": fmt}

    if fmt == "sarif":
        artifacts["sarif"] = {
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "opencode-plan"}},
                    "results": [
                        {
                            "ruleId": "plan-audit",
                            "level": "error" if entry.get("exit_code", 1) != 0 else "note",
                            "message": {"text": json.dumps(entry, ensure_ascii=False)},
                        }
                        for entry in entries
                    ],
                }
            ],
        }
    elif fmt == "markdown":
        bullets = [
            f"- `{entry.get('status', 'unknown')}` → exit {entry.get('exit_code', 'n/a')}"
            for entry in entries
        ]
        artifacts["markdown"] = (
            "\n".join(["# Audit Summary", *bullets])
            if bullets
            else "# Audit Summary\n- No audit entries found"
        )

    return PlanResponse(
        status="audit_generated",
        exit_code=ExitCode.OK,
        artifacts=artifacts,
        agent_hint=AgentHint(
            next_command="opencode-plan rollback --dry-run",
            context="Audit complete. Inspect the history or rollback if needed.",
        ),
    )


def rollback_plan(plan_path: Path, target: str = "latest", dry_run: bool = False) -> PlanResponse:
    snapshots = sorted(snapshot_dir(plan_path).glob("*.json"))
    if not snapshots:
        return PlanResponse(
            status="no_snapshots",
            exit_code=ExitCode.EXECUTION_ERROR,
            errors=["No rollback snapshots available"],
            agent_hint=AgentHint(
                next_command="opencode-plan validate --strict",
                context="Cannot roll back because there are no snapshots.",
                requires_human=True,
            ),
        )

    target_snapshot = (
        snapshots[-1] if target == "latest" else snapshot_dir(plan_path) / f"{target}.json"
    )
    if not target_snapshot.exists():
        return PlanResponse(
            status="snapshot_missing",
            exit_code=ExitCode.EXECUTION_ERROR,
            errors=[f"Snapshot '{target}' not found"],
            agent_hint=AgentHint(
                next_command="opencode-plan audit --format json",
                context="Use the audit trail to list available snapshots.",
                requires_human=True,
            ),
        )

    if dry_run:
        return PlanResponse(
            status="rollback_dry_run",
            exit_code=ExitCode.OK,
            artifacts={
                "current_hash": hash_file(plan_path),
                "target_snapshot": str(target_snapshot),
                "target_hash": hash_file(target_snapshot),
            },
            agent_hint=AgentHint(
                next_command=f"opencode-plan rollback {plan_path} --to {target}",
                context="Dry-run looks safe. Apply when ready.",
            ),
        )

    shutil.copy2(target_snapshot, plan_path)
    return PlanResponse(
        status="rolled_back",
        exit_code=ExitCode.OK,
        artifacts={"restored_from": str(target_snapshot), "plan_hash": hash_file(plan_path)},
        agent_hint=AgentHint(
            next_command="opencode-plan validate --strict",
            context="Rollback applied. Re-validate before execution.",
        ),
    )
