"""T2.2: the built-in fetch never reaches a private address, directly, by redirect, or by rebinding."""
import asyncio

import httpx
import pytest

from app.connectors import web


def _dns(monkeypatch, table):
    def fake(host, port, *a, **k):
        return [(2, 1, 6, "", (table[host], 0))]
    monkeypatch.setattr(web.socket, "getaddrinfo", fake)


def test_a_public_url_that_redirects_to_localhost_is_refused(monkeypatch):
    _dns(monkeypatch, {"good.example": "93.184.216.34", "localhost": "127.0.0.1"})

    def handler(req):
        return httpx.Response(302, headers={"location": "http://localhost/admin"})
    f = web.HttpFetch(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    with pytest.raises(web.WebRefused):
        asyncio.run(f.fetch("http://good.example/"))


@pytest.mark.parametrize("ip", ["10.0.0.5", "169.254.169.254", "100.64.0.1", "::ffff:127.0.0.1", "0.0.0.0", "192.0.0.1"])
def test_non_global_addresses_are_refused(monkeypatch, ip):
    _dns(monkeypatch, {"x.example": ip})
    with pytest.raises(web.WebRefused):
        web.check_url("http://x.example/")


def test_the_connection_is_pinned_to_the_validated_ip(monkeypatch):
    _dns(monkeypatch, {"good.example": "93.184.216.34"})
    url, extra = web._pin("https://good.example:8443/p?q=1")
    assert url == "https://93.184.216.34:8443/p?q=1"
    assert extra["headers"]["Host"] == "good.example:8443" and extra["extensions"]["sni_hostname"] == "good.example"
