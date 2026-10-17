#!/usr/bin/env bash
#
# One-command quality gate for the Entity Scoring System.
#
#   ./scripts/gates.sh            # full gate (backend + web unit + e2e)
#   SKIP_E2E=1 ./scripts/gates.sh # skip the Playwright e2e pass
#
# Runs, in order and failing fast:
#   - backend:  pytest, ruff
#   - web:      typecheck (tsc), lint (eslint), unit tests (vitest)
#   - web e2e:  Playwright (mock mode, its own dev server on :3100)
#
# The e2e pass refuses to start if another `next dev` is already listening on
# :3100. Run `./scripts/fresh_start.sh` first if a stale dev server is up.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PY:-.venv/bin/python}"

hr() { printf '\n========== %s ==========\n' "$1"; }

hr "backend: pytest"
"$PY" -m pytest tests -q

hr "backend: ruff"
"$PY" -m ruff check .

hr "web: typecheck"
( cd apps/web && npm run typecheck )

hr "web: lint"
( cd apps/web && npm run lint )

hr "web: unit tests (vitest)"
( cd apps/web && npx vitest run )

if [[ "${SKIP_E2E:-0}" != "1" ]]; then
  hr "web: e2e (Playwright, mock mode)"
  ( cd apps/web && npm run test:e2e )
else
  printf '\n(skipping e2e: SKIP_E2E=1)\n'
fi

printf '\n\033[32mALL GATES GREEN\033[0m\n'
