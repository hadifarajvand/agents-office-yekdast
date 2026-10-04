import json

from app.worker.claude_code import ClaudeCodeWorker

STREAM = "\n".join(json.dumps(e) for e in [
    {"type": "system", "subtype": "init", "model": "haiku", "tools": ["Bash", "Edit"]},
    {"type": "assistant", "message": {"content": [{"type": "text", "text": "plan"},
                                                  {"type": "tool_use", "name": "Bash", "input": {"command": "npm test"}}]}},
    {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok", "is_error": False}]}},
    {"type": "result", "subtype": "success", "is_error": False, "num_turns": 2, "duration_ms": 9, "result": "done",
     "usage": {"input_tokens": 5, "output_tokens": 7}, "modelUsage": {"haiku": {}}, "total_cost_usd": 0.01},
]) + "\nnot json\n"


def test_trace_digest_and_parse_still_work(tmp_path):
    w = ClaudeCodeWorker()
    p = w.trace(STREAM, tmp_path)
    rows = [json.loads(x) for x in open(p)]
    assert [r["t"] for r in rows] == ["init", "say", "tool", "result", "final"]
    assert rows[2]["name"] == "Bash" and "npm test" in rows[2]["input"]
    meta = w.parse(STREAM, tmp_path)
    assert meta["tokens_out"] == 7 and meta["models_seen"] == ["haiku"]
    assert "stream-json" in w.argv({}) and "--verbose" in w.argv({})
