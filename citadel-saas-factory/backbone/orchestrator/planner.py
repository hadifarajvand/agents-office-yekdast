"""Planner-Executor-Critic loop with typed task graph and stop-gate.

The planner decomposes a goal into steps, the executor runs each step,
and the critic evaluates the result. If the critic rejects, the planner
revises the plan. Depth and fan-out are capped to prevent runaway costs.

Exports:
    PlanTask     - a single task within a plan (used by base.py, router.py, etc.)
    TaskPlan     - a full plan containing ordered tasks (used by supervisor.py)
    Planner      - creates plans from goals using the registry (used by engine.py)
    PlannerLoop  - the LLM-driven plan/execute/critique loop
    PlannerResult - immutable result from the planner loop
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog
import yaml

logger = structlog.get_logger("orchestrator.planner")

MAX_REPLANS = 3
MAX_STEPS_PER_PLAN = 10

# Domain-to-agent-type mapping for default task routing
DOMAIN_AGENT_DEFAULTS: dict[str, str] = {
    "executive": "strategist",
    "marketing": "content",
    "sales": "qualifier",
    "customer_success": "support",
    "product": "designer",
    "engineering": "developer",
    "frontend": "component",
    "devops": "deploy",
    "security": "auditor",
    "data": "analyst",
    "qa": "tester",
    "hr": "recruiter",
    "finance": "billing",
    "legal": "compliance",
    "content": "writer",
}


@dataclass(frozen=True)
class PlanTask:
    """A single task within a plan, routable to an agent."""

    task_id: str
    name: str
    description: str
    domain: str
    agent_type: str
    depends_on: tuple[str, ...] = field(default_factory=tuple)
    priority: int = 5
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskPlan:
    """A full plan: an ordered collection of PlanTasks."""

    plan_id: str
    goal: str
    tasks: tuple[PlanTask, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_execution_batches(self) -> list[list[PlanTask]]:
        """Group tasks into dependency-respecting batches for parallel execution."""
        completed: set[str] = set()
        remaining = list(self.tasks)
        batches: list[list[PlanTask]] = []

        while remaining:
            batch = [t for t in remaining if all(d in completed for d in t.depends_on)]
            if not batch:
                # Deadlock: remaining tasks have unresolvable deps, force them
                batch = remaining[:]
            batches.append(batch)
            completed.update(t.task_id for t in batch)
            remaining = [t for t in remaining if t.task_id not in completed]

        return batches


class Planner:
    """Creates TaskPlans from goals using the agent registry for domain routing.

    Used by Supervisor and BackboneEngine. For the LLM-driven
    plan/execute/critique loop, see PlannerLoop.
    """

    def __init__(self, registry_path: str = ".claude/agents/_registry.yaml") -> None:
        self._registry_path = Path(registry_path)
        self._domains: list[str] = []
        self._load_domains()

    def _load_domains(self) -> None:
        if self._registry_path.exists():
            with open(self._registry_path) as f:
                data = yaml.safe_load(f) or {}
            agents = data.get("agents", [])
            self._domains = sorted({a.get("domain", "") for a in agents})
        else:
            self._domains = list(DOMAIN_AGENT_DEFAULTS.keys())

    async def create_plan(self, goal: str, context: dict[str, Any] | None = None) -> TaskPlan:
        """Decompose a goal into a TaskPlan with routable PlanTasks."""
        plan_id = str(uuid.uuid4())
        tasks = self._decompose_goal(goal)
        return TaskPlan(plan_id=plan_id, goal=goal, tasks=tuple(tasks))

    def _decompose_goal(self, goal: str) -> list[PlanTask]:
        """Simple heuristic decomposition: create one task per relevant domain."""
        goal_lower = goal.lower()
        tasks: list[PlanTask] = []

        domain_keywords: dict[str, list[str]] = {
            "engineering": ["api", "code", "backend", "endpoint", "model", "schema"],
            "frontend": ["ui", "component", "page", "form", "frontend", "react"],
            "security": ["security", "audit", "vulnerability", "scan", "secret"],
            "devops": ["deploy", "docker", "kubernetes", "ci", "pipeline", "infra"],
            "qa": ["test", "coverage", "e2e", "quality", "regression"],
            "data": ["database", "query", "migration", "index", "analytics"],
            "marketing": ["seo", "content", "campaign", "email", "social"],
            "sales": ["lead", "proposal", "pipeline", "forecast", "pricing"],
            "executive": ["strategy", "okr", "board", "competitive", "decision"],
        }

        for domain, keywords in domain_keywords.items():
            if any(kw in goal_lower for kw in keywords):
                agent_type = DOMAIN_AGENT_DEFAULTS.get(domain, "general")
                tasks.append(
                    PlanTask(
                        task_id=f"task-{len(tasks)+1}",
                        name=f"{domain}: {goal[:80]}",
                        description=goal,
                        domain=domain,
                        agent_type=agent_type,
                    )
                )

        if not tasks:
            tasks.append(
                PlanTask(
                    task_id="task-1",
                    name=f"general: {goal[:80]}",
                    description=goal,
                    domain="engineering",
                    agent_type="developer",
                )
            )

        return tasks


@dataclass(frozen=True)
class PlannerResult:
    """Immutable result from the planner loop."""

    status: str  # "ok", "max_replans_reached", "model_unavailable"
    output: str = ""
    iterations: int = 1
    steps_executed: int = 0


class PlannerLoop:
    """Plan -> Execute -> Critique loop with stop-gate."""

    def __init__(
        self,
        router: Any,
        tier: str = "reasoning_fast",
        max_replans: int = MAX_REPLANS,
        max_steps: int = MAX_STEPS_PER_PLAN,
    ) -> None:
        self._router = router
        self._tier = tier
        self._max_replans = max_replans
        self._max_steps = max_steps

    async def run(self, goal: str) -> PlannerResult:
        """Execute the planner loop for a goal."""
        plan = await self._create_plan(goal)
        total_steps = 0

        for iteration in range(1, self._max_replans + 2):  # +1 for initial, +1 for range
            # Execute plan steps
            step_results = []
            steps = plan.get("steps", [])[:self._max_steps]

            for step in steps:
                result = await self._execute_step(step)
                step_results.append(result)
                total_steps += 1

            # Critique results
            critique = await self._critique(goal, plan, step_results)

            if critique.get("approved", False):
                logger.info("plan_approved", iteration=iteration, steps=total_steps)
                return PlannerResult(
                    status="ok",
                    output="\n".join(step_results),
                    iterations=iteration,
                    steps_executed=total_steps,
                )

            # Critic rejected — check if we can replan
            if iteration > self._max_replans:
                logger.warning("max_replans_reached", iterations=iteration)
                return PlannerResult(
                    status="max_replans_reached",
                    output="\n".join(step_results),
                    iterations=iteration,
                    steps_executed=total_steps,
                )

            # Revise plan
            revised = critique.get("revised_plan")
            if revised:
                plan = revised
            else:
                plan = await self._create_plan(
                    f"{goal}\n\nPrevious attempt was rejected: {critique.get('reason', 'unknown')}"
                )

            logger.info("plan_revised", iteration=iteration, reason=critique.get("reason"))

        return PlannerResult(
            status="max_replans_reached",
            iterations=self._max_replans + 1,
            steps_executed=total_steps,
        )

    async def _create_plan(self, goal: str) -> dict[str, Any]:
        """Ask the LLM to create a plan for the goal."""
        messages = [
            {
                "role": "user",
                "content": (
                    f"Create a plan to accomplish this goal:\n{goal}\n\n"
                    f"Respond with JSON: "
                    f'{{"steps": [{{"id": "s1", "action": "...", "input": "..."}}]}}'
                ),
            }
        ]
        response = await self._router.complete(tier=self._tier, messages=messages)
        try:
            return json.loads(response.content)
        except (json.JSONDecodeError, TypeError):
            return {"steps": [{"id": "s1", "action": "execute", "input": goal}]}

    async def _execute_step(self, step: dict[str, Any]) -> str:
        """Execute a single plan step via the LLM."""
        messages = [
            {
                "role": "user",
                "content": f"Execute step: {step.get('action', 'unknown')} with input: {step.get('input', '')}",
            }
        ]
        response = await self._router.complete(tier=self._tier, messages=messages)
        return response.content

    async def _critique(
        self, goal: str, plan: dict[str, Any], results: list[str]
    ) -> dict[str, Any]:
        """Ask the critic to evaluate the execution results."""
        messages = [
            {
                "role": "user",
                "content": (
                    f"Critique the following execution against the goal.\n"
                    f"Goal: {goal}\n"
                    f"Plan: {json.dumps(plan)}\n"
                    f"Results: {json.dumps(results)}\n\n"
                    f"Respond with JSON: "
                    f'{{"approved": true/false, "reason": "...", "revised_plan": {{...}} or null}}'
                ),
            }
        ]
        response = await self._router.complete(tier=self._tier, messages=messages)
        try:
            return json.loads(response.content)
        except (json.JSONDecodeError, TypeError):
            return {"approved": True, "reason": "Unable to parse critique, accepting"}
