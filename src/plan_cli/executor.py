from __future__ import annotations

from pathlib import Path
from typing import Any

from .enterprise import capture_snapshot, check_approval, write_audit
from .planning import dump_json, flatten_tasks, load_json, state_file
from .schema import AgentHint, ExitCode, PlanResponse
from .utils import hash_file, stderr_log

# Idempotent execution state management for approved plans.


def _load_state(plan_path: Path) -> dict[str, Any]:
    path = state_file(plan_path)
    if path.exists():
        try:
            return load_json(path)
        except Exception:
            pass
    return {"completed": [], "current_hash": None, "drift": False, "last_run": None}


def _save_state(plan_path: Path, state: dict[str, Any]) -> None:
    path = state_file(plan_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    dump_json(path, state)


def execute_plan(
    plan_path: Path, require_approval: bool = False, auto_approve: bool = False
) -> PlanResponse:
    plan = load_json(plan_path)
    tasks = flatten_tasks(plan)
    current_hash = hash_file(plan_path)
    state = _load_state(plan_path)

    if require_approval and not auto_approve and not check_approval(plan_path):
        response = PlanResponse(
            status="approval_required",
            exit_code=ExitCode.APPROVAL_REQUIRED,
            errors=["Approval gate not satisfied"],
            agent_hint=AgentHint(
                next_command="opencode-plan audit plan.json --format json",
                context="Wait for approval or use auto-approve only in safe CI/sandbox runs.",
                requires_human=True,
            ),
            plan_hash=current_hash,
        )
        write_audit(plan_path, response, event="approval_required")
        return response

    if state.get("current_hash") and state.get("current_hash") != current_hash:
        state["drift"] = True
        _save_state(plan_path, state)
        response = PlanResponse(
            status="drift_detected",
            exit_code=ExitCode.DRIFT_DETECTED,
            errors=["Plan modified during execution"],
            agent_hint=AgentHint(
                next_command="opencode-plan rollback --dry-run",
                context="Execution stopped because the plan drifted.",
                requires_human=True,
            ),
            plan_hash=current_hash,
        )
        write_audit(plan_path, response, event="drift")
        return response

    capture_snapshot(plan_path)
    completed = list(state.get("completed", []))
    task_ids = [task.get("id") for task in tasks if task.get("id")]

    for task_id in task_ids:
        if task_id in completed:
            continue
        stderr_log(f"Executing task {task_id}")
        completed.append(task_id)

    state.update(
        {
            "completed": completed,
            "current_hash": current_hash,
            "drift": False,
            "last_run": plan.get("updated") or plan.get("created") or None,
        }
    )
    _save_state(plan_path, state)

    response = PlanResponse(
        status="executed",
        exit_code=ExitCode.OK,
        artifacts={
            "completed_tasks": completed,
            "remaining_tasks": [task_id for task_id in task_ids if task_id not in completed],
            "plan_hash": current_hash,
            "state_file": str(state_file(plan_path)),
        },
        next_steps=["opencode-plan audit plan.json --format json"],
        agent_hint=AgentHint(
            next_command="opencode-plan audit plan.json --format json",
            context="Execution is complete. Write the audit trail and review drift state.",
        ),
        plan_hash=current_hash,
        summary=f"Executed {len(completed)} tasks",
    )
    write_audit(plan_path, response, event="execute")
    return response
