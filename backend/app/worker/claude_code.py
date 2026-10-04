"""Claude Code in headless mode (`claude --bare -p ... --output-format json`).

Model access: ANTHROPIC_BASE_URL points at the router gateway (which holds the real
key); the container only sees a placeholder key. Every model alias is pinned to the
builder role so background calls cannot use another model.

UNVERIFIED until the laptop bake-off: --max-turns, the `modelUsage` key in the JSON
result, and 9router's Anthropic endpoint. `models_seen` comes from modelUsage when
present, so a swapped model is detected; if the key is missing the field stays empty
and the run is not provably clean (the bake-off must confirm the key exists).
"""
from __future__ import annotations

from ..config import load_config
from .base import ContainerWorker


class ClaudeCodeWorker(ContainerWorker):
    kind = "claude_code"
    image_key = "claude_code"

    def argv(self, limits):
        model = limits.get("model") or load_config().roles["builder"]
        return ["claude", "--bare", "-p",
                "Read /workspace/TASK.md and carry out the task completely. Run the tests until they pass.",
                "--output-format", "json", "--model", model, "--max-turns", str(limits.get("max_turns", 80)),
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
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "DISABLE_AUTOUPDATER": "1", "DISABLE_TELEMETRY": "1",
        }

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
