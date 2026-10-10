# Agents Office — Yekdast

A private workshop run from one laptop. The owner is the only human (the CEO); 8 departments of agents are the staff.
The goal: get from an idea or a client request to a **validated or killed idea**, or a **live product**, within one working day.

Two lanes over one gated pipeline:

- **validate** (your idea, or "is there a market?"): intake → **research** → you. Web research where every kept claim quotes a page that was actually fetched. The verdict (GO / TEST / NO-GO) is computed from the evidence by the rubric in `backend/app/pipeline/research.py`, never written by an agent. From a finished memo you can start a landing-page test or the MVP.
- **build** (a client job, or an idea you validated): intake → verify → scope → build → security → preview → exposure → handoff. The builder extends a **golden template** (`templates/webapp/`, Next.js + Drizzle + Better Auth + Vitest + Playwright). The job container then installs, builds, tests, starts and browser-tests the app, and a red check sends the work back.

Agents research, build and deploy **previews** only. **Production is your Promote button**: it prepares a private repo and a production app, and deploys only after you confirm the variables are set. It then checks `/healthz`. Outreach and spending stay yours.
Everything that needs you is in one **NEEDS YOU** list on the Jobs screen (J), and Telegram can tell you when it changes.

Forked from [ajsahni/agents-office](https://github.com/ajsahni/agents-office) (see `NOTICE`). The 3D office UI is kept; the runtime is new.

**Read `.claude/plans/MASTER_PLAN.md` first.** It is the only plan: decisions, what is implemented, the 2026-10-10 audit (Part G) and the run log of the laptop runbook (Part F). `PLAN.md` is frozen history.

## What is in the repo

| Part | Where |
|---|---|
| API, model layer (LangChain/LangGraph, 9router), budget per lane | `backend/app/` |
| Job pipeline: lanes, lead and owner gates, exposure tiers, inbox, Promote endpoint | `backend/app/pipeline/` |
| Validate lane: web research and the rubric verdict in code | `backend/app/pipeline/research.py`, `backend/app/connectors/web.py` |
| Build worker (Claude Code headless; mini-swe-agent as a fallback) and hardened sandbox | `backend/app/worker/`, `sandbox.py`, `infra/sandbox/` |
| In-container checks: install, build, test, start, browser tests | `infra/sandbox/run-checks.mjs`, `backend/app/checks/run.py` |
| Golden web-app template every build starts from | `templates/webapp/` |
| Dokploy (previews, production), GitHub (product repos), Telegram (owner notifications) | `backend/app/connectors/` |
| Postgres, egress proxy, router gateway | `docker-compose.yml`, `infra/` |
| UI (single built HTML file) | `src/` → `dist/command-centre-v2.html` |
| Owner's notes (the "brain") | `brain-yekdast/` |

## Run (on the owner's laptop)

```
./setup            # preflight only: venv, npm ci, build, .env.local. Starts nothing.
npm run check      # build + backend tests + headless-browser smoke (live-UI part needs AO_TEST_DATABASE_URL)
npm run boot       # postgres + egress + router-gateway via Docker, then the API on 127.0.0.1:4520 (npm run stop)
npm run verify     # behaviour checklist (both lanes, gates, promote refusals, inbox) against the running office
```

Mutating API calls need the header `X-AO-Client: office` (the bundled UI sends it) and, if `AO_API_TOKEN` is set, `X-AO-Token`.
Secrets are env-var names in config, never values; copy `.env.example` to `.env.local`.

## Tests

`cd backend && python -m pytest -q` (254 tests, fakes for models, workers, Docker, Dokploy, GitHub, Telegram and the web).
Set `AO_TEST_DATABASE_URL=postgresql://…` to also run the real-Postgres tests, including restart-and-resume of a paused job.
`cd templates/webapp && npm ci && npm test && npm run build && npm run test:e2e` checks the template itself.
`?norender=1` on the UI URL skips 3D drawing (needed in headless browsers without a GPU).

## What has not been run

These have not been run against the real thing:
- 9router;
- the Claude Code worker in its container (Docker build of the worker image);
- Dokploy and its production app;
- GitHub repo creation;
- Telegram;
- the owner's web search tool.

The template and the in-container checks were run for real (outside Docker). MASTER_PLAN.md Part F.1 lists each remaining check with its pass/fail line.
