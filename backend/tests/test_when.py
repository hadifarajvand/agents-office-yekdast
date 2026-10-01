from app.when import next_run, parse_when, valid


def test_parse_weekdays():
    w = parse_when("every weekday at 8am")["when"]
    assert w == {"kind": "weekdays", "at": "08:00"}
    assert valid(w)


def test_parse_named_days():
    w = parse_when("every monday and thursday at 2pm")["when"]
    assert w["kind"] == "weekly"
    assert set(w["days"]) == {1, 4}
    assert w["at"] == "14:00"


def test_parse_hourly_range():
    w = parse_when("hourly between 9 and 5 on weekdays")["when"]
    assert w["kind"] == "hourly"
    assert w["weekdaysOnly"] is True


def test_parse_minutes():
    w = parse_when("every 2 min")["when"]
    assert w == {"kind": "minutes", "every": 2}


def test_incomplete_schedule_invalid():
    assert not valid({"kind": "weekly", "days": [1]})  # no "at"
    assert not valid({"kind": "daily"})  # no "at"


def test_next_run_is_in_the_future():
    w = parse_when("daily at noon")["when"]
    now = 1700000000000.0
    nr = next_run(w, now)
    assert nr > now
