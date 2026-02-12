"""Patch 2: Fix cell height and update school holidays with correct dates."""
import pathlib, json

base = pathlib.Path(__file__).parent

# ============================================================
# 1. Fix cell_html: min-height instead of fixed height
# ============================================================
app = base / "app.py"
text = app.read_text(encoding="utf-8")

text = text.replace(
    "height:72px;text-align:center;display:flex;'\n"
    "            f'flex-direction:column;align-items:center;justify-content:flex-start;gap:2px;'\n"
    "            f'overflow:hidden;",
    "min-height:72px;text-align:center;display:flex;'\n"
    "            f'flex-direction:column;align-items:center;justify-content:flex-start;gap:2px;'\n"
    "            f'overflow:visible;"
)

# Also try CRLF version
text = text.replace(
    "height:72px;text-align:center;display:flex;'\r\n"
    "            f'flex-direction:column;align-items:center;justify-content:flex-start;gap:2px;'\r\n"
    "            f'overflow:hidden;",
    "min-height:72px;text-align:center;display:flex;'\r\n"
    "            f'flex-direction:column;align-items:center;justify-content:flex-start;gap:2px;'\r\n"
    "            f'overflow:visible;"
)

app.write_text(text, encoding="utf-8")
print("1. cell_html fixed: min-height + overflow:visible")

# ============================================================
# 2. Update school_holidays.json with correct vacation dates
#    from Ministry of Education for 2025-2026 school year
# ============================================================
holidays = json.loads((base / "school_holidays.json").read_text(encoding="utf-8"))

# Fix 2025 school year (2025-2026 / tashpav) vacation dates
holidays["2025"]["school_vacations"] = [
    {"start": "2025-10-06", "end": "2025-10-14", "text": "\u05d7\u05d5\u05e4\u05e9\u05ea \u05e1\u05d5\u05db\u05d5\u05ea"},
    {"start": "2025-12-14", "end": "2025-12-22", "text": "\u05d7\u05d5\u05e4\u05e9\u05ea \u05d7\u05e0\u05d5\u05db\u05d4"},
    {"start": "2026-02-01", "end": "2026-02-06", "text": "\u05d7\u05d5\u05e4\u05e9\u05ea \u05e1\u05de\u05e1\u05d8\u05e8"},
    {"start": "2026-03-02", "end": "2026-03-04", "text": "\u05d7\u05d5\u05e4\u05e9\u05ea \u05e4\u05d5\u05e8\u05d9\u05dd"},
    {"start": "2026-03-24", "end": "2026-04-08", "text": "\u05d7\u05d5\u05e4\u05e9\u05ea \u05e4\u05e1\u05d7"},
    {"start": "2026-05-21", "end": "2026-05-22", "text": "\u05d7\u05d5\u05e4\u05e9\u05ea \u05e9\u05d1\u05d5\u05e2\u05d5\u05ea"},
    {"start": "2026-06-21", "end": "2026-08-31", "text": "\u05d7\u05d5\u05e4\u05e9\u05ea \u05e7\u05d9\u05e5"},
]

# Fix 2026 school year (2026-2027 / tashpaz) vacation dates
holidays["2026"]["school_vacations"] = [
    {"start": "2026-09-11", "end": "2026-10-04", "text": "\u05d7\u05d5\u05e4\u05e9\u05ea \u05ea\u05e9\u05e8\u05d9"},
    {"start": "2026-12-04", "end": "2026-12-12", "text": "\u05d7\u05d5\u05e4\u05e9\u05ea \u05d7\u05e0\u05d5\u05db\u05d4"},
    {"start": "2027-01-31", "end": "2027-02-05", "text": "\u05d7\u05d5\u05e4\u05e9\u05ea \u05e1\u05de\u05e1\u05d8\u05e8"},
    {"start": "2027-03-22", "end": "2027-03-24", "text": "\u05d7\u05d5\u05e4\u05e9\u05ea \u05e4\u05d5\u05e8\u05d9\u05dd"},
    {"start": "2027-04-12", "end": "2027-04-29", "text": "\u05d7\u05d5\u05e4\u05e9\u05ea \u05e4\u05e1\u05d7"},
    {"start": "2027-06-10", "end": "2027-06-11", "text": "\u05d7\u05d5\u05e4\u05e9\u05ea \u05e9\u05d1\u05d5\u05e2\u05d5\u05ea"},
    {"start": "2027-06-21", "end": "2027-08-31", "text": "\u05d7\u05d5\u05e4\u05e9\u05ea \u05e7\u05d9\u05e5"},
]

(base / "school_holidays.json").write_text(
    json.dumps(holidays, indent=2, ensure_ascii=False), encoding="utf-8"
)
print("2. school_holidays.json updated with correct vacation dates")
print("   - Added חופשת סמסטר (Feb)")
print("   - Fixed חופשת פסח: 24.3.2026-8.4.2026")
print("   - Added חופשת קיץ")

print("\nAll patches applied! Now click 'ייבא חופשות וחגים' in the sidebar.")
