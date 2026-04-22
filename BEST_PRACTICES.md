# /plan Best Practices

## Core rules
- Validate first, execute second.
- Keep outputs JSON-first.
- Use `agent_hint.next_command` as the next safe step.
- Never hand-edit `.plan/` state.
- Keep tasks concrete, bounded, and measurable.
- Every task must have a validation step and 3-point estimate.

## Preferred CLI flow
```bash
opencode-plan init --template enterprise --out plan.json
opencode-plan validate plan.json --strict --auto-fix
opencode-plan simulate plan.json --iterations 10000
opencode-plan execute plan.json --mode plan-and-execute
opencode-plan audit plan.json --format json
opencode-plan rollback plan.json --dry-run
```

## Quality gates
- Quality score should be at least 70/100.
- Overall risk score should stay at or below 60.
- Approval must be explicit before continuous execution.

## Legacy compatibility
The old Python scripts remain available for manual inspection, but the CLI package is the canonical runtime.
