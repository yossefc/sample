import streamlit as st
import json
import io
import requests
from pathlib import Path
from datetime import datetime, timedelta

DATA_FILE = Path(__file__).parent / "schedule_data.json"
MINISTRY_DB_FILE = Path(__file__).parent / "ministry_exams_database.json"
HOLIDAYS_DB_FILE = Path(__file__).parent / "school_holidays.json"

STYLES = {
    "bagrut":   {"bg": "#FFCDD2", "fg": "#B71C1C", "bold": True,  "label": "\u05d1\u05d2\u05e8\u05d5\u05ea"},
    "magen":    {"bg": "#FFE0B2", "fg": "#E65100", "bold": True,  "label": "\u05de\u05d2\u05df / \u05de\u05ea\u05db\u05d5\u05e0\u05ea"},
    "trip":     {"bg": "#C8E6C9", "fg": "#1B5E20", "bold": False, "label": "\u05d8\u05d9\u05d5\u05dc / \u05de\u05e1\u05e2"},
    "vacation": {"bg": "#BBDEFB", "fg": "#0D47A1", "bold": False, "label": "\u05d7\u05d5\u05e4\u05e9\u05d4"},
    "holiday":  {"bg": "#E1BEE7", "fg": "#4A148C", "bold": False, "label": "\u05d7\u05d2 / \u05de\u05d5\u05e2\u05d3"},
    "general":  {"bg": "#F5F5F5", "fg": "#424242", "bold": False, "label": "\u05db\u05dc\u05dc\u05d9"},
}

# Locked event types that cause conflicts with bagrut exams
LOCKED_TYPES = {"trip"}

DAY_NAMES = ["\u05e8\u05d0\u05e9\u05d5\u05df", "\u05e9\u05e0\u05d9", "\u05e9\u05dc\u05d9\u05e9\u05d9", "\u05e8\u05d1\u05d9\u05e2\u05d9", "\u05d7\u05de\u05d9\u05e9\u05d9", "\u05e9\u05d9\u05e9\u05d9", "\u05e9\u05d1\u05ea"]
DAY_KEYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "shabbat"]


def load_data():
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_ministry_db():
    with open(MINISTRY_DB_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_holidays_db():
    if HOLIDAYS_DB_FILE.exists():
        with open(HOLIDAYS_DB_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def fetch_parasha_from_api(start_year, end_year):
    """Fetch parashat hashavua from Hebcal API for the given year range."""
    parasha_map = {}
    for year in range(start_year, end_year + 1):
        try:
            url = (
                f"https://www.hebcal.com/hebcal?v=1&cfg=json&s=on"
                f"&year={year}&month=x&geo=geoname&geonameid=281184"
            )
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("items", []):
                    if item.get("category") == "parashat":
                        d = item.get("date", "")
                        title = item.get("hebrew", item.get("title", ""))
                        if d and title:
                            # Parashat falls on Shabbat; find the Sunday (start) of that week
                            shabbat = datetime.strptime(d, "%Y-%m-%d")
                            sunday = shabbat - timedelta(days=6)
                            parasha_map[sunday.strftime("%Y-%m-%d")] = title
        except Exception:
            pass
    return parasha_map


def get_day_date(start_date_str, day_index):
    try:
        sd = datetime.strptime(start_date_str, "%Y-%m-%d")
        d = sd + timedelta(days=day_index)
        return d.strftime("%d/%m")
    except Exception:
        return ""


def refresh_ministry_db_from_web(season="summer"):
    """Fetch exam data from the Ministry of Education official Excel file."""
    from openpyxl import load_workbook

    if season == "summer":
        url = "https://meyda.education.gov.il/files/Exams/HoursSumExams2026.xlsx"
        moed_label = '\u05de\u05d5\u05e2\u05d3 \u05e7\u05d9\u05e5 \u05ea\u05e9\u05e4"\u05d5 (2026)'
    else:
        url = "https://meyda.education.gov.il/files/Exams/LuachWinExams2026HOURS.xlsx"
        moed_label = '\u05de\u05d5\u05e2\u05d3 \u05d7\u05d5\u05e8\u05e3 \u05ea\u05e9\u05e4"\u05d5 (2026)'

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    wb = load_workbook(io.BytesIO(resp.content), data_only=True)
    ws = wb.active

    exams = []
    for row in ws.iter_rows(min_row=3, max_row=ws.max_row, values_only=True):
        date_val, code, name = row[0], row[1], row[2]
        start_time = row[3] if len(row) > 3 else None
        end_time = row[4] if len(row) > 4 else None
        if not date_val or not code or not name:
            continue
        if isinstance(date_val, datetime):
            date_str = date_val.strftime("%Y-%m-%d")
        else:
            date_str = str(date_val)
        st_str = ""
        et_str = ""
        if start_time and hasattr(start_time, "strftime"):
            st_str = start_time.strftime("%H:%M")
        elif start_time:
            st_str = str(start_time)
        if end_time and hasattr(end_time, "strftime"):
            et_str = end_time.strftime("%H:%M")
        elif end_time:
            et_str = str(end_time)
        exams.append({
            "code": str(int(code)) if isinstance(code, (int, float)) else str(code),
            "name": str(name).strip(),
            "date": date_str,
            "start_time": st_str,
            "end_time": et_str,
        })

    db = {
        "last_updated": datetime.now().strftime("%Y-%m-%d"),
        "moed": moed_label,
        "source": "\u05de\u05e9\u05e8\u05d3 \u05d4\u05d7\u05d9\u05e0\u05d5\u05da - \u05d0\u05d2\u05e3 \u05d1\u05d7\u05d9\u05e0\u05d5\u05ea",
        "exams": exams,
    }
    with open(MINISTRY_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    return len(exams)


def get_full_date(start_date_str, day_index):
    """Return full date object for a specific day in the week."""
    try:
        sd = datetime.strptime(start_date_str, "%Y-%m-%d")
        return sd + timedelta(days=day_index)
    except Exception:
        return None


def date_to_week_day(data, target_date):
    """Find which week index and day key a date falls on. Returns (wi, dk) or None."""
    for wi, wk in enumerate(data["weeks"]):
        try:
            sd = datetime.strptime(wk["start_date"], "%Y-%m-%d")
        except Exception:
            continue
        for di, dk in enumerate(DAY_KEYS):
            d = sd + timedelta(days=di)
            if d.date() == target_date.date():
                return wi, dk
    return None


def check_conflicts_on_date(data, wi, dk, cls):
    """Check if a date has locked events (trips) for given class."""
    events = data["weeks"][wi]["days"].get(dk, [])
    conflicts = []
    for ev in events:
        if ev.get("type") in LOCKED_TYPES and ev.get("class") in (cls, "all"):
            conflicts.append(ev["text"])
    return conflicts


def search_ministry_db(ministry_db, query):
    """Search ministry DB by exam code or name substring. Returns list of matches."""
    query = query.strip()
    if not query:
        return []
    results = []
    for exam in ministry_db.get("exams", []):
        if query == exam["code"]:
            results.append(exam)
        elif query.lower() in exam["name"].lower() or query.lower() in exam.get("name_en", "").lower():
            results.append(exam)
    return results


def exam_card_html(exam):
    """Build HTML for an exam card, compatible with both old and new DB formats."""
    try:
        d = datetime.strptime(exam["date"], "%Y-%m-%d")
        date_display = d.strftime("%d/%m/%Y")
    except Exception:
        date_display = exam["date"]
    details = f'\u05e1\u05de\u05dc: {exam["code"]} | \u05ea\u05d0\u05e8\u05d9\u05da: {date_display}'
    if exam.get("start_time"):
        details += f' | {exam["start_time"]}-{exam.get("end_time", "")}'
    if exam.get("units"):
        details += f' | {exam["units"]} \u05d9\u05d7"\u05dc'
    if exam.get("subject_area"):
        details += f' | {exam["subject_area"]}'
    return (
        f'<div class="ministry-card">'
        f'<b>{exam["name"]}</b><br>'
        f'{details}</div>'
    )


def exam_option_label(ex):
    """Build selectbox label for an exam."""
    label = f"{ex['code']} - {ex['name']}"
    if ex.get("units"):
        label += f" ({ex['units']} \u05d9\u05d7\"\u05dc)"
    return label


def import_exam_to_schedule(data, exam, cls):
    """Import a ministry exam into the local schedule. Returns (success, conflict_msg)."""
    try:
        target = datetime.strptime(exam["date"], "%Y-%m-%d")
    except Exception:
        return False, "\u05ea\u05d0\u05e8\u05d9\u05da \u05dc\u05d0 \u05ea\u05e7\u05d9\u05df"

    loc = date_to_week_day(data, target)
    if loc is None:
        return False, "\u05d4\u05ea\u05d0\u05e8\u05d9\u05da \u05dc\u05d0 \u05e0\u05de\u05e6\u05d0 \u05d1\u05d8\u05d5\u05d5\u05d7 \u05d4\u05e9\u05d1\u05d5\u05e2\u05d5\u05ea \u05e9\u05dc \u05d4\u05dc\u05d5\u05d7"

    wi, dk = loc
    conflict_msg = ""
    conflicts = check_conflicts_on_date(data, wi, dk, cls)
    if conflicts:
        conflict_msg = f"\u05e9\u05d9\u05dd \u05dc\u05d1: \u05d4\u05ea\u05d0\u05e8\u05d9\u05da \u05de\u05ea\u05e0\u05d2\u05e9 \u05e2\u05dd \u05d0\u05d9\u05e8\u05d5\u05e2 \u05e7\u05d9\u05d9\u05dd! ({', '.join(conflicts)})"

    # Build the event with exam_code for resync tracking
    label = f"\u05d1\u05d2\u05e8\u05d5\u05ea {exam['name']} ({exam['code']})"
    new_event = {
        "text": label,
        "type": "bagrut",
        "class": cls,
        "exam_code": exam["code"],
    }

    cell = data["weeks"][wi]["days"].get(dk, [])
    # Check if already imported
    for ev in cell:
        if ev.get("exam_code") == exam["code"] and ev.get("class") == cls:
            return False, "\u05d4\u05d1\u05d2\u05e8\u05d5\u05ea \u05db\u05d1\u05e8 \u05e7\u05d9\u05d9\u05de\u05ea \u05d1\u05dc\u05d5\u05d7 \u05d1\u05ea\u05d0\u05e8\u05d9\u05da \u05d6\u05d4"
    cell.append(new_event)
    data["weeks"][wi]["days"][dk] = cell
    save_data(data)
    return True, conflict_msg


def resync_dates_with_ministry_db(data, ministry_db, cls):
    """
    Iterate through local schedule, find events with exam_code,
    compare dates to ministry DB, and move them if changed.
    Returns list of {code, name, old_date, new_date, conflict} dicts.
    """
    # Build lookup: code -> ministry exam
    ministry_lookup = {ex["code"]: ex for ex in ministry_db.get("exams", [])}

    changes = []

    for wi, wk in enumerate(data["weeks"]):
        try:
            sd = datetime.strptime(wk["start_date"], "%Y-%m-%d")
        except Exception:
            continue
        for di, dk in enumerate(DAY_KEYS):
            cell = wk["days"].get(dk, [])
            current_date = sd + timedelta(days=di)

            # Iterate a copy since we may remove items
            for ev in list(cell):
                code = ev.get("exam_code")
                if not code or ev.get("class") not in (cls, "all"):
                    continue
                if code not in ministry_lookup:
                    continue

                official = ministry_lookup[code]
                try:
                    official_date = datetime.strptime(official["date"], "%Y-%m-%d")
                except Exception:
                    continue

                # Compare dates
                if current_date.date() == official_date.date():
                    continue  # already correct

                # Date changed - find new location
                new_loc = date_to_week_day(data, official_date)
                if new_loc is None:
                    changes.append({
                        "code": code,
                        "name": official["name"],
                        "old_date": current_date.strftime("%d/%m/%Y"),
                        "new_date": official_date.strftime("%d/%m/%Y"),
                        "conflict": "\u05d4\u05ea\u05d0\u05e8\u05d9\u05da \u05d4\u05d7\u05d3\u05e9 \u05de\u05d7\u05d5\u05e5 \u05dc\u05d8\u05d5\u05d5\u05d7 \u05d4\u05dc\u05d5\u05d7",
                    })
                    continue

                new_wi, new_dk = new_loc

                # Check conflicts at new location
                conflicts = check_conflicts_on_date(data, new_wi, new_dk, cls)
                conflict_msg = ""
                if conflicts:
                    conflict_msg = f"\u05d4\u05ea\u05e0\u05d2\u05e9\u05d5\u05ea \u05e2\u05dd: {', '.join(conflicts)}"

                # Remove from old location
                cell.remove(ev)

                # Add to new location
                new_cell = data["weeks"][new_wi]["days"].get(new_dk, [])
                new_cell.append(ev)
                data["weeks"][new_wi]["days"][new_dk] = new_cell

                changes.append({
                    "code": code,
                    "name": official["name"],
                    "old_date": current_date.strftime("%d/%m/%Y"),
                    "new_date": official_date.strftime("%d/%m/%Y"),
                    "conflict": conflict_msg,
                })

    if changes:
        save_data(data)
    return changes


def generate_new_year(start_year):
    """Generate a new school year schedule from September to August.
    start_year is the civil year when school starts (e.g. 2026 for school year 2026-2027).
    Auto-populates holidays, vacations, and parashat hashavua.
    """
    # School year runs from September 1 to August 31
    # Find the first Sunday on or before September 1
    sep1 = datetime(start_year, 9, 1)
    days_since_sunday = (sep1.weekday() + 1) % 7
    first_sunday = sep1 - timedelta(days=days_since_sunday)

    aug31 = datetime(start_year + 1, 8, 31)

    weeks = []
    current = first_sunday
    while current <= aug31:
        end = current + timedelta(days=6)
        if current.month == end.month:
            dr = f"{current.day}-{end.day}.{current.month}"
        else:
            dr = f"{current.day}.{current.month}-{end.day}.{end.month}"

        weeks.append({
            "date_range": dr,
            "start_date": current.strftime("%Y-%m-%d"),
            "days": {dk: [] for dk in DAY_KEYS},
        })
        current += timedelta(days=7)

    # Hebrew year name
    heb_year_start = start_year + 3761
    heb_letters = {
        5784: '\u05ea\u05e9\u05e4"\u05d3', 5785: '\u05ea\u05e9\u05e4"\u05d4',
        5786: '\u05ea\u05e9\u05e4"\u05d5', 5787: '\u05ea\u05e9\u05e4"\u05d6',
        5788: '\u05ea\u05e9\u05e4"\u05d7', 5789: '\u05ea\u05e9\u05e4"\u05d8',
        5790: '\u05ea\u05e9"\u05e6',
    }
    year_label = heb_letters.get(heb_year_start, f'\u05ea\u05e9\u05e4"{heb_year_start - 5000}')

    new_data = {
        "classes": ["\u05d9\u05d0 1", "\u05d9\u05d0 2", "\u05d9\u05d0 3"],
        "year": year_label,
        "weeks": weeks,
        "parashat_hashavua": {},
    }

    # --- Auto-populate holidays from holidays DB ---
    holidays_db = load_holidays_db()
    year_key = str(start_year)
    if year_key in holidays_db:
        year_holidays = holidays_db[year_key]
        # Use label from DB if available
        if "label" in year_holidays:
            new_data["year"] = year_holidays["label"]
        # Add individual holiday events
        for h in year_holidays.get("holidays", []):
            try:
                hdate = datetime.strptime(h["date"], "%Y-%m-%d")
            except Exception:
                continue
            loc = _find_week_day(weeks, hdate)
            if loc is None:
                continue
            wi, dk = loc
            weeks[wi]["days"][dk].append({
                "text": h["text"],
                "type": h.get("type", "holiday"),
                "class": "all",
            })
        # Add vacation ranges
        for v in year_holidays.get("school_vacations", []):
            try:
                vs = datetime.strptime(v["start"], "%Y-%m-%d")
                ve = datetime.strptime(v["end"], "%Y-%m-%d")
            except Exception:
                continue
            d = vs
            while d <= ve:
                loc = _find_week_day(weeks, d)
                if loc:
                    wi, dk = loc
                    # Don't duplicate if a holiday already on this date
                    existing_texts = [e["text"] for e in weeks[wi]["days"][dk]]
                    if v["text"] not in existing_texts:
                        weeks[wi]["days"][dk].append({
                            "text": v["text"],
                            "type": "vacation",
                            "class": "all",
                        })
                d += timedelta(days=1)

    # --- Fetch parashat hashavua from Hebcal API ---
    try:
        parasha = fetch_parasha_from_api(start_year, start_year + 1)
        new_data["parashat_hashavua"] = parasha
    except Exception:
        new_data["parashat_hashavua"] = {}

    return new_data


def _find_week_day(weeks, target_date):
    """Find (week_index, day_key) for a date in a weeks list."""
    for wi, wk in enumerate(weeks):
        try:
            sd = datetime.strptime(wk["start_date"], "%Y-%m-%d")
        except Exception:
            continue
        for di, dk in enumerate(DAY_KEYS):
            d = sd + timedelta(days=di)
            if d.date() == target_date.date():
                return wi, dk
    return None


def chip_html(ev):
    s = STYLES.get(ev["type"], STYLES["general"])
    w = "700" if s["bold"] else "400"
    return (f'<span style="background:{s["bg"]};color:{s["fg"]};font-weight:{w};'
            f'padding:2px 8px;border-radius:10px;font-size:0.78em;display:inline-block;'
            f'margin:1px 0;line-height:1.4;">{ev["text"]}</span>')


def cell_html(date_str, chips_html, even=False):
    bg = "#F8F9FA" if even else "#FFFFFF"
    return (f'<div style="background:{bg};border:1px solid #DEE2E6;border-radius:6px;'
            f'padding:4px 3px;min-min-height:72px;text-align:center;display:flex;'
            f'flex-direction:column;align-items:center;justify-content:flex-start;gap:2px;'
            f'overflow:visible;">'
            f'<div style="color:#90A4AE;font-size:0.7em;font-weight:500;flex-shrink:0;">{date_str}</div>'
            f'{chips_html}</div>')


def to_excel(data, cls):
    from openpyxl import Workbook
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    cols = ["\u05e9\u05d1\u05d5\u05e2"] + DAY_NAMES
    pm = data.get("parashat_hashavua", {})
    wb = Workbook(); ws = wb.active; ws.title = cls
    ws.sheet_view.rightToLeft = True
    hf = PatternFill(start_color="1A237E", end_color="1A237E", fill_type="solid")
    hfn = Font(color="FFFFFF", bold=True, size=11)
    b = Border(*(Side(style="thin", color="B0BEC5") for _ in range(4)))
    for ci, cn in enumerate(cols, 1):
        c = ws.cell(row=1, column=ci, value=cn)
        c.fill = hf; c.font = hfn; c.border = b
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for ri, wk in enumerate(data["weeks"], 2):
        p = pm.get(wk["start_date"], "")
        c = ws.cell(row=ri, column=1, value=wk["date_range"])
        c.font = Font(bold=True, size=10); c.border = b
        c.alignment = Alignment(horizontal="center", vertical="center")
        for di, dk in enumerate(DAY_KEYS):
            evs = [e for e in wk["days"].get(dk, []) if e.get("class") in (cls, "all")]
            tx = [e["text"] for e in evs]
            if dk == "shabbat" and p:
                tx.append(f"\u05e4\u05e8\u05e9\u05ea {p}")
            cell = ws.cell(row=ri, column=di + 2, value="\n".join(tx))
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = b
            if evs:
                pr = ["bagrut", "magen", "trip", "vacation", "holiday"]
                dm = next((x for x in pr if any(e["type"] == x for e in evs)), "general")
                st2 = STYLES[dm]
                cell.fill = PatternFill(start_color=st2["bg"].lstrip("#"), end_color=st2["bg"].lstrip("#"), fill_type="solid")
                cell.font = Font(color=st2["fg"].lstrip("#"), bold=st2["bold"], size=10)
    ws.column_dimensions["A"].width = 14
    for ch in "BCDEFGH":
        ws.column_dimensions[ch].width = 22
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


# =====================================================================
# MAIN
# =====================================================================
def main():
    st.set_page_config(page_title="\u05dc\u05d5\u05d7 \u05e9\u05e0\u05d4", layout="wide")

    st.markdown("""<style>
    @import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;500;700;900&display=swap');
    html, body, .stApp {
        direction: rtl;
        font-family: 'Heebo', sans-serif;
    }
    .block-container { padding-top: 0.5rem; max-width: 98%; }
    .cal-hdr {
        background: linear-gradient(135deg, #1A237E, #283593);
        color: #fff; font-weight: 700; font-size: 0.82em;
        text-align: center; padding: 10px 4px; border-radius: 8px 8px 0 0;
    }
    .cal-week {
        background: linear-gradient(135deg, #37474F, #455A64);
        color: #ECEFF1; font-weight: 700;
        font-size: 0.78em; text-align: center; padding: 6px 2px;
        border-radius: 6px; min-height: 58px;
        display: flex; align-items: center; justify-content: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.15);
    }
    .legend-row {
        display: flex; flex-wrap: wrap; gap: 6px;
        justify-content: center; margin: 8px 0 14px;
    }
    .legend-chip {
        padding: 4px 14px; border-radius: 20px;
        font-size: 0.78em; font-weight: 500;
        box-shadow: 0 1px 2px rgba(0,0,0,0.08);
    }
    .cal-parasha {
        background: #FFF8E1; color: #F57F17; font-weight: 700;
        padding: 2px 7px; border-radius: 10px; font-size: 0.72em;
    }
    .stColumn > div { gap: 2px; }
    div[data-testid="stPopover"] button {
        font-size: 0.75em !important;
        padding: 0 4px !important;
        min-height: 0 !important;
        height: 20px !important;
        line-height: 20px !important;
        border-radius: 4px !important;
        background: #E8EAF6 !important;
        border: 1px solid #C5CAE9 !important;
        color: #3949AB !important;
        cursor: pointer !important;
        width: 100% !important;
    }
    div[data-testid="stPopover"] button:hover {
        background: #C5CAE9 !important;
    }
    .ministry-card {
        background: #E8F5E9; border: 1px solid #A5D6A7; border-radius: 8px;
        padding: 10px 14px; margin: 6px 0;
    }
    </style>""", unsafe_allow_html=True)

    data = load_data()
    ministry_db = load_ministry_db()

    # ==================================================================
    # SIDEBAR
    # ==================================================================
    with st.sidebar:
        st.markdown("### \u05d4\u05d2\u05d3\u05e8\u05d5\u05ea")
        cls = st.selectbox("\u05db\u05d9\u05ea\u05d4", data["classes"])
        is_admin = st.checkbox("\u05de\u05e6\u05d1 \u05e2\u05e8\u05d9\u05db\u05d4")
        if is_admin:
            st.markdown("---")
            nc = st.text_input("\u05d4\u05d5\u05e1\u05e4\u05ea \u05db\u05d9\u05ea\u05d4", key="nc")
            if st.button("\u05d4\u05d5\u05e1\u05e3 \u05db\u05d9\u05ea\u05d4") and nc.strip() and nc.strip() not in data["classes"]:
                data["classes"].append(nc.strip()); save_data(data); st.rerun()

        # ----------------------------------------------------------
        # MINISTRY SEARCH - text search + selectbox
        # ----------------------------------------------------------
        st.markdown("---")
        st.markdown("### \u05d9\u05d9\u05d1\u05d5\u05d0 \u05de\u05de\u05d0\u05d2\u05e8 \u05de\u05e9\u05e8\u05d3 \u05d4\u05d7\u05d9\u05e0\u05d5\u05da")
        moed_info = ministry_db.get("moed", "")
        st.caption(f"{moed_info} | {len(ministry_db.get('exams',[]))} \u05d1\u05d7\u05d9\u05e0\u05d5\u05ea")
        if is_admin:
            if st.button("\u05e8\u05e2\u05e0\u05df \u05de\u05de\u05e9\u05e8\u05d3 \u05d4\u05d7\u05d9\u05e0\u05d5\u05da", key="refresh_ministry"):
                try:
                    with st.spinner("\u05de\u05d5\u05e8\u05d9\u05d3 \u05e0\u05ea\u05d5\u05e0\u05d9\u05dd \u05de\u05de\u05e9\u05e8\u05d3 \u05d4\u05d7\u05d9\u05e0\u05d5\u05da..."):
                        count = refresh_ministry_db_from_web()
                    st.toast(f"\u05e2\u05d5\u05d3\u05db\u05df! {count} \u05d1\u05d7\u05d9\u05e0\u05d5\u05ea \u05d9\u05d5\u05d1\u05d0\u05d5", icon="\u2705")
                    st.rerun()
                except Exception as ex:
                    st.error(f"\u05e9\u05d2\u05d9\u05d0\u05d4: {ex}")

        all_exams = ministry_db.get("exams", [])
        exam_lookup = {ex["code"]: ex for ex in all_exams}

        # --- Text search by subject ---
        search_query = st.text_input(
            "\u05d7\u05d9\u05e4\u05d5\u05e9 \u05dc\u05e4\u05d9 \u05de\u05e7\u05e6\u05d5\u05e2 \u05d0\u05d5 \u05e1\u05de\u05dc",
            key="ministry_text_search",
            placeholder="\u05dc\u05de\u05e9\u05dc: \u05de\u05ea\u05de\u05d8\u05d9\u05e7\u05d4, \u05d0\u05e0\u05d2\u05dc\u05d9\u05ea, 899271...",
        )

        if search_query.strip():
            results = search_ministry_db(ministry_db, search_query)
            if results:
                st.caption(f"\u05e0\u05de\u05e6\u05d0\u05d5 {len(results)} \u05ea\u05d5\u05e6\u05d0\u05d5\u05ea")
                for exam in results:
                    st.markdown(exam_card_html(exam), unsafe_allow_html=True)
                    if st.button(
                        f"\u05d9\u05d9\u05d1\u05d0 {exam['name'][:30]}",
                        key=f"import_search_{exam['code']}",
                    ):
                        success, msg = import_exam_to_schedule(data, exam, cls)
                        if success:
                            if msg:
                                st.toast(msg, icon="\u26a0\ufe0f")
                            else:
                                st.toast(f"\u05d9\u05d5\u05d1\u05d0 \u05d1\u05d4\u05e6\u05dc\u05d7\u05d4: {exam['name']}", icon="\u2705")
                            st.rerun()
                        else:
                            st.info(msg)
            else:
                st.caption("\u05dc\u05d0 \u05e0\u05de\u05e6\u05d0\u05d5 \u05ea\u05d5\u05e6\u05d0\u05d5\u05ea")

        # --- Selectbox with ALL exams ---
        st.markdown("**\u05d0\u05d5 \u05d1\u05d7\u05e8 \u05de\u05d4\u05e8\u05e9\u05d9\u05de\u05d4:**")
        exam_options = ["\u05d1\u05d7\u05e8 \u05de\u05e7\u05e6\u05d5\u05e2..."] + [
            exam_option_label(ex) for ex in all_exams
        ]
        selected_option = st.selectbox(
            "\u05e9\u05dd \u05de\u05e7\u05e6\u05d5\u05e2",
            exam_options,
            key="ministry_select",
            label_visibility="collapsed",
        )

        if selected_option != "\u05d1\u05d7\u05e8 \u05de\u05e7\u05e6\u05d5\u05e2...":
            sel_code = selected_option.split(" - ")[0].strip()
            exam = exam_lookup.get(sel_code)
            if exam:
                st.markdown(exam_card_html(exam), unsafe_allow_html=True)
                if st.button(
                    "\u05d9\u05d9\u05d1\u05d0 \u05dc\u05dc\u05d5\u05d7 \u05e9\u05dc\u05d9",
                    key=f"import_{exam['code']}",
                ):
                    success, msg = import_exam_to_schedule(data, exam, cls)
                    if success:
                        if msg:
                            st.toast(msg, icon="\u26a0\ufe0f")
                        else:
                            st.toast(f"\u05d9\u05d5\u05d1\u05d0 \u05d1\u05d4\u05e6\u05dc\u05d7\u05d4: {exam['name']}", icon="\u2705")
                        st.rerun()
                    else:
                        st.info(msg)

        # ----------------------------------------------------------
        # RESYNC BUTTON
        # ----------------------------------------------------------
        st.markdown("---")
        st.markdown("### \u05e1\u05e0\u05db\u05e8\u05d5\u05df \u05ea\u05d0\u05e8\u05d9\u05db\u05d9 \u05d1\u05d2\u05e8\u05d5\u05ea")
        st.caption("\u05d1\u05d3\u05d5\u05e7 \u05e2\u05d3\u05db\u05d5\u05e0\u05d9 \u05ea\u05d0\u05e8\u05d9\u05db\u05d9\u05dd \u05de\u05d5\u05dc \u05de\u05d0\u05d2\u05e8 \u05de\u05e9\u05e8\u05d3 \u05d4\u05d7\u05d9\u05e0\u05d5\u05da")
        if st.button("\u05e1\u05e0\u05db\u05e8\u05df \u05ea\u05d0\u05e8\u05d9\u05db\u05d9 \u05d1\u05d2\u05e8\u05d5\u05ea", type="primary", use_container_width=True):
            changes = resync_dates_with_ministry_db(data, ministry_db, cls)
            if not changes:
                st.success("\u05db\u05dc \u05d4\u05ea\u05d0\u05e8\u05d9\u05db\u05d9\u05dd \u05de\u05e2\u05d5\u05d3\u05db\u05e0\u05d9\u05dd!")
            else:
                st.markdown("**\u05e9\u05d9\u05e0\u05d5\u05d9\u05d9\u05dd \u05e9\u05d1\u05d5\u05e6\u05e2\u05d5:**")
                for ch in changes:
                    st.markdown(
                        f"- **{ch['name']}** ({ch['code']}): "
                        f"{ch['old_date']} \u2192 {ch['new_date']}"
                    )
                    if ch["conflict"]:
                        st.error(f"\u05d4\u05ea\u05e0\u05d2\u05e9\u05d5\u05ea: {ch['conflict']}")
                st.rerun()

        # ----------------------------------------------------------
        # IMPORT VACATIONS FROM HOLIDAYS DB
        # ----------------------------------------------------------
        st.markdown("---")
        st.markdown("### ייבוא חופשות ממשרד החינוך")
        st.caption("ייבא חגים וחופשות ללוח מקובץ החגים")
        if st.button("ייבא חופשות וחגים", key="import_holidays_btn", use_container_width=True):
            holidays_db = load_holidays_db()
            added_count = 0
            # Determine which year keys to use based on schedule weeks
            first_wk = data["weeks"][0] if data["weeks"] else None
            last_wk = data["weeks"][-1] if data["weeks"] else None
            year_keys = set()
            if first_wk:
                try:
                    sy = datetime.strptime(first_wk["start_date"], "%Y-%m-%d").year
                    year_keys.add(str(sy))
                    if sy >= 2025:
                        year_keys.add(str(sy - 1))
                except Exception:
                    pass
            if last_wk:
                try:
                    ey = datetime.strptime(last_wk["start_date"], "%Y-%m-%d").year
                    year_keys.add(str(ey))
                except Exception:
                    pass
            for yk in year_keys:
                if yk not in holidays_db:
                    continue
                yh = holidays_db[yk]
                # Import individual holidays
                for h in yh.get("holidays", []):
                    try:
                        hdate = datetime.strptime(h["date"], "%Y-%m-%d")
                    except Exception:
                        continue
                    loc = date_to_week_day(data, hdate)
                    if loc is None:
                        continue
                    wi2, dk2 = loc
                    cell2 = data["weeks"][wi2]["days"].get(dk2, [])
                    if any(e["text"] == h["text"] for e in cell2):
                        continue
                    cell2.append({"text": h["text"], "type": h.get("type", "holiday"), "class": "all"})
                    data["weeks"][wi2]["days"][dk2] = cell2
                    added_count += 1
                # Import vacation ranges
                for v in yh.get("school_vacations", []):
                    try:
                        vs = datetime.strptime(v["start"], "%Y-%m-%d")
                        ve = datetime.strptime(v["end"], "%Y-%m-%d")
                    except Exception:
                        continue
                    d = vs
                    while d <= ve:
                        loc = date_to_week_day(data, d)
                        if loc:
                            wi2, dk2 = loc
                            cell2 = data["weeks"][wi2]["days"].get(dk2, [])
                            if not any(e["text"] == v["text"] for e in cell2):
                                cell2.append({"text": v["text"], "type": "vacation", "class": "all"})
                                data["weeks"][wi2]["days"][dk2] = cell2
                                added_count += 1
                        d += timedelta(days=1)
            if added_count > 0:
                save_data(data)
                st.toast(f"יובאו {added_count} אירועים!", icon="✅")
                st.rerun()
            else:
                st.info("כל החגים והחופשות כבר קיימים בלוח")

        # ----------------------------------------------------------
        # YEAR ROLLOVER
        # ----------------------------------------------------------
        if is_admin:
            st.markdown("---")
            st.markdown("### \u05de\u05e2\u05d1\u05e8 \u05dc\u05e9\u05e0\u05d4 \u05d7\u05d3\u05e9\u05d4")
            st.caption("\u05d9\u05d9\u05e6\u05e8 \u05dc\u05d5\u05d7 \u05e9\u05e0\u05d4 \u05d7\u05d3\u05e9 \u05e2\u05dd \u05d7\u05d2\u05d9\u05dd, \u05d7\u05d5\u05e4\u05e9\u05d5\u05ea \u05d5\u05e4\u05e8\u05e9\u05ea \u05d4\u05e9\u05d1\u05d5\u05e2")
            new_year_start = st.number_input(
                "\u05e9\u05e0\u05ea \u05d4\u05ea\u05d7\u05dc\u05d4 (\u05dc\u05d5\u05e2\u05d6\u05d9)",
                min_value=2024,
                max_value=2040,
                value=2026,
                key="new_year_input",
            )
            import_bagrut = st.checkbox(
                "\u05d9\u05d9\u05d1\u05d0 \u05d1\u05d2\u05e8\u05d5\u05d9\u05d5\u05ea \u05d0\u05d5\u05d8\u05d5\u05de\u05d8\u05d9\u05ea (\u05d4\u05e1\u05d8\u05ea \u05ea\u05d0\u05e8\u05d9\u05db\u05d9\u05dd \u05dc\u05e9\u05e0\u05d4 \u05d4\u05e0\u05d1\u05d7\u05e8\u05ea)",
                value=True,
                key="import_bagrut_check",
            )
            if st.button("\u05e6\u05d5\u05e8 \u05e9\u05e0\u05d4 \u05d7\u05d3\u05e9\u05d4", key="gen_new_year"):
                with st.spinner("\u05d9\u05d5\u05e6\u05e8 \u05dc\u05d5\u05d7 \u05e9\u05e0\u05d4 \u05d5\u05de\u05d9\u05d9\u05d1\u05d0 \u05e0\u05ea\u05d5\u05e0\u05d9\u05dd..."):
                    new_data = generate_new_year(int(new_year_start))
                    new_data["classes"] = data["classes"]

                    # Auto-import bagrut exams
                    if import_bagrut:
                        # Detect DB base year from first exam date
                        db_base_year = None
                        for ex in ministry_db.get("exams", []):
                            try:
                                db_base_year = datetime.strptime(ex["date"], "%Y-%m-%d").year
                                break
                            except Exception:
                                continue
                        if db_base_year:
                            # Exams happen in spring of the 2nd civil year of a school year
                            target_exam_year = int(new_year_start) + 1
                            year_offset = target_exam_year - db_base_year
                        else:
                            year_offset = 0

                        placed = 0
                        for exam in ministry_db.get("exams", []):
                            try:
                                orig_date = datetime.strptime(exam["date"], "%Y-%m-%d")
                                if year_offset != 0:
                                    shifted_date = orig_date.replace(year=orig_date.year + year_offset)
                                else:
                                    shifted_date = orig_date
                                loc = _find_week_day(new_data["weeks"], shifted_date)
                                if loc:
                                    wi, dk = loc
                                    label = f'{exam["name"]} ({exam["code"]})'
                                    new_data["weeks"][wi]["days"][dk].append({
                                        "text": label,
                                        "type": "bagrut",
                                        "class": cls,
                                        "exam_code": exam["code"],
                                    })
                                    placed += 1
                            except Exception:
                                continue

                    save_data(new_data)
                st.toast("\u05dc\u05d5\u05d7 \u05e9\u05e0\u05d4 \u05d7\u05d3\u05e9 \u05e0\u05d5\u05e6\u05e8 \u05e2\u05dd \u05d7\u05d2\u05d9\u05dd \u05d5\u05d1\u05d2\u05e8\u05d5\u05d9\u05d5\u05ea!", icon="\u2705")
                st.rerun()

    # ==================================================================
    # MAIN CONTENT
    # ==================================================================

    # ---- Title ----
    st.markdown(
        f'<h2 style="text-align:center;margin:0 0 2px;color:#1A237E;font-weight:900;">'
        f'\u05dc\u05d5\u05d7 \u05e9\u05e0\u05d4 {data.get("year", "")} - \u05e9\u05db\u05d1\u05ea \u05d9\u05d0</h2>',
        unsafe_allow_html=True)
    st.markdown(
        f'<p style="text-align:center;margin:0 0 4px;color:#5C6BC0;font-size:0.9em;">{cls}</p>',
        unsafe_allow_html=True)

    # ---- Legend ----
    lg = "".join(
        f'<span class="legend-chip" style="background:{s["bg"]};color:{s["fg"]};'
        f'font-weight:{"700" if s["bold"] else "400"};">{s["label"]}</span>'
        for s in STYLES.values()
    )
    lg += '<span class="legend-chip cal-parasha">\u05e4\u05e8\u05e9\u05ea \u05d4\u05e9\u05d1\u05d5\u05e2</span>'
    st.markdown(f'<div class="legend-row">{lg}</div>', unsafe_allow_html=True)

    pm = data.get("parashat_hashavua", {})

    # ---- Month / date filter ----
    MONTH_NAMES_HEB = {
        1: "\u05d9\u05e0\u05d5\u05d0\u05e8", 2: "\u05e4\u05d1\u05e8\u05d5\u05d0\u05e8", 3: "\u05de\u05e8\u05e5",
        4: "\u05d0\u05e4\u05e8\u05d9\u05dc", 5: "\u05de\u05d0\u05d9", 6: "\u05d9\u05d5\u05e0\u05d9",
        7: "\u05d9\u05d5\u05dc\u05d9", 8: "\u05d0\u05d5\u05d2\u05d5\u05e1\u05d8", 9: "\u05e1\u05e4\u05d8\u05de\u05d1\u05e8",
        10: "\u05d0\u05d5\u05e7\u05d8\u05d5\u05d1\u05e8", 11: "\u05e0\u05d5\u05d1\u05de\u05d1\u05e8", 12: "\u05d3\u05e6\u05de\u05d1\u05e8",
    }

    # Collect available months from weeks
    available_months = []
    month_set = set()
    for wk in data["weeks"]:
        try:
            sd = datetime.strptime(wk["start_date"], "%Y-%m-%d")
            key = (sd.year, sd.month)
            if key not in month_set:
                month_set.add(key)
                available_months.append(key)
            # Also check end of week (Saturday)
            ed = sd + timedelta(days=6)
            key2 = (ed.year, ed.month)
            if key2 not in month_set:
                month_set.add(key2)
                available_months.append(key2)
        except Exception:
            pass
    available_months.sort()

    month_options = ["\u05db\u05dc \u05d4\u05e9\u05e0\u05d4"] + [
        f"{MONTH_NAMES_HEB[m]} {y}" for y, m in available_months
    ]

    fc1, fc2, fc3 = st.columns([1, 3, 1])
    with fc1:
        selected_month = st.selectbox(
            "\u05e1\u05d9\u05e0\u05d5\u05df \u05dc\u05e4\u05d9 \u05d7\u05d5\u05d3\u05e9",
            month_options,
            key="month_filter",
        )
    with fc3:
        show_past_weeks = st.checkbox(
            "↑ הצג שבועות קודמים",
            value=False,
            key="show_past",
        )

    # Get today's date for filtering
    today = datetime.now().date()

    # Determine which weeks to show
    if selected_month == "\u05db\u05dc \u05d4\u05e9\u05e0\u05d4":
        filtered_weeks = list(enumerate(data["weeks"]))
    else:
        idx = month_options.index(selected_month) - 1
        sel_year, sel_month = available_months[idx]
        filtered_weeks = []
        for wi, wk in enumerate(data["weeks"]):
            try:
                sd = datetime.strptime(wk["start_date"], "%Y-%m-%d")
                ed = sd + timedelta(days=6)
                if (sd.year == sel_year and sd.month == sel_month) or \
                   (ed.year == sel_year and ed.month == sel_month):
                    filtered_weeks.append((wi, wk))
            except Exception:
                filtered_weeks.append((wi, wk))

    # Filter to show only current and future weeks unless checkbox is checked
    if not show_past_weeks:
        current_and_future = []
        for wi, wk in filtered_weeks:
            try:
                sd = datetime.strptime(wk["start_date"], "%Y-%m-%d")
                ed = sd + timedelta(days=6)
                if ed.date() >= today:
                    current_and_future.append((wi, wk))
            except Exception:
                current_and_future.append((wi, wk))
        filtered_weeks = current_and_future

    # ---- Header row ----
    hcols = st.columns(7)
    for i, dn in enumerate(DAY_NAMES):
        with hcols[i]:
            st.markdown(f'<div class="cal-hdr">{dn}</div>', unsafe_allow_html=True)

    # ---- Week rows ----
    for wi, wk in filtered_weeks:
        parasha = pm.get(wk["start_date"], "")
        rcols = st.columns(7)
        even = wi % 2 == 0

        for di, dk in enumerate(DAY_KEYS):
            with rcols[di]:
                day_date = get_day_date(wk.get("start_date", ""), di)
                evs = [e for e in wk["days"].get(dk, []) if e.get("class") in (cls, "all")]
                chips = "".join(chip_html(e) for e in evs)
                if dk == "shabbat" and parasha:
                    chips += f'<span class="cal-parasha">{parasha}</span>'

                st.markdown(cell_html(day_date, chips, even), unsafe_allow_html=True)

                if is_admin:
                    all_cell = wk["days"].get(dk, [])
                    vis = [e for e in all_cell if e.get("class") in (cls, "all")]

                    with st.popover("+", use_container_width=True):
                        st.markdown(f"**{DAY_NAMES[di]} {day_date}**")

                        for idx, ev in enumerate(vis):
                            if st.button(
                                f"\u2715  {ev['text']}",
                                key=f"del_{wi}_{di}_{idx}",
                                use_container_width=True,
                            ):
                                all_cell.remove(ev)
                                save_data(data)
                                st.rerun()

                        nt = st.text_input("\u05e9\u05dd", key=f"t_{wi}_{di}",
                                           placeholder="\u05e9\u05dd \u05d0\u05d9\u05e8\u05d5\u05e2")
                        tp = st.selectbox("\u05e1\u05d5\u05d2", list(STYLES.keys()),
                                          format_func=lambda x: STYLES[x]["label"],
                                          key=f"tp_{wi}_{di}")
                        ecls = st.selectbox("\u05db\u05d9\u05ea\u05d4",
                                            data["classes"] + ["all"],
                                            key=f"c_{wi}_{di}")
                        if st.button("\u05d4\u05d5\u05e1\u05e3", key=f"a_{wi}_{di}",
                                     type="primary", use_container_width=True):
                            if nt.strip():
                                all_cell.append({"text": nt.strip(), "type": tp, "class": ecls})
                                save_data(data)
                                st.rerun()

    # ---- Excel download ----
    st.markdown("---")
    st.download_button(
        "\u05d4\u05d5\u05e8\u05d3 \u05d0\u05e7\u05e1\u05dc",
        data=to_excel(data, cls),
        file_name=f"\u05dc\u05d5\u05d7_{cls}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.document")


if __name__ == "__main__":
    main()
