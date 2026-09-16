/**
 * Draw the schedule to a PNG in the browser.
 *
 * The old app rendered this server-side with Pillow, which needed a bundled
 * Hebrew font and a bidi library. On a canvas the browser shapes and orders
 * Hebrew itself, so the text is simply correct — and rendering at 2× keeps it
 * legible after WhatsApp re-compresses the image.
 */

import { DAY_KEYS, DAY_NAMES, styleFor } from './constants.js';
import { addDays, fmtDate } from './vacationRules.js';

const SCALE = 2;              // draw at 2×, so it survives messaging-app resizing
const PAD = 18;
const COL_W = 210;
const HEADER_H = 46;
const TITLE_H = 72;
const ROW_MIN_H = 118;
const CHIP_H = 26;
const CHIP_GAP = 4;
const FONT = "'Heebo', 'Arial Hebrew', system-ui, sans-serif";

const hebrewDayFmt = new Intl.DateTimeFormat('he-u-ca-hebrew', { day: 'numeric', month: 'long' });
const hebrewDate = (d) => { try { return hebrewDayFmt.format(d); } catch { return ''; } };
const civil = (d) => `${String(d.getUTCDate()).padStart(2, '0')}/${String(d.getUTCMonth() + 1).padStart(2, '0')}`;

/** Shorten text with an ellipsis until it fits `maxWidth`. */
function fit(ctx, text, maxWidth) {
  let s = String(text ?? '');
  if (ctx.measureText(s).width <= maxWidth) return s;
  while (s.length > 1 && ctx.measureText(`${s}…`).width > maxWidth) s = s.slice(0, -1);
  return `${s}…`;
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
}

/**
 * @param {{ weeks: Array<{wk:object, wi:number}>, parashot: object, cls: string,
 *           schoolName: string, yearLabel: string }} opts
 * @returns {Promise<HTMLCanvasElement>}
 */
export async function renderScheduleCanvas({ weeks, parashot, cls, schoolName, yearLabel }) {
  if (document.fonts?.ready) await document.fonts.ready;  // Heebo must be loaded before measuring

  const rows = weeks ?? [];
  const probe = document.createElement('canvas').getContext('2d');
  probe.font = `400 15px ${FONT}`;

  // Row heights vary with how many events a week holds.
  const rowHeights = rows.map(({ wk }) => {
    const most = DAY_KEYS.reduce((max, dk) => {
      const n = (wk.days?.[dk] ?? []).filter((e) => !cls || e.class === cls || e.class === 'all').length;
      return Math.max(max, dk === 'shabbat' && parashot?.[wk.start_date] ? n + 1 : n);
    }, 0);
    return Math.max(ROW_MIN_H, 34 + most * (CHIP_H + CHIP_GAP) + 8);
  });

  const width = PAD * 2 + COL_W * 7;
  const height = PAD * 2 + TITLE_H + HEADER_H + rowHeights.reduce((a, b) => a + b, 0);

  const canvas = document.createElement('canvas');
  canvas.width = width * SCALE;
  canvas.height = height * SCALE;
  const ctx = canvas.getContext('2d');
  ctx.scale(SCALE, SCALE);
  ctx.textBaseline = 'middle';
  ctx.direction = 'rtl';

  ctx.fillStyle = '#FFFFFF';
  ctx.fillRect(0, 0, width, height);

  // Title
  ctx.fillStyle = '#1A237E';
  ctx.textAlign = 'center';
  ctx.font = `800 30px ${FONT}`;
  ctx.fillText(`לוח מבחנים ${yearLabel}`, width / 2, PAD + 22);
  ctx.font = `500 17px ${FONT}`;
  ctx.fillStyle = '#475569';
  ctx.fillText([schoolName, cls].filter(Boolean).join('  |  '), width / 2, PAD + 50);

  // Columns run right-to-left: Sunday is the rightmost.
  const colX = (i) => width - PAD - (i + 1) * COL_W;

  // Day header
  const headerY = PAD + TITLE_H;
  DAY_NAMES.forEach((name, i) => {
    ctx.fillStyle = '#1A237E';
    ctx.fillRect(colX(i), headerY, COL_W - 1, HEADER_H - 1);
    ctx.fillStyle = '#FFFFFF';
    ctx.font = `700 19px ${FONT}`;
    ctx.textAlign = 'center';
    ctx.fillText(name, colX(i) + COL_W / 2, headerY + HEADER_H / 2);
  });

  // Week rows
  let y = headerY + HEADER_H;
  rows.forEach(({ wk }, ri) => {
    const rowH = rowHeights[ri];
    const start = new Date(`${wk.start_date}T00:00:00Z`);
    const parasha = parashot?.[wk.start_date] ?? '';

    DAY_KEYS.forEach((dk, i) => {
      const x = colX(i);
      const date = addDays(start, i);

      ctx.fillStyle = dk === 'shabbat' ? '#F1F5F9' : (ri % 2 ? '#FAFAFA' : '#FFFFFF');
      ctx.fillRect(x, y, COL_W - 1, rowH - 1);
      ctx.strokeStyle = '#E2E8F0';
      ctx.lineWidth = 1;
      ctx.strokeRect(x + 0.5, y + 0.5, COL_W - 1, rowH - 1);

      // Civil date (right) and Hebrew date (left)
      ctx.font = `700 15px ${FONT}`;
      ctx.fillStyle = '#334155';
      ctx.textAlign = 'right';
      ctx.fillText(civil(date), x + COL_W - 8, y + 16);
      ctx.font = `400 12px ${FONT}`;
      ctx.fillStyle = '#94A3B8';
      ctx.textAlign = 'left';
      ctx.fillText(fit(ctx, hebrewDate(date), COL_W - 62), x + 8, y + 16);

      // Event chips
      let chipY = y + 32;
      const events = (wk.days?.[dk] ?? []).filter((e) => !cls || e.class === cls || e.class === 'all');
      for (const ev of events) {
        if (chipY + CHIP_H > y + rowH - 4) break;
        const s = styleFor(ev.type);
        ctx.fillStyle = s.bg;
        ctx.strokeStyle = s.border;
        roundRect(ctx, x + 6, chipY, COL_W - 13, CHIP_H, 7);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = s.fg;
        ctx.font = `${s.bold ? 700 : 400} 14px ${FONT}`;
        ctx.textAlign = 'right';
        ctx.fillText(fit(ctx, `${s.icon} ${ev.text}`, COL_W - 25), x + COL_W - 14, chipY + CHIP_H / 2);
        chipY += CHIP_H + CHIP_GAP;
      }

      if (dk === 'shabbat' && parasha && chipY + CHIP_H <= y + rowH - 4) {
        ctx.fillStyle = '#FEF3C7';
        ctx.strokeStyle = '#FDE68A';
        roundRect(ctx, x + 6, chipY, COL_W - 13, CHIP_H, 7);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = '#92400E';
        ctx.font = `700 14px ${FONT}`;
        ctx.textAlign = 'right';
        ctx.fillText(fit(ctx, `📖 ${parasha}`, COL_W - 25), x + COL_W - 14, chipY + CHIP_H / 2);
      }
    });

    y += rowH;
  });

  return canvas;
}

/** Render and hand the PNG to the browser as a download. */
export async function downloadScheduleImage(opts, filename = 'luach.png') {
  const canvas = await renderScheduleCanvas(opts);
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
  if (!blob) throw new Error('יצירת התמונה נכשלה');
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
  return blob;
}

/**
 * Share straight to WhatsApp and friends where the browser supports it
 * (Android/iOS), falling back to a download on desktop.
 */
export async function shareScheduleImage(opts, filename = 'luach.png', title = 'לוח מבחנים') {
  const canvas = await renderScheduleCanvas(opts);
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
  if (!blob) throw new Error('יצירת התמונה נכשלה');

  const file = new File([blob], filename, { type: 'image/png' });
  if (navigator.canShare?.({ files: [file] })) {
    await navigator.share({ files: [file], title });
    return 'shared';
  }

  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
  return 'downloaded';
}
