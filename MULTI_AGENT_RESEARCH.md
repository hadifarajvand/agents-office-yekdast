# Multi-Agent Orchestration: LangChain & LangGraph Patterns

**Status:** Research Complete  
**Date:** 2026-09-18  
**Target:** Phase 2 Implementation (Agent Office v3.6)  
**Reference:** AutoGPT, CrewAI, LangChain, MetaGPT, Claude Projects  

---

## Table of Contents

1. [LangChain Multi-Agent Patterns](#1-langchain-multi-agent-patterns)
2. [LangGraph Multi-Agent Examples](#2-langgraph-multi-agent-examples)
3. [Hierarchical Orchestration](#3-hierarchical-orchestration)
4. [Agent System Prompts](#4-agent-system-prompts)
5. [Sandboxing & Tool Isolation](#5-sandboxing--tool-isolation)
6. [State Checkpointing](#6-state-checkpointing)
7. [Error Handling & Retries](#7-error-handling--retries)
8. [Production Patterns](#8-production-patterns)

---

## 1. LangChain Multi-Agent Patterns

### 1.1 Overview

LangChain provides several patterns for multi-agent coordination:

1. **Tool Routing Pattern** - Single orchestrator routes to specialized tools/agents
2. **Sequential Agents** - Agents work one after another, passing results
3. **Parallel Agents** - Multiple agents execute simultaneously
4. **Hierarchical Pattern** - Lead agent → Specialist agents (what Agent Office uses)
5. **Message Protocol** - Agents communicate via structured message passing

### 1.2 LangChain Agent Architectures

#### Pattern A: Tool Routing with Orchestrator

```python
from langchain.agents import AgentType, initialize_agent
from langchain.chat_models import ChatAnthropic
from langchain.tools import Tool
from typing import List

class ToolRouter:
    """Routes tasks to appropriate agent based on content"""
    
    def __init__(self, agents: dict, orchestrator_model: str = "claude-sonnet-4"):
        self.agents = agents  # {"research": agent, "writing": agent, ...}
        self.orchestrator = ChatAnthropic(model_name=orchestrator_model)
    
    def route_task(self, task_text: str) -> tuple[str, str]:
        """
        Route task to appropriate agent
        Returns: (agent_key, routing_reason)
        """
        routing_prompt = f"""
        Which agent should handle this task? Choose one:
        - research: for web search, data gathering, analysis
        - writing: for content creation, copywriting
        - code: for programming tasks
        - planning: for strategy and planning
        
        Task: {task_text}
        
        Respond with ONLY the agent name.
        """
        
        response = self.orchestrator.invoke(routing_prompt)
        agent_key = response.content.strip().lower()
        
        return agent_key if agent_key in self.agents else "research"

# Example usage
agents = {
    "research": create_research_agent(),
    "writing": create_writing_agent(),
    "code": create_code_agent(),
}

router = ToolRouter(agents)
task = "Find information about AI trends and write a summary"
agent_key, reason = router.route_task(task)
result = agents[agent_key].invoke(task)
```

#### Pattern B: Sequential Agent Chain

```python
from langchain.schema import HumanMessage, AIMessage
from typing import List, Dict

class AgentChain:
    """Sequential execution: each agent receives previous output"""
    
    def __init__(self, agents: List[dict], orchestrator_model: str):
        self.agents = agents  # [{"name": "research", "agent": agent_obj}, ...]
        self.orchestrator = ChatAnthropic(model_name=orchestrator_model)
    
    def execute(self, task: str, context: dict = None) -> Dict:
        """
        Execute agents sequentially
        Each agent sees previous results
        """
        context = context or {}
        messages = [{"role": "user", "content": task}]
        results = []
        
        for agent_config in self.agents:
            name = agent_config["name"]
            agent = agent_config["agent"]
            
            # Build input for this agent
            input_text = f"{task}\n\nPrevious results:\n"
            for prev in results:
                input_text += f"- {prev['agent']}: {prev['output'][:200]}...\n"
            
            # Execute agent
            try:
                output = agent.invoke(input_text)
                results.append({
                    "agent": name,
                    "output": output.content if hasattr(output, 'content') else output,
                    "status": "success"
                })
            except Exception as e:
                results.append({
                    "agent": name,
                    "error": str(e),
                    "status": "failed"
                })
                # Decide: continue or halt?
                if agent_config.get("critical"):
                    break
        
        return {
            "task": task,
            "steps": results,
            "final_output": results[-1]["output"] if results else None
        }

# Example
chain = AgentChain([
    {"name": "research", "agent": research_agent, "critical": True},
    {"name": "writing", "agent": writing_agent, "critical": False},
    {"name": "review", "agent": review_agent, "critical": False},
])

result = chain.execute("Write a blog post about LangChain")
```

#### Pattern C: Parallel Agent Execution

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any

class ParallelAgentExecutor:
    """Execute multiple agents in parallel, combine results"""
    
    def __init__(self, agents: List[dict], max_workers: int = 4):
        self.agents = agents
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    async def execute_parallel(self, task: str, context: dict = None) -> Dict:
        """
        Execute all agents in parallel
        Combine results via orchestrator
        """
        context = context or {}
        
        # Launch all agents
        futures = []
        for agent_config in self.agents:
            future = asyncio.to_thread(
                self._run_agent,
                agent_config,
                task,
                context
            )
            futures.append(future)
        
        # Wait for all to complete
        results = await asyncio.gather(*futures, return_exceptions=True)
        
        # Combine results
        combined = self._combine_results(results, task)
        return combined
    
    def _run_agent(self, agent_config: dict, task: str, context: dict) -> Dict:
        """Execute single agent"""
        name = agent_config["name"]
        agent = agent_config["agent"]
        
        try:
            # Add context to task
            input_text = f"{task}\n\nContext: {context}"
            output = agent.invoke(input_text)
            
            return {
                "agent": name,
                "output": output.content if hasattr(output, 'content') else output,
                "status": "success",
                "tokens_used": getattr(output, 'usage', {}).get('total_tokens', 0)
            }
        except Exception as e:
            return {
                "agent": name,
                "error": str(e),
                "status": "failed"
            }
    
    def _combine_results(self, results: List[Dict], task: str) -> Dict:
        """Orchestrate combining of parallel results"""
        
        orchestrator = ChatAnthropic(model_name="claude-sonnet-4")
        
        # Format results for orchestrator
        results_text = "\n".join([
            f"- {r['agent']}: {r.get('output', r.get('error'))}"
            for r in results if r
        ])
        
        synthesis_prompt = f"""
        The following agents worked in parallel on this task:
        
        Task: {task}
        
        Results:
        {results_text}
        
        Synthesize these results into a coherent final answer.
        Highlight key insights and any conflicts between agents.
        """
        
        final = orchestrator.invoke(synthesis_prompt)
        
        return {
            "task": task,
            "parallel_results": results,
            "synthesis": final.content,
            "total_tokens": sum(r.get('tokens_used', 0) for r in results)
        }

# Async usage
async def main():
    executor = ParallelAgentExecutor([
        {"name": "research", "agent": research_agent},
        {"name": "financial", "agent": financial_agent},
        {"name": "technical", "agent": technical_agent},
    ])
    
    result = await executor.execute_parallel(
        "Evaluate this startup idea"
    )
    print(result["synthesis"])

# asyncio.run(main())
```

### 1.3 LangChain Tool Management

```python
from langchain.tools import Tool, tool
from langchain.agents import AgentType, initialize_agent
from langchain.chat_models import ChatAnthropic
from typing import Callable, List, Dict

class ToolRegistry:
    """Centralized tool registration and permission management"""
    
    def __init__(self):
        self.tools_by_agent = {}
        self.tools_by_dept = {}
        self.global_tools = {}
    
    @tool
    def web_search(query: str) -> str:
        """Search the web for information"""
        # Implementation: call SerpAPI, Bing, etc.
        return f"Results for: {query}"
    
    @tool
    def file_read(path: str) -> str:
        """Read file contents"""
        try:
            with open(path, 'r') as f:
                return f.read()
        except Exception as e:
            return f"Error: {e}"
    
    @tool
    def file_write(path: str, content: str) -> str:
        """Write content to file"""
        try:
            with open(path, 'w') as f:
                f.write(content)
            return "Success"
        except Exception as e:
            return f"Error: {e}"
    
    def register_agent_tools(self, agent_id: str, tool_list: List[str]):
        """Assign tools to specific agent"""
        self.tools_by_agent[agent_id] = tool_list
    
    def register_dept_tools(self, dept: str, tool_list: List[str]):
        """Assign tools to entire department"""
        self.tools_by_dept[dept] = tool_list
    
    def get_tools_for_agent(self, agent_id: str, dept: str) -> List[Tool]:
        """Get tools accessible by agent (agent-specific + department-wide)"""
        
        # Combine agent-specific and department-wide tools
        allowed_tool_names = set()
        
        if agent_id in self.tools_by_agent:
            allowed_tool_names.update(self.tools_by_agent[agent_id])
        
        if dept in self.tools_by_dept:
            allowed_tool_names.update(self.tools_by_dept[dept])
        
        # Map names to Tool objects
        all_tools_map = {
            "web_search": self.web_search,
            "file_read": self.file_read,
            "file_write": self.file_write,
            # ... more tools
        }
        
        return [all_tools_map[name] for name in allowed_tool_names 
                if name in all_tools_map]

# Usage
registry = ToolRegistry()

# Marketing department can use web_search and file_read
registry.register_dept_tools("marketing", ["web_search", "file_read"])

# Research agent specifically needs file_write (for saving findings)
registry.register_agent_tools("research_agent_1", ["file_write"])

# Get tools for specific agent
tools = registry.get_tools_for_agent("research_agent_1", "marketing")
# Returns: [web_search, file_read, file_write]
```

---

## 2. LangGraph Multi-Agent Examples

### 2.1 Core Concepts

**LangGraph** is a framework for building multi-agent systems with:
- **StateGraph**: Directed acyclic graph of nodes (agents/functions)
- **State**: Shared data structure passed between nodes
- **Conditional Edges**: Route based on state conditions
- **Checkpointing**: Save state to DB for recovery

### 2.2 Basic Multi-Agent Graph

```python
from langgraph.graph import StateGraph
from langchain_anthropic import ChatAnthropic
from typing import TypedDict, Literal, Annotated, Sequence
import anthropic

# Define the state that flows through the graph
class OfficeState(TypedDict):
    """Shared state for all agents in the office"""
    
    # Task definition
    task_id: str
    task_text: str
    department: str
    
    # Routing
    assigned_lead: str
    assigned_agents: list[str]
    
    # Execution
    status: Literal["pending", "assigned", "working", "completed", "failed"]
    messages: list[dict]  # Conversation history
    working_memory: dict  # Intermediate results
    
    # Context
    brain_context: list[dict]  # Relevant notes from brain
    
    # Results
    deliverable: str
    errors: list[str]

# Initialize LLM
client = ChatAnthropic(model="claude-sonnet-4")

# Define nodes (each can be an agent)
class OfficeGraph:
    """Main orchestration graph for Agent Office"""
    
    def __init__(self, roster: dict, brain: dict):
        self.roster = roster
        self.brain = brain
        self.graph = self._build_graph()
    
    def _build_graph(self):
        """Build StateGraph with all nodes"""
        
        builder = StateGraph(OfficeState)
        
        # Add nodes
        builder.add_node("router", self.router_node)
        builder.add_node("brain_context", self.brain_context_node)
        builder.add_node("lead_planning", self.lead_planning_node)
        builder.add_node("specialist_research", self.specialist_research_node)
        builder.add_node("specialist_writing", self.specialist_writing_node)
        builder.add_node("specialist_analysis", self.specialist_analysis_node)
        builder.add_node("synthesis", self.synthesis_node)
        builder.add_node("brain_update", self.brain_update_node)
        builder.add_node("complete", self.complete_node)
        builder.add_node("escalate", self.escalate_node)
        
        # Define edges
        builder.add_edge("START", "router")
        builder.add_conditional_edges(
            "router",
            self.route_by_department,
            {
                "marketing": "brain_context",
                "support": "brain_context",
                "engineering": "brain_context",
                "research": "brain_context",
            }
        )
        builder.add_edge("brain_context", "lead_planning")
        
        # Parallel specialists
        builder.add_edge("lead_planning", "specialist_research")
        builder.add_edge("lead_planning", "specialist_writing")
        builder.add_edge("lead_planning", "specialist_analysis")
        
        # Join parallel results
        builder.add_edge("specialist_research", "synthesis")
        builder.add_edge("specialist_writing", "synthesis")
        builder.add_edge("specialist_analysis", "synthesis")
        
        # Finish
        builder.add_edge("synthesis", "brain_update")
        builder.add_edge("brain_update", "complete")
        
        # Error handling
        builder.add_edge("complete", "END")
        builder.add_edge("escalate", "END")
        
        return builder.compile()
    
    # ===== NODE IMPLEMENTATIONS =====
    
    def router_node(self, state: OfficeState) -> OfficeState:
        """
        Router: Classify task and route to department
        """
        
        router_prompt = f"""
        Classify this task into one of these departments:
        - marketing: campaigns, content, research
        - support: customer issues, billing
        - engineering: code, infrastructure
        - research: analysis, data gathering
        
        Task: {state['task_text']}
        
        Respond with ONLY the department name.
        """
        
        response = client.invoke(router_prompt)
        dept = response.content.strip().lower()
        
        # Validate
        valid_depts = ["marketing", "support", "engineering", "research"]
        if dept not in valid_depts:
            dept = "research"  # fallback
        
        state["department"] = dept
        state["status"] = "assigned"
        
        return state
    
    def brain_context_node(self, state: OfficeState) -> OfficeState:
        """
        Brain Context: Retrieve relevant notes from brain
        """
        
        # Search brain for relevant notes
        query = state["task_text"]
        relevant_notes = self.brain.search(query, limit=5)
        
        state["brain_context"] = relevant_notes
        state["messages"].append({
            "role": "system",
            "content": f"Retrieved {len(relevant_notes)} relevant brain notes"
        })
        
        return state
    
    def lead_planning_node(self, state: OfficeState) -> OfficeState:
        """
        Lead Agent: Plan approach and assign specialists
        """
        
        dept = state["department"]
        lead_id = self.roster.get_lead_for_dept(dept)
        
        planning_prompt = f"""
        You are the {dept} department lead.
        
        Task: {state['task_text']}
        
        Available context:
        {self._format_context(state['brain_context'])}
        
        Plan your approach:
        1. What's the core objective?
        2. What information do you need?
        3. Which specialists should work on this? (research, writing, analysis)
        4. What's your success criteria?
        
        Be concise.
        """
        
        response = client.invoke(planning_prompt)
        plan = response.content
        
        state["assigned_lead"] = lead_id
        state["status"] = "working"
        state["messages"].append({
            "role": "lead",
            "content": plan
        })
        
        # Auto-assign all specialists in department
        specialists = self.roster.get_specialists_for_dept(dept)
        state["assigned_agents"] = [s["id"] for s in specialists]
        
        return state
    
    def specialist_research_node(self, state: OfficeState) -> OfficeState:
        """Research specialist: gather information"""
        
        if state["status"] != "working":
            return state
        
        research_prompt = f"""
        You are a research specialist.
        
        Task: {state['task_text']}
        Lead's plan: {state['messages'][-1]['content']}
        
        Your job: Find relevant information and data.
        Focus on facts, trends, and evidence.
        
        Search for: market trends, competitor moves, data, research papers
        """
        
        response = client.invoke(research_prompt)
        
        state["working_memory"]["research"] = response.content
        state["messages"].append({
            "role": "research",
            "content": response.content
        })
        
        return state
    
    def specialist_writing_node(self, state: OfficeState) -> OfficeState:
        """Writing specialist: create content"""
        
        if state["status"] != "working":
            return state
        
        writing_prompt = f"""
        You are a writing specialist.
        
        Task: {state['task_text']}
        Research findings: {state['working_memory'].get('research', 'None yet')}
        
        Your job: Create compelling, clear content based on the task.
        Focus on: clarity, persuasion, accuracy.
        """
        
        response = client.invoke(writing_prompt)
        
        state["working_memory"]["writing"] = response.content
        state["messages"].append({
            "role": "writing",
            "content": response.content
        })
        
        return state
    
    def specialist_analysis_node(self, state: OfficeState) -> OfficeState:
        """Analysis specialist: metrics and insights"""
        
        if state["status"] != "working":
            return state
        
        analysis_prompt = f"""
        You are an analysis specialist.
        
        Task: {state['task_text']}
        
        Your job: Analyze the situation and provide metrics/insights.
        Focus on: numbers, trends, ROI, risks, opportunities.
        """
        
        response = client.invoke(analysis_prompt)
        
        state["working_memory"]["analysis"] = response.content
        state["messages"].append({
            "role": "analysis",
            "content": response.content
        })
        
        return state
    
    def synthesis_node(self, state: OfficeState) -> OfficeState:
        """Lead synthesizes specialist outputs into final deliverable"""
        
        synthesis_prompt = f"""
        You are the lead synthesizing results.
        
        Task: {state['task_text']}
        
        Specialist outputs:
        - Research: {state['working_memory'].get('research', 'N/A')}
        - Writing: {state['working_memory'].get('writing', 'N/A')}
        - Analysis: {state['working_memory'].get('analysis', 'N/A')}
        
        Synthesize into a cohesive final deliverable.
        Make decisions on conflicting viewpoints.
        Ensure quality and completeness.
        """
        
        response = client.invoke(synthesis_prompt)
        
        state["deliverable"] = response.content
        state["messages"].append({
            "role": "lead",
            "content": f"Final: {response.content[:200]}..."
        })
        
        return state
    
    def brain_update_node(self, state: OfficeState) -> OfficeState:
        """Save learnings to brain"""
        
        # Create brain note from deliverable
        note = {
            "type": "task_result",
            "title": state["task_text"][:50],
            "department": state["department"],
            "task_id": state["task_id"],
            "deliverable": state["deliverable"],
            "created_at": datetime.now().isoformat(),
            "source": "system",
        }
        
        self.brain.save_note(note)
        
        state["messages"].append({
            "role": "system",
            "content": f"Saved learning to brain"
        })
        
        return state
    
    def complete_node(self, state: OfficeState) -> OfficeState:
        """Mark task complete"""
        state["status"] = "completed"
        return state
    
    def escalate_node(self, state: OfficeState) -> OfficeState:
        """Handle errors by escalating"""
        state["status"] = "failed"
        return state
    
    def route_by_department(self, state: OfficeState) -> str:
        """Conditional routing function"""
        return state.get("department", "research")
    
    def _format_context(self, notes: list) -> str:
        """Format brain notes for prompt"""
        if not notes:
            return "No relevant context found"
        return "\n".join([f"- {n.get('title', 'Untitled')}: {n.get('content', '')[:100]}..." 
                         for n in notes[:3]])
    
    def execute(self, task_text: str, task_id: str) -> OfficeState:
        """Execute graph for a task"""
        
        initial_state = OfficeState(
            task_id=task_id,
            task_text=task_text,
            department="",
            assigned_lead="",
            assigned_agents=[],
            status="pending",
            messages=[],
            working_memory={},
            brain_context=[],
            deliverable="",
            errors=[]
        )
        
        return self.graph.invoke(initial_state)
```

### 2.3 LangGraph with Tool Calling

```python
from langgraph.graph import StateGraph
from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
import json

class AgentWithTools:
    """Agent that uses tools in LangGraph"""
    
    def __init__(self, model_name="claude-sonnet-4", available_tools: list = None):
        self.model = ChatAnthropic(model=model_name)
        self.tools = available_tools or []
        
        # Bind tools to model
        if self.tools:
            self.model = self.model.bind_tools(self.tools)
    
    @staticmethod
    def web_search(query: str) -> str:
        """Search the web"""
        return f"Results for '{query}': [mocked search results]"
    
    @staticmethod
    def file_read(path: str) -> str:
        """Read a file"""
        try:
            with open(path) as f:
                return f.read()
        except:
            return f"File not found: {path}"
    
    @staticmethod
    def send_email(to: str, subject: str, body: str) -> str:
        """Send email (restricted - only for approved agents)"""
        return f"Email would be sent to {to}: {subject}"
    
    def process_tool_calls(self, tool_calls: list) -> list:
        """
        Process tool calls from model
        This is where we can enforce permissions
        """
        results = []
        
        for call in tool_calls:
            tool_name = call.get("name")
            tool_input = call.get("input", {})
            
            # Permission check
            if not self._check_permission(tool_name):
                results.append({
                    "tool": tool_name,
                    "error": "Permission denied"
                })
                continue
            
            # Execute tool
            try:
                if tool_name == "web_search":
                    result = self.web_search(tool_input.get("query"))
                elif tool_name == "file_read":
                    result = self.file_read(tool_input.get("path"))
                elif tool_name == "send_email":
                    result = self.send_email(
                        tool_input.get("to"),
                        tool_input.get("subject"),
                        tool_input.get("body")
                    )
                else:
                    result = f"Unknown tool: {tool_name}"
                
                results.append({
                    "tool": tool_name,
                    "result": result,
                    "status": "success"
                })
            except Exception as e:
                results.append({
                    "tool": tool_name,
                    "error": str(e),
                    "status": "failed"
                })
        
        return results
    
    def _check_permission(self, tool_name: str) -> bool:
        """Check if agent has permission to use tool"""
        # This would be populated from config
        allowed_tools = {t.__name__ for t in self.tools}
        return tool_name in allowed_tools

# Define tools
tools = [
    tool(AgentWithTools.web_search),
    tool(AgentWithTools.file_read),
    # Note: send_email would NOT be in list by default
]

# Create agent
agent = AgentWithTools(available_tools=tools)

# Use in agent loop
def agent_loop(query: str, agent: AgentWithTools, max_iterations: int = 5):
    """Agentic loop: think, act, observe"""
    
    messages = [{"role": "user", "content": query}]
    
    for i in range(max_iterations):
        # Get response from model
        response = agent.model.invoke(messages)
        
        # If no tool calls, we're done
        if not hasattr(response, 'tool_calls') or not response.tool_calls:
            return response.content
        
        # Process tool calls
        tool_results = agent.process_tool_calls(response.tool_calls)
        
        # Add to message history
        messages.append({"role": "assistant", "content": response.content})
        messages.append({
            "role": "user",
            "content": json.dumps(tool_results)
        })
    
    return "Max iterations reached"
```

---

## 3. Hierarchical Orchestration

### 3.1 Lead Agent Pattern

This is the pattern Agent Office uses: Lead → Specialists

```python
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
from langchain_anthropic import ChatAnthropic

class AgentRole(Enum):
    LEAD = "lead"
    SPECIALIST = "specialist"
    SUPPORT = "support"

@dataclass
class Agent:
    """Represents an individual agent"""
    id: str
    name: str
    role: AgentRole
    model_size: str  # "haiku", "sonnet", "opus"
    department: str
    tools: list
    system_prompt: str
    autonomy_level: str  # "autonomous", "in_form", "approve_first"

class HierarchicalDepartment:
    """
    Hierarchical orchestration for a single department
    Lead coordinates specialists
    """
    
    def __init__(self, dept_name: str, lead: Agent, specialists: List[Agent]):
        self.dept_name = dept_name
        self.lead = lead
        self.specialists = specialists
        
        self.lead_model = ChatAnthropic(model=self._get_model_name(lead.model_size))
        self.specialist_models = {
            s.id: ChatAnthropic(model=self._get_model_name(s.model_size))
            for s in specialists
        }
    
    def _get_model_name(self, size: str) -> str:
        """Map size to Claude model"""
        return {
            "haiku": "claude-haiku-4-5-20251001",
            "sonnet": "claude-sonnet-4",
            "opus": "claude-opus-4",
        }.get(size, "claude-sonnet-4")
    
    def execute(self, task: str, context: dict = None) -> dict:
        """
        Execute task through hierarchical model:
        1. Lead understands task and creates plan
        2. Lead assigns specialists based on plan
        3. Specialists execute in parallel
        4. Lead synthesizes results
        """
        
        context = context or {}
        
        # Step 1: Lead planning
        plan = self._lead_plan(task, context)
        
        # Step 2: Lead assignment (which specialists needed)
        assignments = self._lead_assign(plan)
        
        # Step 3: Parallel specialist execution
        results = self._execute_specialists(task, plan, assignments)
        
        # Step 4: Lead synthesis
        final = self._lead_synthesize(task, plan, results)
        
        return {
            "task": task,
            "plan": plan,
            "assignments": assignments,
            "specialist_results": results,
            "final_deliverable": final,
            "department": self.dept_name,
        }
    
    def _lead_plan(self, task: str, context: dict) -> str:
        """Lead creates execution plan"""
        
        prompt = f"""
        You are the {self.dept_name.title()} Department Lead.
        
        Task: {task}
        
        Context:
        {self._format_context(context)}
        
        Create an execution plan:
        1. What is the core objective?
        2. What information/work is needed?
        3. Which specialists will you assign? (research, writing, analysis, etc)
        4. What's your success criteria?
        5. Any potential risks?
        
        Keep plan concise but detailed enough for specialists to execute.
        """
        
        response = self.lead_model.invoke(prompt)
        return response.content
    
    def _lead_assign(self, plan: str) -> dict:
        """Lead decides which specialists to use"""
        
        # In production, this would parse the plan intelligently
        # For now, use all available specialists
        
        return {
            "plan_summary": plan[:200],
            "assigned_specialists": [s.id for s in self.specialists],
        }
    
    def _execute_specialists(self, task: str, plan: str, assignments: dict) -> dict:
        """Execute assigned specialists in parallel"""
        
        results = {}
        
        for specialist in self.specialists:
            if specialist.id not in assignments["assigned_specialists"]:
                continue
            
            # Build specialist-specific prompt
            specialist_prompt = f"""
            You are a {specialist.name} specialist in the {self.dept_name} department.
            
            Task: {task}
            
            Lead's Plan:
            {plan}
            
            Your specialty: {self._get_specialty_focus(specialist.id)}
            
            Contribute your expertise to this task.
            Be specific and actionable.
            """
            
            try:
                model = self.specialist_models[specialist.id]
                response = model.invoke(specialist_prompt)
                
                results[specialist.id] = {
                    "specialist": specialist.name,
                    "output": response.content,
                    "status": "success",
                }
            except Exception as e:
                results[specialist.id] = {
                    "specialist": specialist.name,
                    "error": str(e),
                    "status": "failed",
                }
        
        return results
    
    def _lead_synthesize(self, task: str, plan: str, results: dict) -> str:
        """Lead combines specialist outputs"""
        
        specialist_outputs = "\n".join([
            f"- {r['specialist']}: {r.get('output', r.get('error', ''))[:150]}..."
            for r in results.values()
        ])
        
        synthesis_prompt = f"""
        As the {self.dept_name} Lead, synthesize these results:
        
        Original Task: {task}
        Your Plan: {plan}
        
        Specialist Outputs:
        {specialist_outputs}
        
        Create a final, cohesive deliverable that:
        1. Directly answers the task
        2. Incorporates all specialist insights
        3. Resolves any conflicts
        4. Is immediately actionable
        """
        
        response = self.lead_model.invoke(synthesis_prompt)
        return response.content
    
    def _get_specialty_focus(self, specialist_id: str) -> str:
        """Get focus area for specialist"""
        
        focus_map = {
            "research": "Gather data, find information, identify trends",
            "writing": "Create clear, compelling content",
            "analysis": "Provide metrics, insights, ROI analysis",
            "backend": "Technical implementation, APIs",
            "frontend": "User experience, UI, design",
            "devops": "Infrastructure, deployment, monitoring",
        }
        
        # Extract specialty from specialist ID
        for key, desc in focus_map.items():
            if key in specialist_id.lower():
                return desc
        
        return "Contribute your expertise"
    
    def _format_context(self, context: dict) -> str:
        """Format context for prompts"""
        if not context:
            return "No additional context"
        
        lines = []
        for key, value in context.items():
            if isinstance(value, list):
                lines.append(f"- {key}: {', '.join(str(v)[:30] for v in value)}")
            else:
                lines.append(f"- {key}: {str(value)[:100]}")
        
        return "\n".join(lines)

# Setup and usage
lead = Agent(
    id="marketing_lead",
    name="Marketing Lead",
    role=AgentRole.LEAD,
    model_size="sonnet",
    department="marketing",
    tools=["web_search", "file_read"],
    system_prompt="You are a strategic marketing leader",
    autonomy_level="autonomous",
)

specialists = [
    Agent(
        id="marketing_research",
        name="Research Agent",
        role=AgentRole.SPECIALIST,
        model_size="haiku",
        department="marketing",
        tools=["web_search"],
        system_prompt="You are a research specialist",
        autonomy_level="autonomous",
    ),
    Agent(
        id="marketing_writing",
        name="Copy Agent",
        role=AgentRole.SPECIALIST,
        model_size="haiku",
        department="marketing",
        tools=["file_write"],
        system_prompt="You are a copywriting specialist",
        autonomy_level="autonomous",
    ),
    Agent(
        id="marketing_analysis",
        name="Analytics Agent",
        role=AgentRole.SPECIALIST,
        model_size="haiku",
        department="marketing",
        tools=[],  # No tools for analysis
        system_prompt="You are an analytics specialist",
        autonomy_level="autonomous",
    ),
]

marketing_dept = HierarchicalDepartment("marketing", lead, specialists)
result = marketing_dept.execute(
    "Create a Q3 marketing campaign brief",
    context={
        "last_campaign_performance": "67% engagement increase",
        "target_audience": "B2B SaaS",
    }
)

print(result["final_deliverable"])
```

---

## 4. Agent System Prompts

### 4.1 System Prompt Template

```python
"""
Production-grade system prompt templates for agents
Based on research from AutoGPT, CrewAI, Claude Projects
"""

SYSTEM_PROMPT_TEMPLATE = """
You are {agent_name}, a {role} in the {department} department.

## Your Role
{role_description}

## Your Responsibilities
- Primary: {primary_responsibility}
- Secondary: {secondary_responsibility}
- Support: {support_responsibility}

## Your Constraints
- DO: {do_constraint_1}, {do_constraint_2}, {do_constraint_3}
- DON'T: {dont_constraint_1}, {dont_constraint_2}, {dont_constraint_3}

## Your Tools
Available to you: {tools}
Never use tools outside this list.

## Decision-Making Style
- Approach: {decision_approach}
- Risk tolerance: {risk_tolerance}
- Escalation trigger: {escalation_trigger}

## Context & Memory
- You have access to these context sources: {context_sources}
- Remember: {memory_instructions}

## Quality Standards
- Accuracy: {accuracy_standard}
- Completeness: {completeness_standard}
- Timeliness: {timeliness_standard}

## Escalation Rules
If {escalation_condition}, escalate to {escalation_target}.

Be concise, accurate, and professional in all responses.
"""

class SystemPromptBuilder:
    """Build tailored system prompts for each agent"""
    
    def __init__(self):
        self.templates = {}
        self._register_templates()
    
    def _register_templates(self):
        """Register agent-specific templates"""
        
        # Marketing Research Agent
        self.templates["marketing_research"] = {
            "agent_name": "Research Agent",
            "role": "Research Specialist",
            "department": "Marketing",
            "role_description": "Gather market intelligence, analyze trends, identify opportunities",
            "primary_responsibility": "Find relevant market data and competitive insights",
            "secondary_responsibility": "Synthesize findings into actionable intelligence",
            "support_responsibility": "Support writing and analysis teams with research",
            "do_constraint_1": "Use authoritative sources (reports, academic papers, industry data)",
            "do_constraint_2": "Provide citations and source attribution",
            "do_constraint_3": "Flag any uncertainties or limitations in your findings",
            "dont_constraint_1": "Do not create marketing copy (that's the writing team's job)",
            "dont_constraint_2": "Do not make strategic decisions (that's the lead's job)",
            "dont_constraint_3": "Do not access internal financial data",
            "tools": "web_search, file_read, notion_read",
            "decision_approach": "Data-driven, evidence-based",
            "risk_tolerance": "Low - prioritize accuracy over speed",
            "escalation_trigger": "If you can't find data after 3 searches",
            "context_sources": "Brain notes on past campaigns, industry databases",
            "memory_instructions": "Reference previous research to avoid duplication",
            "accuracy_standard": "95%+ - cite sources",
            "completeness_standard": "Cover market, competition, trends, customer segments",
            "timeliness_standard": "Research within 30 minutes",
        }
        
        # Marketing Copy Agent
        self.templates["marketing_writing"] = {
            "agent_name": "Copy Agent",
            "role": "Copywriting Specialist",
            "department": "Marketing",
            "role_description": "Create persuasive, clear marketing content",
            "primary_responsibility": "Write marketing briefs, copy, and messaging",
            "secondary_responsibility": "Ensure brand voice consistency",
            "support_responsibility": "Support campaign execution with content",
            "do_constraint_1": "Use research provided by Research Agent",
            "do_constraint_2": "Follow brand guidelines strictly",
            "do_constraint_3": "Focus on customer benefits, not features",
            "dont_constraint_1": "Do not conduct your own research",
            "dont_constraint_2": "Do not approve campaigns (that's the lead's job)",
            "dont_constraint_3": "Do not deviate from brand voice",
            "tools": "file_write, file_read, notion_write",
            "decision_approach": "Creative but evidence-based",
            "risk_tolerance": "Medium - balance creativity with data",
            "escalation_trigger": "If you lack research to support claims",
            "context_sources": "Brand guidelines, past campaigns, target audience profiles",
            "memory_instructions": "Study successful past copy patterns",
            "accuracy_standard": "100% - no false claims",
            "completeness_standard": "Cover hook, problem, solution, CTA",
            "timeliness_standard": "First draft within 20 minutes",
        }
        
        # Engineering Backend Agent
        self.templates["engineering_backend"] = {
            "agent_name": "Backend Agent",
            "role": "Backend Specialist",
            "department": "Engineering",
            "role_description": "Develop APIs, services, and backend systems",
            "primary_responsibility": "Write clean, tested backend code",
            "secondary_responsibility": "Design data models and APIs",
            "support_responsibility": "Support frontend and DevOps teams",
            "do_constraint_1": "Follow code standards and testing requirements",
            "do_constraint_2": "Document APIs and data models",
            "do_constraint_3": "Consider performance and security",
            "dont_constraint_1": "Do not deploy to production (DevOps team handles that)",
            "dont_constraint_2": "Do not skip tests",
            "dont_constraint_3": "Do not modify database schema without team review",
            "tools": "github_read, github_write, kubernetes_read, database_read",
            "decision_approach": "Pragmatic - balance perfection with shipping",
            "risk_tolerance": "Medium - security is non-negotiable",
            "escalation_trigger": "If security implications are unclear",
            "context_sources": "Architecture docs, API specs, code standards",
            "memory_instructions": "Reference previous similar implementations",
            "accuracy_standard": "Tests must pass 100%",
            "completeness_standard": "Code + tests + documentation",
            "timeliness_standard": "Feature complete within sprint",
        }
        
        # Support Agent
        self.templates["support_agent"] = {
            "agent_name": "Support Agent",
            "role": "Customer Support Specialist",
            "department": "Customer Support",
            "role_description": "Resolve customer issues and answer questions",
            "primary_responsibility": "Process and resolve support tickets",
            "secondary_responsibility": "Identify common issues for improvement",
            "support_responsibility": "Escalate complex issues appropriately",
            "do_constraint_1": "Be empathetic and professional",
            "do_constraint_2": "Search knowledge base before responding",
            "do_constraint_3": "Provide solutions, not excuses",
            "dont_constraint_1": "Do not make refund decisions",
            "dont_constraint_2": "Do not access customer sensitive data",
            "dont_constraint_3": "Do not make product promises",
            "tools": "knowledge_base_search, customer_data_read, notion_read",
            "decision_approach": "Customer-first, pragmatic",
            "risk_tolerance": "Low - protect customer trust",
            "escalation_trigger": "If customer is unhappy after 2 attempts",
            "context_sources": "Knowledge base, ticket history, customer profiles",
            "memory_instructions": "Learn from past similar tickets",
            "accuracy_standard": "100% - never mislead customers",
            "completeness_standard": "Full resolution or clear escalation",
            "timeliness_standard": "Respond within 1 hour",
        }
    
    def build(self, agent_type: str) -> str:
        """Build system prompt for agent type"""
        
        if agent_type not in self.templates:
            return self._build_generic()
        
        template = self.templates[agent_type]
        
        return SYSTEM_PROMPT_TEMPLATE.format(
            agent_name=template["agent_name"],
            role=template["role"],
            department=template["department"],
            role_description=template["role_description"],
            primary_responsibility=template["primary_responsibility"],
            secondary_responsibility=template["secondary_responsibility"],
            support_responsibility=template["support_responsibility"],
            do_constraint_1=template["do_constraint_1"],
            do_constraint_2=template["do_constraint_2"],
            do_constraint_3=template["do_constraint_3"],
            dont_constraint_1=template["dont_constraint_1"],
            dont_constraint_2=template["dont_constraint_2"],
            dont_constraint_3=template["dont_constraint_3"],
            tools=template["tools"],
            decision_approach=template["decision_approach"],
            risk_tolerance=template["risk_tolerance"],
            escalation_trigger=template["escalation_trigger"],
            context_sources=template["context_sources"],
            memory_instructions=template["memory_instructions"],
            accuracy_standard=template["accuracy_standard"],
            completeness_standard=template["completeness_standard"],
            timeliness_standard=template["timeliness_standard"],
        )
    
    def _build_generic(self) -> str:
        """Fallback generic prompt"""
        return """
        You are an AI assistant working in an organization.
        Be helpful, accurate, and professional.
        Ask for clarification if needed.
        """

# Usage
builder = SystemPromptBuilder()
research_prompt = builder.build("marketing_research")
print(research_prompt)
```

### 4.2 Dynamic Prompt Injection

```python
class ContextualPromptBuilder:
    """Build prompts that include current context and memory"""
    
    def build_with_context(
        self,
        agent_type: str,
        system_prompt: str,
        current_task: str,
        brain_context: list,
        working_memory: dict,
    ) -> str:
        """
        Build complete prompt including:
        - System instructions
        - Current task
        - Brain context (relevant previous work)
        - Working memory (current progress)
        """
        
        prompt = f"""{system_prompt}

## Current Task
{current_task}

## Relevant Context from Brain
"""
        
        if brain_context:
            for note in brain_context[:3]:
                prompt += f"- {note.get('title', 'Note')}: {note.get('summary', '')[:100]}\n"
        else:
            prompt += "- No previous related work found\n"
        
        prompt += "\n## What You Know So Far\n"
        
        if working_memory:
            for key, value in working_memory.items():
                if isinstance(value, str):
                    prompt += f"- {key}: {value[:100]}\n"
                else:
                    prompt += f"- {key}: {str(value)[:100]}\n"
        else:
            prompt += "- Starting fresh\n"
        
        prompt += "\n## Your Task\nContinue from above with your expertise.\n"
        
        return prompt

# Usage
builder = ContextualPromptBuilder()
base_prompt = SystemPromptBuilder().build("marketing_research")

context_prompt = builder.build_with_context(
    agent_type="marketing_research",
    system_prompt=base_prompt,
    current_task="Find Q3 market trends in AI/ML",
    brain_context=[
        {"title": "Q2 Market Analysis", "summary": "Market grew 15% YoY"},
        {"title": "Competitor Report", "summary": "3 new entrants in space"},
    ],
    working_memory={
        "searched_keywords": "AI trends, machine learning market",
        "sources_found": "5 Gartner reports, 3 research papers",
    }
)

print(context_prompt)
```

---

## 5. Sandboxing & Tool Isolation

### 5.1 Tool Permission Matrix

```python
from typing import Set, Dict, Tuple
from enum import Enum

class Permission(Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELETE = "delete"

class ResourceType(Enum):
    FILE = "file"
    DATABASE = "database"
    API = "api"
    NETWORK = "network"
    SYSTEM = "system"

class ToolSandbox:
    """
    Permission-based sandbox for agent tool access
    Agents can only use tools their department allows
    """
    
    def __init__(self):
        # Department-level permissions
        self.dept_permissions: Dict[str, Set[Tuple[str, str]]] = {
            "marketing": {
                ("web_search", Permission.EXECUTE.value),
                ("file_read", Permission.READ.value),
                ("file_write", Permission.WRITE.value),
                ("notion_read", Permission.READ.value),
                ("notion_write", Permission.WRITE.value),
                ("google_drive", Permission.READ.value),
            },
            "support": {
                ("knowledge_base_search", Permission.READ.value),
                ("customer_data_read", Permission.READ.value),
                ("ticket_read", Permission.READ.value),
                ("ticket_write", Permission.WRITE.value),
                ("email_send", Permission.EXECUTE.value),  # Limited
            },
            "engineering": {
                ("github_read", Permission.READ.value),
                ("github_write", Permission.WRITE.value),
                ("database_read", Permission.READ.value),
                ("kubernetes_read", Permission.READ.value),
                ("docker_build", Permission.EXECUTE.value),
                # NOTE: No kubernetes_write or database_write - requires approval
            },
        }
        
        # Agent-specific overrides (additional permissions)
        self.agent_permissions: Dict[str, Set[Tuple[str, str]]] = {
            "devops_agent": {
                ("kubernetes_write", Permission.EXECUTE.value),  # Only DevOps can deploy
                ("database_backup", Permission.EXECUTE.value),
            },
            "security_audit": {
                ("database_read", Permission.READ.value),  # Can read any database
                ("log_read", Permission.READ.value),
            },
        }
    
    def can_execute(self, agent_id: str, dept: str, tool_name: str, permission: str) -> bool:
        """
        Check if agent can execute tool
        Returns: True if allowed, False if denied
        """
        
        # Build full permission set
        allowed = set()
        
        # Add department permissions
        if dept in self.dept_permissions:
            allowed.update(self.dept_permissions[dept])
        
        # Add agent-specific permissions
        if agent_id in self.agent_permissions:
            allowed.update(self.agent_permissions[agent_id])
        
        # Check if (tool, permission) is allowed
        return (tool_name, permission) in allowed
    
    def filter_tools(self, agent_id: str, dept: str, all_tools: list) -> list:
        """
        Filter tools list to only those agent can use
        """
        
        accessible_tools = []
        
        for tool in all_tools:
            tool_name = tool.get("name", "")
            
            # Check execute permission (most common)
            if self.can_execute(agent_id, dept, tool_name, "execute"):
                accessible_tools.append(tool)
        
        return accessible_tools

# Usage
sandbox = ToolSandbox()

# Marketing agent can use web_search
print(sandbox.can_execute("market_research_1", "marketing", "web_search", "execute"))
# → True

# Engineering agent CANNOT write to Kubernetes (no approval)
print(sandbox.can_execute("backend_agent", "engineering", "kubernetes_write", "execute"))
# → False

# But DevOps agent CAN write to Kubernetes
print(sandbox.can_execute("devops_agent", "engineering", "kubernetes_write", "execute"))
# → True

# Filter tools for marketing research agent
all_tools = [
    {"name": "web_search", "description": "Search web"},
    {"name": "database_write", "description": "Write to DB"},
    {"name": "file_write", "description": "Write file"},
]

accessible = sandbox.filter_tools("market_research_1", "marketing", all_tools)
# Returns: [web_search, file_write] (not database_write)
```

### 5.2 Docker Container Isolation

```python
"""
Production pattern: Run each agent in isolated Docker container
This provides hard resource limits and process isolation
"""

import docker
import json
import subprocess
from typing import Dict

class ContainerizedAgent:
    """Run agent in isolated Docker container"""
    
    def __init__(self, agent_config: Dict, docker_client=None):
        self.agent_id = agent_config["id"]
        self.docker_client = docker_client or docker.from_env()
        self.config = agent_config
    
    def run_agent(self, task: str, timeout_seconds: int = 300) -> Dict:
        """
        Run agent in isolated container
        
        Hard limits:
        - CPU: 1 core
        - Memory: 512MB
        - Timeout: 5 minutes
        """
        
        # Build container startup script
        start_script = f"""
        python3 -c "
        from backend.agents import {self.config['class_name']}
        import sys
        import json
        
        agent = {self.config['class_name']}()
        result = agent.execute('{task}')
        print(json.dumps(result))
        "
        """
        
        try:
            # Run in container with resource limits
            container = self.docker_client.containers.run(
                image=self.config.get("docker_image", "python:3.11-slim"),
                command=["sh", "-c", start_script],
                
                # Resource limits
                mem_limit="512m",  # 512MB max
                memswap_limit="512m",  # No swap
                cpu_quota=100000,  # 1 core = 100000
                cpu_period=100000,
                
                # Timeout
                timeout=timeout_seconds,
                
                # Remove after completion
                remove=True,
                
                # Network isolation (optional)
                network_disabled=False,  # Can access network
                
                # Read-only filesystem (optional)
                read_only=False,
                
                # No privileged access
                privileged=False,
                
                # Volumes (if needed)
                volumes=self.config.get("volumes", {}),
            )
            
            # Get output
            output = container.logs()
            return json.loads(output)
        
        except docker.errors.ContainerError as e:
            return {
                "status": "failed",
                "error": f"Container error: {e}",
                "agent_id": self.agent_id,
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "error": f"Task exceeded {timeout_seconds}s limit",
                "agent_id": self.agent_id,
            }

# Example config
agent_config = {
    "id": "research_agent_1",
    "class_name": "ResearchAgent",
    "docker_image": "agents-office:latest",
    "volumes": {
        "/data/brain": {"bind": "/agent/brain", "mode": "rw"},
    }
}

agent = ContainerizedAgent(agent_config)
result = agent.run_agent("Find Q3 market trends", timeout_seconds=300)
```

### 5.3 Resource Limits & Quotas

```python
"""
Resource quota system to prevent agents from consuming all resources
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict

@dataclass
class ResourceQuota:
    """Define resource limits per agent/department"""
    
    # API calls per hour
    api_calls_per_hour: int = 100
    
    # Tokens (LLM) per day
    tokens_per_day: int = 100_000
    
    # File operations per hour
    file_ops_per_hour: int = 50
    
    # Database operations per hour
    db_ops_per_hour: int = 1000
    
    # Network bandwidth per day (MB)
    bandwidth_per_day: int = 1000
    
    # Parallel execution limit
    max_concurrent_tasks: int = 5

class QuotaManager:
    """Track and enforce resource quotas"""
    
    def __init__(self):
        self.usage: Dict[str, Dict] = {}
        self.quotas: Dict[str, ResourceQuota] = {}
    
    def set_quota(self, agent_id: str, quota: ResourceQuota):
        """Set quota for agent"""
        self.quotas[agent_id] = quota
        self.usage[agent_id] = self._init_usage()
    
    def _init_usage(self) -> Dict:
        """Initialize usage tracking"""
        return {
            "api_calls": [],  # List of timestamps
            "tokens_used": 0,
            "file_ops": [],
            "db_ops": [],
            "bandwidth_used": 0,
            "concurrent_tasks": 0,
            "reset_at": datetime.now() + timedelta(hours=1),
        }
    
    def check_quota(self, agent_id: str, resource: str) -> bool:
        """Check if agent can use more of resource"""
        
        if agent_id not in self.quotas:
            return True  # No quota = unlimited
        
        quota = self.quotas[agent_id]
        usage = self.usage[agent_id]
        now = datetime.now()
        
        # Reset usage if expired
        if now > usage["reset_at"]:
            self.usage[agent_id] = self._init_usage()
            return True
        
        # Check specific resource
        if resource == "api_calls":
            # Count calls in last hour
            calls_last_hour = len([
                t for t in usage["api_calls"]
                if now - t < timedelta(hours=1)
            ])
            return calls_last_hour < quota.api_calls_per_hour
        
        elif resource == "tokens":
            return usage["tokens_used"] < quota.tokens_per_day
        
        elif resource == "file_ops":
            file_ops_last_hour = len([
                t for t in usage["file_ops"]
                if now - t < timedelta(hours=1)
            ])
            return file_ops_last_hour < quota.file_ops_per_hour
        
        elif resource == "concurrent":
            return usage["concurrent_tasks"] < quota.max_concurrent_tasks
        
        return True
    
    def record_usage(self, agent_id: str, resource: str, amount: int = 1):
        """Record resource usage"""
        
        if agent_id not in self.usage:
            self.usage[agent_id] = self._init_usage()
        
        usage = self.usage[agent_id]
        
        if resource == "api_calls":
            usage["api_calls"].append(datetime.now())
        elif resource == "tokens":
            usage["tokens_used"] += amount
        elif resource == "file_ops":
            usage["file_ops"].append(datetime.now())
        elif resource == "bandwidth":
            usage["bandwidth_used"] += amount

# Usage
manager = QuotaManager()

# Set quotas for departments
marketing_quota = ResourceQuota(
    api_calls_per_hour=100,
    tokens_per_day=50_000,
    file_ops_per_hour=50,
)

manager.set_quota("marketing_dept", marketing_quota)

# Check before executing
if manager.check_quota("marketing_dept", "api_calls"):
    # Proceed with API call
    manager.record_usage("marketing_dept", "api_calls", 1)
else:
    # Raise error
    raise Exception("API quota exceeded for department")
```

---

## 6. State Checkpointing

### 6.1 PostgreSQL Checkpointing

```python
"""
State checkpointing to PostgreSQL for durability and recovery
Following LangGraph pattern
"""

import json
import asyncpg
from datetime import datetime
from typing import Dict, Any, Optional

class PostgreSQLCheckpoint:
    """Save and load LangGraph state to PostgreSQL"""
    
    def __init__(self, db_url: str = "postgresql://user:pass@localhost/agent_office"):
        self.db_url = db_url
        self.pool = None
    
    async def initialize(self):
        """Create connection pool and tables"""
        self.pool = await asyncpg.create_pool(self.db_url)
        
        async with self.pool.acquire() as conn:
            # Create state checkpoints table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS state_checkpoints (
                    checkpoint_id SERIAL PRIMARY KEY,
                    task_id VARCHAR(50) NOT NULL,
                    node_name VARCHAR(100) NOT NULL,
                    state_data JSONB NOT NULL,
                    timestamp TIMESTAMP DEFAULT NOW(),
                    status VARCHAR(20) NOT NULL,
                    error_message TEXT,
                    
                    -- For recovery
                    recoverable BOOLEAN DEFAULT TRUE,
                    
                    -- Indexing
                    UNIQUE(task_id, node_name),
                    INDEX task_idx (task_id),
                    INDEX status_idx (status),
                    INDEX timestamp_idx (timestamp)
                )
            """)
            
            # Create task execution log
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS task_execution_log (
                    log_id SERIAL PRIMARY KEY,
                    task_id VARCHAR(50) NOT NULL,
                    event_type VARCHAR(50) NOT NULL,
                    data JSONB NOT NULL,
                    timestamp TIMESTAMP DEFAULT NOW(),
                    
                    FOREIGN KEY (task_id) REFERENCES state_checkpoints(task_id),
                    INDEX task_idx (task_id),
                    INDEX event_idx (event_type)
                )
            """)
    
    async def save_checkpoint(
        self,
        task_id: str,
        node_name: str,
        state: Dict[str, Any],
        status: str = "success",
        error: Optional[str] = None,
    ) -> int:
        """
        Save state checkpoint after node execution
        
        Returns checkpoint_id for reference
        """
        
        async with self.pool.acquire() as conn:
            # Save checkpoint
            checkpoint_id = await conn.fetchval("""
                INSERT INTO state_checkpoints 
                (task_id, node_name, state_data, status, error_message)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (task_id, node_name) DO UPDATE 
                SET state_data = $3, status = $4, error_message = $5
                RETURNING checkpoint_id
            """, task_id, node_name, json.dumps(state), status, error)
            
            # Log event
            await conn.execute("""
                INSERT INTO task_execution_log (task_id, event_type, data)
                VALUES ($1, $2, $3)
            """, task_id, f"checkpoint_{status}", json.dumps({
                "node": node_name,
                "checkpoint_id": checkpoint_id,
                "timestamp": datetime.now().isoformat(),
            }))
            
            return checkpoint_id
    
    async def load_checkpoint(
        self,
        task_id: str,
        node_name: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Load saved state from checkpoint
        Useful for resuming failed tasks
        """
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT state_data, status
                FROM state_checkpoints
                WHERE task_id = $1 AND node_name = $2
            """, task_id, node_name)
            
            if not row:
                return None
            
            return {
                "state": json.loads(row["state_data"]),
                "status": row["status"],
            }
    
    async def get_latest_node(self, task_id: str) -> Optional[str]:
        """
        Get last executed node for task
        Used to resume execution
        """
        
        async with self.pool.acquire() as conn:
            node = await conn.fetchval("""
                SELECT node_name
                FROM state_checkpoints
                WHERE task_id = $1
                ORDER BY timestamp DESC
                LIMIT 1
            """, task_id)
            
            return node
    
    async def delete_checkpoints(self, task_id: str):
        """
        Clean up checkpoints after successful completion
        Saves storage
        """
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                DELETE FROM state_checkpoints
                WHERE task_id = $1
            """, task_id)

# Usage in LangGraph
class CheckpointedGraph:
    """LangGraph with automatic checkpointing"""
    
    def __init__(self, graph, checkpoint_store: PostgreSQLCheckpoint):
        self.graph = graph
        self.checkpoint = checkpoint_store
    
    async def execute_with_checkpoints(self, initial_state: Dict, task_id: str):
        """
        Execute graph with automatic checkpointing
        Can resume if interrupted
        """
        
        # Try to resume from last checkpoint
        last_node = await self.checkpoint.get_latest_node(task_id)
        if last_node:
            checkpoint_data = await self.checkpoint.load_checkpoint(task_id, last_node)
            initial_state = checkpoint_data["state"]
            print(f"Resuming from node: {last_node}")
        
        try:
            # Execute graph
            state = initial_state
            
            # This is simplified - real LangGraph has built-in checkpointing
            for step in self.graph.steps:  # Pseudo-code
                try:
                    state = await step(state)
                    
                    # Save checkpoint after each node
                    await self.checkpoint.save_checkpoint(
                        task_id=task_id,
                        node_name=step.name,
                        state=state,
                        status="success",
                    )
                
                except Exception as e:
                    # Save failed state
                    await self.checkpoint.save_checkpoint(
                        task_id=task_id,
                        node_name=step.name,
                        state=state,
                        status="failed",
                        error=str(e),
                    )
                    raise
            
            # Clean up on success
            # Note: In production, might keep for audit
            # await self.checkpoint.delete_checkpoints(task_id)
            
            return state
        
        except Exception as e:
            print(f"Task {task_id} failed at checkpoint, can resume later")
            raise

# Initialize
checkpoint = PostgreSQLCheckpoint()
# await checkpoint.initialize()

# Use with graph
# graph = OfficeGraph(roster, brain)
# checkpointed = CheckpointedGraph(graph.graph, checkpoint)
# result = await checkpointed.execute_with_checkpoints(initial_state, "task_123")
```

### 6.2 Checkpoint Strategies

```python
"""
Different checkpointing strategies for different use cases
"""

from enum import Enum

class CheckpointStrategy(Enum):
    """When to save checkpoints"""
    
    # Always save after every node
    EVERY_NODE = "every_node"
    
    # Save only before critical operations
    CRITICAL_ONLY = "critical_only"
    
    # Save every N nodes
    PERIODIC = "periodic"
    
    # Save only on error
    ERROR_ONLY = "error_only"

class AdaptiveCheckpointing:
    """Save checkpoints based on operation type and risk"""
    
    def __init__(self, checkpoint_store: PostgreSQLCheckpoint):
        self.checkpoint = checkpoint_store
        self.critical_nodes = {
            "brain_update",
            "database_write",
            "file_write",
            "send_email",
        }
    
    def should_checkpoint(
        self,
        node_name: str,
        strategy: CheckpointStrategy,
        iteration: int = 0,
    ) -> bool:
        """Determine if should save checkpoint"""
        
        if strategy == CheckpointStrategy.EVERY_NODE:
            return True
        
        elif strategy == CheckpointStrategy.CRITICAL_ONLY:
            return node_name in self.critical_nodes
        
        elif strategy == CheckpointStrategy.PERIODIC:
            return iteration % 3 == 0  # Every 3 nodes
        
        elif strategy == CheckpointStrategy.ERROR_ONLY:
            return False  # Only save on error in exception handler
        
        return False

# For Agent Office: Use CRITICAL_ONLY to minimize storage
# Critical nodes: brain_update, file_write, send_email
# Regular nodes (fast, idempotent): research, analysis, synthesis
```

---

## 7. Error Handling & Retries

### 7.1 Retry Patterns

```python
"""
Production-grade retry strategies for multi-agent systems
"""

import asyncio
from typing import Callable, Any, Optional
from enum import Enum

class RetryStrategy(Enum):
    """Retry behavior when agent fails"""
    
    # Exponential backoff: 1s, 2s, 4s, 8s...
    EXPONENTIAL = "exponential"
    
    # Linear backoff: 1s, 2s, 3s, 4s...
    LINEAR = "linear"
    
    # No backoff: retry immediately
    IMMEDIATE = "immediate"
    
    # Manual: let caller decide
    MANUAL = "manual"

class RetryableAgent:
    """Agent with built-in retry logic"""
    
    def __init__(
        self,
        agent,
        max_retries: int = 3,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
        backoff_factor: float = 2.0,
    ):
        self.agent = agent
        self.max_retries = max_retries
        self.strategy = strategy
        self.backoff_factor = backoff_factor
        self.retry_count = 0
    
    async def execute_with_retry(self, task: str, context: dict = None) -> dict:
        """Execute with automatic retries on failure"""
        
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # Try to execute
                result = await self.agent.execute(task, context)
                
                if attempt > 0:
                    print(f"✓ Succeeded on attempt {attempt + 1}")
                
                return result
            
            except Exception as e:
                last_error = e
                
                if attempt == self.max_retries:
                    # Final attempt failed
                    print(f"✗ Failed after {self.max_retries + 1} attempts")
                    return {
                        "status": "failed",
                        "error": str(e),
                        "attempts": self.max_retries + 1,
                    }
                
                # Calculate backoff
                wait_time = self._calculate_backoff(attempt)
                print(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                
                await asyncio.sleep(wait_time)
        
        return {"status": "failed", "error": str(last_error)}
    
    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate wait time before retry"""
        
        if self.strategy == RetryStrategy.EXPONENTIAL:
            return self.backoff_factor ** attempt
        
        elif self.strategy == RetryStrategy.LINEAR:
            return float(attempt + 1)
        
        elif self.strategy == RetryStrategy.IMMEDIATE:
            return 0.0
        
        return 1.0

# Usage
agent = ResearchAgent()
retryable = RetryableAgent(
    agent,
    max_retries=3,
    strategy=RetryStrategy.EXPONENTIAL,
)

# This will retry up to 3 times with exponential backoff
result = await retryable.execute_with_retry("Find market trends")
```

### 7.2 Escalation Strategy

```python
"""
Escalation when an agent can't handle a task
"""

class EscalationRule:
    """Define when to escalate"""
    
    def __init__(
        self,
        trigger: str,  # "max_retries", "error_type", "confidence_low"
        target_agent: str,  # Who to escalate to
        override_tools: bool = False,  # Give escalated agent more tools
    ):
        self.trigger = trigger
        self.target_agent = target_agent
        self.override_tools = override_tools

class EscalationManager:
    """Handle task escalation between agents"""
    
    def __init__(self, agents: dict, rules: list):
        self.agents = agents
        self.rules = rules
    
    def should_escalate(
        self,
        agent_id: str,
        failure_reason: str,
        retry_count: int,
    ) -> tuple[bool, Optional[str]]:
        """
        Determine if task should be escalated
        Returns: (should_escalate, target_agent_id)
        """
        
        for rule in self.rules:
            # Check escalation triggers
            if rule.trigger == "max_retries" and retry_count >= 3:
                return True, rule.target_agent
            
            elif rule.trigger == "error_type":
                if "timeout" in failure_reason.lower():
                    return True, rule.target_agent
                elif "permission" in failure_reason.lower():
                    return True, rule.target_agent
            
            elif rule.trigger == "confidence_low":
                # If agent's confidence score is < 0.3
                if hasattr(agent, "confidence") and agent.confidence < 0.3:
                    return True, rule.target_agent
        
        return False, None
    
    async def escalate(
        self,
        task: str,
        from_agent: str,
        to_agent: str,
        context: dict,
    ) -> dict:
        """Escalate task to higher-level agent"""
        
        escalation_context = {
            **context,
            "escalated_from": from_agent,
            "reason": "Agent unable to complete",
            "attempt_count": context.get("attempt_count", 0) + 1,
        }
        
        target = self.agents[to_agent]
        return await target.execute(task, escalation_context)

# Example escalation rules
escalation_rules = [
    EscalationRule(
        trigger="max_retries",
        target_agent="marketing_lead",  # Escalate to lead
    ),
    EscalationRule(
        trigger="error_type",
        target_agent="support_lead",  # For permission errors
    ),
]

manager = EscalationManager(agents_dict, escalation_rules)

# Check if should escalate
should_escalate, target = manager.should_escalate(
    agent_id="research_agent",
    failure_reason="Timeout: web search took > 60s",
    retry_count=3,
)

if should_escalate:
    result = await manager.escalate(
        task="Find Q3 trends",
        from_agent="research_agent",
        to_agent=target,
        context={},
    )
```

---

## 8. Production Patterns

### 8.1 Complete Multi-Agent Example

```python
"""
Complete production example: Marketing department workflow
"""

from datetime import datetime
from typing import Dict

class MarketingWorkflow:
    """Full marketing campaign workflow with all patterns"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.checkpoint = PostgreSQLCheckpoint(config["db_url"])
        self.sandbox = ToolSandbox()
        self.quota = QuotaManager()
    
    async def process_campaign_request(self, request: Dict) -> Dict:
        """
        Execute complete campaign creation workflow:
        1. Route to marketing
        2. Lead plans approach
        3. Specialists execute in parallel
        4. Lead synthesizes
        5. Save to brain
        """
        
        task_id = request["task_id"]
        campaign_brief = request["text"]
        
        print(f"[{task_id}] Starting campaign creation")
        
        try:
            # Initialize state
            state = {
                "task_id": task_id,
                "task_text": campaign_brief,
                "department": "marketing",
                "status": "working",
                "messages": [],
                "working_memory": {},
                "brain_context": [],
            }
            
            # Save initial checkpoint
            await self.checkpoint.save_checkpoint(
                task_id=task_id,
                node_name="START",
                state=state,
                status="success",
            )
            
            # 1. Brain context
            print(f"[{task_id}] Retrieving brain context...")
            brain_notes = []  # Would fetch from brain
            state["brain_context"] = brain_notes
            
            await self.checkpoint.save_checkpoint(
                task_id=task_id,
                node_name="brain_context",
                state=state,
            )
            
            # 2. Lead planning
            print(f"[{task_id}] Lead planning...")
            lead = self.config["agents"]["marketing_lead"]
            
            # Check quotas
            if not self.quota.check_quota(lead["id"], "api_calls"):
                raise Exception("API quota exceeded")
            
            plan = await self._lead_plan(campaign_brief)
            state["messages"].append({"role": "lead", "content": plan})
            
            await self.checkpoint.save_checkpoint(
                task_id=task_id,
                node_name="lead_planning",
                state=state,
            )
            
            # 3. Parallel specialists
            print(f"[{task_id}] Executing specialists...")
            
            specialists = [
                ("research_agent", self._research_specialist),
                ("writing_agent", self._writing_specialist),
                ("analysis_agent", self._analysis_specialist),
            ]
            
            results = {}
            for agent_id, executor in specialists:
                # Check permissions
                if not self.sandbox.can_execute(
                    agent_id,
                    "marketing",
                    "web_search",
                    "execute",
                ):
                    print(f"[{task_id}] {agent_id} denied access")
                    continue
                
                try:
                    result = await executor(campaign_brief, plan)
                    results[agent_id] = result
                    
                    await self.checkpoint.save_checkpoint(
                        task_id=task_id,
                        node_name=f"specialist_{agent_id}",
                        state={"results": results},
                    )
                
                except Exception as e:
                    print(f"[{task_id}] {agent_id} failed: {e}")
                    # Could retry or escalate here
            
            state["working_memory"] = results
            
            # 4. Lead synthesis
            print(f"[{task_id}] Lead synthesizing...")
            final = await self._lead_synthesize(campaign_brief, plan, results)
            state["deliverable"] = final
            
            await self.checkpoint.save_checkpoint(
                task_id=task_id,
                node_name="synthesis",
                state=state,
            )
            
            # 5. Brain update
            print(f"[{task_id}] Saving to brain...")
            await self._save_to_brain(task_id, campaign_brief, final)
            
            await self.checkpoint.save_checkpoint(
                task_id=task_id,
                node_name="brain_update",
                state=state,
                status="success",
            )
            
            print(f"[{task_id}] ✓ Complete")
            
            return {
                "task_id": task_id,
                "status": "completed",
                "deliverable": final,
                "timestamp": datetime.now().isoformat(),
            }
        
        except Exception as e:
            print(f"[{task_id}] ✗ Failed: {e}")
            
            await self.checkpoint.save_checkpoint(
                task_id=task_id,
                node_name="ERROR",
                state=state,
                status="failed",
                error=str(e),
            )
            
            return {
                "task_id": task_id,
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
    
    async def _lead_plan(self, task: str) -> str:
        # Implement lead planning
        return f"Plan for: {task}"
    
    async def _research_specialist(self, task: str, plan: str) -> str:
        # Implement research
        return "Research findings..."
    
    async def _writing_specialist(self, task: str, plan: str) -> str:
        # Implement writing
        return "Campaign copy..."
    
    async def _analysis_specialist(self, task: str, plan: str) -> str:
        # Implement analysis
        return "Analysis metrics..."
    
    async def _lead_synthesize(self, task: str, plan: str, results: Dict) -> str:
        # Implement synthesis
        return "Final campaign brief..."
    
    async def _save_to_brain(self, task_id: str, task: str, result: str):
        # Save to brain
        pass

# Usage
config = {
    "db_url": "postgresql://user:pass@localhost/agent_office",
    "agents": {
        "marketing_lead": {"id": "lead_001", "model": "sonnet"},
        "research_agent": {"id": "specialist_001", "model": "haiku"},
    },
}

workflow = MarketingWorkflow(config)
result = await workflow.process_campaign_request({
    "task_id": "task_001",
    "text": "Create Q3 marketing campaign brief",
})
```

### 8.2 Observability & Monitoring

```python
"""
Structured logging and observability for multi-agent systems
"""

import logging
import json
from datetime import datetime

class AgentLogger:
    """Structured logging for agents"""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.logger = logging.getLogger(f"agent.{agent_id}")
    
    def log_event(
        self,
        event_type: str,
        message: str,
        data: dict = None,
        level: str = "INFO",
    ):
        """Log structured event"""
        
        event = {
            "timestamp": datetime.now().isoformat(),
            "agent_id": self.agent_id,
            "event_type": event_type,
            "message": message,
            "data": data or {},
        }
        
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(json.dumps(event))
    
    def log_task_start(self, task_id: str, task_text: str):
        self.log_event(
            "TASK_START",
            f"Starting task",
            {"task_id": task_id, "task_text": task_text[:100]},
        )
    
    def log_tool_call(self, tool_name: str, params: dict, result: str):
        self.log_event(
            "TOOL_CALL",
            f"Called {tool_name}",
            {
                "tool": tool_name,
                "params": params,
                "result_length": len(result),
            },
        )
    
    def log_error(self, error: str, retry_count: int = 0):
        self.log_event(
            "ERROR",
            error,
            {"retry_count": retry_count},
            level="ERROR",
        )
    
    def log_task_complete(self, task_id: str, duration_seconds: float):
        self.log_event(
            "TASK_COMPLETE",
            f"Task completed",
            {"task_id": task_id, "duration": duration_seconds},
        )

# Usage
logger = AgentLogger("research_agent_1")

logger.log_task_start("task_001", "Find Q3 trends")
logger.log_tool_call("web_search", {"query": "Q3 trends"}, "Found 10 results")
logger.log_task_complete("task_001", 45.2)
```

---

## Summary & Next Steps

### Key Takeaways

1. **LangChain** - Good for tool routing and basic agent patterns
2. **LangGraph** - Best for production (durability, checkpointing, error handling)
3. **Hierarchical Pattern** - Lead → Specialists is industry standard (AutoGPT, CrewAI, MetaGPT)
4. **Sandboxing** - Permission matrix + resource quotas prevent runaway agents
5. **Checkpointing** - Save state after critical operations for recovery
6. **Retry/Escalation** - Exponential backoff + escalation to higher authority

### For Agent Office Phase 2

**Recommended Pattern:**
```
LangGraph StateGraph
├── Router Node (classify task)
├── Brain Context Node (retrieve knowledge)
├── Lead Planning Node (orchestrate)
├── [Specialist Nodes] (parallel)
│   ├── Research
│   ├── Writing
│   └── Analysis
├── Synthesis Node (lead combines)
├── Brain Update Node (save learning)
└── Complete/Escalate (finish or retry)
```

**Checkpointing Strategy:**
- Save after: lead_planning, specialist completion, synthesis, brain_update
- Storage: PostgreSQL with task_id + node_name indices
- Recovery: Resume from last checkpoint on restart

**Safety Layers:**
1. Permissions (ToolSandbox)
2. Quotas (ResourceQuota)
3. Retries (RetryableAgent)
4. Escalation (EscalationManager)
5. Monitoring (AgentLogger)

---

**Reference:** This research validates Phase 2 architecture decisions. LangGraph + Hierarchical pattern + Checkpointing = production-grade multi-agent system.
