#!/usr/bin/env bash
# Entry point of every build-job container. Runs the coding agent, then commits whatever
# it wrote and produces the artefacts the host reads, so the host never runs git or
# npm on the agent's repository:
#   /out/patch.bundle      git bundle of the work
#   /out/tree.tar.gz       source tree without .git and node_modules (scanned on the host)
#   /out/npm-audit.json    npm audit of production dependencies
#   /out/checks.json       install / build / test / start / browser-test results (run-checks.mjs)
#   /out/agent.stdout|stderr, /out/exit_code
# With AO_CHECKS_ONLY=1 it only re-runs run-checks.mjs on the existing workspace.
set -uo pipefail
cd /workspace

# Re-run only the proof (the host sets this after a registry outage, so the agent's work is not
# redone): the workspace, patch and tree from the earlier run stay as they are.
if [ -n "${AO_CHECKS_ONLY:-}" ]; then
  rm -f /out/checks.json /out/checks.log
  node /opt/run-checks.mjs >/out/checks.log 2>&1 || true
  exit 0
fi

# A stale result from an earlier attempt must never be read as this run's proof.
rm -f /out/checks.json /out/checks.log /out/patch.bundle /out/tree.tar.gz /out/npm-audit.json /out/exit_code /out/retries

GIT=(git -c core.hooksPath=/dev/null -c safe.directory=/workspace -c user.email=agent@office.local -c user.name=office-agent)
"${GIT[@]}" init -q 2>/dev/null
"${GIT[@]}" add -A && "${GIT[@]}" commit -qm "task" --allow-empty

# A free router model sometimes drops the stream ("API Error: upstream connection lost") and Claude
# Code exits early with is_error. That is the platform's failure, not the agent's: resume the same
# session (--continue) instead of handing a half-done workspace to the review. Bounded; other
# commands and other errors are never retried.
: >/out/agent.stdout; : >/out/agent.stderr
attempt=0; extra=()
while :; do
  "$@" "${extra[@]}" >>/out/agent.stdout 2>>/out/agent.stderr
  code=$?
  attempt=$((attempt + 1))
  last=$(tail -n 1 /out/agent.stdout)
  [ "$1" = claude ] && [ "$attempt" -lt 4 ] && grep -q '"is_error":true' <<<"$last" \
    && grep -qiE 'upstream connection lost|API Error: (5[0-9]{2}|Connection|Request timed out)' <<<"$last" || break
  echo "run-job: transient API error, resuming session (attempt $attempt)" >>/out/agent.stderr
  extra=(--continue); sleep 5
done
echo "$((attempt - 1))" >/out/retries   # recorded by the host as evidence

# The lockfile is made BEFORE the commit, so the bundle and the scanned tree contain it.
if [ -f package.json ] && [ ! -f package-lock.json ]; then
  npm install --package-lock-only --ignore-scripts >/dev/null 2>&1
fi
"${GIT[@]}" add -A && "${GIT[@]}" commit -qm "agent work" --allow-empty
"${GIT[@]}" bundle create /out/patch.bundle --all 2>>/out/agent.stderr
tar --exclude=.git --exclude=node_modules -czf /out/tree.tar.gz -C /workspace . 2>>/out/agent.stderr

if [ -f package.json ]; then
  npm audit --omit=dev --json >/out/npm-audit.json 2>/dev/null
fi

# Prove the app works, here in the job container: the host only reads the results.
node /opt/run-checks.mjs >/out/checks.log 2>&1 || true

echo "$code" >/out/exit_code
exit "$code"
