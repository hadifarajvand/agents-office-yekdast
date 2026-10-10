"""The validate lane: web research with verified quotes and a verdict computed by code.

Pinned down here:
  - a claim survives only if its quote is really on the fetched page;
  - the verdict comes from the rubric: no search tool => TEST, never GO; thin evidence after a
    sufficient search => NO-GO; enough independent evidence => GO;
  - the built-in fetch refuses private, loopback and link-local targets;
  - a validate job runs intake -> research -> owner, and only a finished validate job can seed
    an own-idea build job.
"""
from __future__ import annotations

import asyncio

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app import db
from app.config import load_config
from app.connectors import web as webmod
from app.pipeline import exposure as exp
from app.pipeline import jobs
from app.pipeline.api import thread
from app.pipeline.graph import compile_pipeline
from app.pipeline.ports import Deps, set_deps
from app.pipeline.research import compute_verdict, verify_claims

PAGE = ("Acme Bakeries Pro costs $49 per month and is used by 1,200 bakeries. "
        "I spend two hours every morning copying phone orders into a spreadsheet and it is killing me.")


def claim(gate, subject, tier="none", specific=False, url="https://a.example/x", quote="costs $49 per month"):
    return {"gate": gate, "subject": subject, "claim": "c", "tier": tier, "specific": specific, "quote": quote, "url": url, "type": "FACT"}


# ---------- claims are checked against the page ----------

def test_a_claim_is_kept_only_if_its_quote_is_on_the_page():
    raw = [{"gate": "D1", "subject": "Acme", "tier": "T2", "quote": "costs $49   per month"},
           {"gate": "D1", "subject": "Ghost", "tier": "T1", "quote": "made ten million dollars last year"},
           {"gate": "D9", "subject": "x", "quote": "used by 1,200 bakeries"},
           "not a dict"]
    kept, dropped = verify_claims(raw, "https://a.example/x", PAGE)
    assert [c["subject"] for c in kept] == ["Acme"] and dropped == 3
    assert kept[0]["url"] == "https://a.example/x"


def test_a_long_quote_is_dropped():
    kept, dropped = verify_claims([{"gate": "D2", "quote": PAGE}], "https://a.example", PAGE)
    assert kept == [] and dropped == 1


# ---------- the rubric as code ----------

def strong_evidence():
    out = [claim("D1", f"comp{i}", tier="T2", url=f"https://c{i}.example") for i in range(5)]
    out += [claim("D2", "", specific=True, url=f"https://forum{i % 4}.example/p{i}", quote=f"post number {i} about pain")
            for i in range(11)]
    out += [claim("A1", "r/bakers"), claim("A3", "price")]
    return out


SUFFICIENT = {"search_available": True, "queries": 8, "fetched": 12}


def test_no_search_tool_can_only_give_test_even_with_strong_pages():
    r = compute_verdict(strong_evidence(), {"search_available": False, "queries": 0, "fetched": 12})
    assert r["verdict"] == "TEST" and any("no web search" in x for x in r["reasons"])


def test_strong_independent_evidence_after_a_sufficient_search_is_go():
    r = compute_verdict(strong_evidence(), SUFFICIENT)
    assert r["verdict"] == "GO" and r["confidence"] == "HIGH" and r["gates"] == {"D1": "PASS", "D2": "PASS", "A": "PASS"}


def test_thin_evidence_after_a_sufficient_search_is_no_go():
    r = compute_verdict([claim("D1", "only-one", tier="T2")], SUFFICIENT)
    assert r["verdict"] == "NO-GO" and r["gates"]["D1"] == "FAIL"


def test_thin_evidence_after_an_insufficient_search_is_unknown_so_test():
    r = compute_verdict([claim("D1", "only-one", tier="T2")], {"search_available": True, "queries": 2, "fetched": 1})
    assert r["verdict"] == "TEST" and r["gates"]["D1"] == "UNKNOWN"


def test_missing_audience_evidence_never_fails_but_blocks_go():
    ev = [c for c in strong_evidence() if c["gate"] != "A3"]
    r = compute_verdict(ev, SUFFICIENT)
    assert r["gates"]["A"] == "UNKNOWN" and r["verdict"] == "TEST"


def test_free_competitors_do_not_count_as_revenue_evidence():
    ev = [claim("D1", f"free{i}", tier="none") for i in range(6)]
    r = compute_verdict(ev, SUFFICIENT)
    assert r["counts"]["with_revenue"] == 0 and r["gates"]["D1"] == "FAIL"


# ---------- the built-in fetch ----------

@pytest.mark.parametrize("url", ["http://127.0.0.1:4520/api/jobs", "http://localhost/", "http://169.254.169.254/latest",
                                 "http://10.0.0.5/", "file:///etc/passwd", "http://user:pw@example.com/"])
def test_fetch_refuses_local_and_private_targets(url):
    with pytest.raises(webmod.WebRefused):
        webmod.check_url(url)


def test_search_results_are_normalised_from_common_shapes():
    assert webmod._results({"results": [{"title": "T", "link": "https://x.example"}]})[0]["url"] == "https://x.example"
    assert webmod._results('[{"url": "https://y.example", "description": "d"}]')[0]["snippet"] == "d"
    assert webmod._results("see https://z.example/a and https://z.example/a")[0]["url"] == "https://z.example/a"


def test_html_is_reduced_to_text():
    t = webmod.html_to_text("<html><head><title>x</title><script>evil()</script></head><body><p>Hello&amp;bye</p></body></html>")
    assert t == "Hello&bye"


def test_webtool_refuses_a_private_url_even_for_an_mcp_fetch_server_and_audits_it():
    seen = []

    async def audit(op, res, ok, reason):
        seen.append((op, ok))

    async def mcp_fetch(url):
        raise AssertionError("must not be called")
    tool = webmod.WebTool(None, mcp_fetch, audit)
    with pytest.raises(webmod.WebRefused):
        asyncio.run(tool.fetch("http://127.0.0.1:5432/"))
    assert seen == [("fetch", False)]


# ---------- the lane end to end ----------

class FakeWeb:
    can_search = True
    can_fetch = True

    def __init__(self):
        self.searches, self.fetches = [], []

    async def search(self, q, n=8):
        self.searches.append(q)
        return [{"title": "t", "url": f"https://site{len(self.searches)}.example/page", "snippet": ""}]

    async def fetch(self, url):
        self.fetches.append(url)
        return {"url": url, "status": 200, "text": PAGE * 3}


class ResearchScript:
    def __init__(self):
        self.calls = []

    async def chat_json(self, system, user, *, role="research"):
        self.calls.append(system[:40])
        if "Propose web search queries" in system:
            return {"queries": ["bakery order software", "bakery phone orders pain"]}
        if "extract market evidence" in system:
            return {"claims": [{"gate": "D1", "subject": "Acme Bakeries Pro", "tier": "T2", "quote": "costs $49 per month"},
                               {"gate": "D1", "subject": "Invented", "tier": "T1", "quote": "a sentence not on the page at all"}]}
        if "reviewing your own team's stage" in system:
            import re
            return {"verdict": "PASS", "reasons": ["memo is complete"], "cites": re.findall(r"id=(\S+)", user)[:1]}
        raise AssertionError("unscripted: " + system[:60])


@pytest.fixture
def lane(fake_db, tmp_path, monkeypatch):
    cfg = load_config()
    monkeypatch.setitem(cfg.sandbox, "jobs_dir", str(tmp_path / "jobs"))
    script, web = ResearchScript(), FakeWeb()
    set_deps(Deps(chat_json=script.chat_json, web=web))
    graph = compile_pipeline(InMemorySaver())
    yield type("Lane", (), dict(script=script, web=web, graph=graph))
    set_deps(None)


async def test_a_validate_job_researches_then_waits_for_the_owner_and_finishes(lane):
    brief = {"title": "Bakery order inbox", "description": "Turn phone and Instagram orders into one list for small bakeries."}
    job = jobs.new_job("own", brief["title"], brief, lane="validate")
    await db.save_job(job)
    await lane.graph.ainvoke({"job_id": job["id"], "kind": "own", "lane": "validate", "brief": brief, "requested_tier": 0,
                              "loops": {}, "feedback": "", "route": ""}, config=thread(job["id"]))
    j = await db.get_job(job["id"])
    assert j["status"] == "waiting" and j["pending"][0]["stage"] == "research"
    assert set(j["pending"][0]["roles"]) == {exp.OWNER}  # exec-ceo-strategist already passed it
    memo = [e for e in await db.list_evidence(job["id"]) if e["kind"] == "memo"][0]
    assert memo["body"]["verdict"] == "TEST"  # two queries are not a sufficient search
    assert [c["subject"] for c in memo["body"]["claims"]] == ["Acme Bakeries Pro", "Acme Bakeries Pro"]
    assert memo["body"]["run_log"]["claims_dropped"] == 2  # the invented claim, once per page
    assert lane.web.searches and lane.web.fetches
    await db.record_approval(job["id"], "research", exp.OWNER, "PASS", "", [], exp.OWNER)
    await lane.graph.ainvoke(Command(resume={"owner": "PASS"}), config=thread(job["id"]))
    assert (await db.get_job(job["id"]))["status"] == "done"


def test_the_api_takes_an_own_idea_into_the_validate_lane_and_guards_the_build(fake_db, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.pipeline import api as api_mod
    started = []
    monkeypatch.setattr(api_mod, "_spawn", lambda coro: (started.append(1), coro.close()))
    c = TestClient(app, headers={"X-AO-Client": "office", "Origin": "http://localhost:4520"})
    r = c.post("/api/jobs", json={"kind": "own", "title": "Bakery inbox", "description": "x" * 40})
    assert r.status_code == 200 and r.json()["lane"] == "validate" and [s["name"] for s in r.json()["stages"]] == ["intake", "research"]
    r = c.post("/api/jobs", json={"kind": "own", "lane": "build", "title": "Bakery inbox", "description": "x" * 40})
    assert r.status_code == 400 and "validate job" in r.json()["error"]
