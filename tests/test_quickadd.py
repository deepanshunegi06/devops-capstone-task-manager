from datetime import date

import pytest

from taskmanager.quickadd import next_occurrence, parse, step

TUE = date(2026, 11, 24)          # a Tuesday


def p(text):
    out = parse(text, TUE)
    out.pop("tokens")
    return out


def test_full_sentence():
    r = p("Submit report tomorrow 5pm #Capstone @writing p1 ~45m +alice")
    assert r["title"] == "Submit report"
    assert r["project"] == "Capstone" and r["labels"] == ["writing"] and r["assignee"] == "alice"
    assert r["priority"] == 1 and r["estimate_minutes"] == 45
    assert r["due_date"] == date(2026, 11, 25) and r["due_time"] == "17:00"


@pytest.mark.parametrize("text,expected", [
    ("a today", TUE), ("a tod", TUE), ("a tmr", date(2026, 11, 25)), ("a tomorrow", date(2026, 11, 25)),
    ("a in 3 days", date(2026, 11, 27)), ("a in 2 weeks", date(2026, 12, 8)), ("a in 1 month", date(2026, 12, 24)),
    ("a next week", date(2026, 11, 30)), ("a next month", date(2026, 12, 1)),
    ("a friday", date(2026, 11, 27)), ("a on tue", date(2026, 12, 1)), ("a next mon", date(2026, 11, 30)),
    ("a 2026-12-31", date(2026, 12, 31)), ("a dec 5", date(2026, 12, 5)), ("a 5th jan", date(2027, 1, 5)),
    ("a sept 1st", date(2027, 9, 1)),
])
def test_dates(text, expected):
    r = p(text)
    assert r["due_date"] == expected and r["title"] == "a"


@pytest.mark.parametrize("text,time", [("a 5pm", "17:00"), ("a at 9am", "09:00"), ("a 12am", "00:00"),
                                       ("a 12:30pm", "12:30"), ("a 17:45", "17:45"), ("a at 7:05", "07:05")])
def test_times_default_to_today(text, time):
    r = p(text)
    assert r["due_time"] == time and r["due_date"] == TUE


@pytest.mark.parametrize("text,rule,due", [
    ("gym every monday", "weekly", date(2026, 11, 30)), ("standup every weekday", "weekdays", TUE),
    ("water plants daily", "daily", TUE), ("review weekly", "weekly", TUE),
    ("rent every month", "monthly", TUE), ("taxes yearly", "yearly", TUE),
    ("gym every tue", "weekly", TUE),
])
def test_recurrence(text, rule, due):
    r = p(text)
    assert r["recurrence"] == rule and r["due_date"] == due


def test_project_with_quotes_labels_dedup_and_estimates():
    r = p('Plan #"Family Trip" @home @Home @errand ~1h30m !2')
    assert r["project"] == "Family Trip" and r["labels"] == ["home", "errand"]
    assert r["estimate_minutes"] == 90 and r["priority"] == 2 and r["title"] == "Plan"


def test_plain_text_is_untouched():
    r = p("Email the professor about p5 results #")
    assert r["title"] == "Email the professor about p5 results #"
    assert r["priority"] is None and r["due_date"] is None


def test_invalid_dates_are_ignored():
    assert p("a 2026-02-30")["due_date"] is None
    assert p("a feb 30")["due_date"] is None


def test_trailing_connectors_removed_and_tokens_reported():
    out = parse("Call mom on friday at 6pm", TUE)
    assert out["title"] == "Call mom"
    assert {t["type"] for t in out["tokens"]} == {"date", "time"}


def test_lone_tilde_kept():
    assert p("a ~ b")["estimate_minutes"] is None


def test_weekdays_recurrence_starting_on_weekend():
    out = parse("standup weekdays", date(2026, 11, 28))      # Saturday
    assert out["due_date"] == date(2026, 11, 30)


def test_next_occurrence():
    assert next_occurrence(date(2026, 11, 20), "daily", TUE) == date(2026, 11, 25)   # skips past days
    assert next_occurrence(date(2026, 11, 27), "weekdays", TUE) == date(2026, 11, 30)
    assert next_occurrence(TUE, "weekly", TUE) == date(2026, 12, 1)
    assert next_occurrence(date(2026, 1, 31), "monthly", date(2026, 1, 31)) == date(2026, 2, 28)
    assert next_occurrence(None, "yearly", TUE) == date(2027, 11, 24)
    with pytest.raises(ValueError):
        step(TUE, "hourly")
