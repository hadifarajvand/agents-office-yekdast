# Graph Report - agents-office-yekdast  (2026-10-01)

## Corpus Check
- 143 files · ~141,861 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 17 file(s) not represented in the graph (top: (none) 11, .example 1, .csh 1)

## Summary
- 1037 nodes · 2171 edges · 80 communities (63 shown, 17 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 99 edges (avg confidence: 0.82)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Task/DB Backend (Postgres)
- Frontend Static Data
- Connector Tile Rendering
- Brain Graph UI
- Task Panel UI Logic
- MCP Policy (Python)
- Frontend Build Pipeline
- Legacy Node Server (serve.mjs)
- MCP Policy (Node)
- Routine Scheduling Math
- Routine Card UI
- 3D Office Furniture Builders
- Model/Effort Selection
- Office Architecture Overview
- Roster Unit Tests
- Config Loading (Python)
- Office Event Feed UI
- Camera Focus/Navigation
- Legacy Routine Engine (Node)
- Schedule Parsing (Node)
- Skills Loader (Python)
- Usage Gauge (Python)
- Usage Gauge (Node)
- Task Approval Cards
- LangGraph Engine Core
- Model/Effort Resolution (Python)
- Task Demo/Polling
- Finance & Ops Brain Docs
- MCP Tile Image Baking
- Feedback Learning (Python)
- Feedback Learning (Node)
- Brain Context Retrieval (Python)
- Marketing Brain Docs
- Agent Roster & MCP Matrix Docs
- Release Script
- 3D Avatar Posing
- Config Validator (check.mjs)
- Brain Graph Builder (Node)
- Emails Dept Skill Binding
- Path B Governance Docs
- Changelog & Feature History
- Chat Context Assembly
- Routine State Sync UI
- Haiku Router (LangChain)
- Sales/Marketing Numbers Rules
- Full Agent Roster List
- Onboarding Interview Flow
- Camera Animation Utils
- Python Backend Dependencies
- Skills Loader (Node)
- Shell.html UI Regions
- Legacy V1 Demo Data
- Path B vs Path A Policy
- Company Context Docs
- Phase 1 Setup Docs
- Delivery Dept Brain Docs
- Brain Graph Layout Algorithm
- Dark Mode Dimming
- Task Demo Fixtures
- Docker Compose Services
- Google Workspace Connectors
- Doc/Research Connectors
- Billing & Analytics Connectors
- Sales/Analytics Connector Pair
- Marketing Connector Pair
- AI Creative Connector Pair
- Messaging Connector Pair
- Xero & README Hero
- ChatGPT Connector
- Claude Connector
- FullEnrich Connector
- Jira Connector
- Meta Connector
- Playwright Connector
- Slack Connector
- Territool Connector
- Webflow Connector
- ZoomInfo Connector

## God Nodes (most connected - your core abstractions)
1. `initTasks()` - 84 edges
2. `server` - 39 edges
3. `initBrain()` - 25 edges
4. `MCPRegistry` - 20 edges
5. `initMcp()` - 20 edges
6. `agents_list()` - 15 edges
7. `run()` - 15 edges
8. `chat()` - 15 edges
9. `run_task()` - 14 edges
10. `load()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `#board task board (DOING/NEXT/DONE)` --semantically_similar_to--> `Project Plan Template`  [INFERRED] [semantically similar]
  src/shell.html → brain/70-Delivery/project-plan-template.md
- `QA Checklist` --semantically_similar_to--> `house-style skill`  [INFERRED] [semantically similar]
  brain/70-Delivery/qa-checklist.md → skills/house-style/SKILL.md
- `Northgate Studio` --semantically_similar_to--> `Yekdast SaaS Factory`  [INFERRED] [semantically similar]
  brain/10-Business/business-model.md → brain-yekdast/Company/README.md
- `brain-yekdast/Tech Stack README` --references--> `OLead — Backend & Engineering Lead`  [EXTRACTED]
  brain-yekdast/Tech Stack/README.md → .claude/AGENTS.md
- `serve.mjs (local server)` --references--> `serve.mjs engine (current)`  [INFERRED]
  README.md → .claude/LANGGRAPH-MIGRATION-PLAN.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Path B enforcement mechanisms** — agents_pathb, agents_mcp_router, agents_refusal_protocol, agents_audit_log [EXTRACTED 1.00]
- **LangGraph replaces serve.mjs orchestration** — claude_langgraph_migration_plan_stategraph, claude_langgraph_migration_plan_servemjs, claude_langgraph_migration_plan_hitl, claude_langgraph_migration_plan_checkpointer [EXTRACTED 1.00]
- **Ways to teach an agent how work is done** — skills_md_brief_concept, skills_md_skill_concept, skills_md_lead_interview, skills_md_revise_feedback [EXTRACTED 1.00]
- **Brand Standards Applied Across Channels** — brain_20_brand_voice, brain_20_brand_visual_identity, brain_70_delivery_moc_delivery [INFERRED 0.75]
- **Lead Qualification To Proposal Flow** — brain_30_customers_icp, brain_60_sales_sales_playbook, brain_10_business_proposal_template [INFERRED 0.80]
- **Marketing Content Production Flow** — brain_40_marketing_content_engine, brain_40_marketing_newsletter, brain_40_marketing_reel_hooks [INFERRED 0.80]
- **Finance rules require owner approval for exceptions** — brain_80_finance_invoicing_rules, brain_80_finance_payables_rules, contractor_terms [EXTRACTED 0.90]
- **Delivery pipeline: plan, QA, report all cross-reference each other and the numbers ledger** — brain_70_delivery_project_plan_template, brain_70_delivery_qa_checklist, brain_70_delivery_report_template, numbers_ledger [EXTRACTED 0.90]
- **Owner approval flow spans department billboard, docked rail, and task status panel** — src_shell_html_dept_badge, src_shell_html_rail, src_shell_html_tpanel, src_shell_html_approval_flow [INFERRED 0.80]

## Communities (80 total, 17 thin omitted)

### Community 0 - "Task/DB Backend (Postgres)"
Cohesion: 0.05
Nodes (64): brain_summary(), delete_task(), get_pool(), get_task(), _init(), kv_get(), kv_set(), list_tasks() (+56 more)

### Community 1 - "Frontend Static Data"
Cohesion: 0.04
Nodes (47): APPROVAL_ASKS, APPROVAL_BY_AGENT, BILLBOARDS, DEPTS, LAYOUT, TOKENS, WORKLINES, BB_ROWS (+39 more)

### Community 2 - "Connector Tile Rendering"
Cohesion: 0.10
Nodes (29): fromSummary(), hue(), INK, inkOf(), loadConnectors(), norm(), tile(), AGENT_MCP (+21 more)

### Community 3 - "Brain Graph UI"
Cohesion: 0.11
Nodes (30): agentOf(), DEPT_FOLDERS, GROUP_COL, GROUP_NAME(), initBrain(), centre(), chips(), close() (+22 more)

### Community 4 - "Task Panel UI Logic"
Cohesion: 0.12
Nodes (33): initTasks(), apply(), brainSend(), chipsHTML(), close(), companyHTML(), complete(), copyResult() (+25 more)

### Community 5 - "MCP Policy (Python)"
Cohesion: 0.12
Nodes (10): _display(), _logo_key(), MCPRegistry, norm(), tool_id(), make_registry(), test_allow_list_restricts_to_named_servers(), test_denied_server_is_not_usable() (+2 more)

### Community 6 - "Frontend Build Pipeline"
Cohesion: 0.07
Nodes (27): html, shell, dependencies, d3-force, description, devDependencies, esbuild, playwright-core (+19 more)

### Community 7 - "Legacy Node Server (serve.mjs)"
Cohesion: 0.08
Nodes (26): guessNeedsOk(), ask(), askX(), body(), cfg, CLI_CWD, DATA, discovering (+18 more)

### Community 8 - "MCP Policy (Node)"
Cohesion: 0.14
Nodes (23): ALIASES, allowed(), allowedTools(), cfgMcp, denied(), DEPT_KEYS, DEPTS_BY_KEY, deptsFor() (+15 more)

### Community 9 - "Routine Scheduling Math"
Cohesion: 0.17
Nodes (20): advance(), clock(), _cut(), day_index(), find_time(), from_picker(), hhmm(), _mins() (+12 more)

### Community 10 - "Routine Card UI"
Cohesion: 0.20
Nodes (22): listText(), matchRoutine(), saveState(), agentName(), editRoutine(), enqueue(), fire(), load() (+14 more)

### Community 11 - "3D Office Furniture Builders"
Cohesion: 0.17
Nodes (19): geoCache, makeChair(), makeDesk(), makeDeskScreenTexture(), makeFloorTitle(), makeHolo(), makeMeetingTable(), makePerson() (+11 more)

### Community 12 - "Model/Effort Selection"
Cohesion: 0.18
Nodes (18): DEFAULT_MODEL, EFFORT_KEYS, EFFORT_NAME, effortFor(), effortName(), FROM_TEXT, MODEL_KEYS, modelArgs() (+10 more)

### Community 13 - "Office Architecture Overview"
Cohesion: 0.13
Nodes (17): Agents Office v3 (Beta) README, The Brain (notes folder), dist/command-centre-v2.html, mcp.mjs (connector discovery), office.agents.json (35-agent roster), serve.mjs (local server), brainFile(), defaults() (+9 more)

### Community 14 - "Roster Unit Tests"
Cohesion: 0.19
Nodes (10): defaults(), validate(), test_brief_trimmed_over_limit(), test_department_and_lead_are_immutable(), test_model_must_be_one_of_three(), test_rejects_new_agent(), test_six_departments_35_seats(), test_route_falls_back_to_dept_lead_on_malformed_agent() (+2 more)

### Community 15 - "Config Loading (Python)"
Cohesion: 0.18
Nodes (6): Config, load_config(), _read_json(), brain_file(), load_roster(), _read()

### Community 16 - "Office Event Feed UI"
Cohesion: 0.14
Nodes (18): ago(), applyRoster(), chatPush(), ensureChat(), esc(), feedPush(), fireAgentEvent(), getEmoteTex() (+10 more)

### Community 17 - "Camera Focus/Navigation"
Cohesion: 0.21
Nodes (18): buildDeptRail(), cascadeRows(), enterFocus(), exitFocus(), flyBillboardIntoRail(), flyTo(), focusTarget(), openAgent() (+10 more)

### Community 18 - "Legacy Routine Engine (Node)"
Cohesion: 0.18
Nodes (16): advance(), ALLOWED, askLine(), due(), file(), LATE_AFTER, load(), loadState() (+8 more)

### Community 19 - "Schedule Parsing (Node)"
Cohesion: 0.20
Nodes (16): guessOk(), handleChat(), clock(), cut(), DAY_NAMES, dayIndex(), DAYS, findTime() (+8 more)

### Community 20 - "Skills Loader (Python)"
Cohesion: 0.23
Nodes (7): brain_dir(), _list(), load_skills(), parse_skill(), _read_one(), Skill, Skills

### Community 21 - "Usage Gauge (Python)"
Cohesion: 0.19
Nodes (9): fallback(), fetch_usage(), load_state(), parse_usage(), read_token(), record(), save_state(), state_file() (+1 more)

### Community 22 - "Usage Gauge (Node)"
Cohesion: 0.19
Nodes (13): bumpUsage(), getUsage(), ENDPOINT, fallback(), fetchUsage(), loadState(), parseUsage(), readToken() (+5 more)

### Community 23 - "Task Approval Cards"
Cohesion: 0.22
Nodes (16): modelName(), agentOf(), askApproval(), cardHTML(), cardHTMLr(), connect(), deliver(), metaFor() (+8 more)

### Community 24 - "LangGraph Engine Core"
Cohesion: 0.24
Nodes (8): agent_brief(), chat(), persona(), roster_text(), _specialist_node(), SpecialistState, ask(), Agent

### Community 25 - "Model/Effort Resolution (Python)"
Cohesion: 0.22
Nodes (9): effort_for(), model_for(), model_id(), ModelDef, norm_effort(), norm_model(), test_effort_precedence_and_model_default(), test_model_id_resolves_env_backed_id() (+1 more)

### Community 26 - "Task Demo/Polling"
Cohesion: 0.21
Nodes (15): addTask(), closeBig(), grow(), mk(), onStuck(), poll(), pollUsage(), reconcile() (+7 more)

### Community 27 - "Finance & Ops Brain Docs"
Cohesion: 0.19
Nodes (14): Vendor List, Invoicing Rules, MOC — Finance, Payables Rules, Compliance Checklist, Legal Basics, MOC — Operations, Reporting Cadence (+6 more)

### Community 28 - "MCP Tile Image Baking"
Cohesion: 0.19
Nodes (4): bbox_crop(), try_mark_crop(), bbox_crop(), tile_from()

### Community 29 - "Feedback Learning (Python)"
Cohesion: 0.31
Nodes (8): classify(), count(), dir_(), _file(), _head(), prompt_text(), read(), record()

### Community 30 - "Feedback Learning (Node)"
Cohesion: 0.22
Nodes (12): classify(), count(), dir(), file(), HEAD(), promptText(), read(), record() (+4 more)

### Community 31 - "Brain Context Retrieval (Python)"
Cohesion: 0.24
Nodes (6): business_context(), context_text(), relevant_notes(), vault_index(), _walk_notes(), run_task()

### Community 32 - "Marketing Brain Docs"
Cohesion: 0.29
Nodes (11): Offer Ladder, Proposal Template, Voice, Content Engine, MOC — Marketing, Newsletter, Reel Hooks That Worked, Contractor Terms (+3 more)

### Community 33 - "Agent Roster & MCP Matrix Docs"
Cohesion: 0.21
Nodes (12): DLead — DevOps & Infrastructure Lead, ELead — Support & Operations Lead, OLead — Backend & Engineering Lead, QA — QA Specialist, MCP Access Matrix, Docker MCP server, GitHub MCP server, Gmail MCP server (+4 more)

### Community 34 - "Release Script"
Cohesion: 0.17
Nodes (10): AUTHOR, bg, FILES, OUT, pkg, pub, push, rel (+2 more)

### Community 35 - "3D Avatar Posing"
Cohesion: 0.18
Nodes (12): posePerson(), poseWork(), applyStandAndFacing(), pickWorkMode(), requestApproval(), sample(), setStuckLive(), syncApprovals() (+4 more)

### Community 36 - "Config Validator (check.mjs)"
Cohesion: 0.22
Nodes (6): bad(), cfg, fails, ok(), results, step()

### Community 37 - "Brain Graph Builder (Node)"
Cohesion: 0.29
Nodes (5): loadConfig(), readJSON(), ROOT, OUT, SKIP

### Community 38 - "Emails Dept Skill Binding"
Cohesion: 0.27
Nodes (10): Agent: piper, 30-Customers, 70-Delivery, Department: emails, Offer Ladder (pricing), client-reply skill, house-style skill, proposal skill (+2 more)

### Community 39 - "Path B Governance Docs"
Cohesion: 0.22
Nodes (10): MCP Access Audit Log, MCP Router, brain-yekdast/Agents Office README, Routines Feature (v3.5.0), Skills Feature (v3.2.0), LangChain MCP Tool Adapter, CLAUDE.md (Agents Office — for Claude Code), npm run check (check.mjs) (+2 more)

### Community 40 - "Changelog & Feature History"
Cohesion: 0.20
Nodes (10): Changelog, Real Connectors Feature (v3.1.0), Lead Interview Feature (v3.3.0), Three Models + Effort Levels Feature (v3.6.0/3.6.1), learn.mjs (corrections/feedback), onboard.mjs (set-up interview), SKILLS.md — Teaching the agents how you work, Brief (agent standing instructions) (+2 more)

### Community 41 - "Chat Context Assembly"
Cohesion: 0.36
Nodes (10): namesOf(), agentBrief(), businessContext(), chat(), contextText(), refreshSkills(), relevantNotes(), run() (+2 more)

### Community 42 - "Routine State Sync UI"
Cohesion: 0.31
Nodes (10): withState(), addRoutine(), fireDemo(), railFor(), rtAct(), setRoutines(), syncPills(), describe() (+2 more)

### Community 43 - "Haiku Router (LangChain)"
Cohesion: 0.28
Nodes (3): ask_haiku_json(), _client(), parse_json()

### Community 44 - "Sales/Marketing Numbers Rules"
Cohesion: 0.22
Nodes (7): Numbers Ledger, Visual Identity, Client List, Ideal Customer Profile, Ad Playbook, Pipeline Rules, Sales Playbook

### Community 45 - "Full Agent Roster List"
Cohesion: 0.25
Nodes (9): ALead — Finance & Admin Lead, Invo — Finance & Billing Specialist, Lexi — Growth & Intake Lead, MLead — Product & Architecture Lead, Piper — Account & Business Manager, Report — Database Specialist, Riley — Documentation & Tech Writing, Scout — Security & Compliance Specialist (+1 more)

### Community 46 - "Onboarding Interview Flow"
Cohesion: 0.42
Nodes (8): active(), handle(), load(), progress(), QUESTIONS, save(), stateFile(), writeUp()

### Community 47 - "Camera Animation Utils"
Cohesion: 0.25
Nodes (9): applyCamera(), bezier(), clamp(), loop(), resize(), smooth(), tickLOD(), tickTween() (+1 more)

### Community 48 - "Python Backend Dependencies"
Cohesion: 0.25
Nodes (7): FastAPI dependency, langchain-anthropic dependency, langgraph dependency, LangGraph Migration Plan, Checkpointer (Postgres/SQLite saver), serve.mjs engine (current), LangGraph StateGraph Orchestration Core

### Community 49 - "Skills Loader (Node)"
Cohesion: 0.36
Nodes (7): brainDir(), LIMITS, loadSkills(), parseSkill(), readOne(), SHIPPED, DEPT_KEYS

### Community 50 - "Shell.html UI Regions"
Cohesion: 0.32
Nodes (8): Agents Office V3 UI Shell, Approval (needsOk) UI flow, #board task board (DOING/NEXT/DONE), .badge department billboard, #rail docked side panel (chat/agent), #topbar connector/model strip, #tpanel Task Status panel, #wires connector-to-pod wiring

### Community 51 - "Legacy V1 Demo Data"
Cohesion: 0.25
Nodes (6): FILE_GEN, KPIS, money(), P, STATS, V1

### Community 52 - "Path B vs Path A Policy"
Cohesion: 0.33
Nodes (5): Path A Direct Execution (Forbidden), Refusal Protocol, Human-in-the-loop interrupt, Unused Agent Seats — Expansion Reserve, Expansion Triggers

### Community 53 - "Company Context Docs"
Cohesion: 0.33
Nodes (7): brain/00-Meta/index.md (Index), brain/00-Meta/log.md (Log), brain/00-Meta/numbers-ledger.md (Numbers ledger), Business Model, brain-yekdast/Tech Stack README, Northgate Studio, Yekdast SaaS Factory

### Community 54 - "Phase 1 Setup Docs"
Cohesion: 0.38
Nodes (7): brain-yekdast/Company README (Yekdast Company Context), Phase 1: Yekdast SaaS Factory Office Setup, office.agents.local.json, office.config.local.json, 12-Agent Team (Phase 1), Phase 1 Setup Checklist, setup-local-env.sh

### Community 55 - "Delivery Dept Brain Docs"
Cohesion: 0.47
Nodes (6): Asset Conventions, MOC — Delivery, Project Plan Template, QA Checklist, Report Template, Visual Identity (brand colours)

### Community 56 - "Brain Graph Layout Algorithm"
Cohesion: 0.40
Nodes (6): buildBrainGraph(), layoutGraph(), readOfficeNotes(), readVault(), d3-force, vaultIndex()

### Community 57 - "Dark Mode Dimming"
Cohesion: 0.40
Nodes (6): applySceneDim(), dimTwin(), mix(), restoreSceneDim(), setDark(), tickDim()

### Community 60 - "Task Demo Fixtures"
Cohesion: 0.60
Nodes (5): fill(), freshTask(), pick(), visibleTitles(), rnd()

### Community 61 - "Docker Compose Services"
Cohesion: 0.83
Nodes (4): Docker Compose (Agents Office), app service, postgres service, redis service

### Community 62 - "Google Workspace Connectors"
Cohesion: 1.00
Nodes (3): Gmail, Google Calendar, Google Drive

### Community 63 - "Doc/Research Connectors"
Cohesion: 0.67
Nodes (3): Notion, PandaDoc, Perplexity

### Community 64 - "Billing & Analytics Connectors"
Cohesion: 0.67
Nodes (3): PostHog, RevenueCat, Stripe

## Ambiguous Edges - Review These
- `Ad Playbook` → `MOC — Operations`  [AMBIGUOUS]
  brain/40-Marketing/ad-playbook.md · relation: references
- `Contractor Terms` → `MOC — Finance`  [AMBIGUOUS]
  brain/50-Emails/contractor-terms.md · relation: references
- `Vendor List` → `MOC — Finance`  [AMBIGUOUS]
  brain/50-Emails/vendor-list.md · relation: references

## Knowledge Gaps
- **189 isolated node(s):** `ModelDef`, `shell`, `html`, `results`, `cfg` (+184 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 283 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **17 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Ad Playbook` and `MOC — Operations`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **What is the exact relationship between `Contractor Terms` and `MOC — Finance`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **What is the exact relationship between `Vendor List` and `MOC — Finance`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **Why does `Routine (office.mjs scheduling)` connect `Path B Governance Docs` to `Agent Roster & MCP Matrix Docs`, `Legacy Routine Engine (Node)`?**
  _High betweenness centrality (0.127) - this node is a cross-community bridge._
- **Why does `initTasks()` connect `Task Panel UI Logic` to `Frontend Static Data`, `Routine State Sync UI`, `Model/Effort Selection`, `Schedule Parsing (Node)`, `Task Approval Cards`, `Task Demo/Polling`, `Task Demo Fixtures`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Why does `MCP Access Matrix` connect `Agent Roster & MCP Matrix Docs` to `Full Agent Roster List`, `Phase 1 Setup Docs`, `Path B Governance Docs`?**
  _High betweenness centrality (0.084) - this node is a cross-community bridge._
- **Are the 17 inferred relationships involving `initTasks()` (e.g. with `addRoutine()` and `addTask()`) actually correct?**
  _`initTasks()` has 17 INFERRED edges - model-reasoned connections that need verification._