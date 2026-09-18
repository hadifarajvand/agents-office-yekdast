# Contributing to Agents Office

## Branch Strategy

```
main (production)
  ↑
develop (integration)
  ↑
feature/* (your work)
```

### Creating a Feature Branch

```bash
git checkout develop
git pull origin develop
git checkout -b feature/your-feature-name
```

### Committing

**Format:** `<type>(<scope>): <message>`

```bash
git add backend/langgraph/nodes.py
git commit -m "feat(langgraph): implement team execution node

- Add team planning logic
- Support parallel teammate execution
- Implement piece assembly

Fixes #42
Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

**Types:** `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

**Scopes:** `langgraph`, `api`, `mcp`, `sandbox`, `kb`, `observability`, `docker`, `ci`

### Before Pushing

```bash
# Update with latest develop
git fetch origin
git rebase origin/develop

# Run tests locally
pytest backend/tests -v

# Push
git push origin feature/your-feature-name
```

### Creating a PR

```bash
gh pr create --title "Team Execution: Parallel Agents" \
  --body "Implements parallel agent execution for team tasks.

## Changes
- Add team_split node (lead plans pieces)
- Add parallel_execute node (teammates run concurrently)

## Testing
- [x] Unit tests pass
- [x] Integration tests pass
- [x] Manual testing on local Docker

Fixes #42"
```

## Testing Before Commit

Pre-commit hooks run automatically. If they fail:

```bash
# Fix formatting
black backend/

# Fix linting
# Review flake8 output and fix manually

# Run tests
pytest backend/tests -v

# Retry commit
git commit -m "your message"
```

## Code Style

**Python:** Black (auto-format)
```bash
black backend/
```

**Type hints:** Required for new code
```python
async def run_agent(state: OfficeState) -> Dict[str, Any]:
    ...
```

**Tests:** Required for new features
```python
@pytest.mark.asyncio
async def test_new_feature():
    result = await new_feature()
    assert result is not None
```

## Debugging Merge Conflicts

```bash
# Check status
git status

# Open files and resolve conflicts (<<<<<<, ======, >>>>>>>)

# Mark as resolved
git add conflicted-file.py

# Continue rebase
git rebase --continue
```

## Reverting Changes

**Before pushing (only on your branch):**
```bash
git reset --hard HEAD~1
git push origin feature/name --force-with-lease
```

**After merging (use revert):**
```bash
git log develop  # find commit hash
git revert <hash>
git push origin develop
```

## Reviewing PRs

- Run locally: `git checkout <branch>`
- Check tests pass: `pytest backend/tests -v`
- Review code for:
  - Breaking changes
  - Missing tests
  - Unclear variable names
  - Security issues
- Comment on line: GitHub UI
- Approve or request changes

## Releases

When ready to release (end of week):

```bash
# Merge develop → main (via PR)
git checkout main
git pull origin main
git merge develop
git push origin main

# Tag version
git tag -a v3.6.1-py -m "Add team execution feature"
git push origin v3.6.1-py

# Update VERSION.md
```

## Getting Help

- **Git questions:** See GIT_WORKFLOW.md
- **Code structure:** See BOOTSTRAP_30MIN.md
- **Architecture:** See LANGGRAPH_MIGRATION.md
