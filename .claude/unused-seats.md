# Unused Agent Seats — Expansion Reserve

**Status**: 12 of 35 seats active (Phase 0A, Option C). 23 seats held in reserve.
**Source**: AGENT_ID_MAPPING.json — agents-office v3 fixed roster.
**Rule**: Seat IDs are immutable. The loader rejects any ID outside the fixed 35 with "not one of the 35 seats — skipped". You cannot invent IDs. You can only activate a reserved seat and give it a new name/role/brief.

---

## 1. Seat Census by Department

| Department | Used | Total | Active Seats | Reserved Seats |
|-----------|------|-------|--------------|----------------|
| emails    | 1 | 5 | elead | cmail, imail, vmail, kmail |
| sales     | 2 | 6 | lexi, piper | enzo, ilm, pros, folo |
| marketing | 2 | 7 | mlead, riley | newt, gfx, ada, iggy, vid |
| ops       | 3 | 6 | olead, scout, report | legal, comply, dash |
| fin       | 2 | 4 | alead, invo | apay, recon |
| delivery  | 2 | 7 | dlead, qa | pco, crep, cass, dasst, ona |
| **Total** | **12** | **35** | | **23 reserved** |

---

## 2. Reserved Seats and Suggested Roles

Every suggested role stays inside the Path B execution boundary: agents author, review, and coordinate. They never execute.

### emails (4 reserved) — owner: elead

| Seat | Suggested Role | Rationale |
|------|---------------|-----------|
| `cmail` | Incident Communications | Drafts customer-facing status updates on a 30-min cadence during SEV1. |
| `imail` | Support Triage (Tier 1) | First-pass classification of inbound tickets; routes to olead/dlead/report. |
| `vmail` | Postmortem Author | Owns the 48h postmortem SLA as a dedicated role. |
| `kmail` | Runbook Librarian | Maintains and freshness-checks runbooks; flags stale procedures. |

### sales (4 reserved) — owner: lexi

| Seat | Suggested Role | Rationale |
|------|---------------|-----------|
| `enzo` | Solutions Engineer | Pre-sales technical feasibility; co-signs with mlead. |
| `ilm` | Inbound Lead Qualifier | Structured qualification before lexi invests time. |
| `pros` | Proposal / SOW Writer | Assembles scope documents from lexi's Epic + alead's timeline. |
| `folo` | Renewal & Follow-up | Tracks contract dates and post-delivery check-ins. |

### marketing (5 reserved) — owner: mlead

| Seat | Suggested Role | Rationale |
|------|---------------|-----------|
| `newt` | API / Changelog Publisher | Release-note generation from merged MRs. |
| `gfx` | Diagram & Architecture Visuals | Authors C4/sequence diagrams as committed source. |
| `ada` | Developer Advocate | Writes integration guides and quickstarts. |
| `iggy` | Competitive / Tech Research | Evaluates library and infra choices for ADRs. |
| `vid` | Onboarding Content | Walkthrough scripts and demo scenarios. |

### ops (3 reserved) — owner: olead

| Seat | Suggested Role | Rationale |
|------|---------------|-----------|
| `legal` | Licensing & Contract Review | SBOM license review (GPL/AGPL), DPA and subprocessor terms. |
| `comply` | Compliance Officer | GDPR Article 17 deletion, ELK retention, audit-trail evidence. |
| `dash` | Observability Engineer | Authors Grafana dashboard JSON and Prometheus alert rules. |

### fin (2 reserved) — owner: alead

| Seat | Suggested Role | Rationale |
|------|---------------|-----------|
| `apay` | Vendor & Cloud Spend | Tracks VPS, registry, egress, and LLM token spend. |
| `recon` | Revenue Reconciliation | Reconciles processor webhooks against internal ledger. |

### delivery (5 reserved) — owner: dlead

| Seat | Suggested Role | Rationale |
|------|---------------|-----------|
| `pco` | Release Manager | Owns SemVer tagging, develop→main gating, cutover checklists. |
| `crep` | Performance Engineer | Authors k6 scripts and defines P99/lag budgets. |
| `cass` | Chaos / Resilience | Designs failure drills and validates ADR-002 RTO/RPO claims. |
| `dasst` | Pipeline Maintainer | Keeps .gitlab-ci.yml templates and cache strategy healthy. |
| `ona` | Environment Coordinator | Owns staging reservations and data seeding. |

---

## 3. Expansion Triggers

Do not activate seats speculatively. Activate only when a trigger fires.

| Trigger | Activate | Department |
|---------|----------|------------|
| >3 concurrent customer projects | `enzo`, `pros` | sales |
| >10 support tickets/week | `imail` | emails |
| 2+ SEV1 incidents in 30 days | `cmail`, `vmail` | emails |
| First external API consumer | `newt`, `ada` | marketing |
| Deploy frequency >3/week | `pco`, `dasst` | delivery |
| First customer SLA in signed contract | `cass`, `dash` | delivery, ops |
| P99 latency budget breached twice | `crep` | delivery |
| First EU customer or PII-processing feature | `comply` | ops |
| Third-party dependency with copyleft license | `legal` | ops |
| Monthly infra or token spend exceeds limit | `apay` | fin |
| Billing service reaches production | `recon` | fin |
| riley's doc backlog >2 weeks | `newt` first, then `gfx` | marketing |

---

## 4. Policy: Rename Before You Add

**Preferred order of operations when capacity is short:**

1. **Sharpen an existing brief.** Most perceived capacity gaps are scope ambiguity, not headcount.
2. **Rename a reserved seat.** Take an unused ID from this table, give it a new `name`, `role`, `does`, and `brief`. The ID stays immutable.
3. **Never invent an ID.** `npm run check` will reject it.

**Rules for activating a reserved seat:**

- Keep the seat in its original department (MCP access wiring contract).
- `model` must be one of `sonnet`, `opus`, `fable`, or empty. Never `haiku`.
- `tools` may only reference the 8 wired MCPs: `github`, `gitlab`, `slack`, `gmail`, `notion`, `docker`, `prometheus`, `grafana`.
- Every new seat needs an explicit escalation target and an entry in the MCP access matrix.
- Update this file and re-run `npm run check` in the same commit.

---

## 5. Validation Checklist

Run these commands after modifying office.agents.local.json:

```bash
# All 12 IDs recognized
jq '.agents | length' office.agents.local.json | grep -q 12 && echo "✓ 12 agents"

# No haiku model
grep -q '"haiku"' office.agents.local.json && echo "✗ haiku found" || echo "✓ no haiku"

# Valid tools only (github, gitlab, slack, gmail, notion, docker, prometheus, grafana)
jq -r '.agents[].tools[]' office.agents.local.json | sort -u

# Valid JSON
jq empty office.agents.local.json && echo "✓ valid JSON"

# Final check
npm run check
```

Expected: All 12 agents recognized, zero "not one of the 35 seats" warnings, npm run check passes.
