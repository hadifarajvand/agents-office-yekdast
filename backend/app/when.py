"""Port of src/when.js — routine schedules: plain words -> a schedule, a schedule -> next due
time, a schedule -> the words the office says back. Local time throughout.

when = {kind: 'daily'|'weekdays'|'weekly'|'hourly'|'minutes', at: 'HH:MM', days: [0..6],
        every: N, from/to: 'HH:MM', weekdaysOnly: true}
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

DAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
WORD_TIMES = {
    "noon": "12:00", "midday": "12:00", "lunchtime": "12:30", "midnight": "00:00",
    "morning": "08:00", "mornings": "08:00", "afternoon": "14:00", "afternoons": "14:00",
    "evening": "17:00", "evenings": "17:00", "night": "20:00", "nights": "20:00",
}


def _pad(n: int) -> str:
    return str(n).zfill(2)


def hhmm(h: int, m: int = 0) -> str:
    return f"{_pad(h)}:{_pad(m)}"


def clock(h, m=0, ap=None) -> str | None:
    h = int(h)
    m = int(m or 0)
    if ap == "pm" and h < 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    if h > 23 or m > 59:
        return None
    return hhmm(h, m)


T_RE = re.compile(
    r"\b(?:at\s+)?(\d{1,2})(?::(\d{2}))\s*(am|pm|a\.m\.|p\.m\.)?\b"
    r"|\bat\s+(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)?\b"
    r"|\b(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)\b",
    re.IGNORECASE,
)


def find_time(s: str) -> dict | None:
    m = T_RE.search(s)
    if m:
        ap = (m.group(3) or m.group(5) or m.group(7) or "").replace(".", "").lower() or None
        if m.group(1) is not None:
            at = clock(m.group(1), m.group(2), ap)
        elif m.group(4) is not None:
            at = clock(m.group(4), 0, ap)
        else:
            at = clock(m.group(6), 0, ap)
        if at:
            return {"at": at, "span": (m.start(), m.end()), "guessed": False}
    w = re.search(r"\b(?:at\s+|in\s+the\s+|every\s+|each\s+)?(noon|midday|lunchtime|midnight|mornings?|afternoons?|evenings?|nights?)\b", s, re.IGNORECASE)
    if w:
        word = w.group(1).lower()
        return {"at": WORD_TIMES[word], "span": (w.start(), w.end()), "guessed": not re.match(r"^(noon|midday|midnight)$", word), "word": word}
    return None


def day_index(word: str) -> int:
    w = re.sub(r"s$", "", word.lower())
    for i, d in enumerate(DAYS):
        if len(w) >= 3 and d.startswith(w[:3]):
            return i
    return -1


def _cut(s: str, span: tuple[int, int]) -> str:
    return s[: span[0]] + " " + s[span[1]:]


def tidy(s: str) -> str:
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"^[\s,;:.\-–—]+|[\s,;:.\-–—]+$", "", s)
    s = re.sub(r"^(?:and|then|please|to)\s+", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+,", ",", s)
    return s.strip()


def parse_when(input_: str | None) -> dict | None:
    s = str(input_ or "")

    m = re.search(r"\bevery\s+(\d+)\s*(?:min|mins|minutes?)\b", s, re.IGNORECASE)
    if m:
        return {"when": {"kind": "minutes", "every": max(1, int(m.group(1)))}, "text": tidy(_cut(s, (m.start(), m.end())))}

    m = re.search(r"\b(?:hourly|every\s+(\d+\s+)?hours?|each\s+hour|once\s+an\s+hour)\b", s, re.IGNORECASE)
    if m:
        when = {"kind": "hourly", "every": max(1, int(m.group(1)) if m.group(1) else 1)}
        s = _cut(s, (m.start(), m.end()))
        w = re.search(
            r"\b(?:between|from)?\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*(?:and|to|-|–|until|till)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b",
            s, re.IGNORECASE,
        )
        if w:
            a = clock(w.group(1), w.group(2), w.group(3).lower() if w.group(3) else None)
            b = clock(w.group(4), w.group(5), w.group(6).lower() if w.group(6) else None)
            if a and b:
                if not w.group(3) and not w.group(6) and int(w.group(1)) < 8 and int(w.group(1)) < int(w.group(4)):
                    a = clock(int(w.group(1)) + 12, w.group(2))
                if b < a and not w.group(6):
                    b = clock((int(w.group(4)) % 12) + 12, w.group(5))
                if b > a:
                    when["from"] = a
                    when["to"] = b
                    s = _cut(s, (w.start(), w.end()))
        m2 = re.search(r"\b(?:on\s+)?(?:week\s?days|working\s+days|business\s+days|mon(?:day)?\s*(?:-|–|to)\s*fri(?:day)?)\b", s, re.IGNORECASE)
        if m2:
            when["weekdaysOnly"] = True
            s = _cut(s, (m2.start(), m2.end()))
        return {"when": when, "text": tidy(s)}

    m = re.search(r"\b(?:every|each|on|all)?\s*(?:week\s?days?|working\s+days?|business\s+days?|mon(?:day)?\s*(?:-|–|to|through)\s*fri(?:day)?)\b", s, re.IGNORECASE)
    if m:
        s = _cut(s, (m.start(), m.end()))
        t = find_time(s)
        if t:
            s = _cut(s, t["span"])
        return {"when": {"kind": "weekdays", "at": t["at"] if t else None}, "text": tidy(s),
                "guessed": bool(t and t["guessed"]), "guessWord": t.get("word") if t else None, "needsTime": not t}

    m = re.search(r"\b(?:every|each|on|at)?\s*(?:the\s+)?weekends?\b", s, re.IGNORECASE)
    if m:
        s = _cut(s, (m.start(), m.end()))
        t = find_time(s)
        if t:
            s = _cut(s, t["span"])
        return {"when": {"kind": "weekly", "days": [6, 0], "at": t["at"] if t else None}, "text": tidy(s),
                "guessed": bool(t and t["guessed"]), "guessWord": t.get("word") if t else None, "needsTime": not t}

    day_re = re.compile(
        r"\b(?:every|each|on|all|every\s+other)?\s*"
        r"((?:(?:sun|mon|tues?|wed(?:nes)?|thu(?:rs)?|fri|sat(?:ur)?)(?:day)?s?)"
        r"(?:\s*(?:,|and|&|\+)\s*(?:sun|mon|tues?|wed(?:nes)?|thu(?:rs)?|fri|sat(?:ur)?)(?:day)?s?)*)\b",
        re.IGNORECASE,
    )
    m = day_re.search(s)
    if m:
        days = sorted({day_index(x) for x in re.split(r"\s*(?:,|and|&|\+)\s*", m.group(1)) if day_index(x) >= 0})
        if days:
            s = _cut(s, (m.start(), m.end()))
            t = find_time(s)
            if t:
                s = _cut(s, t["span"])
            s = re.sub(r"\b(?:every|each)\s+week\b", " ", s, flags=re.IGNORECASE)
            s = re.sub(r"\bweekly\b", " ", s, flags=re.IGNORECASE)
            return {"when": {"kind": "weekly", "days": days, "at": t["at"] if t else None}, "text": tidy(s),
                    "guessed": bool(t and t["guessed"]), "guessWord": t.get("word") if t else None, "needsTime": not t}

    m = re.search(r"\b(?:weekly|every\s+week|once\s+a\s+week|each\s+week)\b", s, re.IGNORECASE)
    if m:
        s = _cut(s, (m.start(), m.end()))
        t = find_time(s)
        if t:
            s = _cut(s, t["span"])
        return {"when": {"kind": "weekly", "days": [], "at": t["at"] if t else None}, "text": tidy(s),
                "needsDay": True, "needsTime": not t}

    m = re.search(r"\b(?:daily|every\s+day|each\s+day|once\s+a\s+day|every\s+(?:morning|afternoon|evening|night)|each\s+(?:morning|afternoon|evening|night))\b", s, re.IGNORECASE)
    if m:
        word_m = re.search(r"(morning|afternoon|evening|night)", m.group(0), re.IGNORECASE)
        s = _cut(s, (m.start(), m.end()))
        t = find_time(s)
        if t:
            s = _cut(s, t["span"])
        word = word_m.group(1).lower() if word_m else None
        at = t["at"] if t else (WORD_TIMES[word] if word else None)
        guessed = (not t and bool(word)) or bool(t and t["guessed"])
        guess_word = t.get("word") if (t and t["guessed"]) else word
        return {"when": {"kind": "daily", "at": at}, "text": tidy(s), "guessed": guessed, "guessWord": guess_word, "needsTime": not at}

    return None


def from_picker(cadence: str, at: str | None) -> dict:
    t = at if re.match(r"^\d{2}:\d{2}$", at or "") else "08:00"
    if cadence == "daily":
        return {"kind": "daily", "at": t}
    if cadence == "weekdays":
        return {"kind": "weekdays", "at": t}
    if cadence == "hourly":
        return {"kind": "hourly", "every": 1, "from": "09:00", "to": "17:00", "weekdaysOnly": True}
    d = day_index(cadence)
    if d >= 0:
        return {"kind": "weekly", "days": [d], "at": t}
    return {"kind": "weekdays", "at": t}


def describe(when: dict | None) -> str:
    if not when:
        return ""
    at = f' · {when["at"]}' if when.get("at") else ""
    kind = when.get("kind")
    if kind == "minutes":
        return f'every {when["every"]} min'
    if kind == "hourly":
        base = f'every {when["every"]} hours' if when["every"] > 1 else "every hour"
        if when.get("from"):
            base += f' {when["from"]}–{when["to"]}'
        if when.get("weekdaysOnly"):
            base += " · weekdays"
        return base
    if kind == "daily":
        return "every day" + at
    if kind == "weekdays":
        return "every weekday" + at
    if kind == "weekly":
        d = when.get("days") or []
        if len(d) == 7:
            return "every day" + at
        if len(d) == 2 and 0 in d and 6 in d:
            return "weekends" + at
        if len(d) == 1:
            name = DAYS[d[0]][0].upper() + DAYS[d[0]][1:] + "s"
        else:
            name = ", ".join(SHORT[i] for i in d)
        return name + at
    return ""


def valid(when: dict | None) -> bool:
    if not when or not isinstance(when, dict):
        return False

    def t(s):
        return bool(re.match(r"^\d{2}:\d{2}$", s or ""))

    kind = when.get("kind")
    if kind == "minutes":
        return isinstance(when.get("every"), int) and when["every"] >= 1
    if kind == "hourly":
        if not (isinstance(when.get("every"), int) and when["every"] >= 1):
            return False
        if when.get("from"):
            return t(when.get("from")) and t(when.get("to")) and when["from"] < when["to"]
        return True
    if kind in ("daily", "weekdays"):
        return t(when.get("at"))
    if kind == "weekly":
        days = when.get("days")
        return (t(when.get("at")) and isinstance(days, list) and len(days) > 0
                and all(isinstance(d, int) and 0 <= d <= 6 for d in days))
    return False


def _mins(s: str) -> int:
    h, m = (int(x) for x in s.split(":"))
    return h * 60 + m


def next_run(when: dict | None, from_ms: float | None = None) -> float | None:
    if not valid(when):
        return None
    from_ms = from_ms if from_ms is not None else datetime.now().timestamp() * 1000
    f = datetime.fromtimestamp(from_ms / 1000)
    kind = when["kind"]

    if kind == "minutes":
        step = when["every"] * 60000
        return (from_ms // step) * step + step

    if kind == "hourly":
        start = _mins(when["from"]) if when.get("from") else 0
        end = _mins(when["to"]) if when.get("to") else 24 * 60
        step = when["every"] * 60
        d = f.replace(second=0, microsecond=0, minute=0) + timedelta(hours=1)
        for _ in range(24 * 8):
            dow = (d.weekday() + 1) % 7  # JS getDay(): 0=Sunday
            mm = d.hour * 60
            ok_day = not (when.get("weekdaysOnly") and dow in (0, 6))
            if ok_day and start <= mm <= end and (mm - start) % step == 0:
                return d.timestamp() * 1000
            d += timedelta(hours=1)
        return None

    hh, mi = (int(x) for x in when["at"].split(":"))
    if kind == "daily":
        allowed = [0, 1, 2, 3, 4, 5, 6]
    elif kind == "weekdays":
        allowed = [1, 2, 3, 4, 5]
    else:
        allowed = when["days"]
    d = f.replace(hour=hh, minute=mi, second=0, microsecond=0)
    for _ in range(9):
        if d.timestamp() * 1000 > from_ms:
            dow = (d.weekday() + 1) % 7
            if dow in allowed:
                return d.timestamp() * 1000
        d += timedelta(days=1)
    return None


def until_text(ts: float | None, now: float | None = None) -> str:
    if not ts:
        return "—"
    now = now if now is not None else datetime.now().timestamp() * 1000
    ms = ts - now
    if ms <= 0:
        return "now"
    m = round(ms / 60000)
    if m < 1:
        return "in under a minute"
    if m < 60:
        return f"in {m} min"
    d = datetime.fromtimestamp(ts / 1000)
    today = datetime.fromtimestamp(now / 1000)
    tomorrow = today + timedelta(days=1)
    t = hhmm(d.hour, d.minute)
    if d.date() == today.date():
        return f"at {t}"
    if d.date() == tomorrow.date():
        return f"tomorrow {t}"
    return f"{SHORT[(d.weekday() + 1) % 7]} {t}"


DAY_NAMES = DAYS
