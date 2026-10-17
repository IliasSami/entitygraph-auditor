#!/usr/bin/env bash
#
# Fresh start for local development.
#
#   ./scripts/fresh_start.sh            # reset the dev DB, rebuild + restart API and web
#   KEEP_DB=1 ./scripts/fresh_start.sh  # keep the existing var/ega.db
#   EGA_API_PORT=8000 EGA_WEB_PORT=3000 ./scripts/fresh_start.sh
#
# Steps:
#   1. Stop whatever is listening on the API port, the web port, and the
#      Playwright e2e port (:3100). Other ports (e.g. a second API on :8001)
#      are left untouched.
#   2. (default) back up then remove var/ega.db so the app starts empty.
#   3. Start the FastAPI backend from the repo root (so ./var/ega.db resolves).
#   4. Build the Next.js web app from current source, then serve it.
#   5. Print health for both.
#
# Nothing is committed. Logs land in var/api.log, var/web-build.log, var/web.log.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API_PORT="${EGA_API_PORT:-8000}"
WEB_PORT="${EGA_WEB_PORT:-3000}"
E2E_PORT=3100
PY="${PY:-.venv/bin/python}"

mkdir -p var var/backups

kill_port() {
  local port="$1" pids
  pids="$(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    echo "    stopping pid(s) on :$port -> $pids"
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    sleep 1
  fi
}

echo "==> Stopping stale processes"
kill_port "$API_PORT"
kill_port "$WEB_PORT"
kill_port "$E2E_PORT"   # stray Playwright e2e server (should not persist)

if [[ "${KEEP_DB:-0}" != "1" ]]; then
  echo "==> Resetting the dev database"
  if [[ -f var/ega.db ]]; then
    cp var/ega.db "var/backups/ega.db.bak-$(date +%Y%m%d-%H%M%S)"
    rm -f var/ega.db var/ega.db-wal var/ega.db-shm
    echo "    backed up then removed var/ega.db"
  else
    echo "    no var/ega.db (already fresh)"
  fi
else
  echo "==> Keeping existing var/ega.db (KEEP_DB=1)"
fi

echo "==> Starting API on :$API_PORT (log: var/api.log)"
nohup "$PY" -m uvicorn ega_api.main:app --host 127.0.0.1 --port "$API_PORT" > var/api.log 2>&1 &
sleep 3

echo "==> Building web (log: var/web-build.log)"
# A stale Next.js dev lock makes `next build` fail with "Another next build
# process is already running" (and `next dev` re-creates it). Clear it first.
rm -f "$ROOT/apps/web/.next/dev/lock"
( cd apps/web && npm run build > "$ROOT/var/web-build.log" 2>&1 )
echo "    build complete"

echo "==> Starting web on :$WEB_PORT (log: var/web.log)"
( cd apps/web && PORT="$WEB_PORT" nohup npm run start -- -p "$WEB_PORT" > "$ROOT/var/web.log" 2>&1 & )
sleep 4

echo "==> Health"
printf '    api  :%s -> ' "$API_PORT"
curl -s -m 5 "http://localhost:$API_PORT/api/v1/health" || true
printf '\n    web  :%s -> ' "$WEB_PORT"
curl -s -m 5 -o /dev/null -w '%{http_code}\n' "http://localhost:$WEB_PORT/" || true

echo
echo "Ready:  API http://localhost:$API_PORT/api/v1   Web http://localhost:$WEB_PORT"
