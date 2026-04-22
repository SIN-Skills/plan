# /plan — Agent-first enterprise planning

Standalone home for the OpenCode `/plan` skill and its JSON-first CLI.

## What changed
- `opencode-plan` command tree with strict machine I/O
- Pydantic models for plans, responses, and JSON Schema export
- deterministic validation, DAG analysis, Monte Carlo, and governance
- idempotent execution state in `.plan/`
- packaging, tests, and CI workflows

## Install
```bash
pip install -e .[dev]
# or
opencode-plan --help
```

## Commands
```bash
opencode-plan init --template enterprise --out plan.json
opencode-plan validate plan.json --strict --auto-fix
opencode-plan simulate plan.json --iterations 10000
opencode-plan execute plan.json --mode plan-and-execute
opencode-plan audit plan.json --format sarif
opencode-plan rollback plan.json --dry-run
opencode-plan schema --target plan
```

## Exit codes
| Code | Meaning |
| --- | --- |
| `0` | OK |
| `1` | Validation failed |
| `2` | Execution error |
| `3` | Approval required |
| `4` | Drift detected |
| `5` | Unknown crash |

## Layout
- `SKILL.md` — skill contract
- `BEST_PRACTICES.md` — operator guidance
- `src/plan_cli/` — packaged CLI runtime
- `src/plan_cli/templates/` — machine templates used by `init`
- `templates/` — legacy human templates kept for compatibility
- `scripts/` — compatibility and helper scripts

## Migration
- Keep `SKILL.md` and the CLI in sync.
- Treat `plan_cli` as the runtime contract.
- Prefer `opencode-plan` over ad-hoc script execution.
