"""
Tests for the school-vacation rules (pure, offline).

Regression target: the Tishrei period used to be emitted as one blanket
"חופשת תשרי" span covering Rosh Hashana → Sukkot, which wrongly tagged the
school week between Rosh Hashana and Yom Kippur (14→19/09/2026) as vacation.

Runs under pytest, or standalone:  python tests/test_vacations.py
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vacation_rules import (  # noqa: E402
    calculate_vacation_periods,
    expand_vacation_days,
)


def _hebcal(entries):
    """Build a Hebcal-shaped holiday dict from (title, date) pairs."""
    return {
        f"{title}|{date}": {
            "date": date,
            "hebrew": title,
            "category": "holiday",
            "title": title,
        }
        for title, date in entries
    }


# Real, verified Tishrei תשפ"ז dates (school year starting Sept 2026).
TISHREI_5787 = _hebcal([
    ("Erev Rosh Hashana", "2026-09-11"),
    ("Rosh Hashana 5787", "2026-09-12"),
    ("Rosh Hashana II", "2026-09-13"),
    ("Tzom Gedaliah", "2026-09-14"),
    ("Erev Yom Kippur", "2026-09-20"),
    ("Yom Kippur", "2026-09-21"),
    ("Erev Sukkot", "2026-09-25"),
    ("Sukkot I", "2026-09-26"),
    ("Shmini Atzeret", "2026-10-03"),
])


def _days(year, holidays):
    return expand_vacation_days(calculate_vacation_periods(year, holidays))


def _span(first, last):
    """Inclusive list of YYYY-MM-DD strings between two such strings."""
    d = datetime.strptime(first, "%Y-%m-%d")
    end = datetime.strptime(last, "%Y-%m-%d")
    out = []
    while d <= end:
        out.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    return out


def test_school_week_between_rosh_hashana_and_yom_kippur_is_not_vacation():
    """14→18/09/2026 are school days: no vacation tag at all."""
    days = _days(2026, TISHREI_5787)
    for date in _span("2026-09-14", "2026-09-18"):
        assert date not in days, f"{date} should be a school day, got {days.get(date)}"


def test_festival_days_are_vacation():
    """Rosh Hashana, Yom Kippur and Sukkot→Simchat Torah are tagged."""
    days = _days(2026, TISHREI_5787)
    for date in _span("2026-09-12", "2026-09-13"):      # ראש השנה
        assert date in days, f"{date} should be vacation"
    for date in _span("2026-09-20", "2026-09-21"):      # יום כיפור
        assert date in days, f"{date} should be vacation"
    for date in _span("2026-09-26", "2026-10-03"):      # סוכות → שמחת תורה
        assert date in days, f"{date} should be vacation"


def test_shabbat_19_09_carries_no_vacation_tag():
    """19/09/2026 is Shabbat — no school, but it must not carry a vacation tag."""
    days = _days(2026, TISHREI_5787)
    assert "2026-09-19" not in days


def test_blanket_tishrei_label_is_never_produced():
    """Regression guard: the old single-span label must not come back."""
    labels = {v["text"] for v in calculate_vacation_periods(2026, TISHREI_5787)}
    assert "חופשת תשרי" not in labels
    assert {"חופשת ראש השנה", "חופשת יום כיפור", "חופשת סוכות"} <= labels


def test_rules_are_generic_not_hardcoded_to_2026():
    """Same structural invariants on a different year with shifted dates."""
    shifted = _hebcal([
        ("Rosh Hashana 5788", "2027-10-02"),
        ("Rosh Hashana II", "2027-10-03"),
        ("Yom Kippur", "2027-10-11"),
        ("Sukkot I", "2027-10-16"),
        ("Shmini Atzeret", "2027-10-23"),
    ])
    days = _days(2027, shifted)

    # Festival days tagged.
    for date in _span("2027-10-02", "2027-10-03"):
        assert date in days
    for date in _span("2027-10-10", "2027-10-11"):
        assert date in days
    for date in _span("2027-10-16", "2027-10-23"):
        assert date in days
    # The week between Rosh Hashana and Erev Yom Kippur stays school days.
    for date in _span("2027-10-04", "2027-10-09"):
        assert date not in days, f"{date} should be a school day, got {days.get(date)}"


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS  {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL  {name}: {exc}")
    print("\n" + ("ALL TESTS PASSED" if not failures else f"{failures} FAILURE(S)"))
    sys.exit(1 if failures else 0)
