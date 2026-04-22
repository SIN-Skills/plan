#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from plan_cli.monte_carlo import (  # noqa: E402
    extract_task_estimates,
    generate_histogram_data,
    identify_high_risk_tasks,
    run_monte_carlo,
)
from plan_cli.planning import load_json  # noqa: E402

# Legacy wrapper retained for Monte Carlo automation.

def main() -> int:
    parser = argparse.ArgumentParser(description="Run Monte Carlo analysis for a /plan file")
    parser.add_argument("plan", type=Path)
    parser.add_argument("--iterations", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--chart", action="store_true")
    args = parser.parse_args()

    try:
        plan = load_json(args.plan)
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2, ensure_ascii=False))
        return 1

    tasks = extract_task_estimates(plan)
    if not tasks:
        print(
            json.dumps(
                {"status": "error", "error": "No tasks with 3-point estimates found"},
                indent=2,
                ensure_ascii=False,
            )
        )
        return 1

    results = run_monte_carlo(
        tasks, iterations=args.iterations, seed=args.seed, capture_samples=args.chart
    )
    report = {
        "status": "simulated",
        "plan_title": plan.get("title", "Unknown"),
        "task_count": len(tasks),
        "iterations": args.iterations,
        "results": results,
        "high_risk_tasks": identify_high_risk_tasks(tasks),
        "histogram": generate_histogram_data(results, bins=15) if args.chart else [],
        "verbose_requested": args.verbose,
    }

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
