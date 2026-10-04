"""Model layer: every LLM call goes through the local 9router proxy.

- `router.format` picks the wire format: "openai" (ChatOpenAI -> {base_url}/v1/chat/completions)
  or "anthropic" (ChatAnthropic -> {base_url}/v1/messages). base_url never ends in /v1;
  each client adds its own path, which avoids the doubled "/v1/v1" of the old setup.
- Models are pinned: callers pass a router model id (from a pipeline role, see
  `role_model`) or an office key (haiku/sonnet/opus/fable, see models.model_id).
- Every response is metered. The meter records tokens and the model the router says
  actually answered (`model_seen`). 9router can silently fall back to another model;
  a mismatch marks the run invalid so a verdict cannot rest on an unknown model.
- Budget: a meter with a USD cap raises BudgetExceeded once estimated spend passes it.
"""
from __future__ import annotations

import contextvars
import json
import re
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from .config import load_config
from .models import model_id


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class Call:
    model_pinned: str
    model_seen: str
    input_tokens: int
    output_tokens: int
    usd: float


@dataclass
class RunMeter:
    """Token and model accounting for one run (a task, a job stage, a chat turn)."""
    label: str = ""
    usd_cap: float | None = None
    calls: list[Call] = field(default_factory=list)
    mismatches: list[str] = field(default_factory=list)

    @property
    def tokens(self) -> int:
        return sum(c.input_tokens + c.output_tokens for c in self.calls)

    @property
    def usd(self) -> float:
        return round(sum(c.usd for c in self.calls), 6)

    @property
    def valid(self) -> bool:
        return not self.mismatches

    def summary(self) -> dict:
        return {"label": self.label, "calls": len(self.calls), "tokens": self.tokens, "usd": self.usd,
                "models": sorted({c.model_seen or c.model_pinned for c in self.calls}),
                "mismatches": list(self.mismatches), "valid": self.valid}


current_meter: contextvars.ContextVar[RunMeter | None] = contextvars.ContextVar("current_meter", default=None)

# Callbacks notified after every metered call (main.py registers a DB writer).
_usage_hooks: list[Callable[[Call, str], Awaitable[None]]] = []


def on_usage(fn: Callable[[Call, str], Awaitable[None]]) -> None:
    _usage_hooks.append(fn)


def role_model(role: str) -> str:
    """Router model id pinned for a pipeline role (builder, research, lead_review...)."""
    roles = load_config().roles
    return roles.get(role) or roles.get("drafts") or model_id(None)


def resolve_model(model_key: str | None = None, model: str | None = None, role: str | None = None) -> str:
    if model:
        return model
    if role:
        return role_model(role)
    return model_id(model_key)


def price(model: str, tokens_in: int, tokens_out: int = 0) -> float:
    """Estimated USD for one call or one worker run: budget.usd_per_mtok[model] (or its "default"),
    USD per million input/output tokens. A model missing from the table is never free."""
    table = load_config().budget.get("usd_per_mtok") or {}
    rate = table.get(model) or table.get(model.split("/")[-1]) or table.get("default") or {"in": 1.0, "out": 5.0}
    return round((float(rate.get("in", 0)) * tokens_in + float(rate.get("out", 0)) * tokens_out) / 1e6, 6)


def same_model(pinned: str, seen: str) -> bool:
    """Routers often report the upstream name without their provider prefix
    ("cc/claude-haiku-4-5" -> "claude-haiku-4-5"). Treat those as the same model;
    anything else is a substitution."""
    if not seen:
        return True  # router did not report a model; cannot prove a swap
    def core(s: str) -> str:
        s = s.lower().split("/")[-1]
        return re.sub(r"\[.*?\]$", "", s)
    a, b = core(pinned), core(seen)
    return a == b or a.startswith(b) or b.startswith(a)


def _client(model: str, max_tokens: int):
    cfg = load_config()
    base = cfg.router.get("base_url", "").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    key = cfg.secret("router") or "none"
    timeout = cfg.router.get("timeout_s", 120)
    if cfg.router.get("format") == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, anthropic_api_url=base, anthropic_api_key=key,
                             max_tokens=max_tokens, timeout=timeout)
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=model, base_url=f"{base}/v1", api_key=key, max_tokens=max_tokens,
                      timeout=timeout, stream_usage=True)


async def _record(resp, pinned: str) -> None:
    meta = getattr(resp, "response_metadata", None) or {}
    seen = str(meta.get("model_name") or meta.get("model") or "")
    usage = getattr(resp, "usage_metadata", None) or {}
    tin, tout = int(usage.get("input_tokens", 0) or 0), int(usage.get("output_tokens", 0) or 0)
    call = Call(pinned, seen, tin, tout, price(pinned, tin, tout))
    meter = current_meter.get()
    if meter is not None:
        meter.calls.append(call)
        if not same_model(pinned, seen):
            meter.mismatches.append(f"pinned {pinned}, router answered with {seen}")
    for hook in _usage_hooks:
        try:
            await hook(call, meter.label if meter else "")
        except Exception:
            pass
    if meter is not None and meter.usd_cap is not None and meter.usd > meter.usd_cap:
        raise BudgetExceeded(f"{meter.label or 'run'} spent ${meter.usd:.4f}, over the ${meter.usd_cap:.2f} cap")


def _text(resp) -> str:
    c = resp.content
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in c)
    return str(c)


async def ask(system: str, user: str, *, model_key: str | None = None, model: str | None = None,
              role: str | None = None, max_tokens: int = 4096) -> str:
    """Plain text completion."""
    mid = resolve_model(model_key, model, role)
    resp = await _client(mid, max_tokens).ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
    await _record(resp, mid)
    return _text(resp)


async def ask_json(system: str, user: str, *, role: str = "router", max_tokens: int = 1024) -> dict:
    return parse_json(await ask(system, user, role=role, max_tokens=max_tokens))


async def ask_haiku_json(system: str, user: str) -> dict:
    """The task router hop. Kept under its historical name; the model is the
    pinned "router" role, not necessarily Haiku."""
    return await ask_json(system, user, role="router", max_tokens=512)


async def ask_with_tools(messages: list[dict], tools: list, *, model_key: str | None = None,
                         model: str | None = None, role: str | None = None, max_tokens: int = 4096) -> dict:
    """One step of a tool-calling loop. `messages` are role-tagged dicts
    ({"role": system|user|assistant|tool, ...}). Returns {"content", "tool_calls"};
    empty tool_calls means the model is done."""
    mid = resolve_model(model_key, model, role)
    llm = _client(mid, max_tokens)
    if tools:
        llm = llm.bind_tools(tools)
    lc = []
    for m in messages:
        r = m["role"]
        if r == "system":
            lc.append(SystemMessage(content=m["content"]))
        elif r == "user":
            lc.append(HumanMessage(content=m["content"]))
        elif r == "assistant":
            lc.append(AIMessage(content=m.get("content") or "", tool_calls=m.get("tool_calls") or []))
        elif r == "tool":
            lc.append(ToolMessage(content=str(m["content"]), tool_call_id=m["tool_call_id"]))
    resp = await llm.ainvoke(lc)
    await _record(resp, mid)
    calls = [{"name": tc["name"], "args": tc["args"], "id": tc["id"]} for tc in (resp.tool_calls or [])]
    return {"content": _text(resp), "tool_calls": calls}


def parse_json(text: str) -> dict:
    t = re.sub(r"^```(json)?|```$", "", str(text).strip(), flags=re.MULTILINE).strip()
    m = re.search(r"\{.*\}", t, re.DOTALL)
    if not m:
        raise ValueError(f"no JSON object found in: {str(text)[:200]}")
    return json.loads(m.group(0))
