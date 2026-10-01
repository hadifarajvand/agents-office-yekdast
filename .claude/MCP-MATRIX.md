# MCP Access Matrix — Tool Wiring by Department & Agent

**Last Updated**: 2026-09-17  
**Model**: Least-privilege access — only tools an agent needs are wired.  
**Enforcement**: agents-office router validates every MCP call against this matrix.

---

## Quick Reference: 8 MCP Servers

| Server | Purpose | Connected | Departments | Access Level |
|--------|---------|-----------|-------------|--------------|
| **GitHub** | GitHub PR/issue mirror (read-only) | Yes | sales, delivery | Read |
| **GitLab** | Source of truth: code, CI/CD, issues | Yes | sales, marketing, ops, delivery, fin | Read + Write (selective) |
| **Slack** | Team communications | Yes | All 6 departments | Read + Write |
| **Gmail** | Customer email intake | Yes | emails, sales | Draft-only (no send) |
| **Notion** | Documentation, project tracking, knowledge base | Yes | sales, marketing, ops, fin | Read + Write |
| **Docker** | Container runtime: logs, inspect, ps | Yes | ops, delivery | Logs + Inspect (no run/exec) |
| **Prometheus** | Metrics database: queries, alerting | Yes | ops, delivery | Read (query only) |
| **Grafana** | Dashboards and visualization | Yes | ops, delivery | Read (dashboard view only) |

---

## MCP Access Matrix (Detailed)

### Row Headers: 12 Agents  
### Column Headers: 8 MCPs  
### Cell Contents: Access level and specific scopes

```
Agent      │ GitHub │ GitLab │ Slack  │ Gmail  │ Notion │ Docker │ Prometheus │ Grafana │
───────────┼────────┼────────┼────────┼────────┼────────┼────────┼────────────┼─────────┤
lexi       │   R    │  W/E   │   W    │   D    │   W    │   -    │     -      │    -    │
piper      │   -    │  W/I   │   W    │   D    │   W    │   -    │     -      │    -    │
mlead      │   R    │  W/D   │   W    │   -    │   W    │   -    │     -      │    -    │
riley      │   R    │  W/D   │   W    │   -    │   W    │   -    │     -      │    -    │
olead      │   R    │  W/M   │   W    │   -    │   R    │   L    │     R      │    R    │
scout      │   R    │  W/C   │   W    │   -    │   R    │   -    │     -      │    -    │
report     │   R    │  W/D   │   W    │   -    │   W    │   -    │     -      │    -    │
dlead      │   R    │  W/P   │   W    │   -    │   R    │   L    │     R      │    R    │
qa         │   R    │  W/C   │   W    │   -    │   R    │   L    │     -      │    R    │
elead      │   -    │  W/I   │   W    │   W    │   W    │   -    │     R      │    R    │
alead      │   -    │   R    │   W    │   -    │   W    │   -    │     R      │    -    │
invo       │   -    │  W/D   │   W    │   -    │   W    │   -    │     -      │    -    │
───────────┴────────┴────────┴────────┴────────┴────────┴────────┴────────────┴─────────┘

Access Legend:
  R   = Read only
  W   = Read + Write
  D   = Draft only (applies to Gmail)
  W/E = Write Epic + issues (GitLab)
  W/I = Write Issues + comms (GitLab)
  W/D = Write documentation (GitLab)
  W/M = Write + Merge (GitLab)
  W/C = Write + Comments (GitLab)
  W/P = Write + Pipeline approval (GitLab)
  L   = Logs + Inspect only (Docker)
  R   = Read/Query only (Prometheus, Grafana)
  -   = No access
```

---

## Department-Level Wiring

### Sales Department (2 agents: lexi, piper)

**Departments wired for**: sales

| MCP | Access | Rationale | Scopes |
|-----|--------|-----------|--------|
| GitHub | Read | Review PRs/issues from delivery team | pull_requests:read, issues:read |
| GitLab | Write Epic, Issues | Create Epics for projects; Issues for features/bugs | issues:write, epics:write |
| Slack | Write | Team communications, customer updates | channels:read, chat:write |
| Gmail | Draft-only | Customer email intake, no send authority | mail:read, drafts:write |
| Notion | Write | Account database, project tracking, customer features | pages:read, pages:write, databases:read, databases:write |
| Docker | None | N/A |  |
| Prometheus | None | N/A |  |
| Grafana | None | N/A |  |

**Guardrails**:
- GitLab writes restricted to `sales/` branch or Epic creation (no merge)
- Gmail is draft-only; lexi/piper never send (elead/support sends)
- Notion write restricted to sales-owned databases (no page deletion)

---

### Marketing Department (2 agents: mlead, riley)

**Departments wired for**: marketing

| MCP | Access | Rationale | Scopes |
|-----|--------|-----------|--------|
| GitHub | Read | Review architecture decisions from external PRs | pull_requests:read, repos:read, commits:read |
| GitLab | Write docs | Author ADRs, specs, deployment guides (no merge) | issues:read, merge_requests:read, commits:read |
| Slack | Write | Announce decisions, coordinate with teams | channels:read, chat:write |
| Gmail | None | N/A |  |
| Notion | Write | Document architecture, technical decisions, roadmap | pages:read, pages:write, databases:read, databases:write |
| Docker | None | N/A |  |
| Prometheus | None | N/A |  |
| Grafana | None | N/A |  |

**Guardrails**:
- GitLab writes restricted to docs/ paths and new branches (no direct main commits)
- Notion write restricted to architecture/decision databases
- No merge authority; olead merges after code review

---

### Operations Department (3 agents: olead, scout, report)

**Departments wired for**: ops

| MCP | Access | Rationale | Scopes |
|-----|--------|-----------|--------|
| GitHub | Read | Monitor upstream security issues, dependency updates | pull_requests:read, issues:read, repos:read |
| GitLab | Write + Merge (olead), Write+Comment (scout), Write (report) | Code review, merge approval, security veto, schema docs | pull_requests:write, issues:write, commits:read, pipelines:read |
| Slack | Write | Code review feedback, escalations | channels:read, chat:write, search:read |
| Gmail | None | N/A |  |
| Notion | Write (report), Read (olead, scout) | Database schema docs, security compliance notes | pages:read, pages:write, databases:read |
| Docker | Logs + Inspect (olead, scout, report) | Review container logs, inspect running state | containers:list, containers:inspect, logs:read |
| Prometheus | Read/Query (olead, scout, report) | Performance budgets, baseline metrics | query, query_range, alerts:read |
| Grafana | Read (olead, scout, report) | Review dashboards, baseline alert thresholds | dashboards:read, panels:read, annotations:read |

**Guardrails**:
- GitLab merge restricted to olead (final approval gate)
- Scout has veto authority on security findings (hard block until fix or human waiver)
- Report has write-only access to database-design docs; no production schema access
- Docker access is read-only (no run, exec, stop, rm)
- Prometheus/Grafana read-only; no alert mutation, no dashboard edits

---

### Delivery Department (2 agents: dlead, qa)

**Departments wired for**: delivery

| MCP | Access | Rationale | Scopes |
|-----|--------|-----------|--------|
| GitHub | Read | Monitor PR status, dependency updates | pull_requests:read, issues:read, repos:read |
| GitLab | Write + Pipeline (dlead), Write+Comment (qa) | CI/CD pipeline approval, test result comments | pipelines:read, pipelines:write (manual gates only), issues:write |
| Slack | Write | Deploy notifications, incident alerts | channels:read, chat:write |
| Gmail | None | N/A |  |
| Notion | Read | Review test strategy docs, deployment runbooks | pages:read, databases:read |
| Docker | Logs + Inspect (dlead, qa) | Review container state, logs from CI/CD | containers:list, containers:inspect, logs:read |
| Prometheus | Read/Query (dlead, qa) | Query metrics, validate deploy health | query, query_range, alerts:read |
| Grafana | Read (dlead, qa) | Review post-deploy dashboards, alert status | dashboards:read, panels:read, annotations:read |

**Guardrails**:
- GitLab pipeline write restricted to manual gates only (no direct job triggering; CI/CD owns trigger)
- dlead can approve manual:prod gates after staging smoke ✓ and elead on watch
- qa reads test results from CI/CD job outputs; no test execution authority
- Docker access is read-only (logs + inspect for troubleshooting, no run/exec)
- Prometheus/Grafana read-only; no alert creation or modification

---

### Emails Department (1 agent: elead)

**Departments wired for**: emails

| MCP | Access | Rationale | Scopes |
|-----|--------|-----------|--------|
| GitHub | None | N/A |  |
| GitLab | Write Issues | Declare incidents, open action items | issues:write, pipelines:read (read incident status) |
| Slack | Write | Incident declaration, on-call routing, status updates | channels:read, chat:write, search:read |
| Gmail | Write + Read | Draft and read customer emails; no send authority | mail:read, drafts:write |
| Notion | Write | On-call schedule, runbook updates | pages:read, pages:write, databases:read, databases:write |
| Docker | None | Read-only via Prometheus/Grafana (elead observes, doesn't access Docker directly) |  |
| Prometheus | Read/Query | Observe incident metrics (latency, error rate, queue depth) | query, query_range, alerts:read |
| Grafana | Read | Watch dashboards during incidents, verify baseline nominal | dashboards:read, panels:read, annotations:read |

**Guardrails**:
- GitLab write restricted to incident Issues (issues:write, no merge/code access)
- Gmail is read-only for inbound; draft-only for outbound (elead drafts, humans send)
- Notion write restricted to on-call/runbook databases
- No infrastructure mutation; elead observes Prometheus/Grafana only (read-only)

---

### Finance Department (2 agents: alead, invo)

**Departments wired for**: fin

| MCP | Access | Rationale | Scopes |
|-----|--------|-----------|--------|
| GitHub | None | N/A |  |
| GitLab | Read (alead), Write (invo) | alead reads project status; invo writes billing specs | pull_requests:read, issues:read, repositories:read |
| Slack | Write | Budget alerts, cost notifications | channels:read, chat:write |
| Gmail | None | N/A |  |
| Notion | Write | Budget tracker, cost analysis, billing design | pages:read, pages:write, databases:read, databases:write |
| Docker | None | N/A |  |
| Prometheus | Read (alead) | Query infrastructure cost metrics (egress, storage) | query (cost metrics only) |
| Grafana | None | N/A |  |

**Guardrails**:
- GitLab read-only for both; no write authority on code/infra
- Notion write restricted to fin/* databases (budgets, cost analysis, billing design)
- Prometheus access restricted to cost-related metrics (no service/performance queries)
- No payment execution; alead flags waivers, humans approve

---

## Request Flow & Authorization

### When an Agent Calls an MCP Tool

1. **agents-office router** intercepts the call
2. **Checks**: Is agent in department wired for this MCP? → YES / NO
3. **Checks**: Is the operation within the access level? (Read? Write? Selective scopes?) → YES / NO
4. **If YES**: Call proceeds; audit logged to `brain-yekdast/audit/mcp-access.log`
5. **If NO**: Call denied; agent receives "access denied" error + reason

**Audit Log Entry Example**:
```
2026-09-17 14:23:45 | lexi (sales) | gitlab | create-issue | feature/acme-project | ✓ allowed
2026-09-17 14:24:12 | scout (ops) | gitlab | merge-mr | feat/auth-service | ✓ allowed (veto authority)
2026-09-17 14:25:03 | qa (delivery) | docker | run-container | test-env | ✗ denied (read-only)
```

---

## Updating the Matrix

If a new agent role requires additional access:

1. **Identify the requirement**: What MCP tool? What scopes?
2. **Check the rules**: Is it consistent with execution boundary? (Authors/coordinators only, never executes)
3. **Update office.config.local.json**: Add agent ID to the department's MCP section
4. **Update this table**: Document new access level and rationale
5. **Run validation**: `npm run check` confirms wiring is valid
6. **Restart agents-office**: New access takes effect

**Example: Add observability to marketing**

```json
// office.config.local.json
"mcp": {
  "departments": {
    "Prometheus": ["ops", "delivery", "marketing"],  // Add "marketing"
    "Grafana": ["ops", "delivery", "marketing"]      // Add "marketing"
  }
}
```

Then update this table to show marketing has read access to Prometheus/Grafana.

---

## MCP Connection Checklist

Before Phase 1 deployment, validate each MCP is connected and available:

### GitHub
```bash
# Test: List PRs on yekdast-backend repo
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/hadifaravand/yekdast-backend/pulls

# Agents need: $GITHUB_TOKEN in environment or .env.local
# Scopes: repo:read (public repos), repo (private repos)
```

### GitLab
```bash
# Test: List issues on agents-office-yekdast project
curl -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  https://gitlab.com/api/v4/projects/yekdast-backend/issues

# Agents need: $GITLAB_TOKEN (personal or CI token)
# Scopes: api (everything), read_user, read_repository, write_repository (if write access)
```

### Slack
```bash
# Test: List channels
curl -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  https://slack.com/api/conversations.list

# Agents need: $SLACK_BOT_TOKEN (bot app token)
# Scopes: channels:read, chat:write
```

### Gmail
```bash
# Test: List drafts
curl -H "Authorization: Bearer $GMAIL_TOKEN" \
  https://www.googleapis.com/gmail/v1/users/me/drafts

# Agents need: $GMAIL_TOKEN (service account or OAuth token)
# Scopes: gmail.drafts (draft-only), gmail.readonly (read)
```

### Notion
```bash
# Test: Query a database
curl -X POST -H "Authorization: Bearer $NOTION_TOKEN" \
  -H "Notion-Version: 2022-06-28" \
  https://api.notion.com/v1/databases/{db-id}/query

# Agents need: $NOTION_TOKEN (integration token)
# Scopes: database access via shared database connections
```

### Docker
```bash
# Test: List containers
docker ps

# Agents need: Docker daemon access (usually /var/run/docker.sock)
# Scopes: container inspect, logs read (MCP restricts to read-only)
```

### Prometheus
```bash
# Test: Query metric
curl 'http://prometheus:9090/api/v1/query?query=up'

# Agents need: HTTP access to Prometheus endpoint
# Default: http://localhost:9090 (local dev)
```

### Grafana
```bash
# Test: List dashboards
curl -H "Authorization: Bearer $GRAFANA_API_TOKEN" \
  http://grafana:3000/api/search

# Agents need: $GRAFANA_API_TOKEN (API token or admin credentials)
# Scopes: dashboard:read
```

---

## Secrets & Credentials

**Critical**: All MCP server credentials are environment variables, NEVER hardcoded in config files.

### .env.local (generated by setup-local-env.sh)
```bash
# GitHub
GITHUB_TOKEN=ghp_xxxxx

# GitLab
GITLAB_TOKEN=glpat-xxxxx

# Slack
SLACK_BOT_TOKEN=xoxb-xxxxx

# Gmail
GMAIL_TOKEN=ya29-xxxxx (or service account JSON path)

# Notion
NOTION_TOKEN=secret_xxxxx

# Docker (usually auto-detected at /var/run/docker.sock)
DOCKER_HOST=unix:///var/run/docker.sock

# Prometheus (local dev default)
PROMETHEUS_URL=http://localhost:9090

# Grafana
GRAFANA_URL=http://localhost:3000
GRAFANA_API_TOKEN=eyJrIjoixxxxx
```

### Vault Reference (Phase 2)
In production, agents-office will read MCP credentials from Vault:
```bash
# Instead of .env.local, CI/CD injects secrets via Vault Agent
# vault kv get -field=token secret/mcp/github
# vault kv get -field=token secret/mcp/gitlab
# etc.
```

---

## Access Control Policy Summary

| Principle | Rule |
|-----------|------|
| **Least Privilege** | Each agent gets only tools their role needs |
| **Department Isolation** | Agents in one dept don't see other depts' secrets/data (except shared MCP servers) |
| **Write Restrictions** | Writes limited to specific scopes (e.g., olead can merge, qa cannot) |
| **No Execution Authority** | Agents never execute builds, tests, deploys, or infrastructure commands |
| **Audit Trail** | Every MCP call logged with agent ID, action, result, timestamp |
| **Escalation Required** | Cross-department requests go via Slack/GitLab (asynchronous handoff) |
| **Human Approval Gates** | Critical actions (production deploy, security waiver, spend approval) require human tick |

---

## Questions?

- **"Can agent X use tool Y?"** → Check the matrix row for agent X, column for tool Y
- **"What scopes does agent X have?"** → Check department wiring section
- **"How do I add a new tool?"** → Read "Updating the Matrix" section
- **"Who can approve this action?"** → See GUARDRAILS.md for approval workflow

---

**Matrix enforced by**: agents-office MCP router  
**Authorization validated on**: Every MCP call (sub-50ms overhead)  
**Audit logged to**: `brain-yekdast/audit/mcp-access.log`  
**Run validation**: `npm run check` (detects wiring errors)
