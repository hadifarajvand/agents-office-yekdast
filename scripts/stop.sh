#!/usr/bin/env bash
# Stop the API (by pidfile) and, unless --api-only, the Docker services.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f data/api.pid ]; then
  pid="$(cat data/api.pid)"
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
    for i in $(seq 1 20); do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
    kill -0 "$pid" 2>/dev/null && kill -9 "$pid" || true
  fi
  rm -f data/api.pid
fi
if [ -f data/worker.pid ]; then  # the arq worker (AO_QUEUE=1), also by pidfile
  pid="$(cat data/worker.pid)"
  kill -0 "$pid" 2>/dev/null && kill "$pid" || true
  rm -f data/worker.pid
fi
[ "${1:-}" = "--api-only" ] || { [ "${1:-}" = "--dry-run" ] && echo "[dry-run] docker compose stop" || docker compose stop; }
echo "stopped"
