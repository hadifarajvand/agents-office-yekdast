# Citadel SaaS Factory -- Master Intelligence File

> Universal Full-Stack SaaS Production Framework with 265 Autonomous Business Agents
> Version 3.0 | citadelcloudmanagement.com

---

## 1. Overview

Citadel SaaS Factory is an infrastructure-agnostic SaaS framework. It runs on any Linux server with SSH and Docker. No cloud vendor lock-in. No proprietary APIs. Supports any VPS, bare metal, on-prem, edge, or home lab. Total software cost: $0/month.

A fresh clone can: set ANTHROPIC_API_KEY, run an agent, and get a real model response through guardrails. All 265 agents resolve to executable definitions with RAG retrieval prompts, LLM system prompts, and tier-based model routing.

---

## 2. Architecture

| Layer | Technology | Path |
|-------|-----------|------|
| Backend API | FastAPI (Python 3.12) | `backend/` |
| Agent Runtime | backbone (LiteLLM, structlog) | `backbone/` |
| Frontend | Next.js 14 (TypeScript) | `frontend/` |
| Database | PostgreSQL 16 | docker-compose |
| Vector Store | pgvector (HNSW + GIN) | `backbone/rag/store.py` |
| Cache | Redis 7 | docker-compose |
| Auth | Keycloak 24 (OAuth2, RBAC, MFA) | docker-compose |
| Storage | MinIO (S3-compatible) | docker-compose |
| Messaging | RabbitMQ | docker-compose |
| Orchestration | K3s + ArgoCD (GitOps) | `gitops/` |
| Reverse Proxy | Traefik | `infrastructure/` |
| Service Mesh | Linkerd (mTLS) | `infrastructure/` |
| Secrets | HashiCorp Vault | `infrastructure/` |
| Monitoring | Prometheus + Grafana + Loki | `monitoring/` |

### Directory Map

```
.claude/                        # Harness configuration
  CLAUDE.md                     # This file (master intelligence)
  settings.json                 # Hooks, permissions, tool policies
  agents/                       # Agent definitions (11 hand-written + 265 generated)
    _registry.yaml              # Master registry (265 entries, 15 domains)
    <flat>.md                   # 11 hand-written agents
    <domain>/                   # 15 domain subdirs with generated agents
  commands/                     # 38 slash commands (20 YAML + 18 MD)
  hooks/                        # 11 lifecycle hooks (shell scripts)
  skills/                       # 10 skills (SKILL.md definitions)
  templates/                    # 20 code generation templates
  rules/                        # Project rules (see below)
  memory/                       # Operational state

backbone/                       # Agent runtime engine
  runtime/                      # Model routing, SDK, guardrails
    model_client.py             # ModelRouter: 5 tiers, fallback, budget
    agent_sdk.py                # Agent resolution, execution, sub-agents
    browse_handler.py           # Chrome extension handler
    guarded_client.py           # Triple-layer guardrails wrapper
  orchestrator/                 # Planner-executor-critic loop
    planner.py                  # Task graph with stop-gate
  rag/                          # RAG agentic pipeline
    agentic_loop.py             # Plan-retrieve-grade-rewrite-generate
    chunker.py                  # Structure-aware splitting
    embeddings.py               # Batch embedding (Voyage/Ollama)
    store.py                    # pgvector HNSW store
    retriever.py                # Hybrid search + RRF reranking

backend/                        # FastAPI web application
  app/main.py                   # App with middleware stack
  app/routes/agents.py          # POST /agent/browse, POST /agent/run
  app/middleware/guardrails.py   # guard_llm_call() wrapper

models/                         # Model configuration
  routing.yaml                  # Tier definitions and fallback chains
  catalog.yaml                  # Model IDs, costs, context windows
  embeddings.yaml               # Embedding model config
  rerankers.yaml                # Reranker config

extensions/chrome/              # Chrome MV3 side-panel extension
security/                       # Policies, Sigma rules, guardrails
docs/references/                # HTML field manuals
tests/                          # 20 tests for backbone
```

---

## 3. Agent System

### 3.1 Registry

265 agents across 15 domains. Full registry: `.claude/agents/_registry.yaml`

Every agent has:
- YAML frontmatter (id, domain, tier, rag_enabled, tools, skills)
- RAG Retrieval Prompt (domain-scoped, with metadata filters and citation format)
- LLM System Prompt (role, rules, confidence reporting, escalation protocol)

| Domain | Count | Tier | Dir | Key Agents |
|--------|-------|------|-----|------------|
| Executive and Strategy | 12 | reasoning_deep | `executive/` | CEO Strategist, CTO Technology, OKR Tracker, Board Reporter |
| Marketing and Growth | 22 | cheap_fast | `marketing/` | SEO Strategist, Content Writer, PPC Manager, Analytics |
| Sales and Revenue | 18 | reasoning_fast | `sales/` | Lead Qualifier, Proposals, CRM, Forecast, Pricing |
| Customer Success | 15 | reasoning_fast | `customer-success/` | Onboarding, Ticket Router, Churn Predictor, NPS |
| Product and UI/UX | 20 | reasoning_fast | `product-design/` | UI Designer, Wireframes, Design System, A11y |
| Engineering | 25 | reasoning_fast | `engineering/` | API Designer, Models, Auth, Cache, Search, WebSocket |
| Frontend | 18 | reasoning_fast | `frontend/` | Components, Pages, Forms, Charts, State, PWA |
| DevOps | 28 | reasoning_fast | `devops/` | CI/CD, GitOps, K8s, Helm, Terraform, Canary, Rollback |
| Security | 22 | reasoning_deep | `security/` | SAST, DAST, Secrets, Falco, Kyverno, Pentest |
| Data and Analytics | 18 | reasoning_fast | `data-analytics/` | Schema, ETL, Dashboards, Forecasting, Vector, RLS |
| QA and Testing | 22 | reasoning_fast | `qa-testing/` | Unit, E2E, Load, Chaos, Mutation, Visual Regression |
| HR and People | 12 | cheap_fast | `hr-people/` | Job Descriptions, Interviews, Onboarding, Performance |
| Finance and Billing | 15 | reasoning_fast | `finance/` | Stripe, Subscriptions, Tax, Revenue, Runway |
| Legal and Governance | 8 | reasoning_deep | `legal/` | ToS, DPA, GDPR, SOC2, SLA |
| Content and Comms | 10 | cheap_fast | `content/` | Tech Writing, Blog, Docs, Changelog, Case Studies |

### 3.2 Hand-Written Agents (11)

These live flat in `.claude/agents/` and have richer prompts:

| Agent | Model | Tools | MCP | Purpose |
|-------|-------|-------|-----|---------|
| `code-reviewer` | sonnet | Read, Grep, Glob | -- | Code review: bugs, security, conventions |
| `api-tester` | sonnet | Bash, Read, WebFetch | -- | API endpoint testing and validation |
| `database-explorer` | sonnet | Read, Bash | postgres | Schema exploration, query analysis |
| `deploy-agent` | sonnet | Bash, Read | -- | Deployment via ArgoCD and GitOps |
| `documentation-writer` | haiku | Read, Grep, Write | -- | API docs, guides, ADRs, runbooks |
| `guardrails-validator` | sonnet | Read, Grep, Bash | -- | Output validation, hallucination check |
| `incident-responder` | opus | Read, Grep, Bash, WebFetch | -- | Production incident analysis and remediation |
| `obsidian-curator` | haiku | Read, Write, Grep, Glob | -- | Vault integrity: backlinks, frontmatter, tags |
| `performance-profiler` | sonnet | Bash, Read, Grep | -- | API latency, DB queries, resource profiling |
| `security-auditor` | opus | Read, Grep, Glob | -- | Security audit (read-only, no Write/Edit) |
| `wiki-curator` | sonnet | Read, Write, Grep, Glob | -- | LLM Wiki maintenance and knowledge curation |

### 3.3 Model Tiers

Defined in `models/routing.yaml`, resolved by `backbone/runtime/model_client.py`:

| Tier | Primary | Fallbacks | max_tokens | temp | Use Case |
|------|---------|-----------|------------|------|----------|
| `reasoning_deep` | claude-opus-4-20250514 | claude-sonnet-4-20250514 | 8192 | 0.3 | Architecture, strategy, security |
| `reasoning_fast` | claude-sonnet-4-20250514 | claude-haiku-4-5-20251001 | 4096 | 0.2 | Development, code gen, reviews |
| `cheap_fast` | claude-haiku-4-5-20251001 | -- | 2048 | 0.4 | Content, simple tasks, high volume |
| `rag_specialist` | claude-sonnet-4-20250514 | claude-haiku-4-5-20251001 | 4096 | 0.1 | RAG with citation grounding |
| `local_only` | ollama/llama3.1 | ollama/mistral | 2048 | 0.3 | Budget fallback, offline |

Budget control: $50/day default, in-process tracking, auto-routes to `local_only` when exceeded.

### 3.4 Agent SDK

`backbone/runtime/agent_sdk.py` provides programmatic agent access:

```python
from backbone.runtime.agent_sdk import AgentSDK

sdk = AgentSDK()
result = await sdk.run_agent("eng-api-designer", prompt="Design a REST endpoint")
# result: {"status": "ok", "output": "...", "model_used": "...", "tier": "reasoning_fast"}

# Sub-agent spawning (depth-capped at 3, fan-out at 5)
result = await sdk.spawn_sub_agent("parent-id", "child-id", prompt="...")

# List agents
sdk.list_agents(domain="engineering")  # 25 agents
```

### 3.5 Orchestrator

`backbone/orchestrator/planner.py`: Plan, execute, critique loop with stop-gate. Max 3 replans.

---

## 4. Skills (10)

Skills are deep reference material invoked by agents and commands. Located in `.claude/skills/*/SKILL.md`.

| Skill | Tools | When Invoked |
|-------|-------|-------------|
| `code-review` | Read, Grep, Glob | PR context, staged changes, user asks for review |
| `database-migration` | Bash, Read, Write | Schema changes, new models, index additions |
| `deploy` | Bash, Read | Keywords: deploy, ship it, push to staging/production |
| `graphify` | Bash, Read | `/graphify` command, codebase exploration |
| `guardrails` | Read, Grep, Bash | Auto-invoked on any agent output validation |
| `llm-wiki` | Read, Write, Grep, Glob, Bash | Ingest, query, lint wiki; persistent knowledge |
| `obsidian-linker` | Read, Write, Grep, Glob | Any .md file write; `/project:vault-link` |
| `onboard` | Read, Grep, Glob | New developer, walkthrough, getting started |
| `security-audit` | Read, Grep, Glob | Security keywords, pre-deploy, dependency updates |
| `testing` | Bash, Read, Write | New features, bug fixes, coverage gaps |

---

## 5. MCP Servers (6)

Configured in `.mcp.json` at repo root:

| Server | Package | Env Vars | Used By |
|--------|---------|----------|---------|
| `github` | @modelcontextprotocol/server-github | GITHUB_PERSONAL_ACCESS_TOKEN | code-reviewer, deploy-agent |
| `filesystem` | @modelcontextprotocol/server-filesystem | -- | All file-accessing agents |
| `postgres` | @modelcontextprotocol/server-postgres | DATABASE_URL | database-explorer, data agents |
| `docker` | mcp-server-docker | -- | devops agents, deploy-agent |
| `kubernetes` | mcp-server-kubernetes | KUBECONFIG | devops agents, incident-responder |
| `ruflo` | ruflo@latest | -- | Swarm orchestration (mesh topology) |

---

## 6. Hooks (11 scripts + settings.json)

### 6.1 Settings.json Hooks (runtime)

**PreToolUse** (run before tool execution):

| Matcher | Action | Timeout |
|---------|--------|---------|
| `Write(*.py)` | `ruff check $file` | 10s |
| `Write(*.ts)\|Write(*.tsx)` | `npx eslint $file` | 10s |
| `Write(*.md)\|Write(*.json)` | `guardrails validate --input $file` | 15s |
| `Grep\|Glob` | Remind to consult `docs/vault/wiki/index.md` first | 2s |

**PostToolUse** (run after tool execution):

| Matcher | Action |
|---------|--------|
| `Write(*.py)` | `ruff format $file` |
| `Write(*.ts)\|Write(*.tsx)` | `npx prettier --write $file` |
| `Write(docs/vault/*.md)` | `bash .claude/hooks/vault-autolink.sh $file` |

### 6.2 Lifecycle Hooks (shell scripts in `.claude/hooks/`)

| Hook | Trigger | Action |
|------|---------|--------|
| `pre-commit.sh` | Before git commit | Lint, format, secret scan (TruffleHog) |
| `pre-push.sh` | Before git push | Run tests, security scan |
| `pre-agent.sh` | Before agent execution | Validate context, check blockers |
| `post-agent.sh` | After agent execution | Log activity, update learnings |
| `post-deploy.sh` | After deployment | Smoke tests, health checks |
| `on-deploy-fail.sh` | Deployment failure | Auto-rollback, notification |
| `on-error.sh` | Any agent error | Capture context, log to error patterns |
| `on-file-change.sh` | File modification | Route to appropriate checker (py/ts/yaml/tf) |
| `on-security-alert.sh` | Security finding | Escalate; CRITICAL/HIGH blocks execution |
| `on-test-fail.sh` | Test failure | Suggest fixes, recommend tdd-guide agent |
| `vault-autolink.sh` | Vault .md write | Auto-insert backlinks via obsidian-linker |

### 6.3 Permissions

```json
{
  "allow": ["Read", "Write", "Edit", "Bash(git *)", "Bash(npm *)", "Bash(make *)", "Bash(docker *)"],
  "deny": ["Read(.env)", "Read(.env.*)", "Write(production.*)"]
}
```

---

## 7. Commands (38)

### 7.1 YAML Commands (20) -- operational automation

| Command | Usage | Purpose |
|---------|-------|---------|
| `/audit` | `/audit [--fix]` | Full security and quality audit |
| `/backup` | `/backup [--target db\|storage]` | Database and storage backup |
| `/build` | `/build [service]` | Docker image build |
| `/cert` | `/cert [renew\|status]` | TLS certificate management |
| `/deploy` | `/deploy <environment>` | Deploy to staging/production |
| `/doctor` | `/doctor [--verbose]` | System health diagnostics |
| `/lint` | `/lint [--fix]` | Run all linters and formatters |
| `/logs` | `/logs [service] [--tail N]` | Stream application logs |
| `/migrate` | `/migrate [up\|down]` | Database migrations |
| `/monitor` | `/monitor [grafana\|prometheus]` | Open monitoring dashboards |
| `/release` | `/release [major\|minor\|patch]` | Create tagged release |
| `/restore` | `/restore <backup-id>` | Restore from backup |
| `/rollback` | `/rollback <environment>` | Emergency rollback |
| `/scaffold` | `/scaffold <type> <name>` | Generate from template |
| `/scale` | `/scale <service> <replicas>` | Scale service replicas |
| `/scan` | `/scan [sast\|sca\|secrets]` | Security scanning |
| `/secret` | `/secret [set\|rotate\|list]` | Secret management |
| `/seed` | `/seed [environment]` | Seed database with sample data |
| `/status` | `/status [--all]` | System and agent status |
| `/test` | `/test [unit\|e2e\|all]` | Run tests |

### 7.2 Markdown Commands (18) -- interactive workflows

| Command | Purpose |
|---------|---------|
| `/batch` | Run task across multiple files in parallel |
| `/debug` | Structured debugging workflow |
| `/deploy` | Deploy to target environment (interactive) |
| `/fix-issue` | Fix a GitHub issue by number |
| `/graphify` | Build or query knowledge graph |
| `/guardrails` | Run guardrails validation |
| `/insights` | Generate session insights report |
| `/onboard` | Project walkthrough for new developers |
| `/plan` | Enter plan mode for read-only reasoning |
| `/pr-comments` | Fetch and respond to PR comments |
| `/review` | Review code changes on current branch |
| `/security-review` | Scan branch diff for vulnerabilities |
| `/simplify` | Simplify and refactor code |
| `/test` | Run tests with optional scope |
| `/vault-link` | Insert bidirectional wikilinks |
| `/wiki-ingest` | Ingest source into LLM Wiki |
| `/wiki-lint` | Health-check the LLM Wiki |
| `/wiki-query` | Answer question against wiki |

---

## 8. Templates (20)

Code generation templates in `.claude/templates/`, used by `/scaffold`:

| Template | Output |
|----------|--------|
| `api-endpoint.py.tmpl` | FastAPI route handler |
| `model.py.tmpl` | SQLAlchemy ORM model |
| `schema.py.tmpl` | Pydantic request/response schema |
| `service.py.tmpl` | Business logic service layer |
| `repository.py.tmpl` | Data access repository |
| `middleware.py.tmpl` | FastAPI middleware |
| `migration.py.tmpl` | Alembic migration |
| `worker.py.tmpl` | Celery background worker |
| `component.tsx.tmpl` | React component |
| `page.tsx.tmpl` | Next.js page |
| `store.ts.tmpl` | Zustand state store |
| `hook.ts.tmpl` | React custom hook |
| `api-client.ts.tmpl` | Frontend API client |
| `test-unit.py.tmpl` | pytest unit test |
| `test-integration.py.tmpl` | pytest integration test |
| `test-e2e.py.tmpl` | End-to-end test |
| `dockerfile.tmpl` | Multi-stage Dockerfile |
| `helm-values.yaml.tmpl` | Helm chart values |
| `terraform-module.tf.tmpl` | Terraform module |
| `github-action.yml.tmpl` | GitHub Actions workflow |

---

## 9. RAG Pipeline

Agentic RAG with iterative retrieval, grading, and citation. Field manual: `docs/references/Agentic-RAG-Pattern.html`

**Loop**: Query -> Retrieve (hybrid: vector + keyword + RRF) -> Grade (LLM-as-judge) -> Rewrite if weak -> Generate with [chunk-id] citations -> Self-check. Max 3 iterations.

**Store**: PostgreSQL 16 + pgvector. HNSW index (m=16, ef_construction=200) for vectors, GIN index on metadata JSONB.

**Embedding**: Voyage 3 (1024 dims, production) or Ollama nomic-embed-text (768 dims, local).

**Every agent has a RAG retrieval prompt** with domain-scoped metadata filters:
```
Retrieve chunks with metadata filter: {"domain": "<agent-domain>", "agent_id": "<agent-id>"}
```

---

## 10. Security

### 10.1 Guardrails (triple layer)

1. **Guardrails AI**: hallucination_free, provenance_llm, toxic_language, detect_pii
2. **Input sanitization**: 16 regex patterns strip injection from RAG docs and browser content
3. **Output enforcement**: 10-action allowlist, hallucination threshold 0.85, max 3 retries then reject

Fail-closed: if guardrails unavailable, outputs are rejected.

### 10.2 Agent Safety

- Spawn depth cap: `MAX_SPAWN_DEPTH = 3`
- Fan-out cap: `MAX_FAN_OUT = 5`
- Planner replan cap: `MAX_REPLANS = 3`
- Budget cap: `$50/day`, auto-routes to `local_only` on exceed

### 10.3 Chrome Extension

- Manifest V3, minimal permissions (activeTab, sidePanel, storage)
- Explicit user action per tab (no background surveillance)
- Tab content sanitized through 16 injection patterns before model
- Host permission limited to `http://localhost:8000/*`

### 10.4 Mandatory Checks

Before ANY commit:
- No hardcoded secrets (env vars or Vault only)
- All user inputs validated at system boundaries
- Parameterized queries only
- Rate limiting on all API endpoints
- CORS, CSRF, XSS protection on all routes
- Container image scanning before deployment
- Secret scanning in pre-commit hooks

Reference: `security/ai-security-by-design.html` (OWASP LLM Top 10 mapping)

---

## 11. CI/CD

`.github/workflows/ci-cd.yml`: Lint -> Test -> SAST -> SCA -> Secret Scan -> Build -> Container Scan -> Deploy

| Stage | Tool | Pinned Version |
|-------|------|---------------|
| Lint | ruff (Python), ESLint (TS) | latest |
| Test | pytest + vitest | backend + backbone + frontend |
| SAST | semgrep/semgrep-action | @v1 |
| SCA | aquasecurity/trivy-action | @0.28.0 |
| Secret Scan | trufflesecurity/trufflehog | @v3.82.13 |
| Container Scan | trivy (image) | @0.28.0 |

---

## 12. Conventions

- **Immutability**: Always create new objects, never mutate
- **Small files**: 200-400 lines typical, 800 max
- **Small functions**: under 50 lines, max 4 levels nesting
- **TDD**: Write tests first (RED -> GREEN -> IMPROVE), 80% minimum coverage
- **Conventional commits**: feat, fix, refactor, docs, test, chore, perf, ci
- **Error handling**: Handle at every level, never swallow silently
- **Naming**: kebab-case files, PascalCase classes, camelCase functions (TS), snake_case (Python)
- **Architecture**: domain > use cases > interfaces > infrastructure (dependency flows inward)

---

## 13. Make Targets

| Target | Purpose |
|--------|---------|
| `make dev` | Start full Docker stack (postgres, redis, keycloak, minio, rabbitmq, mailhog) |
| `make backend` | Start FastAPI dev server on :8000 |
| `make frontend` | Start Next.js dev server on :3000 |
| `make test` | Run backend + backbone + frontend tests |
| `make lint` | Run ruff (backend + backbone) + ESLint (frontend) |
| `make security` | Run semgrep + trivy |
| `make deploy` | Deploy to target environment |
| `make expand-agents` | Expand registry into 265 agent .md definitions |
| `make rag-ingest` | Ingest documents into RAG vector store |
| `make rag-query` | Query the RAG pipeline |
| `make vault-sync` | Refresh Graphify knowledge graph + vault mirrors |
| `make wiki-ingest` | Ingest source into LLM Wiki |
| `make wiki-lint` | Health-check the LLM Wiki |
| `make engine-status` | Print current LLM engine config |

---

## 14. Tool Integrations

| Tool | Type | Purpose |
|------|------|---------|
| Ruflo | MCP swarm | Multi-agent orchestration (mesh topology) |
| Graphify | MCP + CLI | Codebase knowledge graph (Tree-sitter AST, 20 languages) |
| GitHub Actions | CI/CD | Security gates (SAST, SCA, secret scan, container scan) |
| LiteLLM | SDK | Multi-provider model routing with fallback |
| Guardrails AI | SDK | Output validation (hallucination, toxicity, PII) |
| pgvector | DB extension | Vector similarity search (HNSW) |
| Obsidian | Vault | Knowledge graph visualization (wikilinks) |

---

## 15. Rules

Project rules in `.claude/rules/`:

| Rule | File | Scope |
|------|------|-------|
| Architecture | `architecture.md` | Clean layers, DDD, repository pattern |
| Code Quality | `code-quality.md` | Immutability, small files/functions |
| API Design | `api-design.md` | REST, response envelope, versioning |
| Database | `database.md` | Migrations, indexes, RLS, parameterized queries |
| Security | `security.md` | No secrets, input validation, rate limiting |
| Testing | `testing.md` | TDD, 80% coverage, test pyramid |
| Frontend | `frontend.md` | Composition, a11y, responsive, performance |
| Git | `git.md` | Conventional commits, feature branches, PR required |
| DevOps | `devops.md` | GitOps, immutable infra, health probes |
| Monitoring | `monitoring.md` | Structured JSON logging, RED metrics |
| Performance | `performance.md` | Caching, lazy loading, query optimization |
| Error Handling | `error-handling.md` | Structured errors, retry, never swallow |
| Accessibility | `accessibility.md` | WCAG 2.1 AA, semantic HTML, ARIA |
| Dependencies | `dependencies.md` | Lock files, audits, minimal deps |
| Documentation | `documentation.md` | OpenAPI, ADRs, inline comments for complex logic |
| Secrets | `secrets.md` | Vault (prod), env vars (dev), 90-day rotation |
| Review | `review.md` | PR required, CI must pass, CRITICAL blocks merge |
| Guardrails | `guardrails.md` | Mandatory validation on all LLM output |
| LLM Wiki | `llm-wiki.md` | Wiki-first lookup, ingest updates index + log |
| Obsidian Backlinks | `obsidian-backlinks.md` | Every .md must have vault links |
| Naming | `naming.md` | snake_case Python, camelCase TS, kebab-case files |

---

## 16. Free Toolchain

ArgoCD, K3s, Traefik, Linkerd, Keycloak, Vault, Prometheus, Grafana, Loki, Falco, Kyverno, Semgrep, Trivy, ZAP, Flagsmith, Grafana OnCall, Velero, MinIO, Ansible.
