"""Checks over /out/tree.tar.gz and /out/npm-audit.json, both produced INSIDE the build
container (infra/sandbox/run-job.sh). The host reads archive members in memory with size
caps and never extracts them or runs git, so a hostile repository cannot execute on the host.

Checks: secrets in files, credential files, tests exist and the app declares a test
script, a README, no oversized or binary blobs, and the npm audit (no high or critical
vulnerabilities in production dependencies).
"""
from __future__ import annotations

import asyncio
import json
import re
import tarfile
from pathlib import Path

from ..policy import _SECRET_PATTERNS

MAX_FILE = 1_000_000
MAX_TOTAL = 50_000_000
SKIP_DIRS = ("node_modules/", ".git/", ".next/")
ROOT_ONLY_SKIP = ("dist/", "build/", "coverage/")  # only at the tree root: a nested build/ may hold a secret
SKIP_NAMES = ("package-lock.json", "yarn.lock", "pnpm-lock.yaml")
CREDENTIAL_FILES = re.compile(r"(^|/)(\.env(\.[\w.-]+)?|id_rsa|id_ed25519|.*\.pem|.*\.key|.*\.p12|\.npmrc|\.netrc|credentials\.json)$")
ALLOWED_ENV = re.compile(r"\.env\.(example|sample|template)$")
TEST_FILE = re.compile(r"(^|/)(__tests__/|tests?/|e2e/)|\.(test|spec)\.[jt]sx?$")


def _norm(name: str) -> str:
    return name[2:] if name.startswith("./") else name


def _secret_hits(text: str) -> list[str]:
    hits = []
    for label, pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            hits.append(label)
    return sorted(set(hits))


def scan_tree(tar_path: Path) -> list[dict]:
    results: list[dict] = []
    secret_files: list[str] = []
    cred_files: list[str] = []
    big: list[str] = []
    names: list[str] = []
    pkg: dict | None = None
    total = 0
    with tarfile.open(tar_path, "r:gz") as tar:
        for m in tar:
            if not m.isfile():
                continue
            n = _norm(m.name)
            if any(n.startswith(d) for d in ROOT_ONLY_SKIP) or any(n.startswith(d) or f"/{d}" in f"/{n}" for d in SKIP_DIRS):
                continue
            names.append(n)
            total += m.size
            if total > MAX_TOTAL:
                big.append("archive exceeds the total size cap")
                break
            if CREDENTIAL_FILES.search(n) and not ALLOWED_ENV.search(n):
                cred_files.append(n)
            if m.size > MAX_FILE:
                big.append(f"{n} ({m.size // 1000} kB)")
                continue
            if Path(n).name in SKIP_NAMES:
                continue
            data = tar.extractfile(m).read()
            if b"\0" in data[:2048]:
                continue  # binary
            text = data.decode("utf-8", "replace")
            if n == "package.json":
                try:
                    pkg = json.loads(text)
                except ValueError:
                    pkg = {}
            if _secret_hits(text):
                secret_files.append(f"{n} ({', '.join(_secret_hits(text))})")
    results.append({"name": "no secrets in the code", "ok": not secret_files,
                    "detail": "clean" if not secret_files else "possible secrets in: " + "; ".join(secret_files[:10])})
    results.append({"name": "no credential files", "ok": not cred_files,
                    "detail": "clean" if not cred_files else "found: " + ", ".join(cred_files[:10])})
    has_tests = any(TEST_FILE.search(n) for n in names)
    has_script = bool(pkg and (pkg.get("scripts") or {}).get("test"))
    results.append({"name": "tests exist and the app declares a test script", "ok": has_tests and has_script,
                    "detail": f"test files: {has_tests}; scripts.test: {has_script}"})
    results.append({"name": "README present", "ok": any(n.lower() == "readme.md" for n in names), "detail": ""})
    results.append({"name": "no oversized files", "ok": not big, "detail": "ok" if not big else "; ".join(big[:10])})
    return results


def audit_result(path: Path) -> dict:
    if not path.exists():
        return {"name": "dependency audit", "ok": False, "detail": "no npm audit result was produced"}
    try:
        d = json.loads(path.read_text())
    except ValueError:
        return {"name": "dependency audit", "ok": False, "detail": "npm audit output was not valid JSON"}
    v = ((d.get("metadata") or {}).get("vulnerabilities")) or {}
    if not v and d.get("error"):
        return {"name": "dependency audit", "ok": False, "detail": f'npm audit failed: {str(d["error"])[:200]}'}
    if not all(k in v for k in ("high", "critical")):
        return {"name": "dependency audit", "ok": False, "detail": "npm audit output has no vulnerability counts"}
    bad = int(v.get("high", 0)) + int(v.get("critical", 0))
    return {"name": "dependency audit", "ok": bad == 0,
            "detail": f'{v.get("critical", 0)} critical, {v.get("high", 0)} high, {v.get("moderate", 0)} moderate, {v.get("low", 0)} low'}


class PatchChecks:
    async def scan(self, patch_path: str) -> list[dict]:
        out = Path(patch_path).parent
        tar = out / "tree.tar.gz"
        if not tar.exists():
            return [{"name": "build output is available", "ok": False, "detail": "no tree.tar.gz in the job output"}]
        try:
            res = await asyncio.to_thread(scan_tree, tar)
        except (tarfile.TarError, OSError) as e:
            return [{"name": "build output is readable", "ok": False, "detail": type(e).__name__}]
        res.append(audit_result(out / "npm-audit.json"))
        return res
