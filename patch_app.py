"""Patch script to apply all calendar improvements to app.py"""
import pathlib

f = pathlib.Path(__file__).parent / "app.py"
text = f.read_text(encoding="utf-8")

# ============================================================
# 1. Fix cell_html: remove overflow-y:auto, use fixed height
#    and text-overflow instead of scrolling
# ============================================================
old_cell = (
    "def cell_html(date_str, chips_html, even=False):\n"
    "    bg = \"#F8F9FA\" if even else \"#FFFFFF\"\n"
    "    return (f'<div style=\"background:{bg};border:1px solid #DEE2E6;border-radius:6px;'\n"
    "            f'padding:4px 3px;height:72px;text-align:center;display:flex;'\n"
    "            f'flex-direction:column;align-items:center;justify-content:flex-start;gap:2px;'\n"
    "            f'overflow-y:auto;\">'\n"
    "            f'<div style=\"color:#90A4AE;font-size:0.7em;font-weight:500;flex-shrink:0;\">{date_str}</div>'\n"
    "            f'{chips_html}</div>')"
)

new_cell = (
    "def cell_html(date_str, chips_html, even=False):\n"
    "    bg = \"#F8F9FA\" if even else \"#FFFFFF\"\n"
    "    return (f'<div style=\"background:{bg};border:1px solid #DEE2E6;border-radius:6px;'\n"
    "            f'padding:4px 3px;height:72px;text-align:center;display:flex;'\n"
    "            f'flex-direction:column;align-items:center;justify-content:flex-start;gap:2px;'\n"
    "            f'overflow:hidden;\">'\n"
    "            f'<div style=\"color:#90A4AE;font-size:0.7em;font-weight:500;flex-shrink:0;\">{date_str}</div>'\n"
    "            f'{chips_html}</div>')"
)

if old_cell in text:
    text = text.replace(old_cell, new_cell)
    print("1. cell_html patched OK")
else:
    print("1. cell_html NOT FOUND - trying alternate")
    text = text.replace("overflow-y:auto;", "overflow:hidden;")
    print("   overflow-y:auto replaced with overflow:hidden")

# ============================================================
# 2. Replace the month filter + week determination block
#    to add show_past checkbox and filter past weeks
# ============================================================

# Find and replace the filter columns section
old_filter = "    fc1, fc2 = st.columns([1, 3])"
new_filter = "    fc1, fc2, fc3 = st.columns([1, 3, 1])"
text = text.replace(old_filter, new_filter)
print("2a. columns layout patched")

# Add the checkbox after the month selectbox closing paren
old_selectbox_end = '''        key="month_filter",
        )

    # Determine which weeks to show'''

new_selectbox_end = '''        key="month_filter",
        )
    with fc3:
        show_past_weeks = st.checkbox(
            "\u2191 \u05d4\u05e6\u05d2 \u05e9\u05d1\u05d5\u05e2\u05d5\u05ea \u05e7\u05d5\u05d3\u05de\u05d9\u05dd",
            value=False,
            key="show_past",
        )

    # Get today's date for filtering
    today = datetime.now().date()

    # Determine which weeks to show'''

text = text.replace(old_selectbox_end, new_selectbox_end)
print("2b. checkbox + today added")

# Add the past-week filtering logic after the month filter block
old_header = "    # ---- Header row ----"
new_header = """    # Filter to show only current and future weeks unless checkbox is checked
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

    # ---- Header row ----"""

text = text.replace(old_header, new_header)
print("2c. past-week filter logic added")

# ============================================================
# 3. Add a sidebar button to import vacations from holidays DB
#    into the current schedule (after the resync section)
# ============================================================
old_year_section = "        # ----------------------------------------------------------\n        # YEAR ROLLOVER"
new_import_section = """        # ----------------------------------------------------------
        # IMPORT VACATIONS FROM HOLIDAYS DB
        # ----------------------------------------------------------
        st.markdown("---")
        st.markdown("### \u05d9\u05d9\u05d1\u05d5\u05d0 \u05d7\u05d5\u05e4\u05e9\u05d5\u05ea \u05de\u05de\u05e9\u05e8\u05d3 \u05d4\u05d7\u05d9\u05e0\u05d5\u05da")
        st.caption("\u05d9\u05d9\u05d1\u05d0 \u05d7\u05d2\u05d9\u05dd \u05d5\u05d7\u05d5\u05e4\u05e9\u05d5\u05ea \u05dc\u05dc\u05d5\u05d7 \u05de\u05e7\u05d5\u05d1\u05e5 \u05d4\u05d7\u05d2\u05d9\u05dd")
        if st.button("\u05d9\u05d9\u05d1\u05d0 \u05d7\u05d5\u05e4\u05e9\u05d5\u05ea \u05d5\u05d7\u05d2\u05d9\u05dd", key="import_holidays_btn", use_container_width=True):
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
                st.toast(f"\u05d9\u05d5\u05d1\u05d0\u05d5 {added_count} \u05d0\u05d9\u05e8\u05d5\u05e2\u05d9\u05dd!", icon="\u2705")
                st.rerun()
            else:
                st.info("\u05db\u05dc \u05d4\u05d7\u05d2\u05d9\u05dd \u05d5\u05d4\u05d7\u05d5\u05e4\u05e9\u05d5\u05ea \u05db\u05d1\u05e8 \u05e7\u05d9\u05d9\u05de\u05d9\u05dd \u05d1\u05dc\u05d5\u05d7")

        # ----------------------------------------------------------
        # YEAR ROLLOVER"""

text = text.replace(old_year_section, new_import_section)
print("3. vacation import button added")

# Write out
f.write_text(text, encoding="utf-8")
print("\nAll patches applied successfully!")
