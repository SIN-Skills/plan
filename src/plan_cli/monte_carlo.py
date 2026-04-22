from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .planning import flatten_tasks, load_json, task_estimates
from .schema import AgentHint, ExitCode, PlanResponse
from .utils import hash_file

# Monte Carlo duration estimation for 3-point plan task estimates.


def extract_task_estimates(plan: dict[str, Any]) -> list[dict[str, float | str]]:
    tasks: list[dict[str, float | str]] = []
    for task in flatten_tasks(plan):
        estimates = task_estimates(task)
        if estimates is None:
            continue
        tasks.append(
            {
                "id": task.get("id", ""),
                "description": task.get("description", ""),
                "phase": task.get("phase_name") or task.get("phase_id") or "",
                **estimates,
            }
        )
    return tasks


def identify_high_risk_tasks(tasks: list[dict[str, float | str]]) -> list[dict[str, float | str]]:
    high_risk: list[dict[str, float | str]] = []
    for task in tasks:
        pessimistic = float(task["pessimistic"])
        optimistic = float(task["optimistic"])
        if pessimistic <= 0:
            continue
        uncertainty_ratio = (pessimistic - optimistic) / pessimistic
        if uncertainty_ratio > 0.5:
            high_risk.append(
                {
                    "id": task["id"],
                    "description": task["description"],
                    "uncertainty_ratio": uncertainty_ratio,
                    "pessimistic": pessimistic,
                    "optimistic": optimistic,
                    "expected": float(task["expected"]),
                }
            )
    return sorted(high_risk, key=lambda item: float(item["uncertainty_ratio"]), reverse=True)


def run_monte_carlo(
    tasks: list[dict[str, float | str]],
    iterations: int = 10000,
    seed: int = 42,
    capture_samples: bool = False,
) -> dict[str, Any]:
    if not tasks:
        return {"error": "No tasks with 3-point estimates found"}

    rng = np.random.default_rng(seed)
    sims = np.zeros(iterations, dtype=float)
    for task in tasks:
        expected = float(task["expected"])
        std_dev = max(0.0, float(task["std_dev"]))
        if std_dev == 0.0:
            sims += expected
            continue
        sample = rng.normal(expected, std_dev, size=iterations)
        min_val = expected - 3 * std_dev
        max_val = expected + 3 * std_dev
        sims += np.clip(sample, min_val, max_val)

    percentile_marks = [10, 25, 50, 75, 85, 90, 95, 99]
    percentiles = {mark: float(np.percentile(sims, mark)) for mark in percentile_marks}
    mean = float(np.mean(sims))
    std_dev = float(np.std(sims))

    result: dict[str, Any] = {
        "iterations": iterations,
        "task_count": len(tasks),
        "summary": {
            "mean": mean,
            "std_dev": std_dev,
            "min": float(np.min(sims)),
            "max": float(np.max(sims)),
            "expected_total": float(sum(float(task["expected"]) for task in tasks)),
            "pessimistic_total": float(sum(float(task["pessimistic"]) for task in tasks)),
            "optimistic_total": float(sum(float(task["optimistic"]) for task in tasks)),
        },
        "percentiles": {
            "p10": percentiles[10],
            "p25": percentiles[25],
            "p50": percentiles[50],
            "p75": percentiles[75],
            "p85": percentiles[85],
            "p90": percentiles[90],
            "p95": percentiles[95],
            "p99": percentiles[99],
        },
        "confidence_intervals": {
            "50%": f"{percentiles[50]:.1f}h",
            "85%": f"{percentiles[85]:.1f}h",
            "95%": f"{percentiles[95]:.1f}h",
        },
    }

    if capture_samples:
        result["_raw_results"] = sims.tolist()

    return result


def generate_histogram_data(results: dict[str, Any], bins: int = 20) -> list[dict[str, Any]]:
    raw = results.get("_raw_results", [])
    if not raw:
        return []

    bins = max(1, bins)
    sims = np.array(raw, dtype=float)
    min_val = float(np.min(sims))
    max_val = float(np.max(sims))
    if max_val == min_val:
        return [
            {"range": f"{min_val:.1f}-{max_val:.1f}h", "count": len(sims), "probability": 100.0}
        ]

    edges = np.linspace(min_val, max_val, bins + 1)
    histogram: list[dict[str, Any]] = []
    for i in range(bins):
        lo = float(edges[i])
        hi = float(edges[i + 1])
        if i == bins - 1:
            count = int(np.sum((sims >= lo) & (sims <= hi)))
        else:
            count = int(np.sum((sims >= lo) & (sims < hi)))
        histogram.append(
            {"range": f"{lo:.1f}-{hi:.1f}h", "count": count, "probability": count / len(sims) * 100}
        )
    return histogram


def simulate_plan(plan_path: Path, iterations: int = 10000, seed: int = 42) -> PlanResponse:
    plan = load_json(plan_path)
    tasks = extract_task_estimates(plan)
    if not tasks:
        return PlanResponse(
            status="invalid",
            exit_code=ExitCode.VALIDATION_FAILED,
            errors=["No tasks with 3-point estimates found"],
            agent_hint=AgentHint(
                next_command="opencode-plan validate plan.json --strict",
                context="Add task estimates before running a simulation.",
                requires_human=True,
            ),
            plan_hash=hash_file(plan_path),
        )

    results = run_monte_carlo(tasks, iterations=iterations, seed=seed)
    high_risk = identify_high_risk_tasks(tasks)
    mean = float(results["summary"]["mean"])
    std_dev = float(results["summary"]["std_dev"])
    risk_score = (std_dev / mean * 100) if mean else 0.0
    if risk_score < 15:
        risk_label = "LOW"
    elif risk_score < 30:
        risk_label = "MEDIUM"
    elif risk_score < 50:
        risk_label = "HIGH"
    else:
        risk_label = "CRITICAL"

    return PlanResponse(
        status="simulated",
        exit_code=ExitCode.OK,
        artifacts={
            "task_count": len(tasks),
            "iterations": iterations,
            "results": results,
            "high_risk_tasks": high_risk,
            "risk_assessment": {"score": risk_score, "label": risk_label},
        },
        next_steps=["opencode-plan validate plan.json --strict"],
        agent_hint=AgentHint(
            next_command="opencode-plan validate plan.json --strict",
            context="Simulation complete. Validate or execute when ready.",
        ),
        plan_hash=hash_file(plan_path),
        summary=f"Simulated {len(tasks)} tasks over {iterations} iterations",
    )
