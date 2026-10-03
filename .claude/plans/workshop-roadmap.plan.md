# Plan: Workshop Ecosystem — Validate → Build → Ship → Market (lean)

**Date**: 2026-10-03 · **Supersedes**: `agents-office-implementation.plan.md` (kept as history; do not execute it)
**Owner goal (2026-10-03)**: an internal workshop for building, deploying and marketing SaaS products and apps, where departments first research a product idea and decide whether it is worth building.
**Constraints**: internal use only (see Risk 1). One real connector: GitHub. Everything else is LLM + web search.

## Principles

1. **Validate before building.** Stage 1 (research + evaluation) is the product. If it is not useful alone, nothing after it matters.
2. **Prove one vertical slice per stage** on a real idea before adding any seat, department, or UI.
3. **No new seats.** Use existing seats by renaming (`office.agents.local.json`). The 35-seat roster is already more than needed. The 70-seat redesign, `success`/`product` departments and 3-column layout are **frozen**.
4. **Agents author, a human approves, CI executes** (Path B). Keep it, test it with real calls.
5. **Every stage has a kill criterion.** If it fails, stop and rethink rather than add features.

## Stage 0 — Honest baseline (≈2 days)

- Resolve the license question (Risk 1) before more building.
- Make docs match code: rewrite `CLAUDE.md` / `README.md` for the Python/Docker backend (no `claude mcp list`, no `npm start` meaning Node). Fix the Haiku-vs-Sonnet default and the routine-department drift.
- Delete or archive dead Node leftovers and `.claude/` planning docs that no longer apply. Keep `GUARDRAILS.md`.
- Pin compatible `langgraph` + `langgraph-checkpoint-postgres` versions (current pair warns as incompatible).
- Run `docker compose up --build` with a real model proxy and record the result.
- **Done when**: stack boots, one trivial task completes through the UI, `pytest` and `npm run check` are green with deps installed.

## Stage 1 — Idea Validation pipeline (≈1 week) — THE CORE

Input: a one-paragraph product idea. Output: a one-page **go / no-go memo** saved to the brain.

Roles (rename 5 existing seats; do not add any):
| Role | Job |
|---|---|
| Market Researcher | Size, competitors, pricing, demand signals, via web search with cited sources |
| Customer Analyst | Who pays, why, current alternatives, willingness to pay |
| Technical Scoper | Build complexity, stack, effort in weeks, main technical risks |
| Financial Modeller | Cost to build/run, price points, break-even; every number labeled assumption or sourced |
| Critic (adversarial) | Attacks the other four: weakest assumption, strongest counterargument, kill reasons |

Flow: Researcher + Analyst + Scoper + Modeller work in parallel, then the Critic, then the lead issues **GO / TEST / NO-GO** with the top three risks. Human approves the verdict (existing approval gate).

Rules baked into the skill: cite sources or mark as unverified; separate fact from assumption; no verdict without a stated kill criterion.

- **Done when**: run on 3 ideas you already know the answer to (one good, one bad, one ambiguous). The pipeline reaches the right verdict on the clear ones and flags the real uncertainty on the ambiguous one.
- **Kill criterion**: if memos read as generic or uncited after 2 prompt/skill iterations, stop and rethink the approach before building Stage 2.

## Stage 2 — GitHub connector, read-only (≈3 days)

- Implement real `discover()` in `backend/app/mcp.py` with the GitHub MCP server (explicit URL + token from `.env.local`, not CLI discovery). Read-only scopes only.
- Give the Technical Scoper repo-reading ability so scoping can use existing code.
- **Done when**: an agent reads a real repo through the policy gate, the call appears in `mcp-access.log`, and a write attempt is refused.

## Stage 3 — Build by draft PR (≈1–2 weeks)

- Only for ideas with a human-approved GO.
- Engineer seat plans, then opens a **draft PR** to a scratch repo (write scope limited to that repo). A human reviews and merges. No direct pushes to main, no deploys by agents.
- **Done when**: one small real feature goes idea → memo → draft PR → merged by you, with tests passing.
- **Kill criterion**: if review effort exceeds writing it yourself on 3 consecutive tasks, stop and reconsider.

## Stage 4 — Deploy and marketing (later, only after Stage 3 passes)

- Deploy: agents write CI/CD config; the pipeline runs it; human approves production. Needs GitLab/CI credentials you have not provided.
- Marketing: copy, landing page and email drafts only. Nothing sent without approval. Needs connectors you have not listed.
- Do not design these further until Stage 3 exists.

## Frozen / removed from scope

70-seat expansion, `success`/`product` departments, Citadel persona mapping, 3-column layout, Redis routine locking beyond what exists, 20-agent arena validation. Reopen only if Stages 1–3 prove demand for them.

## Risks

1. **License.** The repo is a fork under PolyForm Noncommercial. Using it internally is fine. Using it as the engine of a business that sells SaaS is a gray area at best. Get written clarification from the upstream author, or rewrite the orchestration core without upstream code, before commercial use of the workshop.
2. **Research quality.** LLM market research hallucinates figures. Mitigation: mandatory citations, Critic role, human approval, and testing on known-answer ideas first.
3. **Safety heuristic.** Boundary checks are word-matching between prose and tool names. Treat as defence in depth only; the real controls are read-only scopes, scratch-repo write scope, and human approval.
4. **Cost.** Parallel multi-agent research multiplies token spend. Keep Haiku default, escalate the Critic and lead only; log tokens per memo.

## Success metrics (2 weeks)

- 3 validation memos produced; ≥2 judged by you as useful enough to act on.
- Median cost and time per memo recorded.
- Zero unapproved outbound or write actions in the audit log.
