from __future__ import annotations

from pathlib import Path

from .enterprise import check_approval, write_audit
from .executor import execute_plan
from .schema import AgentHint, ExitCode, PlanResponse
from .utils import stderr_log
from .validator import validate_plan

# Continuous validate/execute loop used for plan-and-execute mode.


def run_agent_loop(
    plan_path: Path, max_iterations: int = 5, auto_approve: bool = False
) -> PlanResponse:
    last_response: PlanResponse | None = None
    for iteration in range(1, max_iterations + 1):
        stderr_log(f"Loop iteration {iteration}")
        validation = validate_plan(plan_path, strict=True, auto_fix=True)
        write_audit(plan_path, validation, event="validate")
        last_response = validation
        if validation.exit_code != ExitCode.OK:
            return validation

        if not auto_approve and not check_approval(plan_path):
            response = PlanResponse(
                status="approval_required",
                exit_code=ExitCode.APPROVAL_REQUIRED,
                errors=["Approval gate not satisfied"],
                agent_hint=AgentHint(
                    next_command="opencode-plan audit plan.json --format json",
                    context="Wait for approval before continuing.",
                    requires_human=True,
                ),
                plan_hash=validation.plan_hash,
            )
            write_audit(plan_path, response, event="approval_required")
            return response

        execution = execute_plan(
            plan_path, require_approval=not auto_approve, auto_approve=auto_approve
        )
        last_response = execution
        if execution.exit_code in (
            ExitCode.OK,
            ExitCode.DRIFT_DETECTED,
            ExitCode.APPROVAL_REQUIRED,
        ):
            return execution

    return PlanResponse(
        status="loop_exhausted",
        exit_code=ExitCode.EXECUTION_ERROR,
        errors=["Max iterations reached without convergence"],
        agent_hint=AgentHint(
            next_command="opencode-plan rollback --dry-run",
            context="The loop did not converge. Inspect drift or rollback.",
            requires_human=True,
        ),
        plan_hash=getattr(last_response, "plan_hash", None),
    )
