# Agents Office — Yekdast

A private workshop: 27 staffed seats (room for 10 per department) in 8 departments, plus a bench of Citadel roles that leads can spawn, run from one laptop, that take a request through a gated pipeline —
**intake → verify → scope → build → security → preview → exposure → handoff** — and stop at every gate for the lead who owns that stage.
Agents may research, validate, build and deploy a **preview** only. The owner does outreach, production and spending.

Forked from [ajsahni/agents-office](https://github.com/ajsahni/agents-office) (see `NOTICE`). The 3D office UI is kept; the runtime is new.

**Read `.claude/plans/PLAN.md` first.** It is the only plan: decisions, architecture, what is implemented, and the laptop runbook.

## What is in the repo

| Part | Where |
|---|---|
| API, task engine, model layer (LangChain/LangGraph, 9router) | `backend/app/` |
| Job pipeline (LangGraph, Postgres checkpointer, lead gates, exposure tiers) | `backend/app/pipeline/` |
| Build workers (Claude Code, mini-swe-agent, OpenHands, fake) and hardened sandbox | `backend/app/worker/`, `sandbox.py`, `infra/sandbox/` |
| Dokploy and GitHub connectors behind an allow-list | `backend/app/connectors/` |
| Postgres, egress proxy, router gateway | `docker-compose.yml`, `infra/` |
| UI (single built HTML file) | `src/` → `dist/command-centre-v2.html` |
| Owner's notes (the "brain") | `brain-yekdast/` |

## Run (on the owner's laptop)

```
./setup            # preflight only: venv, npm ci, build, .env.local. Starts nothing.
npm run check      # build + backend tests + headless-browser smoke (live-UI part needs AO_TEST_DATABASE_URL)
npm start          # postgres + egress + router-gateway via Docker, then the API on 127.0.0.1:4520
```

Mutating API calls need the header `X-AO-Client: office` (the bundled UI sends it) and, if `AO_API_TOKEN` is set, `X-AO-Token`.
Secrets are env-var names in config, never values; copy `.env.example` to `.env.local`.

## Tests

`cd backend && python -m pytest -q` (182 tests, fakes for models, workers, Docker and Dokploy).
Set `AO_TEST_DATABASE_URL=postgresql://…` to also run the real-Postgres tests, including restart-and-resume of a paused job.
`?norender=1` on the UI URL skips 3D drawing (needed in headless browsers without a GPU).

## What has not been run

No live 9router, real worker CLI, Docker sandbox, Dokploy or VPS has been exercised. PLAN.md §11 lists each check with its pass/fail line.
