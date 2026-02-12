"""
app.py - Multi-Tenant SaaS School Exam Schedule Platform ("Luach Mivchanim").

Modules:
  1. Firebase Database Architecture (Firestore collections)
  2. Authentication & Roles (Director / Teacher / Parent-Public)
  3. Visual Scheduler (color-coded grid with Hebrew calendar)
  4. Intelligent Features (Ministry sync, conflict detection, WhatsApp share)
  5. Payments (billing structure per class)

No hardcoded dates - all dates come from Firestore or external APIs.
"""

import io
import urllib.parse
from datetime import datetime, timedelta

import requests
import streamlit as st

from auth_manager import authenticate
from db_manager import (
    add_class_to_school,
    add_event,
    add_payment,
    create_school,
    delete_payment,
    get_holidays,
    get_ministry_exam,
    get_ministry_exams,
    get_ministry_meta,
    get_payments,
    get_payments_for_class,
    get_permissions,
    get_schedule,
    remove_event,
    remove_teacher_permission,
    save_ministry_exams,
    save_schedule,
    search_ministry_exams,
    set_teacher_permission,
    update_school,
)

# ===================================================================
# CONSTANTS (no hardcoded dates)
# ===================================================================

STYLES = {
    "bagrut":   {"bg": "#FFCDD2", "fg": "#B71C1C", "bold": True,  "label": "בגרות"},
    "magen":    {"bg": "#FFE0B2", "fg": "#E65100", "bold": True,  "label": "מגן / מתכונת"},
    "trip":     {"bg": "#C8E6C9", "fg": "#1B5E20", "bold": False, "label": "טיול / מסע"},
    "vacation": {"bg": "#BBDEFB", "fg": "#0D47A1", "bold": False, "label": "חופשה"},
    "holiday":  {"bg": "#E1BEE7", "fg": "#4A148C", "bold": False, "label": "חג / מועד"},
    "general":  {"bg": "#F5F5F5", "fg": "#424242", "bold": False, "label": "כללי"},
}

LOCKED_TYPES = {"trip"}

DAY_NAMES = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"]
DAY_KEYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "shabbat"]

MONTH_NAMES_HEB = {
    1: "ינואר", 2: "פברואר", 3: "מרץ", 4: "אפריל",
    5: "מאי", 6: "יוני", 7: "יולי", 8: "אוגוסט",
    9: "ספטמבר", 10: "אוקטובר", 11: "נובמבר", 12: "דצמבר",
}


# ===================================================================
# HELPERS
# ===================================================================

def get_day_date(start_date_str: str, day_index: int) -> str:
    try:
        sd = datetime.strptime(start_date_str, "%Y-%m-%d")
        d = sd + timedelta(days=day_index)
        return d.strftime("%d/%m")
    except Exception:
        return ""


def get_full_date(start_date_str: str, day_index: int):
    try:
        sd = datetime.strptime(start_date_str, "%Y-%m-%d")
        return sd + timedelta(days=day_index)
    except Exception:
        return None


def date_to_week_day(weeks: list, target_date) -> tuple | None:
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


def check_conflicts_on_date(weeks: list, wi: int, dk: str, cls: str) -> list[str]:
    events = weeks[wi]["days"].get(dk, [])
    return [
        ev["text"] for ev in events
        if ev.get("type") in LOCKED_TYPES and ev.get("class") in (cls, "all")
    ]


def fetch_parasha_from_api(start_year: int, end_year: int) -> dict:
    """Fetch Parashat HaShavua from Hebcal API. Returns {sunday_date: hebrew_name}."""
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
                            shabbat = datetime.strptime(d, "%Y-%m-%d")
                            sunday = shabbat - timedelta(days=6)
                            parasha_map[sunday.strftime("%Y-%m-%d")] = title
        except Exception:
            pass
    return parasha_map


def refresh_ministry_db_from_web(season: str = "summer") -> int:
    """Download Ministry of Education exam schedule Excel and store in Firestore."""
    from openpyxl import load_workbook

    current_year = datetime.now().year
    if season == "summer":
        url = f"https://meyda.education.gov.il/files/Exams/HoursSumExams{current_year}.xlsx"
        moed_label = f'מועד קיץ {current_year}'
    else:
        url = f"https://meyda.education.gov.il/files/Exams/LuachWinExams{current_year}HOURS.xlsx"
        moed_label = f'מועד חורף {current_year}'

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

    save_ministry_exams(exams, moed=moed_label, source="משרד החינוך - אגף בחינות")
    return len(exams)


def generate_new_year(start_year: int) -> dict:
    """Generate a new academic year schedule structure. No hardcoded dates."""
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

    # Hebrew year label derived from start_year
    heb_year_num = start_year + 3761
    heb_letters = {
        5784: 'תשפ"ד', 5785: 'תשפ"ה', 5786: 'תשפ"ו', 5787: 'תשפ"ז',
        5788: 'תשפ"ח', 5789: 'תשפ"ט', 5790: 'תש"צ',
    }
    year_label = heb_letters.get(heb_year_num, f"תשפ {heb_year_num - 5000}")

    new_data = {
        "classes": [],
        "year": year_label,
        "weeks": weeks,
        "parashat_hashavua": {},
    }

    # Auto-fill holidays from Firestore
    for yr_key in [str(start_year), str(start_year + 1)]:
        holidays_data = get_holidays(yr_key)
        if not holidays_data:
            continue
        if "label" in holidays_data and yr_key == str(start_year):
            new_data["year"] = holidays_data["label"]
        for h in holidays_data.get("holidays", []):
            try:
                hdate = datetime.strptime(h["date"], "%Y-%m-%d")
            except Exception:
                continue
            loc = date_to_week_day(weeks, hdate)
            if loc is None:
                continue
            wi, dk = loc
            weeks[wi]["days"][dk].append({
                "text": h["text"], "type": h.get("type", "holiday"), "class": "all",
            })
        for v in holidays_data.get("school_vacations", []):
            try:
                vs = datetime.strptime(v["start"], "%Y-%m-%d")
                ve = datetime.strptime(v["end"], "%Y-%m-%d")
            except Exception:
                continue
            d = vs
            while d <= ve:
                loc = date_to_week_day(weeks, d)
                if loc:
                    wi, dk = loc
                    existing_texts = [e["text"] for e in weeks[wi]["days"][dk]]
                    if v["text"] not in existing_texts:
                        weeks[wi]["days"][dk].append({
                            "text": v["text"], "type": "vacation", "class": "all",
                        })
                d += timedelta(days=1)

    # Auto-fill Parashat HaShavua from Hebcal
    try:
        parasha = fetch_parasha_from_api(start_year, start_year + 1)
        new_data["parashat_hashavua"] = parasha
    except Exception:
        new_data["parashat_hashavua"] = {}

    return new_data


# ===================================================================
# IMPORT EXAM TO SCHEDULE
# ===================================================================

def import_exam_to_schedule(data: dict, exam: dict, cls: str) -> tuple[bool, str]:
    """Add a ministry exam to the schedule. Returns (success, message)."""
    try:
        target = datetime.strptime(exam["date"], "%Y-%m-%d")
    except Exception:
        return False, "תאריך לא תקין"

    loc = date_to_week_day(data["weeks"], target)
    if loc is None:
        return False, "התאריך לא נמצא בטווח השבועות של הלוח"

    wi, dk = loc
    conflict_msg = ""
    conflicts = check_conflicts_on_date(data["weeks"], wi, dk, cls)
    if conflicts:
        conflict_msg = f"שים לב: התאריך מתנגש עם אירוע קיים! ({', '.join(conflicts)})"

    label = f"בגרות {exam['name']} ({exam['code']})"
    new_event = {
        "text": label, "type": "bagrut", "class": cls, "exam_code": exam["code"],
    }

    cell = data["weeks"][wi]["days"].get(dk, [])
    for ev in cell:
        if ev.get("exam_code") == exam["code"] and ev.get("class") == cls:
            return False, "הבגרות כבר קיימת בלוח בתאריך זה"
    cell.append(new_event)
    data["weeks"][wi]["days"][dk] = cell
    return True, conflict_msg


def resync_dates_with_ministry(data: dict, cls: str) -> list[dict]:
    """Re-check all bagrut events against Firestore ministry data. Move if dates changed."""
    all_exams = get_ministry_exams()
    ministry_lookup = {ex["code"]: ex for ex in all_exams if ex.get("code") != "_metadata"}
    changes = []

    for wi, wk in enumerate(data["weeks"]):
        try:
            sd = datetime.strptime(wk["start_date"], "%Y-%m-%d")
        except Exception:
            continue
        for di, dk in enumerate(DAY_KEYS):
            cell = wk["days"].get(dk, [])
            current_date = sd + timedelta(days=di)
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
                if current_date.date() == official_date.date():
                    continue
                new_loc = date_to_week_day(data["weeks"], official_date)
                if new_loc is None:
                    changes.append({
                        "code": code, "name": official["name"],
                        "old_date": current_date.strftime("%d/%m/%Y"),
                        "new_date": official_date.strftime("%d/%m/%Y"),
                        "conflict": "התאריך החדש מחוץ לטווח הלוח",
                    })
                    continue
                new_wi, new_dk = new_loc
                conflict_list = check_conflicts_on_date(data["weeks"], new_wi, new_dk, cls)
                conflict_msg = f"התנגשות עם: {', '.join(conflict_list)}" if conflict_list else ""
                cell.remove(ev)
                new_cell = data["weeks"][new_wi]["days"].get(new_dk, [])
                new_cell.append(ev)
                data["weeks"][new_wi]["days"][new_dk] = new_cell
                changes.append({
                    "code": code, "name": official["name"],
                    "old_date": current_date.strftime("%d/%m/%Y"),
                    "new_date": official_date.strftime("%d/%m/%Y"),
                    "conflict": conflict_msg,
                })
    return changes


# ===================================================================
# HTML RENDERING
# ===================================================================

def chip_html(ev: dict) -> str:
    s = STYLES.get(ev.get("type", "general"), STYLES["general"])
    w = "700" if s["bold"] else "400"
    return (
        f'<span style="background:{s["bg"]};color:{s["fg"]};font-weight:{w};'
        f'padding:2px 8px;border-radius:10px;font-size:0.78em;display:inline-block;'
        f'margin:1px 0;line-height:1.4;">{ev["text"]}</span>'
    )


def cell_html(date_str: str, chips_html: str, even: bool = False) -> str:
    bg = "#F8F9FA" if even else "#FFFFFF"
    return (
        f'<div style="background:{bg};border:1px solid #DEE2E6;border-radius:6px;'
        f'padding:4px 3px;min-height:72px;text-align:center;display:flex;'
        f'flex-direction:column;align-items:center;justify-content:flex-start;gap:2px;'
        f'overflow:visible;">'
        f'<div style="color:#90A4AE;font-size:0.7em;font-weight:500;flex-shrink:0;">{date_str}</div>'
        f'{chips_html}</div>'
    )


def exam_card_html(exam: dict) -> str:
    try:
        d = datetime.strptime(exam["date"], "%Y-%m-%d")
        date_display = d.strftime("%d/%m/%Y")
    except Exception:
        date_display = exam.get("date", "")
    details = f'סמל: {exam["code"]} | תאריך: {date_display}'
    if exam.get("start_time"):
        details += f' | {exam["start_time"]}-{exam.get("end_time", "")}'
    return (
        f'<div class="ministry-card"><b>{exam["name"]}</b><br>{details}</div>'
    )


# ===================================================================
# EXPORT: EXCEL
# ===================================================================

def to_excel(data: dict, cls: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    cols = ["שבוע"] + DAY_NAMES
    pm = data.get("parashat_hashavua", {})
    wb = Workbook()
    ws = wb.active
    ws.title = cls
    ws.sheet_view.rightToLeft = True
    hf = PatternFill(start_color="1A237E", end_color="1A237E", fill_type="solid")
    hfn = Font(color="FFFFFF", bold=True, size=11)
    b = Border(*(Side(style="thin", color="B0BEC5") for _ in range(4)))
    for ci, cn in enumerate(cols, 1):
        c = ws.cell(row=1, column=ci, value=cn)
        c.fill = hf
        c.font = hfn
        c.border = b
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for ri, wk in enumerate(data["weeks"], 2):
        p = pm.get(wk["start_date"], "")
        c = ws.cell(row=ri, column=1, value=wk["date_range"])
        c.font = Font(bold=True, size=10)
        c.border = b
        c.alignment = Alignment(horizontal="center", vertical="center")
        for di, dk in enumerate(DAY_KEYS):
            evs = [e for e in wk["days"].get(dk, []) if e.get("class") in (cls, "all")]
            tx = [e["text"] for e in evs]
            if dk == "shabbat" and p:
                tx.append(f"פרשת {p}")
            cell = ws.cell(row=ri, column=di + 2, value="\n".join(tx))
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = b
            if evs:
                pr = ["bagrut", "magen", "trip", "vacation", "holiday"]
                dm = next((x for x in pr if any(e["type"] == x for e in evs)), "general")
                st2 = STYLES[dm]
                cell.fill = PatternFill(
                    start_color=st2["bg"].lstrip("#"),
                    end_color=st2["bg"].lstrip("#"),
                    fill_type="solid",
                )
                cell.font = Font(color=st2["fg"].lstrip("#"), bold=st2["bold"], size=10)
    ws.column_dimensions["A"].width = 14
    for ch in "BCDEFGH":
        ws.column_dimensions[ch].width = 22
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ===================================================================
# EXPORT: PNG / HTML
# ===================================================================

def schedule_to_png(data: dict, cls: str, filtered_weeks: list):
    pm = data.get("parashat_hashavua", {})
    html_parts = [
        '<html><head><meta charset="utf-8"><style>'
        '@import url("https://fonts.googleapis.com/css2?family=Heebo:wght@400;700&display=swap");'
        'body{direction:rtl;font-family:"Heebo",sans-serif;}'
        'table{border-collapse:collapse;width:100%;direction:rtl;}'
        'th{background:#1A237E;color:#fff;font-weight:700;padding:8px 6px;font-size:12px;border:1px solid #B0BEC5;}'
        'td{padding:4px 4px;font-size:11px;border:1px solid #DEE2E6;text-align:center;vertical-align:top;min-width:100px;}'
        '</style></head><body>'
        f'<h3 style="text-align:center;color:#1A237E;">לוח שנה {data.get("year","")} - {cls}</h3>'
        '<table><thead><tr>'
    ]
    for dn in DAY_NAMES:
        html_parts.append(f'<th>{dn}</th>')
    html_parts.append('</tr></thead><tbody>')

    for wi, wk in filtered_weeks:
        parasha = pm.get(wk["start_date"], "")
        html_parts.append('<tr>')
        for di, dk in enumerate(DAY_KEYS):
            day_date = get_day_date(wk.get("start_date", ""), di)
            evs = [e for e in wk["days"].get(dk, []) if e.get("class") in (cls, "all")]
            bg_color = "#FFFFFF" if wi % 2 else "#F8F9FA"
            if evs:
                pr = ["bagrut", "magen", "trip", "vacation", "holiday"]
                dm = next((x for x in pr if any(e["type"] == x for e in evs)), "general")
                bg_color = STYLES[dm]["bg"]
            cell_texts = [f'<small style="color:#90A4AE;">{day_date}</small>']
            for ev in evs:
                s = STYLES.get(ev["type"], STYLES["general"])
                cell_texts.append(
                    f'<span style="color:{s["fg"]};font-weight:{"700" if s["bold"] else "400"};">'
                    f'{ev["text"]}</span>'
                )
            if dk == "shabbat" and parasha:
                cell_texts.append(f'<span style="color:#F57F17;font-weight:700;">{parasha}</span>')
            html_parts.append(f'<td style="background:{bg_color};">{"<br>".join(cell_texts)}</td>')
        html_parts.append('</tr>')

    html_parts.append('</tbody></table></body></html>')
    full_html = "".join(html_parts)

    try:
        import imgkit
        png_bytes = imgkit.from_string(full_html, False, options={"encoding": "UTF-8", "width": 1200})
        return png_bytes
    except Exception:
        return full_html.encode("utf-8")


# ===================================================================
# WHATSAPP SHARE
# ===================================================================

def build_whatsapp_text(data: dict, cls: str, filtered_weeks: list) -> str:
    pm = data.get("parashat_hashavua", {})
    lines = [f"*לוח שנה {data.get('year', '')} - {cls}*\n"]
    for wi, wk in filtered_weeks:
        parasha = pm.get(wk["start_date"], "")
        week_has_events = False
        week_lines = [f"\n*שבוע {wk['date_range']}*"]
        if parasha:
            week_lines.append(f"  פרשת {parasha}")
        for di, dk in enumerate(DAY_KEYS):
            day_date = get_day_date(wk.get("start_date", ""), di)
            evs = [e for e in wk["days"].get(dk, []) if e.get("class") in (cls, "all")]
            if evs:
                week_has_events = True
                day_label = DAY_NAMES[di]
                for ev in evs:
                    week_lines.append(f"  {day_label} {day_date}: {ev['text']}")
        if week_has_events:
            lines.extend(week_lines)
    return "\n".join(lines)


# ===================================================================
# CSS
# ===================================================================

APP_CSS = """<style>
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
    font-size: 0.75em !important; padding: 0 4px !important;
    min-height: 0 !important; height: 20px !important;
    line-height: 20px !important; border-radius: 4px !important;
    background: #E8EAF6 !important; border: 1px solid #C5CAE9 !important;
    color: #3949AB !important; cursor: pointer !important;
    width: 100% !important;
}
div[data-testid="stPopover"] button:hover { background: #C5CAE9 !important; }
.ministry-card {
    background: #E8F5E9; border: 1px solid #A5D6A7; border-radius: 8px;
    padding: 10px 14px; margin: 6px 0;
}
.payment-card {
    background: #FFF3E0; border: 1px solid #FFE0B2; border-radius: 8px;
    padding: 10px 14px; margin: 6px 0;
}
</style>"""


# ===================================================================
# PAGES
# ===================================================================

def page_create_school(auth_info: dict):
    """Page shown when a director has no school yet - create one."""
    st.markdown(
        '<h2 style="text-align:center;color:#1A237E;">יצירת מוסד חדש</h2>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="text-align:center;color:#5C6BC0;">צור את מוסד הלימודים שלך כדי להתחיל</p>',
        unsafe_allow_html=True,
    )
    with st.form("create_school_form"):
        school_name = st.text_input("שם המוסד", placeholder="בית ספר תיכון...")
        school_id = st.text_input(
            "מזהה מוסד (אנגלית, ללא רווחים)",
            placeholder="my-school-2026",
        )
        classes_input = st.text_input(
            "כיתות (מופרדות בפסיק)",
            value="יא 1, יא 2, יא 3",
        )
        submitted = st.form_submit_button("צור מוסד", type="primary", use_container_width=True)
        if submitted and school_name.strip() and school_id.strip():
            classes = [c.strip() for c in classes_input.split(",") if c.strip()]
            if not classes:
                classes = ["יא 1", "יא 2", "יא 3"]
            try:
                create_school(school_id.strip(), auth_info["email"], school_name.strip(), classes)
                # Generate initial schedule
                current_year = datetime.now().year
                month_now = datetime.now().month
                start_year = current_year if month_now >= 8 else current_year - 1
                new_schedule = generate_new_year(start_year)
                new_schedule["classes"] = classes
                save_schedule(school_id.strip(), new_schedule)
                st.toast("המוסד נוצר בהצלחה!", icon="✅")
                st.rerun()
            except Exception as ex:
                st.error(f"שגיאה: {ex}")


def page_manage_staff(auth_info: dict):
    """Director page: manage teachers and their class permissions."""
    school_id = auth_info["school_id"]
    st.markdown("### ניהול צוות")

    # Current permissions
    perms = get_permissions(school_id)
    if perms:
        st.markdown("**צוות קיים:**")
        for email, perm in perms.items():
            if email == auth_info["email"]:
                continue  # Don't show self
            role = perm.get("role", "teacher")
            classes = ", ".join(perm.get("allowed_classes", []))
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{email}** ({role}) - כיתות: {classes}")
            with col2:
                if st.button("הסר", key=f"remove_{email}"):
                    remove_teacher_permission(school_id, email)
                    st.toast(f"{email} הוסר", icon="✅")
                    st.rerun()

    st.markdown("---")
    st.markdown("**הוספת מורה חדש:**")
    with st.form("add_teacher_form"):
        teacher_email = st.text_input("אימייל המורה", placeholder="teacher@school.co.il")
        available_classes = auth_info["allowed_classes"]
        selected_classes = st.multiselect("כיתות מורשות", available_classes)
        if st.form_submit_button("הוסף מורה", type="primary"):
            if teacher_email.strip() and selected_classes:
                set_teacher_permission(school_id, teacher_email.strip(), selected_classes)
                st.toast(f"{teacher_email} נוסף בהצלחה!", icon="✅")
                st.rerun()
            else:
                st.warning("יש למלא אימייל ולבחור כיתות")


def sidebar_ministry_tools(data: dict, cls: str, school_id: str):
    """Sidebar section: Ministry of Education import + sync tools."""
    st.markdown("---")
    st.markdown("### ייבוא ממאגר משרד החינוך")
    meta = get_ministry_meta()
    moed_info = meta.get("moed", "")
    exam_count = meta.get("count", 0)
    st.caption(f"{moed_info} | {exam_count} בחינות")

    if st.button("רענן ממשרד החינוך", key="refresh_ministry"):
        try:
            with st.spinner("מוריד נתונים ממשרד החינוך..."):
                count = refresh_ministry_db_from_web()
            st.toast(f"עודכן! {count} בחינות יובאו", icon="✅")
            st.rerun()
        except Exception as ex:
            st.error(f"שגיאה: {ex}")

    # Search
    search_query = st.text_input(
        "חיפוש לפי מקצוע או סמל",
        key="ministry_text_search",
        placeholder="למשל: מתמטיקה, אנגלית, 899271...",
    )
    if search_query.strip():
        results = search_ministry_exams(search_query)
        if results:
            st.caption(f"נמצאו {len(results)} תוצאות")
            for exam in results:
                st.markdown(exam_card_html(exam), unsafe_allow_html=True)
                if st.button(f"ייבא {exam['name'][:30]}", key=f"import_search_{exam['code']}"):
                    success, msg = import_exam_to_schedule(data, exam, cls)
                    if success:
                        save_schedule(school_id, data)
                        st.toast(msg if msg else f"יובא בהצלחה: {exam['name']}", icon="✅" if not msg else "⚠️")
                        st.rerun()
                    else:
                        st.info(msg)
        else:
            st.caption("לא נמצאו תוצאות")

    # Dropdown list
    all_exams = get_ministry_exams()
    all_exams = [e for e in all_exams if e.get("code") != "_metadata"]
    if all_exams:
        st.markdown("**או בחר מהרשימה:**")
        exam_options = ["בחר מקצוע..."] + [
            f"{ex['code']} - {ex['name']}" for ex in all_exams
        ]
        selected_option = st.selectbox("שם מקצוע", exam_options, key="ministry_select", label_visibility="collapsed")
        if selected_option != "בחר מקצוע...":
            sel_code = selected_option.split(" - ")[0].strip()
            exam = get_ministry_exam(sel_code)
            if exam:
                st.markdown(exam_card_html(exam), unsafe_allow_html=True)
                if st.button("ייבא ללוח שלי", key=f"import_{exam['code']}"):
                    success, msg = import_exam_to_schedule(data, exam, cls)
                    if success:
                        save_schedule(school_id, data)
                        st.toast(msg if msg else f"יובא בהצלחה: {exam['name']}", icon="✅" if not msg else "⚠️")
                        st.rerun()
                    else:
                        st.info(msg)

    # Resync
    st.markdown("---")
    st.markdown("### סנכרון תאריכי בגרות")
    st.caption("בדוק עדכוני תאריכים מול מאגר משרד החינוך")
    if st.button("סנכרן תאריכי בגרות", type="primary", use_container_width=True):
        changes = resync_dates_with_ministry(data, cls)
        if not changes:
            st.success("כל התאריכים מעודכנים!")
        else:
            save_schedule(school_id, data)
            st.markdown("**שינויים שבוצעו:**")
            for ch in changes:
                st.markdown(
                    f"- **{ch['name']}** ({ch['code']}): {ch['old_date']} → {ch['new_date']}"
                )
                if ch["conflict"]:
                    st.error(f"התנגשות: {ch['conflict']}")
            st.rerun()


def sidebar_holidays_import(data: dict, school_id: str):
    """Sidebar section: import holidays and vacations."""
    st.markdown("---")
    st.markdown("### ייבוא חופשות וחגים")
    st.caption("ייבא חגים וחופשות ללוח ממאגר החגים")
    if st.button("ייבא חופשות וחגים", key="import_holidays_btn", use_container_width=True):
        added_count = 0
        year_keys = set()
        if data["weeks"]:
            try:
                sy = datetime.strptime(data["weeks"][0]["start_date"], "%Y-%m-%d").year
                year_keys.add(str(sy))
                year_keys.add(str(sy - 1))
            except Exception:
                pass
            try:
                ey = datetime.strptime(data["weeks"][-1]["start_date"], "%Y-%m-%d").year
                year_keys.add(str(ey))
            except Exception:
                pass
        for yk in year_keys:
            holidays_data = get_holidays(yk)
            if not holidays_data:
                continue
            for h in holidays_data.get("holidays", []):
                try:
                    hdate = datetime.strptime(h["date"], "%Y-%m-%d")
                except Exception:
                    continue
                loc = date_to_week_day(data["weeks"], hdate)
                if loc is None:
                    continue
                wi, dk = loc
                cell = data["weeks"][wi]["days"].get(dk, [])
                if any(e["text"] == h["text"] for e in cell):
                    continue
                cell.append({"text": h["text"], "type": h.get("type", "holiday"), "class": "all"})
                data["weeks"][wi]["days"][dk] = cell
                added_count += 1
            for v in holidays_data.get("school_vacations", []):
                try:
                    vs = datetime.strptime(v["start"], "%Y-%m-%d")
                    ve = datetime.strptime(v["end"], "%Y-%m-%d")
                except Exception:
                    continue
                d = vs
                while d <= ve:
                    loc = date_to_week_day(data["weeks"], d)
                    if loc:
                        wi, dk = loc
                        cell = data["weeks"][wi]["days"].get(dk, [])
                        if not any(e["text"] == v["text"] for e in cell):
                            cell.append({"text": v["text"], "type": "vacation", "class": "all"})
                            data["weeks"][wi]["days"][dk] = cell
                            added_count += 1
                    d += timedelta(days=1)
        if added_count > 0:
            save_schedule(school_id, data)
            st.toast(f"יובאו {added_count} אירועים!", icon="✅")
            st.rerun()
        else:
            st.info("כל החגים והחופשות כבר קיימים בלוח")


def sidebar_year_rollover(data: dict, cls: str, school_id: str):
    """Sidebar section: generate a new academic year."""
    st.markdown("---")
    st.markdown("### מעבר לשנה חדשה")
    st.caption("ייצר לוח שנה חדש עם חגים, חופשות ופרשת השבוע")
    current_year = datetime.now().year
    new_year_start = st.number_input(
        "שנת התחלה (לועזי)", min_value=2024, max_value=2040,
        value=current_year, key="new_year_input",
    )
    import_bagrut = st.checkbox("ייבא בגרויות אוטומטית", value=True, key="import_bagrut_check")
    if st.button("צור שנה חדשה", key="gen_new_year"):
        with st.spinner("יוצר לוח שנה ומייבא נתונים..."):
            new_data = generate_new_year(int(new_year_start))
            new_data["classes"] = data["classes"]

            if import_bagrut:
                all_exams = get_ministry_exams()
                all_exams = [e for e in all_exams if e.get("code") != "_metadata"]
                db_base_year = None
                for ex in all_exams:
                    try:
                        db_base_year = datetime.strptime(ex["date"], "%Y-%m-%d").year
                        break
                    except Exception:
                        continue
                if db_base_year:
                    target_exam_year = int(new_year_start) + 1
                    year_offset = target_exam_year - db_base_year
                else:
                    year_offset = 0

                for exam in all_exams:
                    try:
                        orig_date = datetime.strptime(exam["date"], "%Y-%m-%d")
                        shifted_date = orig_date.replace(year=orig_date.year + year_offset) if year_offset else orig_date
                        loc = date_to_week_day(new_data["weeks"], shifted_date)
                        if loc:
                            wi, dk = loc
                            label = f'{exam["name"]} ({exam["code"]})'
                            new_data["weeks"][wi]["days"][dk].append({
                                "text": label, "type": "bagrut",
                                "class": cls, "exam_code": exam["code"],
                            })
                    except Exception:
                        continue

            save_schedule(school_id, new_data)
        st.toast("לוח שנה חדש נוצר!", icon="✅")
        st.rerun()


def sidebar_payments(data: dict, cls: str, school_id: str, auth_info: dict):
    """Sidebar section: payment management for directors.

    Model: Schools pay an annual subscription to use the platform.
    Directors can also create charges visible to parents (e.g. field trips).
    """
    st.markdown("---")
    st.markdown("### ניהול תשלומים")

    # --- School subscription status ---
    from db_manager import get_school
    school = get_school(school_id)
    sub_status = school.get("subscription_status", "trial") if school else "trial"
    sub_expiry = school.get("subscription_expiry", "")
    status_labels = {"trial": "ניסיון", "active": "פעיל", "expired": "פג תוקף"}
    st.markdown(
        f'**מנוי מוסד:** {status_labels.get(sub_status, sub_status)}'
        f'{" | עד " + sub_expiry if sub_expiry else ""}'
    )

    # --- Charges for students (visible to parents via public link) ---
    st.markdown("---")
    st.markdown("**חיובים לתלמידים:**")
    payments = get_payments(school_id)

    with st.expander("יצירת חיוב חדש לכיתה"):
        charge_desc = st.text_input("תיאור החיוב", key="charge_desc", placeholder="למשל: מסע זהות")
        charge_amount = st.number_input("סכום (₪)", min_value=0.0, step=10.0, key="charge_amount")
        charge_class = st.selectbox("כיתה", data["classes"] + ["כולם"], key="charge_class")
        charge_due = st.date_input("תאריך יעד לתשלום", key="charge_due")
        if st.button("צור חיוב", key="create_charge"):
            if charge_desc.strip() and charge_amount > 0:
                add_payment(school_id, {
                    "description": charge_desc.strip(),
                    "amount": charge_amount,
                    "class": charge_class,
                    "due_date": charge_due.strftime("%Y-%m-%d"),
                    "created_by": auth_info.get("email", ""),
                })
                st.toast("חיוב נוצר בהצלחה!", icon="✅")
                st.rerun()

    if payments:
        for ch in payments:
            target = ch.get("class", "כולם")
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(
                    f'<div class="payment-card">'
                    f'<b>{ch["description"]}</b> - ₪{ch["amount"]}<br>'
                    f'כיתה: {target} | יעד: {ch.get("due_date", "")}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with col2:
                if st.button("מחק", key=f"del_pay_{ch['id']}"):
                    delete_payment(school_id, ch["id"])
                    st.rerun()


def _get_base_url() -> str:
    """Auto-detect the app's base URL from Streamlit context."""
    try:
        # Streamlit Cloud / hosted: use the session's browser URL
        ctx = st.context
        if hasattr(ctx, "headers"):
            host = ctx.headers.get("Host", "")
            scheme = ctx.headers.get("X-Forwarded-Proto", "https")
            if host:
                return f"{scheme}://{host}"
    except Exception:
        pass
    return "http://localhost:8501"


def sidebar_public_link(data: dict, school_id: str):
    """Sidebar section: generate public sharing links."""
    st.markdown("---")
    st.markdown("### קישור שיתוף להורים")
    st.caption("צור קישור ציבורי שהורים יכולים לצפות בו ללא סיסמה")
    share_class = st.selectbox("כיתה לשיתוף", data["classes"], key="share_class_select")
    detected_url = _get_base_url()
    base_url = st.text_input("כתובת האפליקציה", value=detected_url, key="base_url_input")
    share_url = f"{base_url}?school_id={urllib.parse.quote(school_id)}&class={urllib.parse.quote(share_class)}&mode=view"
    st.code(share_url, language=None)
    st.caption("שלח קישור זה להורים - הם יוכלו לראות את הלוח ללא התחברות")


# ===================================================================
# MAIN SCHEDULER VIEW
# ===================================================================

def render_scheduler(data: dict, cls: str, auth_info: dict):
    """Render the main visual schedule grid."""
    school_id = auth_info.get("school_id", "")
    is_director = auth_info["role"] == "director"
    is_teacher = auth_info["role"] == "teacher"
    can_edit = is_director or is_teacher

    school_name = auth_info.get("school_name", "")
    st.markdown(
        f'<h2 style="text-align:center;margin:0 0 2px;color:#1A237E;font-weight:900;">'
        f'לוח מבחנים {data.get("year", "")} - {school_name}</h2>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<p style="text-align:center;margin:0 0 4px;color:#5C6BC0;font-size:0.9em;">{cls}</p>',
        unsafe_allow_html=True,
    )

    # Legend
    lg = "".join(
        f'<span class="legend-chip" style="background:{s["bg"]};color:{s["fg"]};'
        f'font-weight:{"700" if s["bold"] else "400"};">{s["label"]}</span>'
        for s in STYLES.values()
    )
    lg += '<span class="legend-chip cal-parasha">פרשת השבוע</span>'
    st.markdown(f'<div class="legend-row">{lg}</div>', unsafe_allow_html=True)

    pm = data.get("parashat_hashavua", {})

    # Month filter
    available_months = []
    month_set = set()
    for wk in data["weeks"]:
        try:
            sd = datetime.strptime(wk["start_date"], "%Y-%m-%d")
            key = (sd.year, sd.month)
            if key not in month_set:
                month_set.add(key)
                available_months.append(key)
            ed = sd + timedelta(days=6)
            key2 = (ed.year, ed.month)
            if key2 not in month_set:
                month_set.add(key2)
                available_months.append(key2)
        except Exception:
            pass
    available_months.sort()

    month_options = ["כל השנה"] + [
        f"{MONTH_NAMES_HEB[m]} {y}" for y, m in available_months
    ]

    fc1, fc2, fc3 = st.columns([1, 3, 1])
    with fc1:
        selected_month = st.selectbox("סינון לפי חודש", month_options, key="month_filter")
    with fc3:
        show_past_weeks = st.checkbox("הצג שבועות קודמים", value=False, key="show_past")

    today = datetime.now().date()

    if selected_month == "כל השנה":
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

    # Header row
    hcols = st.columns(7)
    for i, dn in enumerate(DAY_NAMES):
        with hcols[i]:
            st.markdown(f'<div class="cal-hdr">{dn}</div>', unsafe_allow_html=True)

    # Week rows
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

                if can_edit:
                    all_cell = wk["days"].get(dk, [])
                    vis = [e for e in all_cell if e.get("class") in (cls, "all")]

                    with st.popover("+", use_container_width=True):
                        st.markdown(f"**{DAY_NAMES[di]} {day_date}**")

                        for idx_ev, ev in enumerate(vis):
                            if st.button(
                                f"✕  {ev['text']}", key=f"del_{wi}_{di}_{idx_ev}",
                                use_container_width=True,
                            ):
                                all_cell.remove(ev)
                                save_schedule(school_id, data)
                                st.rerun()

                        nt = st.text_input("שם", key=f"t_{wi}_{di}", placeholder="שם אירוע")
                        tp = st.selectbox(
                            "סוג", list(STYLES.keys()),
                            format_func=lambda x: STYLES[x]["label"],
                            key=f"tp_{wi}_{di}",
                        )
                        ecls = st.selectbox(
                            "כיתה", auth_info["allowed_classes"] + ["all"],
                            key=f"c_{wi}_{di}",
                        )
                        if st.button("הוסף", key=f"a_{wi}_{di}", type="primary", use_container_width=True):
                            if nt.strip():
                                all_cell.append({"text": nt.strip(), "type": tp, "class": ecls})
                                save_schedule(school_id, data)
                                st.rerun()

    # ==================================================================
    # EXPORT SECTION
    # ==================================================================
    st.markdown("---")
    st.markdown("### שיתוף וייצוא")
    
    exp_col1, exp_col2 = st.columns(2)

    with exp_col1:
        st.download_button(
            "📥 הורד אקסל",
            data=to_excel(data, cls),
            file_name=f"לוח_{cls}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.document",
            use_container_width=True,
        )

    with exp_col2:
        if st.button("📄 הורד HTML (לצילום מסך)", key="export_html_btn", use_container_width=True):
            # Generate HTML for screenshot
            png_data = schedule_to_png(data, cls, filtered_weeks)
            st.download_button(
                "⬇️ לחץ כאן להוריד", 
                data=png_data, 
                file_name=f"לוח_{cls}.html",
                mime="text/html", 
                key="download_html",
                use_container_width=True,
            )
            st.info("💡 פתח את הקובץ בדפדפן, צלם מסך (Win+Shift+S), ושלח בווצאפ!")

    # WhatsApp sharing section
    st.markdown("---")
    st.markdown("### 📱 שיתוף בווצאפ")
    
    wa_col1, wa_col2 = st.columns(2)
    
    with wa_col1:
        # Text version
        wa_text = build_whatsapp_text(data, cls, filtered_weeks)
        wa_url = f"https://wa.me/?text={urllib.parse.quote(wa_text[:4000])}"
        st.markdown(
            f'<a href="{wa_url}" target="_blank" style="'
            f'display:inline-block;width:100%;text-align:center;'
            f'background:#25D366;color:white;padding:12px;border-radius:8px;'
            f'text-decoration:none;font-weight:700;font-size:0.9em;">'
            f'📝 שלח טקסט בווצאפ</a>',
            unsafe_allow_html=True,
        )
        st.caption("שולח את האירועים כטקסט")
    
    with wa_col2:
        # Public link for parents
        if not auth_info.get("is_public") and school_id:
            base = st.session_state.get("base_url_input", _get_base_url())
            link = f"{base}?school_id={urllib.parse.quote(school_id)}&class={urllib.parse.quote(cls)}&mode=view"
            
            # Copy link button
            st.markdown(
                f'<div style="background:#F0F4FF;border:2px solid #1A237E;border-radius:8px;padding:8px;margin-bottom:4px;">'
                f'<div style="font-size:0.75em;color:#666;margin-bottom:4px;">📎 קישור ישיר להורים:</div>'
                f'<input type="text" value="{link}" readonly '
                f'style="width:100%;padding:6px;border:1px solid #ddd;border-radius:4px;font-size:0.8em;direction:ltr;text-align:left;" '
                f'onclick="this.select();document.execCommand(\'copy\');alert(\'הקישור הועתק!\');">'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.caption("לחץ על הקישור להעתקה ושלח בווצאפ")


    # ==================================================================
    # PAYMENTS VIEW (visible on public link - no login needed)
    # ==================================================================
    if school_id:
        relevant = get_payments_for_class(school_id, cls)
        if relevant:
            st.markdown("---")
            st.markdown("### תשלומים נדרשים")
            for ch in relevant:
                st.markdown(
                    f'<div class="payment-card">'
                    f'<b>{ch["description"]}</b> - ₪{ch["amount"]}<br>'
                    f'יעד תשלום: {ch.get("due_date", "")}</div>',
                    unsafe_allow_html=True,
                )


# ===================================================================
# MAIN
# ===================================================================

def main():
    st.set_page_config(page_title="לוח מבחנים", layout="wide")
    st.markdown(APP_CSS, unsafe_allow_html=True)

    # ---- Authenticate ----
    auth_info = authenticate()

    if not auth_info["authenticated"]:
        return

    # ---- Public mode: skip sidebar, render read-only ----
    if auth_info["is_public"]:
        school_id = auth_info["school_id"]
        if not school_id:
            st.error("קישור לא תקין - חסר מזהה מוסד")
            return
        data = get_schedule(school_id)
        if not data["weeks"]:
            st.error("לא נמצאו נתונים למוסד זה")
            return
        allowed = auth_info["allowed_classes"]
        cls = allowed[0] if allowed else (data["classes"][0] if data["classes"] else "יא 1")
        render_scheduler(data, cls, auth_info)
        return

    # ---- No school yet -> create school flow ----
    if not auth_info["school_id"] and not auth_info["schools"]:
        page_create_school(auth_info)
        return

    if not auth_info["school_id"]:
        st.info("בחר מוסד מהתפריט בצד")
        return

    # ---- Load schedule data ----
    school_id = auth_info["school_id"]
    data = get_schedule(school_id)

    # ---- Sidebar ----
    is_director = auth_info["role"] == "director"
    allowed_classes = auth_info["allowed_classes"]

    with st.sidebar:
        st.markdown("### הגדרות")
        if allowed_classes:
            cls = st.selectbox("כיתה", allowed_classes)
        else:
            cls = st.selectbox("כיתה", data.get("classes", ["יא 1"]))

        if is_director:
            # Add class
            nc = st.text_input("הוספת כיתה", key="nc")
            if st.button("הוסף כיתה") and nc.strip() and nc.strip() not in data.get("classes", []):
                add_class_to_school(school_id, nc.strip())
                data["classes"].append(nc.strip())
                save_schedule(school_id, data)
                st.rerun()

            # Manage Staff page (in expander)
            with st.expander("ניהול צוות"):
                page_manage_staff(auth_info)

            # Ministry tools
            sidebar_ministry_tools(data, cls, school_id)

            # Holidays import
            sidebar_holidays_import(data, school_id)

            # Year rollover
            sidebar_year_rollover(data, cls, school_id)

            # Public share link
            sidebar_public_link(data, school_id)

            # Payments
            sidebar_payments(data, cls, school_id, auth_info)
        else:
            st.markdown("---")
            st.caption(f"תפקיד: {'מורה' if auth_info['role'] == 'teacher' else 'צופה'}")

    # ---- Render the scheduler ----
    render_scheduler(data, cls, auth_info)


if __name__ == "__main__":
    main()
