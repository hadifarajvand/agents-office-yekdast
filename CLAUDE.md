# Agents Office — for Claude Code

Read `.claude/plans/PLAN.md` before doing anything. It is the single plan and holds the decisions, the architecture and **§11, the laptop runbook**. Update it when a decision changes; do not create other plan files.

## Your job on the laptop
Execute the runbook in order: S1 9router → S2 worker bake-off → S3 Postgres restart/resume → S4 cost metering → S5 Dokploy preview → boot → stress test → agent personas. Record each result (pass/fail line, evidence) in PLAN.md §11 and fix the code only where a check proves it wrong.

## Rules that do not bend
- Agents may build and deploy **previews** only. Never production, marketing, outreach or spending.
- Separation of duties: the building department never approves exposure. Each lead approves only its own stages (map in `backend/app/config.py`, `DEFAULT_STAGES`).
- Never put a secret in a file; config holds env-var **names**. Never give a container the Docker socket or credentials.
- Never use `pkill -f` / `pgrep -f`; use pid files.
- Unverified flags in `backend/app/worker/*.py` are marked; confirm them against the real CLI before trusting them.

## Layout
`backend/app/` API + pipeline (`pipeline/`), workers (`worker/`), `sandbox.py`, `connectors/`, `checks/`, `migrations/`. UI in `src/` built by `node build.mjs`. Seat names come from `backend/app/seed/roster_seed.json`; `office.agents.json` holds only overrides (`brief`, `does`, `tools`, `model`, `effort`; `id`/`department`/`lead` are fixed).
Owner skills live in `<brain>/Agents Office/skills/<name>/SKILL.md` (guide: `SKILLS.md`); routines in `<brain>/Agents Office/routines.json`.

## Loop
`npm run check` after any change (set `AO_TEST_DATABASE_URL` for the live-UI and Postgres parts). One check run at a time: they share one database.
