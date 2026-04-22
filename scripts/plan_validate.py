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

from plan_cli.validator import validate_plan  # noqa: E402

# Legacy wrapper retained for shell-based automation.

def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a /plan JSON file")
    parser.add_argument("plan", type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--auto-fix", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    response = validate_plan(args.plan, strict=args.strict, auto_fix=args.auto_fix)
    print(json.dumps(response.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return int(response.exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
