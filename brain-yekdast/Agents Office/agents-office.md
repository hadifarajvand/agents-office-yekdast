# Agents Office — how this office works

This folder is the office's own working area inside the brain. The platform writes here:

- `skills/<name>/SKILL.md` — how a kind of work is done (see SKILLS.md in the repo).
- `feedback/<agent-id>.md` — corrections the owner gave an agent; standing rules are read before every task.
- `routines.json` — scheduled tasks.
- `audit/mcp-access.log` — every connector call, allowed or refused.

Everything except this note is local runtime data and is not committed.

The office runs client jobs through one pipeline: intake → verify → scope → build → security review → preview deploy → exposure decision → handoff. Each stage is approved by the lead of the department that owns it. The building department never decides whether its own app is exposed to the public.
