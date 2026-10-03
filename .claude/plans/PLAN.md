# PLAN — Workshop platform (single source of truth)

**Updated**: 2026-10-03 · **Supersedes and replaces**: `agents-office-implementation.plan.md` (70-seat org redesign + foundation tasks), `workshop-roadmap.plan.md`, `LANGGRAPH-MIGRATION-PLAN.md`. Their useful content is merged here; the rest was dropped on purpose (section 11). Recover any of them from git history if needed.
**Related**: `docs/design/01-rubric.md` (idea-validation decision rubric, draft), `.claude/GUARDRAILS.md` (Path B execution rules).

Items marked **[verified]** were checked against a source or by running code. **[unverified]** means a claim from docs or reasoning that has not been tested here. **[decided]** means the owner decided it.

---

## 1. Goal and decisions

**Goal [decided]**: an internal workshop platform, running on the owner's machine, that takes a candidate product (the owner's own or a client's), decides whether it is worth building, builds an MVP, and produces a client-visible preview — with the owner approving at gates.

| Decision | Value | Source |
|---|---|---|
| Users | One owner; platform stays on owner's machine; VPS is only the deploy target | owner |
| Idea source | Owner supplies candidates; platform deepens them. No scanning in v1 | owner |
| First job | A client request. Client work requires a **paid deposit or contract** before any build | owner |
| Strictness | Strict: building a bad idea costs more than missing a good one. TEST is a common outcome | owner |
| Agents may | Research, validate, build, deploy a **preview** | owner |
| Agents may not | Marketing, client outreach, production deploy, spend. Owner does all outreach personally | owner |
| After GO | **3-day** launch deadline, otherwise archived | owner |
| 60-day success metric | A verdict the owner trusts, plus a deployable MVP preview. (First paying customer comes later) | owner |
| Orchestration | **LangChain + LangGraph are required** | owner |
| Checkpoint store | **Postgres** | owner |
| Language | Python | owner |
| Container | Docker, **container-based sandbox** | owner |
| Model access | **9router** local proxy | owner |
| Sequencing | Platform first, no manual run | owner |
| Licence | Internal use only (fork of PolyForm Noncommercial upstream) | owner |

Contradiction the owner has accepted: the owner does all outreach, and last time "couldn't reach buyers" was a failure. The platform makes validation and building cheap; it does not fix distribution.

## 2. Operating model

Two paths, one pipeline:

```
intake → verify → scope → [GATE: owner approves verdict] → build → preview-deploy-config → handoff
```

- **Client path (first)**: demand evidence is the paid deposit or contract. Verify = the deposit/contract is real, scope and acceptance criteria are clear, price fits effort, 3-day delivery is realistic.
- **Own-product path (later)**: needs evidence from the web (competitor revenue, public pain posts) per the rubric. **Blocked until web search and fetch tools exist and are gated.**
- Real-world tests (landing page price test, outreach, pre-sale) are marketing, so they are **owner actions**; the memo hands them over.
- Deploy: agents write deploy configuration into the job folder; **the owner runs it** against the VPS. No SSH keys reach an agent.
- Rubric details (gates, evidence tiers, verdict rules, budget): `docs/design/01-rubric.md`. Its numeric thresholds are proposals until calibrated.

**Run budget [decided target, unmeasured]**: under $1 per validation memo. With 9router the displayed cost is an estimate, so the platform meters tokens itself (section 6).

## 3. Architecture

```
Host (owner's machine)
├─ Orchestrator (FastAPI on 127.0.0.1, token header) ─ LangGraph graph ─ Postgres (checkpoints + job state)
│    └─ talks OpenAI-format to 9router (localhost:20128/v1)
├─ Egress proxy (allowlist, logging, credential injection)
├─ MCP servers on the host (GitHub read-only), reached by the orchestrator, never inside the sandbox
└─ Per-job sandbox container(s)  ← build worker runs here, no host credentials, no direct internet
```

### 3.1 Stack (dependency resolution checked with `pip --dry-run`, nothing installed or run)

| Layer | Choice | Version | Status |
|---|---|---|---|
| Orchestration | LangGraph | 1.2.12 | resolves [verified]; **major jump from repo's 0.2.68, API changes unchecked** |
| Checkpointer | langgraph-checkpoint-postgres | 3.1.2 (+ psycopg 3.3.x) | resolves [verified] |
| Model client | langchain-openai | 1.6.7 | resolves [verified]; chosen because 9router documents only an OpenAI-compatible API |
| Tools | langchain-mcp-adapters | 0.3.2 (mcp 1.30) | resolves [verified] |
| API | FastAPI | 0.142 | resolves [verified] |
| Docker control | `docker` Python SDK | 7.2 | resolves [verified] |
| Build worker | **OpenHands Software Agent SDK + Agent Server** | 1.51.0, Python >=3.12 | see 4; **in its own image, never in the orchestrator's environment** |

Dropped from the old stack: Redis (existed only for a multi-replica routine lock; routines are out of v1), `langchain-anthropic` (9router is OpenAI-format), Node legacy modules (after test porting), the 35-seat/8-department structure for v1.

### 3.2 Why LangGraph here
Pause-and-resume at approval gates, parallel evidence branches merged into a critic, durable job state in Postgres. Required by the owner regardless.

## 4. Build worker — OpenHands (Docker-based)

Chosen: **OpenHands Software Agent SDK / Agent Server** (MIT, REST API, runs each conversation in its own Docker container, conversation persistence, MCP support, headless, any LLM via LiteLLM with a custom base URL). It is the only candidate that is natively Docker-based, drivable from an external orchestrator over REST, and works with an OpenAI-compatible endpoint such as 9router.

| Candidate | Verdict |
|---|---|
| **OpenHands SDK + Agent Server** | **Chosen.** Caveats: project marked beta; SDK repo ~1.2k stars (the 72k figure is the parent project); Python >=3.12 with a heavy dependency tree (litellm, fastmcp, pins on `docker<8`, `openai<3`) so it must be isolated in its own image. |
| mini-swe-agent | Documented fallback for small jobs: ~100-line core, bash-only, Docker/Podman environments, LiteLLM, >74% SWE-bench Verified (self-reported). No file-editor tools, no MCP. |
| Claude Agent SDK / Claude Code | Strong, but expects the Anthropic Messages format and API-key auth; 9router's Anthropic-endpoint support is unconfirmed and Anthropic says third parties may not offer claude.ai login. Revisit only if 9router is replaced by an API key. |
| Dagger container-use | Rejected for v1: experimental, MCP-server model, docs state nothing about egress control or secrets. |
| Aider, Goose, OpenCode, Codex CLI, Cline | **Not researched in depth.** Not ruled out; evaluate only if the OpenHands spike fails. |
| Managed Agents (Anthropic-hosted) | Rejected: hosted beta, client code leaves the machine, not ZDR-eligible. |

**Docker-socket rule**: the agent container must never get `/var/run/docker.sock` (that is host-root). The host orchestrator starts and stops sandboxes; the worker runs inside a container it cannot escape from. Whether OpenHands' Docker workspace can run that way is **[unverified] — Spike S2**.

## 5. Sandbox — hardened Docker containers

Container-based, layered. All layers are required for the build stage.

1. **Boundary**: one throwaway container per job. Non-root user, `--cap-drop ALL`, `no-new-privileges`, read-only root filesystem, tmpfs for scratch, memory/CPU/pids limits, seccomp profile. (Flags from Anthropic's secure-deployment guide [verified, doc].)
2. **Stronger runtime tier (optional per job)**: gVisor `--runtime=runsc` (Linux hosts) or Kata/Sysbox for untrusted client repos. Plain Docker shares a kernel with the Docker VM/host; on macOS Docker Desktop that kernel sits inside a Linux VM, which protects the host but not one job from another. Host OS is **unknown**, so the runtime is configurable.
3. **Network**: job network is `internal` (no route out). The only path out is an **egress proxy sidecar** (Squid or mitmproxy) with a domain allowlist: 9router endpoint (one host:port), package registries needed for the job, nothing else. DNS only via the proxy. Everything logged. (Pattern: two Docker networks, dual-homed proxy [documented by several projects].)
4. **Credentials**: the container holds only placeholders; the proxy injects real tokens. GitHub access is a host-side MCP server, not a token in the container.
5. **Filesystem**: the job gets a **copy** of the workspace in a volume — never a bind mount of the home directory, never `~/.ssh`, `~/.aws`, `.env`. Output leaves as a patch or git bundle that the orchestrator copies out and the owner reviews.
6. **Stage split (key rule)**: the *validation* stage may read the web but never holds client code; the *build* stage holds client code but has no open internet. No stage has private data + untrusted content + a way out at the same time.
7. **Inside the container**: the worker's own permission/confirmation mode stays on for any action outside the job directory.

Known limits (honest): a proxy that allowlists by hostname without TLS inspection can be bypassed by domain fronting; any allowed domain can still carry exfiltrated data the agent can read. This lowers risk, it does not remove it. Docker Sandboxes (microVM) is the escalation if container isolation proves insufficient; the owner asked for container-based, so it is not the default.

## 6. Model access — 9router

**Facts [verified from the 9router docs and README, not by running it]**: local OpenAI-compatible endpoint `http://localhost:20128/v1`; translates between OpenAI/Claude/Gemini formats; routes across subscription accounts, cheap and free tiers with automatic fallback; model names like `cc/claude-opus-5[1m]`; default `REQUIRE_API_KEY=false`; Docker image binds `0.0.0.0`; cost figures are "estimated costs, not actual billing"; no provider-terms disclaimer.

**Consequences for the design**
- **Pin the model for verdict-bearing stages.** Silent fallback "subscription → cheap → free" means a different, weaker model can answer without notice. Use single-model combos for gates and the critic, and record the model name returned in every response in the run log. A verdict whose model cannot be identified is invalid.
- **Lock the router down.** Set `REQUIRE_API_KEY=true`, bind to loopback or the Docker network only, never LAN. It holds subscription OAuth tokens.
- **Meter tokens ourselves** from response usage fields to enforce the $1 cap; do not trust 9router's estimates.
- **Use the OpenAI-format client** (`langchain-openai`). Whether 9router also serves Anthropic `/v1/messages` is unconfirmed (**Spike S1**); the old code assumed it with `/v1` appended, which would double the path.
- **Provider-terms risk, recorded once**: Anthropic's Agent SDK docs state third parties may not offer claude.ai login or rate limits to their products and direct developers to API keys. Routing a subscription through a third-party router is the owner's decision; its compatibility with Anthropic's terms is **unverified here**. Mitigation: keep a pay-per-token API-key provider configured in 9router as the fallback so the platform does not stop if the subscription route is closed.

## 7. Security requirements (carried from audit)

- API on `127.0.0.1` only; token header; reject non-JSON bodies; origin/host checks; generic error bodies. (Browser pages can reach localhost services, so localhost alone is not enough.)
- Secrets: redact in logs, never in deliverables. **Done** in `policy.py` (`redact`, `redact_secrets`, newline-safe audit lines) with tests.
- Tool gating: explicit per-job allow-list enforced by a pre-tool hook/gate — not word-matching against prose.
- Approvals atomic (compare-and-set) so a double click cannot approve twice.
- Path B (agents author, humans approve and execute) stays: `.claude/GUARDRAILS.md`.

## 8. Current state (from the 2026-10-03 audit)

**Verified**: backend tests pass (104 incl. 9 new); `npm run check` 15/17 with deps missing (environmental). Stack has never been booted against a live model.

**Done**: skills loader no longer crashes when the brain is outside the app root; stronger secret redaction; audit-log lines cannot be forged with newlines; regression tests (`backend/tests/test_phase_a_hardening.py`).

**Open Critical/High**
1. No authentication or CSRF protection on `/api/*`; compose publishes the port on all interfaces.
2. `learn.classify` is called with a `timeout` argument that `llm.ask` rejects, so lessons are never classified (silently swallowed).
3. Human-in-the-loop only wired for routines; manual tasks ignore router `needs_ok`.
4. Double-approve race; fire-and-forget tasks with no references; tasks stuck in "doing" never recovered; silent exception swallowing in the routine tick.
5. Routine data loss paths (invalid routines deleted on save, non-atomic writes, PATCH unvalidated, state wipe).
6. Policy gate is a word-match heuristic; `mcp.discover()` is a stub and `tools_for()` returns `[]`, so the tool loop only ever ran against fakes. The prompt also claims web tools that do not exist.
7. `engine.py` uses the final output redaction that mangles emails/phones in drafts — switch to `redact_secrets()`.
8. Roster file `office.agents.json` is the stale legacy business-ops roster (29/35 names differ from the seed/UI; no briefs; dead connectors). Moot for v1 if the 35-seat structure is retired.
9. Frontend contract gaps (parked): the approval card never shows because the backend omits `waitingAt`/`startedAt`/`doneAt`; `/api/brain` lacks `nodes/links`.
10. Hygiene: default model contradicts across files (`office.config.json` says sonnet; code/docs say haiku); `brain-yekdast/` not git-ignored; `.arena/` and `graphify-out/` committed (4.4 MB generated); `./setup` and `scripts/release.mjs` reference nonexistent files (release script would push to the upstream author's repo); no `NOTICE`/upstream credit.

## 9. Roadmap (revised order)

**Phase 0 — Spikes (decide before building). Each has a pass/fail test.**
- **S1 · 9router surface**: does it serve what we need, and can the model be pinned? *Pass*: a LangGraph node calls it with `langchain-openai`; the response names the exact model; fallback does not trigger when a combo is pinned; with `REQUIRE_API_KEY=true` a keyless request fails; token usage is returned for metering.
- **S2 · OpenHands in a hardened container**: *Pass*: the Agent Server runs from our hardened container (cap-drop ALL, read-only root, non-root), on an `internal` network, reaching only 9router and one package registry through the egress proxy; a write outside the job dir fails; a request to a non-allowlisted domain is refused and logged; no docker.sock inside; it completes a small coding task and exports a patch.
- **S3 · LangGraph 1.x**: *Pass*: a minimal graph with an interrupt before an approval node, Postgres checkpointer, survives a process restart and resumes exactly once after one approval; a double approval does not re-run the node.
- **S4 · Cost metering**: *Pass*: a stub validation run on the pinned model logs tokens per step and total, and stops at the cap.
If S1 or S2 fails, stop and revisit sections 4–6 before anything else.

**Phase 1 — Stabilize the foundation**: finish the open items in section 8 that the new design keeps (auth/hygiene, atomic approve, classify fix, redaction switch), upgrade to LangGraph 1.x with tests, repo hygiene (gitignore, remove generated dirs, NOTICE, fix or delete `setup` and `release.mjs`), one model default, README/CLAUDE.md rewritten for the real runtime.

**Phase 2 — Job pipeline core**: Postgres job/stage/evidence/approval tables, the LangGraph graph (intake → verify → scope → gate → build → preview config → handoff), owner approval via API, per-stage cost log, memo output. Client path only.

**Phase 3 — Sandbox and worker in production shape**: egress proxy, hardened job containers, OpenHands worker, patch export, preview-deploy configuration generator. Acceptance: a real small client job completes inside the 3-day window with every action in the audit log.

**Phase 4 — Own-product path**: web search + fetch tools (gated, budget-capped), evidence table, critic stage, rubric calibration on three owner-chosen known-answer ideas.

**Later / parked**: frontend and the approval card; routines/scheduling; production deploy; marketing; Redis; multi-user.

## 10. Open items needing the owner

1. **Host OS** (macOS vs Linux, Apple silicon or not): decides the stronger runtime tier (gVisor/Kata are Linux; Docker Sandboxes microVM is the Mac escalation).
2. First client job details: what is asked, deposit status, what the client expects to see in 3 days, and whether "config only, owner runs it" is accepted for deploys.
3. Rubric inputs: three known-answer ideas, the ad budget cap, excluded categories, and which small real build will test the "MVP in hours" claim.
4. Confirm the provider-terms risk in section 6 is accepted and an API-key fallback provider will be configured in 9router.
5. Whether to keep `office.agents.json`'s 35 seats at all, or reduce the roster to the pipeline roles (researcher, scoper, builder, critic, reviewer).

## 11. Dropped on purpose

70-seat/8-department redesign, `success`/`product` departments, Citadel persona mapping, 3-column UI layout, the 20-agent "arena" validation (inconclusive), Redis routine locking, Foundation Tasks 9b–17 of the old plan. Foundation Tasks 1–8 were committed earlier but the audit found they do not yet deliver what they claim (no real tools, partial HITL), so they are re-scoped into Phases 1–3 above rather than counted as done.

## 12. Documents and where things live

| Path | Role |
|---|---|
| `.claude/plans/PLAN.md` | This file. The only plan |
| `docs/design/01-rubric.md` | Decision rubric (draft). Specs 02 (objects) and 03 (boundaries) not yet written |
| `.claude/GUARDRAILS.md` | Path B execution rules (keep; update to GitHub/CI wording) |
| `.claude/AGENTS.md`, `MCP-MATRIX.md`, `Phase1-Setup.md`, `SETUP-CHECKLIST.md`, `unused-seats.md` | **Stale** (describe departments and connectors that do not exist). Not plan files, so not merged; `engine.py` and a test still cite `AGENTS.md`. Candidates for archive after those references are updated |
| `.arena/`, `graphify-out/` | Generated artifacts, committed. Candidates for removal and `.gitignore` |
