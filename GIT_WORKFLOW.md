# Git Workflow & Version Control Strategy

**Branches:**
- `main` — Production (stable, all tests pass)
- `develop` — Integration (features merged here, staging)
- `feature/*` — Feature branches (create from develop)
- `bugfix/*` — Bug fixes (create from develop)
- `hotfix/*` — Critical production fixes (create from main)

**Naming Convention:**
```
feature/team-execution-parallel-agents
feature/agent-knowledge-base
bugfix/approval-workflow-timeout
hotfix/critical-security-issue
```

---

## Branch Workflow

### 1. Start Feature Work

```bash
# Update develop
git checkout develop
git pull origin develop

# Create feature branch
git checkout -b feature/team-execution-parallel-agents

# Work on feature
git add backend/langgraph/
git commit -m "feat(langgraph): implement parallel team execution

- Add team state to OfficeState
- Create team planning node (lead splits work)
- Implement parallel node execution
- Add piece assembly (lead merges results)

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

### 2. Keep Feature Branch Updated

```bash
# Regularly pull latest develop
git fetch origin
git rebase origin/develop

# If conflicts
git rebase --continue
# or abort if needed
git rebase --abort
```

### 3. Push & Create PR

```bash
# Push to remote
git push origin feature/team-execution-parallel-agents

# Create PR on GitHub (or manually):
gh pr create --title "Team Execution: Parallel Agent Coordination" \
  --body "Implements feature X, fixes issue #123"
```

### 4. After PR Merge

```bash
# Delete branch locally
git branch -d feature/team-execution-parallel-agents

# Delete on remote
git push origin --delete feature/team-execution-parallel-agents

# Back to develop
git checkout develop
git pull origin develop
```

---

## Commit Message Format

```
<type>(<scope>): <subject>

<body>

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
```

**Types:**
- `feat` — New feature
- `fix` — Bug fix
- `refactor` — Code restructure (no behavior change)
- `test` — Tests only
- `docs` — Documentation only
- `chore` — Build, deps, CI/CD

**Scopes:**
- `langgraph` — State graphs & nodes
- `api` — FastAPI routes
- `mcp` — MCP tool integration
- `sandbox` — Tool sandboxing
- `kb` — Knowledge base system
- `observability` — Tracing & logging
- `docker` — Docker setup
- `ci` — GitHub Actions / CI/CD

**Example:**
```
feat(langgraph): add team execution parallel nodes

- Implement team_split node (lead plans pieces)
- Create parallel_execute node (teammates run concurrently)
- Add piece_merge node (lead combines results)
- Update StateGraph routing for team tasks

Fixes #45
Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
```

---

## Version Management

**Semantic Versioning:** `MAJOR.MINOR.PATCH`

- **MAJOR:** Breaking changes (full backend rewrite)
- **MINOR:** New features (team execution, routines, etc.)
- **PATCH:** Bug fixes

**Current:** `3.6.0-py` (Python rewrite of v3.6)

**Tag releases:**
```bash
git tag -a v3.6.1-py -m "Add team execution feature"
git push origin v3.6.1-py
```

---

## Protected Branches

**Main branch rules:**
- Require PR review (1+ approver)
- Require all tests passing
- Require branch up-to-date with develop
- No direct pushes (only via PR)

**Develop branch rules:**
- Require PR review (1+ approver)
- Require all tests passing
- Allow direct commits for hotfixes

---

## Pre-Commit Hooks

Run tests & linting before committing (see `.git/hooks/` setup below).

```bash
# Install hooks
git config core.hooksPath .githooks

# Make executable
chmod +x .githooks/*
```

If tests fail, commit is blocked. Fix and retry:
```bash
git add .
git commit -m "fix: resolve linting issues"
```

To skip hooks (emergency only):
```bash
git commit --no-verify
```

---

## Reverting Changes

**If you pushed to feature branch (not merged yet):**
```bash
# Reset to previous commit (local)
git reset --soft HEAD~1  # keep changes
git reset --hard HEAD~1  # discard changes

# Force push (dangerous, only on feature branches)
git push origin feature/branch-name --force
```

**If merged to develop (need to revert):**
```bash
git revert <commit-hash>
git push origin develop
```

**If merged to main (hotfix needed):**
```bash
git checkout main
git revert <commit-hash>
git push origin main

# Then fix in hotfix branch
git checkout -b hotfix/issue-name
# fix code
git commit
git push origin hotfix/issue-name
# Create PR to main
```

---

## Daily Workflow

**Morning:**
```bash
git checkout develop
git pull origin develop
```

**While coding:**
```bash
git add backend/langgraph/nodes.py
git commit -m "feat(langgraph): add load_context node"

# Every few commits, sync with develop
git fetch origin
git rebase origin/develop
```

**End of day:**
```bash
git push origin feature/your-feature
```

**Before PR:**
```bash
# Ensure up-to-date
git rebase origin/develop

# Run tests locally
pytest backend/tests -v

# Push
git push origin feature/your-feature --force-with-lease
```

---

## Debugging with Git

**Find when a bug was introduced:**
```bash
git bisect start
git bisect bad HEAD  # current is broken
git bisect good v3.6.0-py  # last known good

# Test each version
git bisect reset
```

**See blame for a line:**
```bash
git blame backend/langgraph/nodes.py | grep "def run_agent"
```

**See commit history for a file:**
```bash
git log --follow backend/langgraph/nodes.py
```

**See what changed in a commit:**
```bash
git show <commit-hash>
```

---

## CI/CD Integration

Every push triggers:
1. **Lint** (black, flake8)
2. **Type check** (mypy)
3. **Unit tests** (pytest)
4. **Integration tests** (docker-compose up + test)
5. **Security scan** (bandit)

If any fail, PR cannot be merged.

Check status:
```bash
git status
gh pr checks  # GitHub CLI
```

View logs:
```bash
gh run list
gh run view <run-id>
```
