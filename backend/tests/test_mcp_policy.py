from app.mcp import MCPRegistry


def make_registry(deny=None, allow=None):
    r = MCPRegistry()
    r.configure({"mcp": {"allow": allow or [], "deny": deny or [], "departments": {}}, "tools": {"web": True}})
    return r


def test_denied_server_is_not_usable():
    r = make_registry(deny=["Stripe"])
    r.servers = [r._make("Stripe", "", "connected"), r._make("Gmail", "", "connected")]
    usable_names = [s["name"] for s in r.usable()]
    assert "Stripe" not in usable_names
    assert "Gmail" in usable_names


def test_allow_list_restricts_to_named_servers():
    r = make_registry(allow=["Gmail"])
    r.servers = [r._make("Stripe", "", "connected"), r._make("Gmail", "", "connected")]
    usable_names = [s["name"] for s in r.usable()]
    assert usable_names == ["Gmail"]


def test_no_connectors_falls_back_to_web_only_prompt():
    r = make_registry()
    text = r.prompt_text([])
    assert "web search and web fetch" in text
    assert "No business connectors" in text


def test_prompt_text_lists_usable_connectors_and_rules():
    r = make_registry()
    r.servers = [r._make("Gmail", "", "connected")]
    text = r.prompt_text([])
    assert "Gmail" in text
    assert "ONLY when the owner's request" in text
