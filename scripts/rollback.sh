#!/usr/bin/env bash
set -euo pipefail

PLAN_FILE="${1:-plan.json}"
TARGET="${2:-latest}"
DRY_RUN="${3:-false}"

if [[ "$DRY_RUN" == "true" ]]; then
  exec opencode-plan rollback "$PLAN_FILE" --to "$TARGET" --dry-run
fi

exec opencode-plan rollback "$PLAN_FILE" --to "$TARGET"
