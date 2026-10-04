#!/usr/bin/env bash
# Boot the stack on the owner's laptop: Postgres + egress proxy + router gateway (Docker), then the API.
#   scripts/boot.sh [--dry-run]       the API runs on 127.0.0.1:${PORT:-4520}; its pid is in data/api.pid
# Stops with scripts/stop.sh. Never uses pattern kills: only the pidfile.
set -euo pipefail
cd "$(dirname "$0")/.."
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
PORT="${PORT:-4520}"
run() { if [ "$DRY" = 1 ]; then echo "[dry-run] $*"; else "$@"; fi; }
die() { if [ "$DRY" = 1 ]; then echo "[dry-run] would stop here: $*"; else echo "boot: $*" >&2; exit 1; fi; }

command -v docker >/dev/null || die "docker is not installed"
docker compose version >/dev/null 2>&1 || die "docker compose v2 is required"
[ -x backend/.venv/bin/uvicorn ] || die "run ./setup first (backend/.venv is missing)"
[ -f .env.local ] || die ".env.local is missing: cp .env.example .env.local and fill it in"
if [ -f .env.local ]; then set -a; . ./.env.local; set +a; fi
[ -n "${ROUTER_API_KEY:-}" ] || die "ROUTER_API_KEY is empty in .env.local"
if [ -f data/api.pid ] && kill -0 "$(cat data/api.pid)" 2>/dev/null; then die "the API is already running (pid $(cat data/api.pid)); scripts/stop.sh first"; fi
if (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; then die "port $PORT is in use"; fi

run docker compose up -d postgres egress router-gateway
if [ "$DRY" = 0 ]; then
  for i in $(seq 1 60); do
    [ "$(docker compose ps --format '{{.Health}}' postgres 2>/dev/null | head -1)" = "healthy" ] && break
    [ "$i" = 60 ] && die "postgres did not become healthy"
    sleep 1
  done
fi

mkdir -p data
if [ "$DRY" = 1 ]; then
  echo "[dry-run] backend/.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port $PORT  (pid -> data/api.pid, log -> data/api.log)"
  exit 0
fi
nohup backend/.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port "$PORT" > data/api.log 2>&1 &
echo $! > data/api.pid
for i in $(seq 1 60); do
  curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null && { echo "up: http://127.0.0.1:$PORT (pid $(cat data/api.pid))"; exit 0; }
  kill -0 "$(cat data/api.pid)" 2>/dev/null || die "the API exited; see data/api.log"
  sleep 1
done
die "the API did not answer on /api/health; see data/api.log"
