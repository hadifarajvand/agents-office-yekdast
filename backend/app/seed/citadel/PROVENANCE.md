# Citadel personas (vendored, unmodified)

Source: https://github.com/Citadel-Cloud-Management/citadel-saas-factory
Commit: 7c7ba41d6a262d3b97de8525f39b32100192f6c5
License: MIT, Copyright (c) 2026 Citadel Cloud Management (see LICENSE and /NOTICE)

Files here are byte-for-byte copies of `.claude/` from that commit. Do not edit them; re-vendor
from a new commit and update the hash above. Our own choices (which seat uses which persona,
which tier maps to which model, which tools a seat may call) live in code and config, not here.

- `agents/<domain>/`  the persona files our four live departments draw on: executive and legal -> exec,
  engineering -> engineering, security and data-analytics -> secdata, devops and qa-testing -> devops
  (87 + 8 + 22 + 18 = 135 files)
- `agents/hand/`    the 11 hand-written Claude Code subagents (they carry real tool allowlists)
- `rules/`          the rules that apply to those departments
- `skills/`         code-review, deploy, security-audit, guardrails, tdd
- `catalog/`        registry, subagent and tool catalogs (reference; read by `app/personas.py` only
  for the tool vocabulary)

Known limits of the source, measured at this commit: the 135 department persona files are one template
with the name and role text swapped; every one has `tools: []` and `skills: []`.
