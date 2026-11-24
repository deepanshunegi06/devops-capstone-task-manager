"""Natural-language quick add + recurrence engine (pure functions, no database access).

    parse("Submit report tomorrow 5pm #Capstone @writing p1 ~45m every week +alice", today)

returns the cleaned title plus every attribute that was recognised, and a list of tokens
so the UI can highlight what was understood.
"""
import calendar
import re
from datetime import date, timedelta

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
WEEKDAY_ALIASES = {**{d: i for i, d in enumerate(WEEKDAYS)},
                   **{d[:3]: i for i, d in enumerate(WEEKDAYS)}, "tues": 1, "thur": 3, "thurs": 3}
MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})
MONTHS["sept"] = 9

_WD = "|".join(sorted(WEEKDAY_ALIASES, key=len, reverse=True))
_MON = "|".join(sorted(MONTHS, key=len, reverse=True))
B, E = r"(?<!\S)", r"(?![\w])"          # token must start after whitespace / string start


def _add_months(d, months):
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def next_weekday(today, weekday, allow_today=False):
    delta = (weekday - today.weekday()) % 7
    if delta == 0 and not allow_today:
        delta = 7
    return today + timedelta(days=delta)


def step(d, recurrence):
    if recurrence == "daily":
        return d + timedelta(days=1)
    if recurrence == "weekdays":
        d += timedelta(days=1)
        while d.weekday() >= 5:
            d += timedelta(days=1)
        return d
    if recurrence == "weekly":
        return d + timedelta(days=7)
    if recurrence == "monthly":
        return _add_months(d, 1)
    if recurrence == "yearly":
        return _add_months(d, 12)
    raise ValueError(f"unknown recurrence {recurrence!r}")


def next_occurrence(due, recurrence, today):
    """Next due date after completing a recurring task: strictly after both `due` and `today`."""
    nxt = step(due or today, recurrence)
    while nxt <= today:
        nxt = step(nxt, recurrence)
    return nxt


class _Parser:
    def __init__(self, text, today):
        self.text = f" {text} "
        self.today = today
        self.tokens = []
        self.out = {"project": None, "labels": [], "assignee": None, "priority": None, "due_date": None,
                    "due_time": None, "recurrence": None, "estimate_minutes": None}

    def take(self, pattern, kind, flags=re.I):
        """Find the first match, remove it from the text, record a token, return the match."""
        m = re.search(pattern, self.text, flags)
        if m:
            self.tokens.append({"type": kind, "text": m.group(0).strip()})
            self.text = self.text[:m.start()] + " " + self.text[m.end():]
        return m

    def run(self):
        o = self.out
        m = self.take(B + r'#"([^"]+)"', "project") or self.take(B + r"#([\w\-]+)", "project")
        if m:
            o["project"] = m.group(1)
        while True:
            m = self.take(B + r"@([\w\-]+)", "label")
            if not m:
                break
            if m.group(1).lower() not in [lb.lower() for lb in o["labels"]]:
                o["labels"].append(m.group(1))
        m = self.take(B + r"\+([\w.]+)" + E, "assignee")
        if m:
            o["assignee"] = m.group(1)
        m = self.take(B + r"(?:p|!)([1-4])" + E, "priority")
        if m:
            o["priority"] = int(m.group(1))
        m = self.take(B + r"~(?:(\d+)h)?(?:(\d+)m(?:in)?)?" + E, "estimate")
        if m and (m.group(1) or m.group(2)):
            o["estimate_minutes"] = int(m.group(1) or 0) * 60 + int(m.group(2) or 0)
        elif m:                                   # a lone "~" - give the text back
            self.tokens.pop()
        self._recurrence()
        self._time()
        self._date()
        title = re.sub(r"\s+", " ", self.text).strip()
        title = re.sub(r"(?:\s+(?:at|on|by|due))+$", "", title, flags=re.I).strip()
        return {"title": title, **o, "tokens": self.tokens}

    def _recurrence(self):
        o, t = self.out, self.today
        rules = [
            (r"every\s+weekday|weekdays", "weekdays"),
            (r"every\s+day|daily|everyday", "daily"),
            (r"every\s+week|weekly", "weekly"),
            (r"every\s+month|monthly", "monthly"),
            (r"every\s+year|yearly|annually", "yearly"),
        ]
        m = self.take(B + rf"every\s+({_WD})" + E, "recurrence")
        if m:
            o["recurrence"] = "weekly"
            o["due_date"] = next_weekday(t, WEEKDAY_ALIASES[m.group(1).lower()], allow_today=True)
            return
        for pattern, rule in rules:
            if self.take(B + rf"(?:{pattern})" + E, "recurrence"):
                o["recurrence"] = rule
                start = t
                if rule == "weekdays":
                    while start.weekday() >= 5:
                        start += timedelta(days=1)
                o["due_date"] = start
                return

    def _time(self):
        m = self.take(B + r"(?:at\s+)?(\d{1,2})(?::([0-5]\d))?\s*(am|pm)" + E, "time")
        if m:
            hour, minute = int(m.group(1)) % 12, int(m.group(2) or 0)
            if m.group(3).lower() == "pm":
                hour += 12
            if hour < 24:
                self.out["due_time"] = f"{hour:02d}:{minute:02d}"
            return
        m = self.take(B + r"(?:at\s+)?([01]?\d|2[0-3]):([0-5]\d)" + E, "time")
        if m:
            self.out["due_time"] = f"{int(m.group(1)):02d}:{m.group(2)}"

    def _date(self):
        t, o = self.today, self.out
        explicit = None
        if self.take(B + r"(?:today|tod|tonight)" + E, "date"):
            explicit = t
        elif self.take(B + r"(?:tomorrow|tmrw|tmr)" + E, "date"):
            explicit = t + timedelta(days=1)
        elif m := self.take(B + r"in\s+(\d+)\s+(day|days|week|weeks|month|months)" + E, "date"):
            n, unit = int(m.group(1)), m.group(2).lower()
            explicit = (t + timedelta(days=n) if unit.startswith("day") else
                        t + timedelta(weeks=n) if unit.startswith("week") else _add_months(t, n))
        elif self.take(B + r"next\s+week" + E, "date"):
            explicit = next_weekday(t, 0)
        elif self.take(B + r"next\s+month" + E, "date"):
            explicit = _add_months(t.replace(day=1), 1)
        elif m := self.take(B + r"(\d{4})-(\d{2})-(\d{2})" + E, "date"):
            try:
                explicit = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                self.tokens.pop()
        elif m := (self.take(B + rf"(?:on\s+)?({_MON})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?" + E, "date")
                   or self.take(B + rf"(?:on\s+)?(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MON})" + E, "date")):
            a, b = m.group(1), m.group(2)
            month, day = (MONTHS[a.lower()], int(b)) if a.isalpha() else (MONTHS[b.lower()], int(a))
            try:
                explicit = date(t.year, month, day)
                if explicit < t:
                    explicit = date(t.year + 1, month, day)
            except ValueError:
                self.tokens.pop()
                explicit = None
        elif m := self.take(B + rf"(?:on\s+|next\s+)?({_WD})" + E, "date"):
            explicit = next_weekday(t, WEEKDAY_ALIASES[m.group(1).lower()])
        if explicit:
            o["due_date"] = explicit
        elif o["due_time"] and not o["due_date"]:
            o["due_date"] = t                     # "call mom 6pm" means today at 6pm


def parse(text, today=None):
    return _Parser(text or "", today or date.today()).run()
