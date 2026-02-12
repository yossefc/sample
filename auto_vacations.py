"""
auto_vacations.py - Automatic School Vacation Generator for Israel

This script automatically generates school vacation dates based on the Hebrew calendar.
It uses the Hebcal API to get Jewish holiday dates, then calculates vacation periods
according to Israel Ministry of Education standard rules.

Usage:
    python auto_vacations.py 2027
    # Generates and uploads vacations for school year 2027-2028
"""

import requests
from datetime import datetime, timedelta
from db_manager import save_holidays


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
                holidays[english_name] = {
                    "date": date_str,
                    "hebrew": hebrew_name,
                    "category": item.get("category")
                }
    
    return holidays


def calculate_vacation_periods(year, holidays):
    """
    Calculate school vacation periods based on Jewish holidays.
    
    Rules (based on Israel Ministry of Education patterns):
    - חופשת תשרי: Erev Rosh Hashana → end of Sukkot
    - חופשת חנוכה: ~10 days during Chanukah
    - חופשת סמסטר: ~5 days in late January/early February
    - חופשת פורים: 2-3 days around Purim
    - חופשת פסח: Erev Pesach → +16 days
    - חופשת שבועות: 1-2 days around Shavuot
    - חופשת קיץ: June 21 → August 31
    """
    vacations = []
    
    # Helper to find holiday by name
    def find_holiday(name):
        for h_name, h_data in holidays.items():
            if name.lower() in h_name.lower():
                return datetime.strptime(h_data["date"], "%Y-%m-%d")
        return None
    
    # 1. חופשת תשרי (Tishrei vacation - Rosh Hashana to Sukkot)
    rosh_hashana = find_holiday("Rosh Hashana")
    sukkot_end = find_holiday("Shmini Atzeret")  # Last day of Sukkot period
    
    if rosh_hashana and sukkot_end:
        # Start one day before Rosh Hashana
        start = rosh_hashana - timedelta(days=1)
        # End the day after Simchat Torah/Shmini Atzeret
        end = sukkot_end + timedelta(days=1)
        
        vacations.append({
            "start": start.strftime("%Y-%m-%d"),
            "end": end.strftime("%Y-%m-%d"),
            "text": "חופשת תשרי"
        })
    
    # 2. חופשת חנוכה (Chanukah vacation)
    chanukah = find_holiday("Chanukah")
    if chanukah:
        # Usually 10 days starting from Chanukah
        start = chanukah
        end = chanukah + timedelta(days=9)
        
        vacations.append({
            "start": start.strftime("%Y-%m-%d"),
            "end": end.strftime("%Y-%m-%d"),
            "text": "חופשת חנוכה"
        })
    
    # 3. חופשת סמסטר (Winter/Semester break - usually late January/early February)
    # This is approximately 6 months after the school year starts (Sept 1)
    # Usually around end of January or early February
    school_start = datetime(year, 9, 1) if rosh_hashana and rosh_hashana.month >= 9 else datetime(year - 1, 9, 1)
    semester_break = school_start + timedelta(days=150)  # ~5 months
    
    # Adjust to Sunday start if needed
    while semester_break.weekday() != 6:  # 6 = Sunday
        semester_break += timedelta(days=1)
    
    vacations.append({
        "start": semester_break.strftime("%Y-%m-%d"),
        "end": (semester_break + timedelta(days=5)).strftime("%Y-%m-%d"),
        "text": "חופשת סמסטר"
    })
    
    # 4. חופשת פורים (Purim vacation)
    purim = find_holiday("Purim")
    if purim:
        # 2-3 days around Purim
        start = purim - timedelta(days=1)
        end = purim + timedelta(days=1)
        
        vacations.append({
            "start": start.strftime("%Y-%m-%d"),
            "end": end.strftime("%Y-%m-%d"),
            "text": "חופשת פורים"
        })
    
    # 5. חופשת פסח (Pesach vacation)
    pesach = find_holiday("Pesach")
    if pesach:
        # Start day before Pesach, extend ~16 days
        start = pesach - timedelta(days=1)
        end = pesach + timedelta(days=16)
        
        vacations.append({
            "start": start.strftime("%Y-%m-%d"),
            "end": end.strftime("%Y-%m-%d"),
            "text": "חופשת פסח"
        })
    
    # 6. חופשת שבועות (Shavuot vacation)
    shavuot = find_holiday("Shavuot")
    if shavuot:
        # 1-2 days around Shavuot
        vacations.append({
            "start": shavuot.strftime("%Y-%m-%d"),
            "end": (shavuot + timedelta(days=1)).strftime("%Y-%m-%d"),
            "text": "חופשת שבועות"
        })
    
    # 7. חופשת קיץ (Summer vacation - June 21 to August 31)
    # The next year because school year spans two calendar years
    summer_year = year + 1 if rosh_hashana and rosh_hashana.month >= 9 else year
    vacations.append({
        "start": f"{summer_year}-06-21",
        "end": f"{summer_year}-08-31",
        "text": "חופשת קיץ"
    })
    
    return vacations


def format_holidays_for_firestore(holidays):
    """Convert Hebcal holidays to Firestore format."""
    formatted = []
    for name, data in holidays.items():
        formatted.append({
            "date": data["date"],
            "text": data["hebrew"],
            "type": "holiday" if data["category"] == "holiday" else "general"
        })
    return formatted


def generate_and_save_vacations(year):
    """
    Main function: Generate vacations for a school year and save to Firestore.
    
    Args:
        year: The starting year of the school year (e.g., 2027 for 2027-2028)
    """
    print(f"\n📅 Generating school vacations for {year}-{year+1}...")
    print(f"🔍 Fetching Hebrew holidays from Hebcal API...")
    
    # Fetch holidays for both years (school year spans two calendar years)
    holidays_year1 = fetch_hebrew_holidays(year)
    holidays_year2 = fetch_hebrew_holidays(year + 1)
    all_holidays = {**holidays_year1, **holidays_year2}
    
    print(f"   ✅ Found {len(all_holidays)} Jewish holidays")
    
    # Calculate vacation periods
    print(f"🧮 Calculating vacation periods...")
    vacations = calculate_vacation_periods(year, all_holidays)
    
    print(f"   ✅ Generated {len(vacations)} vacation periods:")
    for v in vacations:
        print(f"      • {v['text']}: {v['start']} → {v['end']}")
    
    # Format for Firestore
    holidays_formatted = format_holidays_for_firestore(all_holidays)
    
    # Prepare data structure
    data = {
        "label": f"תשפ\"{'ו' if year == 2025 else 'ז' if year == 2026 else 'ח'}",  # Hebrew year
        "holidays": holidays_formatted,
        "school_vacations": vacations,
        "generated_by": "auto_vacations.py",
        "generated_at": datetime.now().isoformat()
    }
    
    # Save to Firestore
    print(f"\n📤 Uploading to Firestore...")
    save_holidays(str(year), data)
    
    print(f"✅ Successfully saved vacations for {year}!")
    print(f"\n🎉 You can now use 'ייבא חופשות וחגים' in the app to import these vacations.")


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
