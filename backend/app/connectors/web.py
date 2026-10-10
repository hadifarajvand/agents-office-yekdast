"""Web access for the research stage only (validate lane). Runs on the host, never in a job
container, and never in a stage that holds client code (PLAN.md section 5, rule 6).

Two sources, configured in office.config.json "web":
  - an MCP server the owner already runs (keyless search and/or fetch), bound by command:
        "web": {"search": {"command": ["npx", "-y", "<server>"], "tool": "<tool name>", "arg": "query"},
                "fetch":  {"command": [...], "tool": "fetch", "arg": "url"}}
    The tool names and argument keys of the owner's server are not known here (laptop S1b).
  - a built-in fetch (httpx) used when no fetch server is configured. There is no built-in
    search: without a search tool the memo says so and the verdict cannot leave UNKNOWN/TEST.

Every call is audited before it runs. The built-in fetch refuses anything that resolves to a
private, loopback or link-local address (no reaching the owner's machine or LAN), follows at
most 4 redirects (each re-checked), stops after MAX_BYTES and keeps plain text only.
"""
from __future__ import annotations

import asyncio
import html
import ipaddress
import json
import logging
import re
import socket
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

log = logging.getLogger("agents_office.web")

MAX_BYTES = 1_500_000
TEXT_CHARS = 12_000
UA = "Mozilla/5.0 (compatible; AgentsOfficeResearch/1.0)"


class WebRefused(ValueError):
    pass


def _public_host(host: str) -> None:
    """Raise unless every address the host resolves to is public."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise WebRefused(f"cannot resolve {host}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise WebRefused(f"{host} resolves to a non-public address")


def check_url(url: str) -> str:
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise WebRefused("only http(s) URLs can be fetched")
    if u.username or u.password:
        raise WebRefused("URLs with credentials are refused")
    _public_host(u.hostname)
    return url


def html_to_text(body: str) -> str:
    body = re.sub(r"(?is)<(script|style|noscript|svg|head)[^>]*>.*?</\1>", " ", body)
    body = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h[1-6]|tr)>", "\n", body)
    body = re.sub(r"<[^>]+>", " ", body)
    body = html.unescape(body)
    body = re.sub(r"[ \t\r\f\v]+", " ", body)
    return re.sub(r"\n\s*\n+", "\n", body).strip()


class HttpFetch:
    def __init__(self, client: httpx.AsyncClient | None = None, resolve=True):
        self._client, self._resolve = client, resolve

    async def fetch(self, url: str) -> dict:
        client = self._client or httpx.AsyncClient(timeout=15, follow_redirects=False, headers={"User-Agent": UA})
        try:
            for _ in range(5):
                if self._resolve:
                    await asyncio.to_thread(check_url, url)
                async with client.stream("GET", url) as r:
                    if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                        url = urljoin(url, r.headers["location"])
                        continue
                    buf = b""
                    async for chunk in r.aiter_bytes():
                        buf += chunk
                        if len(buf) > MAX_BYTES:
                            break
                    ctype = r.headers.get("content-type", "")
                    text = buf.decode(r.encoding or "utf-8", "replace")
                    if "html" in ctype or text.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
                        text = html_to_text(text)
                    return {"url": url, "status": r.status_code, "text": text[:TEXT_CHARS]}
            raise WebRefused("too many redirects")
        finally:
            if self._client is None:
                await client.aclose()


def _results(raw: Any) -> list[dict]:
    """Normalise whatever a search tool returns into [{title, url, snippet}]."""
    if isinstance(raw, list) and raw and isinstance(raw[0], dict) and "text" in raw[0] and "url" not in raw[0]:
        raw = "\n".join(str(b.get("text", "")) for b in raw)
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return [{"title": "", "url": u, "snippet": ""} for u in dict.fromkeys(re.findall(r"https?://[^\s)\]>\"']+", raw))]
    if isinstance(raw, dict):
        raw = raw.get("results") or raw.get("items") or raw.get("data") or []
    out = []
    for r in raw if isinstance(raw, list) else []:
        if isinstance(r, dict):
            url = r.get("url") or r.get("link") or r.get("href")
            if url:
                out.append({"title": str(r.get("title", ""))[:200], "url": str(url),
                            "snippet": str(r.get("snippet") or r.get("description") or r.get("content") or "")[:400]})
    return out


class WebTool:
    """search(q) and fetch(url) for the research stage, audited, with per-job call caps set by the caller."""

    def __init__(self, search_fn=None, fetch_fn=None, audit=None):
        self._search, self._fetch, self._audit = search_fn, fetch_fn, audit

    @property
    def can_search(self) -> bool:
        return self._search is not None

    @property
    def can_fetch(self) -> bool:
        return self._fetch is not None

    async def _log(self, op: str, resource: str, ok: bool, reason: str = "") -> None:
        if self._audit:
            try:
                await self._audit(op, resource, ok, reason)
            except Exception:
                log.exception("audit write failed")

    async def search(self, query: str, n: int = 8) -> list[dict]:
        if not self._search:
            return []
        await self._log("search", query[:200], True)
        return _results(await self._search(query))[:n]

    async def fetch(self, url: str) -> dict:
        if not self._fetch:
            raise WebRefused("no fetch tool")
        try:  # checked for every source: an MCP fetch server also runs on the owner's machine
            await asyncio.to_thread(check_url, url)
        except WebRefused as e:
            await self._log("fetch", url[:300], False, str(e))
            raise
        await self._log("fetch", url[:300], True)
        res = await self._fetch(url)
        if isinstance(res, dict):
            return {"url": res.get("url", url), "status": int(res.get("status", 200)), "text": str(res.get("text", ""))[:TEXT_CHARS]}
        text = res if isinstance(res, str) else "\n".join(str(b.get("text", "")) for b in res) if isinstance(res, list) else str(res)
        return {"url": url, "status": 200, "text": html_to_text(text)[:TEXT_CHARS]}


def from_config(cfg) -> WebTool:
    from .. import db
    from .mcp_client import McpSession
    web = cfg.web or {}

    async def audit(op, resource, ok, reason):
        await db.audit("exec-ceo-strategist", "exec", "web", op, resource, ok, reason)

    def mcp_call(spec: dict, name: str):
        cmd = spec["command"]
        session = McpSession(f"web-{name}", {"transport": "stdio", "command": cmd[0], "args": cmd[1:],
                                             "env": {k: v for k, v in (spec.get("env") or {}).items()}})
        tool, arg = spec.get("tool", name), spec.get("arg", "query" if name == "search" else "url")

        async def call(value: str):
            return await session.invoke(tool, {arg: value})
        return call

    search = mcp_call(web["search"], "search") if (web.get("search") or {}).get("command") else None
    if (web.get("fetch") or {}).get("command"):
        fetch = mcp_call(web["fetch"], "fetch")
    else:
        built_in = HttpFetch()
        fetch = built_in.fetch
    return WebTool(search, fetch, audit)
