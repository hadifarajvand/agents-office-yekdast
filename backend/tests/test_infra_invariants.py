"""Static checks on the infrastructure files. They fail if an edit weakens an isolation
property the plan depends on (see PLAN.md sections 5 and 7)."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def compose():
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text())


def test_job_network_is_internal_and_named_as_the_sandbox_expects():
    from app.config import load_config
    net = compose()["networks"]["ao-internal"]
    assert net["internal"] is True and net["name"] == load_config().sandbox["network"]


def test_only_egress_and_gateway_bridge_the_job_network_to_the_outside():
    c = compose()
    internal = {n for n, s in c["services"].items() if "ao-internal" in (s.get("networks") or [])}
    assert internal == {"egress", "router-gateway"}
    for n in internal:
        assert "ao-egress" in c["services"][n]["networks"]


def test_published_ports_are_loopback_only():
    for name, svc in compose()["services"].items():
        for p in svc.get("ports", []):
            assert str(p).startswith("127.0.0.1:"), f"{name} publishes {p} beyond loopback"


def test_the_app_never_mounts_the_real_docker_socket():
    c = compose()["services"]
    assert not any("docker.sock" in v for v in c["app"].get("volumes", []))
    assert any("docker.sock" in v and v.endswith(":ro") for v in c["docker-proxy"]["volumes"])
    env = c["docker-proxy"]["environment"]
    assert env["EXEC"] == 0 and env["IMAGES"] == 0 and env["BUILD"] == 0 and env["NETWORKS"] == 0


def test_app_and_proxy_are_opt_in_and_postgres_has_a_healthcheck():
    c = compose()["services"]
    assert c["app"]["profiles"] == ["app"] and c["docker-proxy"]["profiles"] == ["app"]
    assert "healthcheck" in c["postgres"] and "healthcheck" in c["app"]
    assert "redis" not in c


def test_egress_allowlist_is_small_and_has_no_wildcard_everything():
    lines = [ln.strip() for ln in (ROOT / "infra/egress/allowlist.txt").read_text().splitlines()
             if ln.strip() and not ln.startswith("#")]
    assert 1 <= len(lines) <= 8
    assert "registry.npmjs.org" in lines and not any(x in (".com", "*", ".") for x in lines)
    squid = (ROOT / "infra/egress/squid.conf").read_text()
    assert "http_access deny all" in squid and squid.index("deny all") > squid.index("allow CONNECT allowed_domains")


def test_router_gateway_exposes_only_the_model_api_and_adds_the_key():
    t = (ROOT / "infra/router-gateway/default.conf.template").read_text()
    assert "location /v1/" in t and "location / { return 404; }" in t
    assert "Bearer ${ROUTER_API_KEY}" in t


def test_job_entrypoint_never_runs_agent_code_on_the_host_and_makes_the_artifacts():
    s = (ROOT / "infra/sandbox/run-job.sh").read_text()
    for needle in ("patch.bundle", "tree.tar.gz", "npm-audit.json", "core.hooksPath=/dev/null", "run-checks.mjs"):
        assert needle in s


def test_no_job_image_runs_as_root():
    for f in (ROOT / "infra/sandbox").glob("*.Dockerfile"):
        assert "USER 1000:1000" in f.read_text(), f.name
    assert "USER office" in (ROOT / "Dockerfile").read_text()


def test_env_example_has_no_real_looking_secrets_and_covers_every_secret_the_config_names():
    from app.config import load_config
    text = (ROOT / ".env.example").read_text()
    cfg = load_config()
    for name in (cfg.router["api_key_env"], cfg.dokploy["url_env"], cfg.dokploy["api_key_env"], cfg.dokploy["preview_domain_env"],
                 cfg.dokploy["source_repo_env"], cfg.dokploy["source_token_env"], cfg.github["token_env"], cfg.api["token_env"]):
        assert f"{name}=" in text, name
    import re
    assert not re.search(r"(ghp_|sk-ant-|xox[bp]-|AKIA)", text)


def test_dokploy_script_is_a_dry_run_unless_applied_and_proves_closure_from_outside():
    s = (ROOT / "infra/dokploy/harden-almalinux.sh").read_text()
    assert 'APPLY=0' in s and '"--apply"' in s and "DOCKER-USER" in s and "SERVER_PUBLIC_IP:3000" in s
