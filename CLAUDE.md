# Agents Office — for Claude Code

Read `.claude/plans/PLAN.md` before doing anything. It is the single plan and holds the decisions, the architecture and **§11, the laptop runbook**. Update it when a decision changes; do not create other plan files.

## Your job on the laptop
Boot with `npm run boot`, check it with `npm run verify`, and execute the runbook in PLAN.md §11 in order. In short:
- S1: 9router.
- S1b: find and bind the owner's keyless web search/fetch tool.
- S2: build the worker image and run the bakery job on Claude Code/Haiku from the template; record the wall clock.
- S3: Postgres restart and resume.
- S4: budget per lane.
- S5: Dokploy preview.
- S6: Promote one app to production.
- S7: Telegram.
- Then a stress test.

Record each result (pass/fail line, evidence, minutes) in PLAN.md §11 and fix the code only where a check proves it wrong.

## Rules that do not bend
- Agents may build and deploy **previews** only. Never production, marketing, outreach or spending. Production is the owner's Promote endpoint (`/api/jobs/{id}/promote`); nothing an agent can call may reach it (`tests/test_promote.py` pins this).
- A verdict that can be computed is computed: build gates on the container's checks, market verdicts on the rubric in `pipeline/research.py`. Never let a model's prose upgrade either.
- Builds extend `templates/webapp/`; keep its `npm test`, `npm run test:e2e`, `/healthz`, Dockerfile and `start` script working when you change it, and rerun `infra/sandbox/run-checks.mjs` on a copy.
- Separation of duties: the building department never approves exposure. Each lead approves only its own stages (map in `backend/app/config.py`, `DEFAULT_STAGES`).
- Never put a secret in a file; config holds env-var **names**. Never give a container the Docker socket or credentials.
- Never use `pkill -f` / `pgrep -f`; use pid files.
- Unverified flags in `backend/app/worker/*.py` are marked; confirm them against the real CLI before trusting them.

## Layout
`backend/app/` API + pipeline (`pipeline/`), workers (`worker/`), `sandbox.py`, `connectors/`, `checks/`, `migrations/`. UI in `src/` built by `node build.mjs`. Seat names come from `backend/app/seed/roster_seed.json`; `office.agents.json` holds only overrides (`brief`, `does`, `tools`, `model`, `effort`; `id`/`department`/`lead` are fixed).
Owner skills live in `<brain>/Agents Office/skills/<name>/SKILL.md` (guide: `SKILLS.md`); routines in `<brain>/Agents Office/routines.json`.

## Loop
`npm run check` after any change (set `AO_TEST_DATABASE_URL` for the live-UI and Postgres parts). One check run at a time: they share one database.
