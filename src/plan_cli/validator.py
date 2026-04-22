from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .dag import analyse_dependency_graph, build_graph, find_cycles
from .planning import approval_gate_required, dump_json, flatten_tasks, load_json, task_estimates
from .schema import AgentHint, ExitCode, PlanDocument, PlanResponse
from .utils import hash_file

# Schema validation, quality scoring, and auto-fix logic for plans.

REQUIRED_SECTIONS = [
    "outcomes",
    "current_state",
    "decisions",
    "assumptions",
    "phases",
    "dependency_graph",
    "risks",
    "rollback_plan",
    "done_criteria",
    "approvals",
    "metrics",
    "learning",
]


def calculate_quality_score(plan: dict[str, Any]) -> dict[str, int]:
    scores = {
        "completeness": 0,
        "clarity": 0,
        "risk_coverage": 0,
        "estimation_quality": 0,
        "dependency_modeling": 0,
        "outcome_alignment": 0,
    }

    present = sum(1 for field in REQUIRED_SECTIONS if field in plan and plan[field] is not None)
    scores["completeness"] = int((present / len(REQUIRED_SECTIONS)) * 25)

    tasks = flatten_tasks(plan)
    with_validation = sum(1 for task in tasks if task.get("validation"))
    if tasks:
        scores["clarity"] = int((with_validation / len(tasks)) * 20)

    risks = plan.get("risks", []) or []
    if risks:
        risks_with_mitigation = sum(1 for risk in risks if risk.get("mitigation"))
        scores["risk_coverage"] = int((risks_with_mitigation / len(risks)) * 20)
    elif float(plan.get("overall_risk_score", 0) or 0) == 0:
        scores["risk_coverage"] = 10

    with_estimates = 0
    with_3point = 0
    for task in tasks:
        effort = task.get("effort") or {}
        if effort:
            with_estimates += 1
            if all(key in effort for key in ("pessimistic", "realistic", "optimistic")):
                with_3point += 1
    if with_estimates:
        scores["estimation_quality"] = int((with_3point / with_estimates) * 15)

    graph = plan.get("dependency_graph") or {}
    if graph.get("nodes") and graph.get("edges") and graph.get("critical_path"):
        scores["dependency_modeling"] = 10
    elif graph.get("nodes") and graph.get("edges"):
        scores["dependency_modeling"] = 5
    elif graph.get("nodes"):
        scores["dependency_modeling"] = 3

    outcomes = plan.get("outcomes") or {}
    if outcomes.get("objective") and outcomes.get("key_results"):
        scores["outcome_alignment"] = 10
    elif outcomes.get("objective"):
        scores["outcome_alignment"] = 5

    scores["total"] = sum(scores.values())
    return scores


def _update_dependency_cycle(plan: dict[str, Any], source: str, target: str) -> bool:
    updated = False

    for task in plan.get("tasks", []) or []:
        if isinstance(task, dict) and task.get("id") == target:
            deps = list(task.get("dependencies") or task.get("depends_on") or [])
            if source in deps:
                task["dependencies"] = [dep for dep in deps if dep != source]
                updated = True

    for phase in plan.get("phases", []) or []:
        for task in phase.get("tasks", []) or []:
            if isinstance(task, dict) and task.get("id") == target:
                deps = list(task.get("dependencies") or task.get("depends_on") or [])
                if source in deps:
                    task["dependencies"] = [dep for dep in deps if dep != source]
                    updated = True

    if updated:
        for edge in plan.get("dependency_graph", {}).get("edges", []) or []:
            if edge.get("from") == source and edge.get("to") == target:
                edge["type"] = "external"
        plan.setdefault("updated", plan.get("updated"))
    return updated


def _apply_auto_fix(
    plan_path: Path, plan: dict[str, Any], cycles: list[list[str]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not cycles:
        return plan, {"applied": False, "reason": "no cycles"}

    cycle = cycles[0]
    if len(cycle) < 2:
        return plan, {"applied": False, "reason": "cycle too small"}

    source = cycle[-1]
    target = cycle[0]
    fixed = _update_dependency_cycle(plan, source, target)
    if fixed:
        dump_json(plan_path, plan)
        return plan, {"applied": True, "removed_dependency": {"from": source, "to": target}}

    return plan, {"applied": False, "reason": "unable to update dependency graph"}


def validate_plan(plan_path: Path, strict: bool = False, auto_fix: bool = False) -> PlanResponse:
    try:
        raw = load_json(plan_path)
    except Exception as exc:
        return PlanResponse(
            status="invalid_json",
            exit_code=ExitCode.VALIDATION_FAILED,
            errors=[str(exc)],
            agent_hint=AgentHint(
                next_command="opencode-plan init --template enterprise",
                context="Fix JSON syntax or re-initialize the plan.",
                requires_human=True,
            ),
        )

    warnings: list[str] = []
    try:
        plan = PlanDocument.model_validate(raw).model_dump(mode="json", by_alias=True)
    except ValidationError as exc:
        return PlanResponse(
            status="invalid_schema",
            exit_code=ExitCode.VALIDATION_FAILED,
            errors=[str(item["msg"]) for item in exc.errors()],
            agent_hint=AgentHint(
                next_command="opencode-plan schema --target plan",
                context="The plan is missing required schema fields.",
                requires_human=True,
            ),
        )

    tasks = flatten_tasks(plan)
    if not tasks:
        return PlanResponse(
            status="invalid",
            exit_code=ExitCode.VALIDATION_FAILED,
            errors=["No tasks found in plan"],
            agent_hint=AgentHint(
                next_command="opencode-plan init --template enterprise",
                context="Add phases and tasks before continuing.",
                requires_human=True,
            ),
        )

    graph, _, _ = build_graph(plan)
    cycles = find_cycles(graph)
    quality = calculate_quality_score(plan)
    dependency_report = analyse_dependency_graph(plan)
    task_issues: list[str] = []

    for task in tasks:
        if not task.get("validation"):
            task_issues.append(f"Task {task.get('id', '<missing>')} is missing a validation step")
        if task_estimates(task) is None:
            task_issues.append(f"Task {task.get('id', '<missing>')} is missing a 3-point estimate")

    if cycles and auto_fix:
        plan, fix_info = _apply_auto_fix(plan_path, plan, cycles)
        if fix_info.get("applied"):
            try:
                reloaded = load_json(plan_path)
                plan = PlanDocument.model_validate(reloaded).model_dump(mode="json", by_alias=True)
                graph, _, _ = build_graph(plan)
                cycles = find_cycles(graph)
                dependency_report = analyse_dependency_graph(plan)
            except Exception as exc:
                warnings.append(f"Auto-fix wrote the plan, but reload failed: {exc}")
        else:
            warnings.append(f"Auto-fix not applied: {fix_info.get('reason', 'unknown')}")

    errors: list[str] = []
    if cycles:
        errors.append(f"DAG cycle detected: {cycles}")
    errors.extend(task_issues)

    if strict:
        if not approval_gate_required(plan):
            errors.append("Missing approval gate or approvals in strict mode")
        if quality["total"] < 70:
            errors.append(f"plan_quality_score below threshold: {quality['total']}")
        if float(plan.get("overall_risk_score", 0) or 0) > 60:
            errors.append(f"overall_risk_score above threshold: {plan.get('overall_risk_score')}")

    if quality["total"] < 70:
        warnings.append(f"plan_quality_score is {quality['total']} (<70)")
    if float(plan.get("overall_risk_score", 0) or 0) > 60:
        warnings.append(f"overall_risk_score is {plan.get('overall_risk_score')} (>60)")

    if plan.get("plan_quality_score") not in (None, quality["total"]):
        warnings.append(
            "plan_quality_score field "
            f"({plan.get('plan_quality_score')}) differs from computed score "
            f"({quality['total']})"
        )

    status = "ready" if not errors else "invalid"
    exit_code = ExitCode.OK if not errors else ExitCode.VALIDATION_FAILED
    next_command = "opencode-plan execute plan.json --mode plan-and-execute"
    if errors:
        next_command = "opencode-plan validate plan.json --strict --auto-fix"
    elif strict and not approval_gate_required(plan):
        status = "approval_required"
        exit_code = ExitCode.APPROVAL_REQUIRED
        warnings.append("Approval gate required before execution")
        next_command = "opencode-plan audit plan.json --format json"

    return PlanResponse(
        status=status,
        exit_code=exit_code,
        errors=errors,
        warnings=warnings,
        artifacts={
            "quality_breakdown": quality,
            "dependency_report": dependency_report,
            "task_count": len(tasks),
            "plan": plan,
            "auto_fixed": auto_fix and not cycles,
        },
        next_steps=[next_command],
        agent_hint=AgentHint(
            next_command=next_command,
            context="Plan validated. Execute only when the contract is clean.",
            requires_human=bool(errors) or (strict and not approval_gate_required(plan)),
        ),
        plan_hash=hash_file(plan_path),
        summary=f"{len(tasks)} tasks, quality {quality['total']}/100",
    )
