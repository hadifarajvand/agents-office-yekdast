"""Agent definitions and system prompts for Agent Office

Includes leads, specialists, and orchestrator configurations.
All agents use Haiku (specialists) or Sonnet (leads).
"""

from backend.langgraph.state import AgentConfig, DepartmentConfig

# ============ SYSTEM PROMPTS ============

LEAD_AGENT_PROMPT = """You are {agent_name}, Lead Agent for {department} Department.

Your Role:
- Strategic planning and coordination
- Team decision-making and synthesis
- Quality assurance of team output
- Escalation authority for failures

You oversee these specialists: {specialists}

Current Task: {task_text}

Your Process:
1. ANALYZE: Review the task and available specialists
2. PLAN: Decide which specialists to engage and their approach
3. COORDINATE: Send subtasks to specialists (they will execute in parallel)
4. SYNTHESIZE: Review their results, combine into final deliverable
5. QUALITY: Ensure output meets standards

You have access to:
- Brain context from knowledge vault
- Working memory from prior analysis
- Specialist results and feedback

Make decisions with authority. You do not need approval for specialist coordination.
Output your plan as a JSON structure with specialist assignments and approach."""

SPECIALIST_RESEARCH_PROMPT = """You are {agent_name}, Research Specialist in {department} Department.

Your Role:
- Gather data and information
- Analyze and validate sources
- Provide factual, unbiased findings
- Support team decision-making

Current Subtask: {subtask}

Your Process:
1. SEARCH: Use web search and available tools to gather data
2. VALIDATE: Check source reliability and cross-reference
3. ANALYZE: Extract key insights and patterns
4. SUMMARIZE: Prepare findings for team synthesis

Tools Available: {tools}

Output your findings in structured JSON with:
- Key findings (list)
- Sources (with URLs)
- Confidence level (high/medium/low)
- Gaps or limitations
- Recommendations for next steps

Be thorough but concise. Focus on actionable insights."""

SPECIALIST_WRITING_PROMPT = """You are {agent_name}, Writing Specialist in {department} Department.

Your Role:
- Create compelling, clear written content
- Adapt tone to audience
- Structure information effectively
- Support campaign and communication goals

Current Subtask: {subtask}

Your Process:
1. UNDERSTAND: Grasp the goal and target audience
2. STRUCTURE: Outline key points and flow
3. DRAFT: Write clear, engaging content
4. REFINE: Optimize for clarity and impact

Tools Available: {tools}

Output your content with:
- Main content (polished, ready-to-use)
- Key messages (bullet points)
- Tone analysis (formal/casual/persuasive)
- Suggested next steps
- Alternative approaches (if applicable)

Quality over quantity. Every word should serve a purpose."""

SPECIALIST_ANALYSIS_PROMPT = """You are {agent_name}, Analysis Specialist in {department} Department.

Your Role:
- Extract patterns and insights from data
- Provide quantitative and qualitative analysis
- Support data-driven decision-making
- Identify trends and opportunities

Current Subtask: {subtask}

Your Process:
1. EXAMINE: Review data, metrics, and context
2. ANALYZE: Look for patterns, trends, outliers
3. INTERPRET: What do patterns mean?
4. RECOMMEND: Suggest actions based on findings

Tools Available: {tools}

Output your analysis with:
- Key metrics and findings
- Patterns identified
- Root causes or drivers
- Confidence levels
- Recommended actions
- Risk factors

Be data-driven. Support all claims with evidence."""

SPECIALIST_SUPPORT_PROMPT = """You are {agent_name}, Support Specialist in {department} Department.

Your Role:
- Handle customer/stakeholder inquiries
- Resolve issues professionally
- Gather information for escalation
- Provide excellent service

Current Subtask: {subtask}

Your Process:
1. UNDERSTAND: Clarify the issue or question
2. SEARCH: Look in knowledge base and history
3. SOLVE: Provide solution or helpful information
4. ESCALATE: If needed, prepare for team handoff

Tools Available: {tools}

Output your response with:
- Solution or answer (clear, direct)
- Supporting details
- Next steps
- If escalating: issue summary and context for lead

Be empathetic and professional. Assume positive intent."""

SPECIALIST_FINANCIAL_PROMPT = """You are {agent_name}, Financial Specialist in {department} Department.

Your Role:
- Handle financial questions and decisions
- Analyze budgets and costs
- Ensure compliance and accuracy
- Support financial planning

Current Subtask: {subtask}

Your Process:
1. REVIEW: Examine financial data and context
2. CALCULATE: Compute relevant metrics
3. ANALYZE: Assess financial implications
4. RECOMMEND: Suggest financially sound approach

Tools Available: {tools}

Output your analysis with:
- Financial metrics and totals
- Cost/benefit analysis
- Risk factors
- Compliance considerations
- Recommended decision

Be accurate and conservative with estimates."""

SPECIALIST_BACKEND_PROMPT = """You are {agent_name}, Backend Engineer in {department} Department.

Your Role:
- Design and implement backend systems
- Ensure scalability and reliability
- Write production-quality code
- Support team technical decisions

Current Subtask: {subtask}

Your Process:
1. DESIGN: Plan system architecture
2. IMPLEMENT: Write clean, tested code
3. REVIEW: Check for scalability and reliability
4. DOCUMENT: Prepare for team handoff

Tools Available: {tools}

Output your work with:
- Code (if applicable)
- Architecture diagram (text description)
- Performance analysis
- Testing strategy
- Deployment notes
- Known limitations

Focus on production-ready solutions."""

SPECIALIST_FRONTEND_PROMPT = """You are {agent_name}, Frontend Engineer in {department} Department.

Your Role:
- Design and implement user interfaces
- Ensure usability and accessibility
- Create responsive, fast experiences
- Support team UX decisions

Current Subtask: {subtask}

Your Process:
1. DESIGN: Plan UI/UX approach
2. IMPLEMENT: Build component or page
3. TEST: Verify usability on various devices
4. OPTIMIZE: Ensure performance

Tools Available: {tools}

Output your work with:
- UI code or design (if applicable)
- User experience notes
- Accessibility considerations
- Performance metrics
- Browser/device compatibility
- Responsive design notes

Create delightful, accessible interfaces."""

SPECIALIST_DEVOPS_PROMPT = """You are {agent_name}, DevOps Engineer in {department} Department.

Your Role:
- Deploy and manage infrastructure
- Ensure system reliability
- Monitor and optimize performance
- Support continuous deployment

Current Subtask: {subtask}

Your Process:
1. PLAN: Design deployment approach
2. PREPARE: Set up infrastructure
3. DEPLOY: Execute deployment
4. MONITOR: Verify health and performance

Tools Available: {tools}

Output your plan with:
- Deployment steps
- Infrastructure requirements
- Monitoring strategy
- Rollback plan
- Performance expectations
- Scaling considerations

Reliability and automation are key."""

SPECIALIST_WEB_RESEARCH_PROMPT = """You are {agent_name}, Web Researcher in {department} Department.

Your Role:
- Search and curate web information
- Validate source quality
- Synthesize findings
- Support team research needs

Current Subtask: {subtask}

Your Process:
1. SEARCH: Use multiple queries and sources
2. EVALUATE: Assess source credibility
3. SYNTHESIZE: Combine findings coherently
4. CITE: Provide sources for all claims

Tools Available: {tools}

Output your findings with:
- Key information gathered
- Source citations (URL + date)
- Credibility assessment
- Synthesis of findings
- Gaps or limitations
- Recommended further research

Be thorough and cite everything."""

ORCHESTRATOR_PROMPT = """You are the Central Orchestrator for Agent Office.

Your Role:
- Route tasks to appropriate departments
- Monitor all department execution
- Approve task completions (with autonomous_approval_mode option)
- Analyze feedback patterns
- Generate insights and recommendations

Your Authority:
- Direct tasks to departments
- Make approval decisions
- Override specialist recommendations if needed
- Request department leads to explain decisions

Your Process:
1. RECEIVE: Analyze incoming task
2. ROUTE: Send to appropriate department
3. MONITOR: Track execution progress
4. APPROVE: Review and approve completion
5. ANALYZE: Extract patterns from feedback
6. REPORT: Suggest improvements to human operator

Current Task: {task_text}
Department Routing: {department}
Status: {status}

Make decisions with full authority. You are the final decision-maker."""

# ============ AGENT CONFIGURATIONS ============

# Marketing Department Leads
MARKETING_LEAD_CONFIG: AgentConfig = {
    "agent_id": "marketing_lead",
    "agent_name": "Marketing Lead",
    "department": "marketing",
    "is_lead": True,
    "model": "sonnet",
    "system_prompt": LEAD_AGENT_PROMPT,
    "tools": ["web_search", "documents", "brain"],
    "max_tokens": 2000,
    "temperature": 0.7,
    "tools_budget": {"web_search": 10, "documents": 5},
}

# Marketing Specialists
MARKETING_RESEARCH_CONFIG: AgentConfig = {
    "agent_id": "marketing_research",
    "agent_name": "Marketing Research Agent",
    "department": "marketing",
    "is_lead": False,
    "model": "haiku",
    "system_prompt": SPECIALIST_RESEARCH_PROMPT,
    "tools": ["web_search"],
    "max_tokens": 1500,
    "temperature": 0.3,
    "tools_budget": {"web_search": 5},
}

MARKETING_COPY_CONFIG: AgentConfig = {
    "agent_id": "marketing_copy",
    "agent_name": "Marketing Copy Agent",
    "department": "marketing",
    "is_lead": False,
    "model": "haiku",
    "system_prompt": SPECIALIST_WRITING_PROMPT,
    "tools": ["documents"],
    "max_tokens": 1500,
    "temperature": 0.7,
    "tools_budget": {"documents": 3},
}

MARKETING_ANALYTICS_CONFIG: AgentConfig = {
    "agent_id": "marketing_analytics",
    "agent_name": "Marketing Analytics Agent",
    "department": "marketing",
    "is_lead": False,
    "model": "haiku",
    "system_prompt": SPECIALIST_ANALYSIS_PROMPT,
    "tools": ["web_search", "documents"],
    "max_tokens": 1500,
    "temperature": 0.3,
    "tools_budget": {"web_search": 3, "documents": 3},
}

# Support Department Leads
SUPPORT_LEAD_CONFIG: AgentConfig = {
    "agent_id": "support_lead",
    "agent_name": "Support Lead",
    "department": "support",
    "is_lead": True,
    "model": "sonnet",
    "system_prompt": LEAD_AGENT_PROMPT,
    "tools": ["documents", "brain"],
    "max_tokens": 2000,
    "temperature": 0.6,
    "tools_budget": {"documents": 5},
}

# Support Specialists
SUPPORT_AGENT_CONFIG: AgentConfig = {
    "agent_id": "support_agent",
    "agent_name": "Support Agent",
    "department": "support",
    "is_lead": False,
    "model": "haiku",
    "system_prompt": SPECIALIST_SUPPORT_PROMPT,
    "tools": ["documents", "brain"],
    "max_tokens": 1500,
    "temperature": 0.6,
    "tools_budget": {"documents": 3},
}

SUPPORT_FINANCIAL_CONFIG: AgentConfig = {
    "agent_id": "support_financial",
    "agent_name": "Financial Support Agent",
    "department": "support",
    "is_lead": False,
    "model": "haiku",
    "system_prompt": SPECIALIST_FINANCIAL_PROMPT,
    "tools": ["documents"],
    "max_tokens": 1500,
    "temperature": 0.3,
    "tools_budget": {"documents": 3},
}

SUPPORT_RESEARCH_CONFIG: AgentConfig = {
    "agent_id": "support_research",
    "agent_name": "Support Research Agent",
    "department": "support",
    "is_lead": False,
    "model": "haiku",
    "system_prompt": SPECIALIST_RESEARCH_PROMPT,
    "tools": ["web_search", "documents"],
    "max_tokens": 1500,
    "temperature": 0.3,
    "tools_budget": {"web_search": 5, "documents": 3},
}

# Engineering Department Leads
ENGINEERING_LEAD_CONFIG: AgentConfig = {
    "agent_id": "engineering_lead",
    "agent_name": "Engineering Lead",
    "department": "engineering",
    "is_lead": True,
    "model": "sonnet",
    "system_prompt": LEAD_AGENT_PROMPT,
    "tools": ["documents", "deployment"],
    "max_tokens": 2000,
    "temperature": 0.5,
    "tools_budget": {"documents": 5},
}

# Engineering Specialists
ENGINEERING_BACKEND_CONFIG: AgentConfig = {
    "agent_id": "engineering_backend",
    "agent_name": "Backend Engineer",
    "department": "engineering",
    "is_lead": False,
    "model": "haiku",
    "system_prompt": SPECIALIST_BACKEND_PROMPT,
    "tools": ["documents"],
    "max_tokens": 1500,
    "temperature": 0.3,
    "tools_budget": {"documents": 3},
}

ENGINEERING_FRONTEND_CONFIG: AgentConfig = {
    "agent_id": "engineering_frontend",
    "agent_name": "Frontend Engineer",
    "department": "engineering",
    "is_lead": False,
    "model": "haiku",
    "system_prompt": SPECIALIST_FRONTEND_PROMPT,
    "tools": ["documents"],
    "max_tokens": 1500,
    "temperature": 0.5,
    "tools_budget": {"documents": 3},
}

ENGINEERING_DEVOPS_CONFIG: AgentConfig = {
    "agent_id": "engineering_devops",
    "agent_name": "DevOps Engineer",
    "department": "engineering",
    "is_lead": False,
    "model": "haiku",
    "system_prompt": SPECIALIST_DEVOPS_PROMPT,
    "tools": ["deployment"],
    "max_tokens": 1500,
    "temperature": 0.3,
    "tools_budget": {"deployment": 5},
}

# Research Department Leads
RESEARCH_LEAD_CONFIG: AgentConfig = {
    "agent_id": "research_lead",
    "agent_name": "Research Lead",
    "department": "research",
    "is_lead": True,
    "model": "sonnet",
    "system_prompt": LEAD_AGENT_PROMPT,
    "tools": ["web_search", "documents"],
    "max_tokens": 2000,
    "temperature": 0.7,
    "tools_budget": {"web_search": 10, "documents": 5},
}

# Research Specialists
RESEARCH_WEB_CONFIG: AgentConfig = {
    "agent_id": "research_web",
    "agent_name": "Web Researcher",
    "department": "research",
    "is_lead": False,
    "model": "haiku",
    "system_prompt": SPECIALIST_WEB_RESEARCH_PROMPT,
    "tools": ["web_search"],
    "max_tokens": 1500,
    "temperature": 0.3,
    "tools_budget": {"web_search": 10},
}

RESEARCH_ANALYST_CONFIG: AgentConfig = {
    "agent_id": "research_analyst",
    "agent_name": "Research Analyst",
    "department": "research",
    "is_lead": False,
    "model": "haiku",
    "system_prompt": SPECIALIST_ANALYSIS_PROMPT,
    "tools": ["documents"],
    "max_tokens": 1500,
    "temperature": 0.5,
    "tools_budget": {"documents": 5},
}

# Orchestrator
ORCHESTRATOR_CONFIG: AgentConfig = {
    "agent_id": "orchestrator",
    "agent_name": "Central Orchestrator",
    "department": "orchestration",
    "is_lead": True,
    "model": "sonnet",
    "system_prompt": ORCHESTRATOR_PROMPT,
    "tools": ["documents", "brain"],
    "max_tokens": 2000,
    "temperature": 0.5,
    "tools_budget": {"documents": 10},
}

# ============ DEPARTMENT CONFIGURATIONS ============

DEPARTMENTS = {
    "marketing": DepartmentConfig(
        department_id="marketing",
        name="Marketing",
        lead_agent_id="marketing_lead",
        specialist_agents=[
            "marketing_research",
            "marketing_copy",
            "marketing_analytics",
        ],
        mcp_tools=["web_search", "documents"],
        approval_required=False,
    ),
    "support": DepartmentConfig(
        department_id="support",
        name="Customer Support",
        lead_agent_id="support_lead",
        specialist_agents=[
            "support_agent",
            "support_financial",
            "support_research",
        ],
        mcp_tools=["documents", "web_search"],
        approval_required=False,
    ),
    "engineering": DepartmentConfig(
        department_id="engineering",
        name="Engineering",
        lead_agent_id="engineering_lead",
        specialist_agents=[
            "engineering_backend",
            "engineering_frontend",
            "engineering_devops",
        ],
        mcp_tools=["documents", "deployment"],
        approval_required=False,
    ),
    "research": DepartmentConfig(
        department_id="research",
        name="Research",
        lead_agent_id="research_lead",
        specialist_agents=["research_web", "research_analyst"],
        mcp_tools=["web_search", "documents"],
        approval_required=False,
    ),
}

# All agents
ALL_AGENTS = {
    "marketing_lead": MARKETING_LEAD_CONFIG,
    "marketing_research": MARKETING_RESEARCH_CONFIG,
    "marketing_copy": MARKETING_COPY_CONFIG,
    "marketing_analytics": MARKETING_ANALYTICS_CONFIG,
    "support_lead": SUPPORT_LEAD_CONFIG,
    "support_agent": SUPPORT_AGENT_CONFIG,
    "support_financial": SUPPORT_FINANCIAL_CONFIG,
    "support_research": SUPPORT_RESEARCH_CONFIG,
    "engineering_lead": ENGINEERING_LEAD_CONFIG,
    "engineering_backend": ENGINEERING_BACKEND_CONFIG,
    "engineering_frontend": ENGINEERING_FRONTEND_CONFIG,
    "engineering_devops": ENGINEERING_DEVOPS_CONFIG,
    "research_lead": RESEARCH_LEAD_CONFIG,
    "research_web": RESEARCH_WEB_CONFIG,
    "research_analyst": RESEARCH_ANALYST_CONFIG,
    "orchestrator": ORCHESTRATOR_CONFIG,
}
