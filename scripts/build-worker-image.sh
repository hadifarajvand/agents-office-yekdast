#!/usr/bin/env bash
# Build the job image (agents-office/worker-node:latest) from the layer cache.
# Never pulls the base image (--pull=false), and says how many layers were reused. The slow,
# downloading layers (apt, Claude Code, Chromium, the template's npm cache) sit above the two
# COPYs of run-job.sh / run-checks.mjs, so editing those scripts rebuilds in about a second. Only
# a change to templates/webapp/package.json or package-lock.json re-runs the npm layer.
set -euo pipefail
cd "$(dirname "$0")/.."
log="$(mktemp)"
trap 'rm -f "$log"' EXIT
docker build --pull=false --progress=plain \
  --build-context template=templates/webapp \
  -f infra/sandbox/worker-node.Dockerfile \
  -t agents-office/worker-node:latest infra/sandbox >"$log" 2>&1 || { tail -30 "$log"; exit 1; }
steps="$(grep -E '^#[0-9]+ \[stage-0 +[0-9]+/[0-9]+\]' "$log" | grep -vc ' FROM ' || true)"
cached="$(grep -cE '^#[0-9]+ CACHED' "$log" || true)"
echo "agents-office/worker-node:latest built: ${cached} of ${steps} layers reused"
if [ "$cached" -lt "$steps" ]; then
  echo "re-run layers (the rest were reused):"
  # a step line followed by CACHED is a hit; the rest ran
  awk '/^#[0-9]+ \[stage-0 +[0-9]+\/[0-9]+\]/ && !/ FROM / {id=$1; line=$0; sub(/^#[0-9]+ /, "", line); s[id]=line}
       /^#[0-9]+ CACHED/ {hit[$1]=1}
       END {for (k in s) if (!(k in hit)) print "  " s[k]}' "$log" | cut -c1-110 | sort
fi
