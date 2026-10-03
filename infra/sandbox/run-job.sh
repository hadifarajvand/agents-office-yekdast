#!/usr/bin/env bash
# Entry point of every build-job container. Runs the coding agent, then commits whatever
# it wrote and produces the artefacts the host reads, so the host never runs git or
# npm on the agent's repository:
#   /out/patch.bundle      git bundle of the work
#   /out/tree.tar.gz       source tree without .git and node_modules (scanned on the host)
#   /out/npm-audit.json    npm audit of production dependencies
#   /out/agent.stdout|stderr, /out/exit_code
set -uo pipefail
cd /workspace

GIT=(git -c core.hooksPath=/dev/null -c user.email=agent@office.local -c user.name=office-agent)
"${GIT[@]}" init -q 2>/dev/null
"${GIT[@]}" add -A && "${GIT[@]}" commit -qm "task" --allow-empty

"$@" >/out/agent.stdout 2>/out/agent.stderr
code=$?

"${GIT[@]}" add -A && "${GIT[@]}" commit -qm "agent work" --allow-empty
"${GIT[@]}" bundle create /out/patch.bundle --all 2>>/out/agent.stderr
tar --exclude=.git --exclude=node_modules -czf /out/tree.tar.gz -C /workspace . 2>>/out/agent.stderr

if [ -f package.json ]; then
  [ -f package-lock.json ] || npm install --package-lock-only --ignore-scripts >/dev/null 2>&1
  npm audit --omit=dev --json >/out/npm-audit.json 2>/dev/null
fi

echo "$code" >/out/exit_code
exit "$code"
