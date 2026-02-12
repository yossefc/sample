"""
generate_image.py - Génère une image PNG du tableau de planning directement.

Usage:
    python generate_image.py
    python generate_image.py "יא 2"

Le fichier PNG sera sauvegardé dans le dossier courant.
"""

import json
import sys
from datetime import datetime, timedelta

# --- Constants from app.py ---
STYLES = {
    "bagrut":   {"bg": "#FFCDD2", "fg": "#B71C1C", "bold": True,  "label": "בגרות"},
    "magen":    {"bg": "#FFE0B2", "fg": "#E65100", "bold": True,  "label": "מגן / מתכונת"},
    "trip":     {"bg": "#C8E6C9", "fg": "#1B5E20", "bold": False, "label": "טיול / מסע"},
    "vacation": {"bg": "#BBDEFB", "fg": "#0D47A1", "bold": False, "label": "חופשה"},
    "holiday":  {"bg": "#E1BEE7", "fg": "#4A148C", "bold": False, "label": "חג / מועד"},
    "general":  {"bg": "#F5F5F5", "fg": "#424242", "bold": False, "label": "כללי"},
}
DAY_NAMES = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"]
DAY_KEYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "shabbat"]


def get_day_date(start_date_str, day_index):
    try:
        sd = datetime.strptime(start_date_str, "%Y-%m-%d")
        d = sd + timedelta(days=day_index)
        return d.strftime("%d/%m")
    except Exception:
        return ""


def build_schedule_html(data, cls, filtered_weeks):
    pm = data.get("parashat_hashavua", {})
    html_parts = [
        '<html><head><meta charset="utf-8"><style>'
        '@import url("https://fonts.googleapis.com/css2?family=Heebo:wght@400;700&display=swap");'
        'body{direction:rtl;font-family:"Heebo",sans-serif;margin:16px;background:#fff;}'
        'h3{text-align:center;color:#1A237E;margin:8px 0 12px;}'
        'table{border-collapse:collapse;width:100%;direction:rtl;}'
        'th{background:#1A237E;color:#fff;font-weight:700;padding:10px 8px;font-size:13px;border:1px solid #B0BEC5;}'
        'td{padding:6px 5px;font-size:12px;border:1px solid #DEE2E6;text-align:center;vertical-align:top;min-width:110px;}'
        '.date-label{color:#90A4AE;font-size:0.8em;}'
        '.parasha{color:#F57F17;font-weight:700;}'
        '</style></head><body>'
        f'<h3>לוח שנה {data.get("year","")} - {cls}</h3>'
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
            cell_texts = [f'<small class="date-label">{day_date}</small>']
            for ev in evs:
                s = STYLES.get(ev["type"], STYLES["general"])
                cell_texts.append(
                    f'<span style="color:{s["fg"]};font-weight:{"700" if s["bold"] else "400"};">'
                    f'{ev["text"]}</span>'
                )
            if dk == "shabbat" and parasha:
                cell_texts.append(f'<span class="parasha">{parasha}</span>')
            html_parts.append(f'<td style="background:{bg_color};">{"<br>".join(cell_texts)}</td>')
        html_parts.append('</tr>')

    html_parts.append('</tbody></table></body></html>')
    return "".join(html_parts)


def main():
    # Load data
    with open("schedule_data.json", encoding="utf-8") as f:
        data = json.load(f)

    # Choose class
    cls = sys.argv[1] if len(sys.argv) > 1 else data["classes"][0]
    print(f"📋 Classe sélectionnée: {cls}")
    print(f"📅 Année: {data.get('year', '')}")

    # Filter weeks: only current and future weeks
    today = datetime.now().date()
    filtered_weeks = []
    for wi, wk in enumerate(data["weeks"]):
        try:
            sd = datetime.strptime(wk["start_date"], "%Y-%m-%d")
            ed = sd + timedelta(days=6)
            if ed.date() >= today:
                filtered_weeks.append((wi, wk))
        except Exception:
            filtered_weeks.append((wi, wk))

    print(f"📊 {len(filtered_weeks)} semaines à afficher")

    # Build HTML
    full_html = build_schedule_html(data, cls, filtered_weeks)

    # Render with Playwright
    print("🎨 Génération de l'image en cours...")
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": 1200, "height": 800},
                device_scale_factor=2,
            )
            page.set_content(full_html, wait_until="networkidle")
            page.wait_for_timeout(2000)  # Wait for fonts
            png_bytes = page.screenshot(full_page=True, type="png")
            browser.close()

        # Save the file
        safe_cls = cls.replace(" ", "_")
        filename = f"לוח_{safe_cls}.png"
        with open(filename, "wb") as f:
            f.write(png_bytes)

        print(f"✅ Image sauvegardée: {filename}")
        print(f"📁 Emplacement: {filename}")
        print(f"📱 Tu peux maintenant l'envoyer sur WhatsApp !")

    except ImportError:
        print("❌ Playwright n'est pas installé. Lance:")
        print("   pip install playwright")
        print("   playwright install chromium")
    except Exception as ex:
        print(f"❌ Erreur: {ex}")


if __name__ == "__main__":
    main()
