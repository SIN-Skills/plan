from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from jsonschema import Draft202012Validator

from .agent_loop import run_agent_loop
from .enterprise import generate_audit, record_approval, rollback_plan
from .executor import execute_plan
from .monte_carlo import simulate_plan
from .planning import template_text
from .schema import AgentHint, ExitCode, PlanResponse, schema_for
from .utils import json_out
from .validator import validate_plan

# Typer CLI entrypoints for the packaged plan runtime.

app = typer.Typer(no_args_is_help=True, add_completion=False, pretty_exceptions_enable=False)


@app.command()
def init(
    template: Annotated[str, typer.Option(help="enterprise|agile|compliance")] = "enterprise",
    out: Annotated[Path, typer.Option(help="Output plan path")] = Path("plan.json"),
    force: Annotated[bool, typer.Option(help="Overwrite existing output")] = False,
) -> None:
    if out.exists() and not force:
        json_out(
            PlanResponse(
                status="exists",
                exit_code=ExitCode.VALIDATION_FAILED,
                errors=[f"{out} already exists"],
                agent_hint=AgentHint(
                    next_command=f"opencode-plan init --template {template} --out {out} --force",
                    context="Use --force to overwrite the existing file.",
                ),
            )
        )
        return

    try:
        payload = template_text(template)
    except FileNotFoundError as exc:
        json_out(
            PlanResponse(
                status="missing_template",
                exit_code=ExitCode.VALIDATION_FAILED,
                errors=[str(exc)],
                agent_hint=AgentHint(
                    next_command="opencode-plan init --template enterprise --out plan.json",
                    context="Choose one of the built-in templates.",
                    requires_human=True,
                ),
            )
        )
        return

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(payload, encoding="utf-8")
    json_out(
        PlanResponse(
            status="initialized",
            exit_code=ExitCode.OK,
            artifacts={"path": str(out), "template": template},
            agent_hint=AgentHint(
                next_command=f"opencode-plan validate {out} --strict",
                context="Template created. Validate before execution.",
            ),
        )
    )


@app.command()
def validate(
    plan: Annotated[Path, typer.Argument(exists=True, readable=True)],
    strict: Annotated[bool, typer.Option(help="Enable strict gate checks")] = False,
    auto_fix: Annotated[bool, typer.Option(help="Repair trivial issues when safe")] = False,
) -> None:
    json_out(validate_plan(plan, strict=strict, auto_fix=auto_fix))


@app.command()
def simulate(
    plan: Annotated[Path, typer.Argument(exists=True, readable=True)],
    iterations: Annotated[int, typer.Option(help="Monte Carlo runs")] = 10000,
    seed: Annotated[int, typer.Option(help="Deterministic seed")] = 42,
) -> None:
    json_out(simulate_plan(plan, iterations=iterations, seed=seed))


@app.command()
def execute(
    plan: Annotated[Path, typer.Argument(exists=True, readable=True)],
    mode: Annotated[
        str,
        typer.Option(help="plan-only|plan-and-execute|continuous|resume-approved-plan"),
    ] = "plan-only",
    auto_approve: Annotated[
        bool, typer.Option(help="Bypass the approval gate in safe CI runs")
    ] = False,
) -> None:
    if mode == "continuous":
        json_out(run_agent_loop(plan, auto_approve=auto_approve))
    else:
        json_out(
            execute_plan(plan, require_approval=mode != "plan-only", auto_approve=auto_approve)
        )


@app.command()
def audit(
    plan: Annotated[Path, typer.Argument(exists=True, readable=True)],
    format: Annotated[str, typer.Option(help="json|sarif|markdown")] = "json",
) -> None:
    json_out(generate_audit(plan, fmt=format))


@app.command()
def rollback(
    plan: Annotated[Path, typer.Argument(exists=True, readable=True)],
    to: Annotated[str, typer.Option(help="Snapshot name or latest")] = "latest",
    dry_run: Annotated[bool, typer.Option(help="Preview rollback without applying it")] = False,
) -> None:
    json_out(rollback_plan(plan, target=to, dry_run=dry_run))


@app.command()
def approve(
    plan: Annotated[Path, typer.Argument(exists=True, readable=True)],
    role: Annotated[str, typer.Option(help="Approver role")] = "tech-lead",
    reviewer: Annotated[str, typer.Option(help="Reviewer name")] = "unknown",
    notes: Annotated[str, typer.Option(help="Approval notes")] = "",
) -> None:
    json_out(record_approval(plan, role=role, reviewer=reviewer, notes=notes))


@app.command(name="schema")
def export_schema(target: str = typer.Option("plan", help="plan|response")) -> None:
    if target not in {"plan", "response"}:
        raise typer.BadParameter("target must be plan or response")
    schema = schema_for(target)
    Draft202012Validator.check_schema(schema)
    print(json.dumps(schema, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    app()
