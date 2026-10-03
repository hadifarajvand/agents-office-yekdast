from app.roster import DEPTS, boundaries_text, defaults, validate


def test_eight_departments_35_seats():
    assert len(DEPTS) == 8
    assert len(defaults()) == 35


def test_rejects_new_agent():
    r = validate({"agents": [{"id": "not-a-real-seat", "name": "X"}]})
    assert any("not one of the 35 seats" in p for p in r["problems"])


def test_department_and_lead_are_immutable():
    base = defaults()
    seat = base[0]
    r = validate({"agents": [{"id": seat.id, "department": "nowhere", "lead": not seat.lead}]}, base)
    assert any("department cannot change" in p for p in r["problems"])
    assert any("lead cannot change" in p for p in r["problems"])


def test_brief_trimmed_over_limit():
    base = defaults()
    seat = base[0]
    r = validate({"agents": [{"id": seat.id, "brief": "x" * 3000}]}, base)
    assert any("over 2000 characters" in p for p in r["problems"])
    updated = next(a for a in r["agents"] if a.id == seat.id)
    assert len(updated.brief) == 2000


def test_model_accepts_haiku_now_a_valid_choice():
    base = defaults()
    seat = base[0]
    r = validate({"agents": [{"id": seat.id, "model": "haiku"}]}, base)
    assert not any("must be sonnet, opus, fable or haiku" in p for p in r["problems"])
    updated = next(a for a in r["agents"] if a.id == seat.id)
    assert updated.model == "haiku"


def test_model_rejects_unknown_value():
    base = defaults()
    seat = base[0]
    r = validate({"agents": [{"id": seat.id, "model": "bogus"}]}, base)
    assert any("must be sonnet, opus, fable or haiku" in p for p in r["problems"])


def test_boundaries_parsed_and_capped():
    base = defaults()
    seat = base[0]
    r = validate({"agents": [{
        "id": seat.id,
        "boundaries": {
            "can": ["Draft replies"],
            "cannot": ["Access production systems", "x" * 300],
            "escalation": [{"condition": "a refund over $500", "target_agent": "invo"}],
        },
    }]}, base)
    updated = next(a for a in r["agents"] if a.id == seat.id)
    assert updated.boundaries["can"] == ["Draft replies"]
    assert updated.boundaries["cannot"][0] == "Access production systems"
    assert len(updated.boundaries["cannot"][1]) == 200
    assert updated.boundaries["escalation"] == [{"condition": "a refund over $500", "target_agent": "invo"}]


def test_boundaries_must_be_object():
    base = defaults()
    seat = base[0]
    r = validate({"agents": [{"id": seat.id, "boundaries": "not an object"}]}, base)
    assert any("boundaries must be an object" in p for p in r["problems"])


def test_boundaries_escalation_entry_needs_condition_and_target():
    base = defaults()
    seat = base[0]
    r = validate({"agents": [{
        "id": seat.id,
        "boundaries": {"escalation": [{"condition": "missing target"}]},
    }]}, base)
    assert any('need "condition" and "target_agent"' in p for p in r["problems"])
    updated = next(a for a in r["agents"] if a.id == seat.id)
    assert updated.boundaries.get("escalation") == []


def test_rejects_new_agent_consistently_with_boundaries_field():
    """Same unknown-seat rejection applies whether the entry sets boundaries
    or any other editable field — boundaries isn't a backdoor around the
    35-seat limit."""
    r = validate({"agents": [{"id": "not-a-real-seat", "boundaries": {"cannot": ["x"]}}]})
    assert any("not one of the 35 seats" in p for p in r["problems"])


def test_boundaries_text_renders_can_cannot_escalate():
    base = defaults()
    seat = base[0]
    r = validate({"agents": [{
        "id": seat.id,
        "boundaries": {
            "can": ["Draft replies"],
            "cannot": ["Access production systems"],
            "escalation": [{"condition": "a refund over $500", "target_agent": "invo"}],
        },
    }]}, base)
    updated = next(a for a in r["agents"] if a.id == seat.id)
    text = boundaries_text(updated)
    assert "YOU CAN:\n- Draft replies" in text
    assert "YOU CANNOT:\n- Access production systems" in text
    assert "ESCALATE:\n- a refund over $500 -> invo" in text
