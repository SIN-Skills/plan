#!/usr/bin/env bash
        set -euo pipefail

        PLAN_FILE="${1:-plan.json}"
        MAX_LOOPS="${2:-5}"

        for _ in $(seq 1 "$MAX_LOOPS"); do
          RESP=$(opencode-plan validate "$PLAN_FILE" --strict --auto-fix)
          STATUS=$(printf '%s' "$RESP" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status", ""))')
          EXIT_CODE=$(printf '%s' "$RESP" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("exit_code", 1))')

          if [[ "$STATUS" == "ready" ]]; then
            exec opencode-plan execute "$PLAN_FILE" --mode continuous --auto-approve
          fi

          if [[ "$EXIT_CODE" != "1" ]]; then
            printf '%s
' "$RESP"
            exit "$EXIT_CODE"
          fi
        done

        printf '%s
' '{"status":"loop_exhausted","exit_code":2,"agent_hint":{"next_command":"opencode-plan rollback --dry-run","context":"Max loops reached"}}'
        exit 2
