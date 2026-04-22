from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

# Shared plan helpers for parsing, normalization, and templates.
DURATION_UNITS = {"h": 1.0, "d": 8.0, "w": 40.0}


def plan_root(plan_path: Path) -> Path:
    return plan_path.expanduser().resolve().parent


def state_dir(plan_path: Path) -> Path:
    return plan_root(plan_path) / ".plan"


def state_file(plan_path: Path) -> Path:
    return state_dir(plan_path) / "state.json"


def parse_duration(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().lower()
    if not text:
        return 0.0

    suffix = text[-1]
    if suffix in DURATION_UNITS:
        try:
            return float(text[:-1]) * DURATION_UNITS[suffix]
        except ValueError:
            return 0.0

    try:
        return float(text)
    except ValueError:
        return 0.0


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def normalize_task(task: dict[str, Any], phase: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized = dict(task)
    deps = normalized.get("dependencies")
    if deps is None:
        deps = normalized.get("depends_on", [])
    if deps is None:
        deps = []
    if not isinstance(deps, list):
        if isinstance(deps, (tuple, set)):
            deps = list(deps)
        elif deps:
            deps = [deps]
        else:
            deps = []

    normalized["dependencies"] = [str(dep) for dep in deps if dep is not None]

    if phase:
        phase_id = phase.get("id")
        phase_name = phase.get("name")
        phase_priority = phase.get("priority")
        if phase_id is not None:
            normalized.setdefault("phase_id", phase_id)
        if phase_name is not None:
            normalized.setdefault("phase_name", phase_name)
        if phase_priority is not None:
            normalized.setdefault("phase_priority", phase_priority)
    return normalized


def flatten_tasks(plan: dict[str, Any]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    seen: set[str] = set()

    for task in plan.get("tasks", []) or []:
        if isinstance(task, dict) and task.get("id") and task["id"] not in seen:
            tasks.append(normalize_task(task))
            seen.add(task["id"])

    for phase in plan.get("phases", []) or []:
        for task in phase.get("tasks", []) or []:
            if isinstance(task, dict) and task.get("id") and task["id"] not in seen:
                tasks.append(normalize_task(task, phase))
                seen.add(task["id"])

    return tasks


def task_duration_hours(task: dict[str, Any]) -> float:
    effort = task.get("effort") or {}
    if isinstance(effort, dict):
        return parse_duration(effort.get("realistic") or effort.get("estimate") or "0h")
    return 0.0


def task_estimates(task: dict[str, Any]) -> dict[str, float] | None:
    effort = task.get("effort") or {}
    if not isinstance(effort, dict):
        return None
    if not all(key in effort for key in ("pessimistic", "realistic", "optimistic")):
        return None

    pessimistic = parse_duration(effort["pessimistic"])
    realistic = parse_duration(effort["realistic"])
    optimistic = parse_duration(effort["optimistic"])
    return {
        "pessimistic": pessimistic,
        "realistic": realistic,
        "optimistic": optimistic,
        "expected": (pessimistic + 4 * realistic + optimistic) / 6,
        "std_dev": max(0.0, (pessimistic - optimistic) / 6),
    }


def task_dependencies(task: dict[str, Any]) -> list[str]:
    deps = task.get("dependencies") or task.get("depends_on") or []
    if isinstance(deps, list):
        return [str(dep) for dep in deps]
    if deps:
        return [str(deps)]
    return []


def approval_gate_required(plan: dict[str, Any]) -> bool:
    return bool(plan.get("approval_gate")) or bool(plan.get("approvals"))


def template_text(name: str) -> str:
    resource = files("plan_cli").joinpath("templates", f"{name}.json")
    if resource.is_file():
        return resource.read_text(encoding="utf-8")

    fallback = Path(__file__).resolve().parents[2] / "templates" / f"{name}.json"
    if fallback.exists():
        return fallback.read_text(encoding="utf-8")

    raise FileNotFoundError(f"Template '{name}' not found")
