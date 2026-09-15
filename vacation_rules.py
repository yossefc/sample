"""
vacation_rules.py — Pure school-vacation rules for the Israeli school year.

Deliberately dependency-free (stdlib only): no Streamlit, no Firebase, no
network. That keeps the rules unit-testable offline and makes them easy to port
to another runtime later.

The rules are expressed in terms of Hebrew-calendar anchors (Rosh Hashana, Yom
Kippur, Shmini Atzeret, Pesach...) resolved from Hebcal data, never hard-coded
Gregorian dates, so they stay correct for תשפ"ח, תשפ"ט and beyond.
"""

from datetime import datetime, timedelta

# Bump whenever the rules below change in a way that invalidates stored results.
# generate_new_year() treats holiday documents stamped with an older version as
# absent and regenerates them, so corrections self-heal instead of being masked
# by stale data.
HOLIDAY_RULES_VERSION = 2


def find_holiday(holidays: dict, name: str, year: int):
    """First day of a holiday, by title, inside the school-year window.

    Matches exact title first, then a "name ..." / "name: ..." prefix. Skips
    "Erev" (eve) entries and tolerates date strings carrying a time component.
    The window (Aug 1 of `year` → Aug 31 of `year+1`) makes Pesach resolve to the
    coming spring rather than the one that just passed.
    """
    name_l = name.lower()
    season_start = datetime(year, 8, 1)
    season_end = datetime(year + 1, 8, 31)
    exact = None
    prefix = None
    for h_data in holidays.values():
        title = str(h_data.get("title", "")).lower()
        if not title or title.startswith("erev"):
            continue
        try:
            d = datetime.strptime(str(h_data.get("date", ""))[:10], "%Y-%m-%d")
        except ValueError:
            continue
        if d < season_start or d > season_end:
            continue
        if title == name_l:
            if exact is None or d < exact:
                exact = d
        elif title.startswith(name_l + " ") or title.startswith(name_l + ":"):
            if prefix is None or d < prefix:
                prefix = d
    return exact if exact is not None else prefix


def _period(start: datetime, end: datetime, text: str) -> dict:
    return {
        "start": start.strftime("%Y-%m-%d"),
        "end": end.strftime("%Y-%m-%d"),
        "text": text,
    }


def calculate_vacation_periods(year: int, holidays: dict) -> list[dict]:
    """School vacation periods for the year starting in September `year`.

    Tishrei is NOT one long break: the Ministry calendar keeps the week between
    Rosh Hashana and Yom Kippur as school days, so distinct periods are emitted
    rather than a single blanket "חופשת תשרי" span.
    """
    vacations = []

    def anchor(name):
        return find_holiday(holidays, name, year)

    rosh_hashana = anchor("Rosh Hashana")
    yom_kippur = anchor("Yom Kippur")
    sukkot = anchor("Sukkot")
    sukkot_end = anchor("Shmini Atzeret")  # = Simchat Torah in Israel

    # חופשת ראש השנה — ערב + שני ימי החג. School resumes the next day (ג' תשרי),
    # so צום גדליה is a regular school day.
    if rosh_hashana:
        vacations.append(_period(
            rosh_hashana - timedelta(days=1),
            rosh_hashana + timedelta(days=1),
            "חופשת ראש השנה",
        ))

    # חופשת יום כיפור — ערב + יום החג.
    if yom_kippur:
        vacations.append(_period(
            yom_kippur - timedelta(days=1),
            yom_kippur,
            "חופשת יום כיפור",
        ))

    # חופשת סוכות — from the day after Yom Kippur (the Ministry's "ימי חופשה בין
    # יום הכיפורים לסוכות") through Simchat Torah inclusive.
    sukkot_start = None
    if yom_kippur:
        sukkot_start = yom_kippur + timedelta(days=1)
    elif sukkot:
        sukkot_start = sukkot - timedelta(days=1)
    if sukkot_start and sukkot_end:
        vacations.append(_period(sukkot_start, sukkot_end, "חופשת סוכות"))

    # חופשת חנוכה — ~10 days from the first day.
    chanukah = anchor("Chanukah")
    if chanukah:
        vacations.append(_period(chanukah, chanukah + timedelta(days=9), "חופשת חנוכה"))

    # חופשת סמסטר — ~5 months into the year, snapped to the following Sunday.
    semester_break = datetime(year, 9, 1) + timedelta(days=150)
    while semester_break.weekday() != 6:  # 6 = Sunday
        semester_break += timedelta(days=1)
    vacations.append(_period(
        semester_break, semester_break + timedelta(days=5), "חופשת סמסטר",
    ))

    # חופשת פורים.
    purim = anchor("Purim")
    if purim:
        vacations.append(_period(
            purim - timedelta(days=1), purim + timedelta(days=1), "חופשת פורים",
        ))

    # חופשת פסח — from the eve, ~16 days.
    pesach = anchor("Pesach")
    if pesach:
        vacations.append(_period(
            pesach - timedelta(days=1), pesach + timedelta(days=16), "חופשת פסח",
        ))

    # חופשת שבועות.
    shavuot = anchor("Shavuot")
    if shavuot:
        vacations.append(_period(shavuot, shavuot + timedelta(days=1), "חופשת שבועות"))

    # חופשת קיץ — fixed civil dates, in the second calendar year of the school year.
    summer_year = year + 1
    vacations.append({
        "start": f"{summer_year}-06-21",
        "end": f"{summer_year}-08-31",
        "text": "חופשת קיץ",
    })

    return vacations


def expand_vacation_days(vacations: list[dict]) -> dict:
    """Flatten periods into {"YYYY-MM-DD": [labels]} — one entry per covered day."""
    days = {}
    for v in vacations or []:
        try:
            start = datetime.strptime(str(v.get("start", ""))[:10], "%Y-%m-%d")
            end = datetime.strptime(str(v.get("end", ""))[:10], "%Y-%m-%d")
        except ValueError:
            continue
        d = start
        while d <= end:
            days.setdefault(d.strftime("%Y-%m-%d"), []).append(v.get("text", ""))
            d += timedelta(days=1)
    return days


def format_holidays_for_firestore(holidays: dict) -> list[dict]:
    """Convert Hebcal holiday entries to the stored {date, text, type} shape."""
    formatted = []
    for data in holidays.values():
        formatted.append({
            "date": data.get("date", ""),
            "text": data.get("hebrew", ""),
            "type": "holiday" if data.get("category") == "holiday" else "general",
        })
    return formatted
