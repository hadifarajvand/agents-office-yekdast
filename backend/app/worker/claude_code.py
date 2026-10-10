"""Claude Code in headless mode (`claude --bare -p ... --output-format stream-json --verbose`).

stream-json is one JSON event per line, so agent.stdout is the full log and survives a kill;
the last line is the same result object `json` gave. trace() digests it into out/trace.jsonl.
`--verbose` (required by stream-json with -p) and the event shapes are UNVERIFIED until the S2 run.

Model access: ANTHROPIC_BASE_URL points at the router gateway (which holds the real
key); the container only sees a placeholder key. Every model alias is pinned to the
builder role so background calls cannot use another model.

UNVERIFIED until the laptop bake-off: --max-turns, the `modelUsage` key in the JSON
result, and 9router's Anthropic endpoint. `models_seen` comes from modelUsage when
present, so a swapped model is detected; if the key is missing the field stays empty
and the run is not provably clean (the bake-off must confirm the key exists).
"""
from __future__ import annotations

import json
from pathlib import Path

from ..config import load_config
from .base import ContainerWorker


class ClaudeCodeWorker(ContainerWorker):
    kind = "claude_code"
    image_key = "claude_code"

    def argv(self, limits):
        model = limits.get("model") or load_config().roles["builder"]
        return ["claude", "--bare", "-p",
                "Read /workspace/TASK.md and carry out the task completely. Run the tests until they pass.",
                "--output-format", "stream-json", "--verbose", "--model", model, "--max-turns", str(limits.get("max_turns", 80)),
                "--dangerously-skip-permissions"]

    def env(self, limits):
        cfg = load_config()
        model = limits.get("model") or cfg.roles["builder"]
        return {
            "ANTHROPIC_BASE_URL": cfg.sandbox["router_gateway"],
            "ANTHROPIC_API_KEY": "placeholder", "ANTHROPIC_AUTH_TOKEN": "placeholder",
            "ANTHROPIC_MODEL": model, "ANTHROPIC_DEFAULT_HAIKU_MODEL": model,
            "ANTHROPIC_DEFAULT_SONNET_MODEL": model, "ANTHROPIC_DEFAULT_OPUS_MODEL": model,
            "ANTHROPIC_SMALL_FAST_MODEL": model,
            # Free router models (oc/*) stall for 8-13 s between stream chunks; Claude Code then falls back
            # to a non-streaming call, and 9router answers that in OpenAI format (not a Message), which
            # kills the run. Keep it on streaming, retry instead, and cap runaway generations.
            # Flag names confirmed present in the worker image CLI binary (2026-10-05).
            "CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK": "1", "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "8192",
            # nemotron answers a turn in about 2 s (big-pickle took 21-34 s), so a stalled stream is declared
            # dead after 60 s, a whole request after 3 min, and a failed call is retried 3 times, not 6.
            "API_TIMEOUT_MS": "180000", "CLAUDE_STREAM_IDLE_TIMEOUT_MS": "60000", "CLAUDE_CODE_MAX_RETRIES": "3",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "DISABLE_AUTOUPDATER": "1", "DISABLE_TELEMETRY": "1",
        }

    def trace(self, stdout, out_dir):
        """stream-json -> out/trace.jsonl: one short line per say / tool call / tool result."""
        def cut(v, n=400):
            s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
            return s if len(s) <= n else s[:n] + "…"
        rows = []
        for line in stdout.splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if not isinstance(e, dict):
                continue
            kind = e.get("type")
            if kind == "system" and e.get("subtype") == "init":
                rows.append({"t": "init", "model": e.get("model"), "tools": len(e.get("tools") or [])})
            elif kind in ("assistant", "user"):
                content = (e.get("message") or {}).get("content")
                for b in content if isinstance(content, list) else []:
                    bt = b.get("type")
                    if bt == "text" and kind == "assistant":
                        rows.append({"t": "say", "text": cut(b.get("text", ""))})
                    elif bt == "tool_use":
                        rows.append({"t": "tool", "name": b.get("name"), "input": cut(b.get("input", {}))})
                    elif bt == "tool_result":
                        c = b.get("content")
                        if isinstance(c, list):
                            c = " ".join(x.get("text", "") for x in c if isinstance(x, dict))
                        rows.append({"t": "result", "ok": not b.get("is_error"), "out": cut(c or "")})
            elif kind == "result":
                rows.append({"t": "final", "subtype": e.get("subtype"), "is_error": bool(e.get("is_error")),
                             "turns": e.get("num_turns"), "ms": e.get("duration_ms"), "text": cut(e.get("result", ""))})
        p = Path(out_dir) / "trace.jsonl"
        p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        return str(p)

    def parse(self, stdout, out_dir):
        d = self._last_json_line(stdout) or {}
        usage = d.get("usage") or {}
        n = lambda k: int(usage.get(k, 0) or 0)  # noqa: E731
        tin = n("input_tokens") + n("cache_creation_input_tokens")
        tout, cached = n("output_tokens"), n("cache_read_input_tokens")
        models = list((d.get("modelUsage") or {}).keys())
        return {"tokens": tin + tout + cached, "tokens_in": tin, "tokens_out": tout, "tokens_cached": cached,
                "usd": float(d.get("total_cost_usd", 0.0) or 0.0), "models_seen": models,
                "is_error": bool(d.get("is_error"))}
