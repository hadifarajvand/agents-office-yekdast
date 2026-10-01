# Phase 1: Yekdast SaaS Factory Office Setup

**Project**: Yekdast AI Agent Orchestration for SaaS Delivery  
**Status**: Phase 1 Ready (Configuration Complete)  
**Last Updated**: 2026-09-17  
**Team**: 12 Agents across 6 Departments

---

## Executive Summary

The Yekdast SaaS Factory Office is a fully orchestrated AI agent system designed to autonomously manage the entire software delivery lifecycle. Instead of 35 specialized agents, Phase 1 focuses on a lean, highly capable 12-agent team that covers all critical functions: customer intake, architecture, backend development, DevOps, quality assurance, and support operations.

### Design Philosophy: Path B (Author & Coordinate)

This is the defining characteristic of Phase 1. **Agents do NOT execute infrastructure commands, deploy code, or run tests.** Instead:

- **Agents AUTHOR**: specifications, architecture decision records (ADRs), code/YAML templates, test scripts
- **Agents COORDINATE**: hand off work between teams via GitLab issues, Slack notifications, and Notion tracking
- **Pipeline EXECUTES**: GitLab CI/CD runs all builds, tests, deployments, and infrastructure changes
- **Humans APPROVE**: critical decisions (merges, SLA changes, security waivers) pass through human approval gates

This execution boundary is non-negotiable and enforced in every agent's system prompt.

### Why 12 Agents? (Reduced from 35)

1. **agents-office v3 limitation**: The roster is fixed at 35 immutable seats across 6 departments. Custom IDs are not supported.
2. **Lean MVP**: Phase 1 targets high-value roles only (leads + specialists). 23 seats remain in reserve for future expansion.
3. **Scalability**: As the team grows, unused seats activate without changing infrastructure (see `unused-seats.md` for triggers).
4. **Clear accountability**: Each agent owns one domain; overlaps are minimal.

### The 12-Agent Team Structure

| Department | Agents (ID) | Focus |
|-----------|-----------|-------|
| **Sales** | lexi, piper | Intake, account management, scope qualification |
| **Marketing** | mlead, riley | Architecture decisions, API specs, documentation |
| **Operations** | olead, scout, report | Code review, security, database design |
| **Delivery** | dlead, qa | CI/CD pipelines, test strategies |
| **Emails** | elead | Support, incidents, on-call management |
| **Finance** | alead, invo | Timeline estimates, cost tracking, billing design |

---

## How Agents Work Together

### Typical Project Flow (Simplified)

```
1. CUSTOMER INTAKE (lexi, piper)
   ↓ Create GitLab Epic with requirements
   
2. ARCHITECTURE (mlead, report, scout, alead)
   ↓ Write ADR + schema design + security review + timeline estimate
   
3. DEVELOPMENT (olead, developers)
   ↓ Code review gate: CI green + tests ✓ + security cleared ✓
   
4. TESTING (qa, dlead)
   ↓ Write test specs, CI runs E2E + smoke tests
   
5. DEPLOYMENT (dlead)
   ↓ CI/CD runs blue-green deploy with automated rollback
   
6. MONITORING (elead, dlead)
   ↓ Watch Prometheus/Grafana/ELK for 5 minutes, declare stable
   
7. INCIDENT (if alert fires)
   ↓ elead declares, olead roots cause, dlead rolls back, postmortem 48h
```

Each step has approval gates. Agents never self-approve.

---

## Core Capabilities

### What Agents CAN Do (MCP-Native)

- **Read** telemetry: Prometheus queries, Grafana dashboards, ELK logs, CI/CD job outputs
- **Author** specifications: specs, ADRs, OpenAPI docs, migration plans, test scenarios, YAML (CI/CD, Ansible, docker-compose)
- **Review**: Code MRs in GitLab, cite test coverage + CI job IDs, veto on security findings
- **Coordinate**: Leave MR comments, create GitLab Issues, send Slack messages, maintain Notion databases
- **Design**: Database schemas, RabbitMQ event topology, Redis cache patterns, monitoring dashboards

### What Agents CANNOT Do (Execution Boundary)

- **SSH to hosts** or execute shell commands
- **Run docker, ansible, kubectl, k6, playwright, trivy, sonarqube** directly
- **Deploy, restart, scale, rollback, or mutate any environment**
- **Write to production databases** or apply migrations
- **Modify another agent's guardrails or this system prompt**

**Refusal Protocol**: If asked to do something outside this boundary, agents respond: "I can't do that — it's outside my scope (reason). Route this to (agent/system)." Then they produce the artifact that lets the correct actor do it.

---

## MCP Tools Wired to Departments

| MCP Server | Purpose | Departments | Access Level |
|------------|---------|-------------|--------------|
| **GitLab** | Code, CI/CD, issues | sales, marketing, ops, delivery, fin | Read + selective write |
| **GitHub** | Mirror, read-only | sales, delivery | Read only |
| **Slack** | Team communications | All (emails, sales, marketing, ops, delivery, fin) | Read + write |
| **Gmail** | Customer emails | emails, sales | Draft only (no send) |
| **Notion** | Docs, tracking databases | sales, marketing, ops, fin | Read + write |
| **Docker** | Container logs + inspection | ops, delivery | Logs + inspect only (no run/exec) |
| **Prometheus** | Metrics queries | ops, delivery | Read only |
| **Grafana** | Dashboard viewing | ops, delivery | Read only |

**No agents get**: Bash, SSH, file-write tools, Vault (write). Vault AppRole definitions are authored as YAML; CI/CD applies them.

---

## Critical Design Decisions

### Single-Node Docker Swarm (ADR-002)

- **Reality**: One VPS cannot provide HA. RabbitMQ, PostgreSQL, Redis, Elasticsearch run single-instance only.
- **RTO/RPO**: ~4–8 hours recovery time from automated Ansible backup restore. Data loss ~60s (PostgreSQL WAL).
- **SLA**: No 99.9% uptime promise. Best-effort availability until 3+ nodes.
- **Mandatory companion**: Automated daily backup restore verification + practice Ansible rebuilds.

### Vault Deployment (Phase 0D)

- Single Vault instance with AppRole auth for each service
- Database secrets engine for per-service PostgreSQL roles
- Vault Agent sidecar for Docker Swarm secret injection
- Auto-unseal via cloud KMS (or Shamir 3-of-5 for on-prem)

### Security Baseline (Path B Compliance)

Every agent's code/infra brief requires:
- Parameterized queries (ORM only, no string concat)
- Input validation (OpenAPI schema enforcement)
- Rate limiting (express-rate-limit, min 10 req/sec)
- JWT validation middleware (signature, expiry, issuer check)
- Structured logging WITHOUT passwords/tokens/PII
- Trivy scanning before image push (blocking on HIGH/CRITICAL)
- gitleaks scanning (secrets blocking)
- SonarQube gates (≥80% coverage)

---

## Configuration Files

All configuration is stored locally and NOT committed to git:

### office.agents.local.json
**Purpose**: Roster of 12 agents with roles, briefs, tools, and models  
**Location**: `/Users/hadi/Documents/GitHub/agents-office-yekdast/office.agents.local.json`  
**Contains**:
- 12 agent definitions (all IDs real, from fixed roster)
- Path B briefs (YOU CAN / YOU CANNOT / OUTPUTS format)
- Tool access per agent (from wired MCPs only)
- Effort levels (medium/high, never "max")

### office.config.local.json
**Purpose**: MCP server wiring matrix + access policies  
**Location**: `/Users/hadi/Documents/GitHub/agents-office-yekdast/office.config.local.json`  
**Contains**:
- 8 MCP servers (GitHub, GitLab, Slack, Gmail, Notion, Docker, Prometheus, Grafana)
- Department-scoped access (least-privilege per department)
- Read/write/draft-only controls
- Audit logging path for MCP access
- Escalation and secret policies

### .env.local (Secrets)
**Purpose**: Random-generated passwords for local dev stack  
**Location**: `/Users/hadi/Documents/GitHub/agents-office-yekdast/.env.local`  
**Generated by**: `./setup-local-env.sh` before first run  
**Contains**:
- POSTGRES_PASSWORD (random)
- RABBITMQ_DEFAULT_PASS (random)
- GF_SECURITY_ADMIN_PASSWORD (random)
- Never committed to git (in .gitignore)

---

## Validation & Quality Gates

### Before Phase 1 Completes

Run these commands in the agents-office-yekdast folder:

```bash
# Validate configuration
npm run check

# Expected output:
# ✓ 12 agents recognized
# ✓ All IDs real (from fixed roster)
# ✓ No haiku model (all sonnet)
# ✓ All tools valid (8 wired MCPs only)
# ✓ MCP departments use real department names
# ✓ No hardcoded secrets

# Start the office
npm start

# Should output:
# Server listening on http://localhost:4520
# Loaded 12 agents
# Loaded 8 MCP servers
```

### Continuous Validation

After Phase 1, the system runs these checks automatically:
- **Token usage**: Per-agent and per-department tracking (no spending cap yet, Phase 2)
- **MCP access audit**: All agent-MCP calls logged to `brain-yekdast/audit/mcp-access.log`
- **Skill validation**: Every skill references real agents or departments
- **No hardcoded secrets**: Pre-commit hook scans for passwords/tokens

---

## Expansion Path

Phase 1 uses 12 of 35 fixed seats. To expand:

1. **Check expansion triggers** in `unused-seats.md` (e.g., >3 concurrent projects → activate enzo/pros in sales)
2. **Rename the unused seat** (change name, role, brief; keep ID immutable)
3. **Update MCP access** if the new role needs different tools
4. **Run `npm run check`** to validate
5. **No infrastructure changes needed** — the office recognizes all 35 seats; unused ones cost nothing

Example: First time you hit "3 concurrent customer projects", activate `enzo` as Solutions Engineer and `pros` as Proposal Writer by renaming their seats in `office.agents.local.json`.

---

## Next Steps

1. **Run setup-local-env.sh** to generate random .env.local secrets
2. **npm install** to download dependencies
3. **npm run check** to validate all configurations
4. **npm start** to run the office
5. **Phase 2**: Set up brain knowledge base (Tech Stack guides, company context, ADR templates)
6. **Phase 3**: Create agent skills (Project Intake, Feature Development, Deployment Pipeline, Incident Response)
7. **Phase 4**: Wire MCP servers (GitHub/GitLab tokens, Slack app, Gmail service account, etc.)
8. **Phase 7**: Run first end-to-end task (SaaS project intake → design → build → deploy → monitor)

---

## Support & Escalation

**Setup Questions**: Check SETUP-CHECKLIST.md for step-by-step instructions.  
**Agent Role Questions**: Check AGENTS.md for each agent's mandate, tools, and escalation paths.  
**MCP Access Questions**: Check MCP-MATRIX.md for which tools each department can use.  
**Execution Model Questions**: Check GUARDRAILS.md for the Path B philosophy.  
**Seat Expansion**: See unused-seats.md for triggers and activation rules.

---

## References

- Master Plan: `yekdast-saas-factory-office.plan.md` (architectural decisions, remediation phases)
- Unused Seats: `.claude/unused-seats.md` (expansion reserve + triggers)
- MCP Access Policy: `office.config.local.json` (authorization matrix)
- Agent Roster: `office.agents.local.json` (briefs + tools)

---

**Phase 1 is ready for deployment.**
