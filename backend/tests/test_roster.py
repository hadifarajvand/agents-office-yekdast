from app.roster import DEPTS, defaults, validate


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


def test_model_must_be_one_of_three():
    base = defaults()
    seat = base[0]
    r = validate({"agents": [{"id": seat.id, "model": "haiku"}]}, base)
    assert any("must be sonnet, opus or fable" in p for p in r["problems"])
