"""
auto_vacations.py - Automatic School Vacation Generator for Israel

Fetches Jewish holiday dates from the Hebcal API and stores the resulting school
vacation periods in Firestore. The vacation *rules* themselves live in
vacation_rules.py (pure, offline-testable); this module only handles the network
fetch, the Firestore write and the CLI.

Usage:
    python auto_vacations.py 2027
    # Generates and uploads vacations for school year 2027-2028
"""

import requests
from datetime import datetime

from db_manager import hebrew_year_label, save_holidays
from vacation_rules import (
    HOLIDAY_RULES_VERSION,
    calculate_vacation_periods,
    format_holidays_for_firestore,
)

__all__ = [
    "fetch_hebrew_holidays",
    "calculate_vacation_periods",
    "format_holidays_for_firestore",
    "generate_and_save_vacations",
    "HOLIDAY_RULES_VERSION",
]


def fetch_hebrew_holidays(year):
    """Fetch Jewish holidays from Hebcal API for Israeli schools."""
    url = f"https://www.hebcal.com/hebcal?v=1&cfg=json&year={year}&month=x&geo=geoname&geonameid=281184&i=off"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()

    holidays = {}
    for item in data.get("items", []):
        if item.get("category") in ["holiday", "roshchodesh"]:
            date_str = item.get("date", "")
            hebrew_name = item.get("hebrew", item.get("title", ""))
            english_name = item.get("title", "")

            if date_str:
                # Key by title+date so multi-day entries and the two-year merge
                # below don't overwrite each other (which previously dropped the
                # autumn occurrence and shifted Rosh Hashana to the wrong year).
                holidays[f"{english_name}|{date_str}"] = {
                    "date": date_str,
                    "hebrew": hebrew_name,
                    "category": item.get("category"),
                    "title": english_name,
                }

    return holidays


def build_holiday_document(year: int) -> dict:
    """Fetch Hebcal data for the school year and build the stored document.

    Carries `rules_version` so that documents produced by an older rule set are
    detected as stale and regenerated instead of being trusted forever.
    """
    holidays_year1 = fetch_hebrew_holidays(year)
    holidays_year2 = fetch_hebrew_holidays(year + 1)
    all_holidays = {**holidays_year1, **holidays_year2}

    return {
        "label": hebrew_year_label(year + 3761),  # Hebrew year (gematria)
        "holidays": format_holidays_for_firestore(all_holidays),
        "school_vacations": calculate_vacation_periods(year, all_holidays),
        "rules_version": HOLIDAY_RULES_VERSION,
        "generated_by": "auto_vacations.py",
        "generated_at": datetime.now().isoformat(),
    }


def generate_and_save_vacations(year):
    """Generate vacations for a school year and save them to Firestore.

    Args:
        year: The starting year of the school year (e.g., 2027 for 2027-2028)
    """
    print(f"\n📅 Generating school vacations for {year}-{year+1}...")
    print("🔍 Fetching Hebrew holidays from Hebcal API...")

    data = build_holiday_document(year)

    print(f"   ✅ Found {len(data['holidays'])} Jewish holidays")
    print(f"   ✅ Generated {len(data['school_vacations'])} vacation periods:")
    for v in data["school_vacations"]:
        print(f"      • {v['text']}: {v['start']} → {v['end']}")

    print("\n📤 Uploading to Firestore...")
    save_holidays(str(year), data)

    print(f"✅ Successfully saved vacations for {year}!")
    print("\n🎉 You can now use 'ייבא חופשות וחגים' in the app to import these vacations.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        year = int(sys.argv[1])
    else:
        # Default to current year if not specified
        current_month = datetime.now().month
        current_year = datetime.now().year
        # If we're in Sep-Dec, use current year; otherwise use next year
        year = current_year if current_month >= 9 else current_year + 1
        print(f"ℹ️  No year specified, using {year}")

    generate_and_save_vacations(year)
