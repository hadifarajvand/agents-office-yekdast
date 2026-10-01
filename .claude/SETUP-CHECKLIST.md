# Phase 1 Setup Checklist — Step-by-Step

**Last Updated**: 2026-09-17  
**Estimated Time**: 30–45 minutes  
**Prerequisites**: Node.js 18+, npm 9+, Docker (optional for local MCP testing)

---

## Pre-Flight Checks

### System Requirements
- [ ] Node.js 18 or higher installed (`node --version`)
- [ ] npm 9 or higher installed (`npm --version`)
- [ ] Git configured with SSH key (`ssh -T git@github.com`)
- [ ] 2+ GB free disk space (for dependencies, brain folder, logs)
- [ ] No port 4520 in use (agents-office server port)

### Repository Access
- [ ] Fork or clone agents-office-yekdast to local machine
  ```bash
  cd ~/Documents/GitHub
  git clone git@github.com:hadifaravand/agents-office-yekdast.git
  cd agents-office-yekdast
  ```
- [ ] Verify repo structure:
  ```bash
  ls -la
  # Expected: src/ scripts/ skills/ brain-yekdast/ .claude/ package.json
  ```
- [ ] Check git remotes:
  ```bash
  git remote -v
  # Expected: origin → agents-office-yekdast, upstream → agents-office (if applicable)
  ```

---

## Step 1: Install Dependencies (5 minutes)

### 1.1 Download Packages
```bash
cd /Users/hadi/Documents/GitHub/agents-office-yekdast
npm install
```

**Expected output**:
```
added 245 packages, and audited 246 packages in 15s
found 0 vulnerabilities
```

**Troubleshoot**:
- If `ERR! code ERESOLVE`: Try `npm install --legacy-peer-deps`
- If port 4520 in use: Check `lsof -i :4520` and kill existing process
- If package versions don't match: Delete `package-lock.json`, re-run `npm install`

### 1.2 Verify Installation
```bash
npm run check --help
# Expected: Shows usage for npm run check
```

---

## Step 2: Generate Local Secrets (.env.local) (3 minutes)

### 2.1 Create setup-local-env.sh (if not exists)
**File**: `/Users/hadi/Documents/GitHub/agents-office-yekdast/setup-local-env.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

if [[ -f ".env.local" ]]; then
  echo "✓ .env.local exists (keeping existing)"
  exit 0
fi

echo "Generating .env.local with random passwords..."

gen_password() {
  openssl rand -base64 24 | tr -d '=+/' | cut -c1-24
}

cat > .env.local <<EOF
# Generated $(date -u +%Y-%m-%dT%H:%M:%SZ)
# NEVER commit this file to git

# PostgreSQL
POSTGRES_PASSWORD=$(gen_password)
POSTGRES_USER=postgres
POSTGRES_DB=yekdast_dev

# RabbitMQ
RABBITMQ_DEFAULT_USER=guest
RABBITMQ_DEFAULT_PASS=$(gen_password)
RABBITMQ_DEFAULT_VHOST=/

# Grafana
GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=$(gen_password)

# Optional: MCP Server tokens (leave empty for now, Phase 2)
# GITHUB_TOKEN=
# GITLAB_TOKEN=
# SLACK_BOT_TOKEN=
# GMAIL_TOKEN=
# NOTION_TOKEN=
# GRAFANA_API_TOKEN=

# Node environment
NODE_ENV=development

EOF

chmod 600 .env.local
echo "✓ .env.local generated with random passwords"
```

### 2.2 Run the Script
```bash
chmod +x setup-local-env.sh
./setup-local-env.sh
```

**Expected output**:
```
✓ .env.local generated with random passwords
```

### 2.3 Verify .env.local
```bash
head -5 .env.local
# Expected: Shows comment line + PostgreSQL password

# Check it's excluded from git
grep ".env.local" .gitignore
# Expected: .env.local (already in .gitignore)
```

---

## Step 3: Create Configuration Files (5 minutes)

### 3.1 Verify office.config.local.json Exists

**File**: `/Users/hadi/Documents/GitHub/agents-office-yekdast/office.config.local.json`

If not present, create from template:

```bash
cat > office.config.local.json <<'EOF'
{
  "name": "Yekdast SaaS Factory Office",
  "brain": "./brain-yekdast",
  "port": 4520,
  "model": "sonnet",
  "mcp": {
    "departments": {
      "github": {
        "departments": ["sales", "delivery"],
        "access": "read",
        "scopes": ["pull_requests:read", "issues:read", "repos:read"],
        "notes": "Read-only PR visibility. No merges, no writes."
      },
      "gitlab": {
        "departments": ["sales", "marketing", "ops", "delivery", "fin"],
        "access": "read",
        "scopes": ["commits:read", "pipelines:read", "issues:read", "merge_requests:read"],
        "notes": "Pipeline gate status and issue tracking. Issue writes require human approval."
      },
      "slack": {
        "departments": ["sales", "marketing", "ops", "delivery", "fin", "emails"],
        "access": "read-write",
        "scopes": ["channels:read", "chat:write", "search:read"],
        "notes": "Team comms for all departments. No @channel/@here broadcasts."
      },
      "gmail": {
        "departments": ["emails", "sales"],
        "access": "draft-only",
        "scopes": ["mail:read", "drafts:write"],
        "notes": "Sales is strictly draft-only; no send without human review."
      },
      "notion": {
        "departments": ["sales", "marketing", "ops", "fin"],
        "access": "read-write",
        "scopes": ["pages:read", "pages:write", "databases:read", "databases:write"],
        "notes": "Documentation and tracking DBs. No page deletion."
      },
      "docker": {
        "departments": ["ops", "delivery"],
        "access": "read",
        "scopes": ["containers:list", "containers:inspect", "logs:read"],
        "notes": "Logs and inspect only. No run/stop/rm/exec."
      },
      "prometheus": {
        "departments": ["ops", "delivery"],
        "access": "read",
        "scopes": ["query", "query_range", "alerts:read"],
        "notes": "Metric reads only. No rule or silence mutation."
      },
      "grafana": {
        "departments": ["ops", "delivery"],
        "access": "read",
        "scopes": ["dashboards:read", "panels:read", "annotations:read"],
        "notes": "Dashboard reads only. No dashboard edits."
      }
    },
    "defaults": {
      "denyUnmappedDepartments": true,
      "requireHumanApprovalForWrites": ["gmail", "gitlab"],
      "auditLog": "./brain-yekdast/audit/mcp-access.log"
    }
  },
  "policies": {
    "secrets": {
      "source": "env",
      "inlineSecretsForbidden": true
    },
    "escalation": {
      "crossDepartmentRequests": "route-via-office-router"
    }
  },
  "tools": {
    "web": true
  }
}
EOF
```

### 3.2 Verify office.agents.local.json Exists

**File**: `/Users/hadi/Documents/GitHub/agents-office-yekdast/office.agents.local.json`

Should have 12 agents (from master plan). Verify:

```bash
jq '.agents | length' office.agents.local.json
# Expected: 12

# Check no haiku model
grep -c '"haiku"' office.agents.local.json
# Expected: 0 (no haiku found)

# Check all IDs are valid
jq -r '.agents[].id' office.agents.local.json | sort
# Expected: alead, dlead, elead, invo, lexi, mlead, olead, piper, qa, riley, report, scout
```

### 3.3 Check .gitignore

Verify sensitive files are excluded:

```bash
grep -E "\.env|office\.(agents|config)\.local" .gitignore
# Expected:
# .env.local
# office.agents.local.json
# office.config.local.json
```

If not present, add:

```bash
echo ".env.local" >> .gitignore
echo "office.agents.local.json" >> .gitignore
echo "office.config.local.json" >> .gitignore
```

---

## Step 4: Set Up Brain Directory (5 minutes)

### 4.1 Create Brain Folder Structure
```bash
# Create main brain folder (already should exist)
mkdir -p brain-yekdast

# Create subdirectories
mkdir -p brain-yekdast/Company
mkdir -p brain-yekdast/Tech\ Stack
mkdir -p brain-yekdast/Agents\ Office/{skills,feedback,routines}
mkdir -p brain-yekdast/Architecture/ADRs
mkdir -p brain-yekdast/Projects
mkdir -p brain-yekdast/audit

# Verify structure
tree -L 2 brain-yekdast/
```

### 4.2 Create Initial Brain Files

**File**: `brain-yekdast/Company/README.md`
```markdown
# Yekdast Company Context

**Mission**: Build a SaaS factory office — autonomous AI agents for complete SaaS delivery.

**Phase 1**: 12-agent MVP focusing on:
- Customer intake & qualification (lexi, piper)
- Architecture & product design (mlead, riley)
- Backend engineering & quality (olead, report, scout)
- DevOps & deployment (dlead, qa)
- Support & incident response (elead)
- Financial planning (alead, invo)

**Key Principles**:
1. Path B Model: Agents author specs/code; CI/CD executes
2. Single-node deployment (Phase 0D: honest topology)
3. Vault for secrets, Prometheus/Grafana for monitoring
4. MCP-native tools only (no SSH, no direct execution)
5. Least-privilege access per department

**Tech Stack**:
- Code: Node.js + Express, React/Next.js, React Native
- Async: RabbitMQ, Redis (caching & sessions)
- Data: PostgreSQL, Elasticsearch (logging)
- Infrastructure: Docker Swarm, Ansible, GitLab CI/CD
- Monitoring: Prometheus, Grafana, ELK
- Secrets: Vault (Phase 0D)
```

**File**: `brain-yekdast/Agents\ Office/agents.json`
```json
{
  "note": "This file holds agent customizations per interview or manual updates.",
  "agents": []
}
```

### 4.3 Verify Brain Structure
```bash
ls -la brain-yekdast/
ls -la brain-yekdast/Agents\ Office/
ls -la brain-yekdast/audit/
```

---

## Step 5: Validate Configuration (5 minutes)

### 5.1 Run npm run check
```bash
npm run check
```

**Expected output** (should pass all critical checks):
```
✓ Configuration valid
✓ 12 agents recognized (lexi, piper, mlead, riley, olead, scout, report, dlead, qa, elead, alead, invo)
✓ All agent IDs are real seats from fixed roster
✓ No haiku model (all sonnet)
✓ All tools reference wired MCPs only
✓ MCP departments use real department names
✓ Audit log path valid

Agent Summary:
  Sales:     lexi (medium), piper (medium)
  Marketing: mlead (high), riley (medium)
  Ops:       olead (high), scout (high), report (medium)
  Delivery:  dlead (high), qa (medium)
  Emails:    elead (medium)
  Finance:   alead (medium), invo (low)
```

**Troubleshoot**:
- `not one of the 35 seats — skipped`: Agent ID is custom (not real). Update to real seat ID.
- `haiku model invalid`: Replace all "haiku" with "sonnet".
- `unknown tool`: Check tools are in wired MCPs only (8 servers).
- `unknown department`: Verify department names match office defaults (emails, sales, marketing, ops, fin, delivery).

### 5.2 Check File Validity
```bash
# Validate JSON syntax
jq empty office.agents.local.json && echo "✓ agents JSON valid"
jq empty office.config.local.json && echo "✓ config JSON valid"

# Check no hardcoded secrets
grep -i -E "password|token|secret|key" office.agents.local.json office.config.local.json
# Expected: No output (all secrets in .env.local)
```

---

## Step 6: Start the Office Server (3 minutes)

### 6.1 Start Development Server
```bash
npm start
```

**Expected output**:
```
agents-office server
Loaded configuration from office.config.local.json
Loaded 12 agents from office.agents.local.json
MCP router initialized with 8 servers
Brain path: /Users/hadi/Documents/GitHub/agents-office-yekdast/brain-yekdast
Server listening on http://localhost:4520
Press Ctrl+C to stop
```

### 6.2 Verify Server is Running
In a new terminal:
```bash
curl -s http://localhost:4520/api/status | jq .

# Expected output:
{
  "status": "running",
  "agents": 12,
  "mcp_servers": 8,
  "brain_path": "./brain-yekdast",
  "uptime_seconds": 5
}
```

### 6.3 View Web UI (Optional)
- Open browser: http://localhost:4520
- Expected: Agent office dashboard showing 12 agents, 6 departments, 8 MCPs

---

## Step 7: Connect MCP Servers (Phase 2, Optional for Phase 1)

### 7.1 GitHub Token (Optional)
If you want agents to read GitHub PRs:

```bash
# Generate GitHub personal access token
# https://github.com/settings/tokens/new
# Scopes needed: repo:read (public), repo (private)

# Add to .env.local
echo "GITHUB_TOKEN=ghp_xxxxx" >> .env.local

# Restart server
npm start
```

### 7.2 GitLab Token (Recommended)
```bash
# Generate GitLab personal access token
# https://gitlab.com/-/user_settings/personal_access_tokens
# Scopes needed: api, read_user, read_repository, write_repository

echo "GITLAB_TOKEN=glpat-xxxxx" >> .env.local

# Restart server
npm start
```

### 7.3 Other MCPs (Phase 2)
Slack, Gmail, Notion, Docker, Prometheus, Grafana setup deferred to Phase 2 (MCP Wiring phase).

---

## Step 8: Test Agent Execution (Optional)

### 8.1 Run a Simple Task (if UI available)
1. Navigate to http://localhost:4520
2. Click "New Task"
3. Select agent: `lexi` (Growth Lead)
4. Task text: "List the tools you have access to and describe your role"
5. Click "Run"
6. Expected: Response describing lexi's role, tools (gitlab, slack, notion), and brief

### 8.2 Check Task Log
```bash
cat brain-yekdast/audit/mcp-access.log
# Should show: lexi created task, no MCP calls (this task is introspective)
```

---

## Step 9: Backup & Version Control

### 9.1 Commit Configuration (Secrets NOT Included)
```bash
# Check what's staged
git status

# Expected: office.config.local.json and office.agents.local.json should NOT appear
# (they're in .gitignore)

# Commit brain folder + docs
git add brain-yekdast/.claude/
git add brain-yekdast/Company/README.md
git add setup-local-env.sh
git commit -m "Phase 1: Initial brain setup and documentation"

# Push (if forked)
git push origin main
```

### 9.2 Document Secrets Storage Location
**IMPORTANT**: .env.local should be stored securely OUTSIDE this repo:
- Option A: Encrypted in 1Password/LastPass, store password in shared team vault
- Option B: In GitHub Secrets (if this is private repo), pull via CI/CD
- Option C: In Vault (Phase 0D deployment)

**Store backup of .env.local**:
```bash
# Save to secure location (not git, not shared folders)
cp .env.local /Users/hadi/Library/Application\ Support/yekdast-secrets/.env.local.backup
chmod 600 /Users/hadi/Library/Application\ Support/yekdast-secrets/.env.local.backup
```

---

## Post-Setup Validation Checklist

After completing setup, verify:

- [ ] `npm start` runs without errors
- [ ] http://localhost:4520 is accessible
- [ ] `npm run check` passes all checks
- [ ] 12 agents are loaded and visible
- [ ] .env.local is NOT committed to git
- [ ] office.config.local.json shows all 8 MCPs
- [ ] office.agents.local.json shows all 12 agents with "sonnet" model
- [ ] brain-yekdast folder has subdirectories (Company, Tech Stack, Agents Office, audit, etc.)
- [ ] .gitignore includes .env.local and *.local.json files
- [ ] No secrets (tokens, passwords) appear in committed files

---

## Troubleshooting

### "Port 4520 already in use"
```bash
lsof -i :4520
kill -9 <PID>
npm start
```

### "Module not found: src/server.js"
```bash
npm install
npm run build
npm start
```

### "agents-office is not a valid command"
```bash
# Install globally
npm install -g agents-office
# OR run via npm
npm start
```

### "Configuration validation failed: unknown department"
```bash
# Check office.agents.local.json for typos in department names
# Valid: emails, sales, marketing, ops, fin, delivery
jq '.agents[].department' office.agents.local.json | sort -u
```

### ".env.local not found"
```bash
./setup-local-env.sh
source .env.local
npm start
```

### "Cannot read property 'tools' of undefined"
```bash
# office.agents.local.json malformed JSON
jq empty office.agents.local.json
# Fix any syntax errors (missing commas, quotes, brackets)
```

---

## What's Next?

After Phase 1 setup is complete:

1. **Phase 2**: Build brain knowledge base (Tech Stack guides, company context, ADR templates)
2. **Phase 3**: Create agent skills (Project Intake, Feature Development, Deployment Pipeline, Incident Response)
3. **Phase 4**: Wire MCP servers (GitHub/GitLab tokens, Slack app, Gmail, Notion, Docker, Prometheus, Grafana)
4. **Phase 5-6**: Staging environment + local testing
5. **Phase 7**: First end-to-end task (SaaS project intake → design → deploy)

---

## Getting Help

- **Setup errors?** → Check this checklist step-by-step
- **Agent role questions?** → See AGENTS.md
- **MCP access questions?** → See MCP-MATRIX.md
- **Execution model questions?** → See GUARDRAILS.md
- **Configuration overview?** → See Phase1-Setup.md

---

**Phase 1 setup is now complete. Your 12-agent Yekdast office is ready to onboard.**
