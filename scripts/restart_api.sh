#!/usr/bin/env bash
# Restart only the API (Postgres keeps running): used by the restart/resume check.
set -euo pipefail
cd "$(dirname "$0")/.."
scripts/stop.sh --api-only
set -a; . ./.env.local; set +a
mkdir -p data
nohup backend/.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port "${PORT:-4520}" > data/api.log 2>&1 &
echo $! > data/api.pid
