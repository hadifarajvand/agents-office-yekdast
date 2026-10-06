# Execution Pass Notes

## What Shipped

### Phase 0 - Baseline
- Created `backbone/` package with pyproject.toml (litellm, anthropic, pydantic, structlog, pyyaml)
- Created `models/` directory with routing.yaml, catalog.yaml, embeddings.yaml, rerankers.yaml
- Created `tests/` directory at repo root
- All Python files compile clean

### Phase 1 - Multi-Model Client and Tier Router
- `backbone/runtime/model_client.py`: ModelRouter with tier resolution, LiteLLM integration, ordered fallbacks, daily budget tracking, cost estimation
- 5 tiers: reasoning_deep, reasoning_fast, cheap_fast, rag_specialist, local_only
- 5 tests covering tier resolution, fallback behavior, budget control

### Phase 2 - 265 Executable Agents
- `scripts/expand-registry.py`: generates .md definitions for all 265 registry entries into domain subdirs
- `scripts/validate-registry.py`: validates every agent has a .md file and resolvable tier
- All 265 agents now have executable definitions with RAG retrieval prompts and LLM system prompts
- 11 pre-existing hand-written agents preserved (flat in .claude/agents/)

### Phase 3 - RAG Agentic Pattern
- `backbone/rag/chunker.py`: structure-aware splitting with token bounds and overlap
- `backbone/rag/embeddings.py`: batch embedding service (Voyage 3 / Ollama)
- `backbone/rag/store.py`: pgvector HNSW index with metadata JSONB + GIN index
- `backbone/rag/retriever.py`: hybrid retrieval (vector + keyword) with reciprocal rank fusion
- `backbone/rag/agentic_loop.py`: plan-retrieve-grade-rewrite-generate-selfcheck loop (max 3 iters)
- `docs/references/Agentic-RAG-Pattern.html`: self-contained field manual
- 3 tests covering retrieval, query rewriting, and iteration capping

### Phase 4 - Agentic Depth and Chrome Extension
- `backbone/orchestrator/planner.py`: planner-executor-critic loop with typed task graph and stop-gate
- `backbone/runtime/browse_handler.py`: tab content handler with injection sanitization
- `extensions/chrome/`: Manifest V3 extension with side panel UI and service worker
- 4 tests covering plan rejection/replan, depth capping, browse response, and injection sanitization

### Phase 5 - AI Security
- `backbone/runtime/guarded_client.py`: GuardedModelClient wrapping ModelRouter with validation
- `sanitize_rag_context()`: strips 16 injection patterns from untrusted document content
- Action allowlist enforcement for agent outputs
- 2 tests covering retry-then-reject and injection blocking

### Phase 6 - Reconciliation and CI
- CI: pinned semgrep to `semgrep/semgrep-action@v1`, trivy to `@0.28.0`, trufflehog to `@v3.82.13`
- CI: added backbone test step
- Makefile: updated test and lint targets to include backbone, added expand-agents and rag targets

## Test Summary
- 14 tests total, all passing
- test_model_router.py: 5 tests (tier resolution, fallback, budget)
- test_rag.py: 3 tests (retrieval, rewrite, cap)
- test_planner.py: 2 tests (reject/replan, depth cap)
- test_browse_route.py: 2 tests (response, sanitization)
- test_guardrails_path.py: 2 tests (retry/reject, injection blocking)

## Assumptions

- `backbone/` is a new top-level Python package, separate from `backend/` (the FastAPI app)
- `models/` at repo root holds YAML configs for model routing, catalog, embeddings, rerankers
- The 11 existing hand-written agent .md files are flat in `.claude/agents/`; Phase 2 creates domain subdirs
- Tests live at repo root `tests/` for backbone; backend keeps its own `backend/tests/`
- LiteLLM is the model routing layer; Anthropic SDK is available for direct access patterns
- Model IDs use Anthropic current model strings (claude-opus-4-20250514, claude-sonnet-4-20250514, claude-haiku-4-5-20251001)

## Design Decisions

- **Tier router over direct SDK calls**: LiteLLM provides a unified interface across providers with built-in retry/fallback. Cost: extra dependency. Benefit: provider-agnostic, supports local Ollama fallback.
- **In-process budget tracking**: Simple atomic counter, not distributed. Good enough for single-process agent runs. For multi-process, would need Redis-backed tracking.
- **backbone/ as separate package**: Keeps agent runtime cleanly separated from the FastAPI web app. They share structlog and pydantic but have independent dependency trees.
- **Sanitization over firewall**: For both RAG docs and browser content, we strip known injection patterns rather than running a separate content firewall. Simpler, but patterns need to be maintained.

## Deferred Items

- [ ] Distributed budget tracking across multiple processes (Redis-backed)
- [ ] NeMo Guardrails integration (third layer alongside guardrails-ai and DeepEval)
- [ ] Real pgvector connection pooling optimization
- [ ] Keycloak JWT integration for starter-kit auth (currently placeholder)
- [ ] MCP server validation (6 configured in .mcp.json, README claims "314 tools" which needs audit)
- [ ] Agent SDK wrapper (`backbone/runtime/agent_sdk.py`) for Claude Agent SDK patterns
- [ ] Sigma rules and OPA/Kyverno policies for the /agent/browse endpoint
- [ ] security/ai-security-by-design.html (referenced in task but file does not exist yet)

## Residual Risks

1. **Injection sanitization is pattern-based**: Adversaries can craft novel patterns not in the blocklist. Should be augmented with LLM-based injection detection.
2. **Budget tracking resets on process restart**: No persistence. Multi-worker deployments can exceed budget.
3. **Agent .md definitions are templated**: Hand-written agents may have richer prompts. The 254 generated ones are functional but generic.
4. **Chrome extension uses localhost**: Production deployment needs configurable API endpoint.
5. **Coverage is 14 tests**: Backend (backend/) has zero tests in this pass. The 80% coverage gate in pyproject.toml will fail until backend tests exist.

## Unrelated Problems Noticed

- `backend/build/` directory contains stale copies of source files (leftover from pip install -e)
- `backend/alembic.ini` is staged with changes but alembic/ dir is untracked
- `.env` file exists at root (in .gitignore but present locally)
- `docker-compose.yml` uses version "3.8" which is deprecated in modern Docker Compose
- README claims "314 MCP tools" but only 6 MCP servers are configured in .mcp.json
