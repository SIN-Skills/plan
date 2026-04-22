from __future__ import annotations

import hashlib
import json
import sys
import traceback
from pathlib import Path
from types import TracebackType
from typing import Any

from pydantic import BaseModel

from .schema import AgentHint, ExitCode, PlanResponse

# Utility helpers for JSON output, hashing, and crash reporting.


def as_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: as_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [as_jsonable(item) for item in value]
    return value


def json_out(response: PlanResponse) -> None:
    sys.stdout.write(
        json.dumps(response.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"
    )
    raise SystemExit(int(response.exit_code))


def stderr_log(message: str) -> None:
    sys.stderr.write(f"[plan-cli] {message}\n")


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def crash_handler(
    exc_type: type[BaseException],
    exc_value: BaseException,
    tb: TracebackType | None,
) -> None:
    stderr_log("".join(traceback.format_exception(exc_type, exc_value, tb)))
    response = PlanResponse(
        status="crash",
        exit_code=ExitCode.UNKNOWN,
        errors=[str(exc_value)],
        agent_hint=AgentHint(
            next_command="opencode-plan validate --strict",
            context="Unexpected crash. Validate the plan and inspect logs.",
            requires_human=True,
        ),
    )
    sys.stdout.write(
        json.dumps(response.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"
    )
    raise SystemExit(int(response.exit_code))
