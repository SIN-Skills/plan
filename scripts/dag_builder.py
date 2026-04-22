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

from plan_cli.dag import analyse_dependency_graph  # noqa: E402
from plan_cli.planning import load_json  # noqa: E402

# Legacy wrapper retained for dependency graph automation.

def main() -> int:
    parser = argparse.ArgumentParser(description="Build a dependency DAG from a /plan file")
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--visualize", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    try:
        plan = load_json(args.plan)
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2, ensure_ascii=False))
        return 1

    report = analyse_dependency_graph(plan)
    report["plan_title"] = plan.get("title", "Unknown")
    report["status"] = "ready" if not report["cycles"] else "cycle_detected"
    report["visualize_requested"] = args.visualize
    report["verbose_requested"] = args.verbose

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not report["cycles"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
