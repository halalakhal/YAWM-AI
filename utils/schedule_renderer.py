"""
utils/schedule_renderer.py
───────────────────────────
Renders the final daily schedule as a beautiful dark-theme PNG card.

Color key:
  🟢 prayer    → #34D399   🔵 deep_work → #60A5FA
  🔴 rest      → #F87171   💜 sleep     → #A78BFA
  🟠 meal      → #FB923C   🟡 meeting   → #FBBF24
  🩵 dhikr     → #6EE7B7   🩷 quran     → #F9A8D4
  ⚪ flexible  → #94A3B8
"""
from __future__ import annotations
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from config.settings import SCHEDULE_CARD_PATH

# ─── Design tokens ────────────────────────────────────────────────────────────
BLOCK_COLORS = {
    "prayer":    "#34D399",
    "deep_work": "#60A5FA",
    "rest":      "#F87171",
    "sleep":     "#A78BFA",
    "meal":      "#FB923C",
    "meeting":   "#FBBF24",
    "dhikr":     "#6EE7B7",
    "quran":     "#F9A8D4",
    "flexible":  "#94A3B8",
}

W, H           = 960, 1280
BG             = (5, 11, 24)
TEXT_LIGHT     = (226, 232, 240)
TEXT_DIM       = (100, 116, 139)
ACCENT         = (232, 121, 249)
GRID_LINE      = (30, 41, 59)
LEFT           = 88
TOP            = 230
BOTTOM_PAD     = 60
TL_START_H     = 4
TL_END_H       = 24
TL_MINUTES     = (TL_END_H - TL_START_H) * 60
TL_HEIGHT      = H - TOP - BOTTOM_PAD


def _hex(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _t2y(t: str) -> int:
    """HH:MM → Y pixel."""
    hh, mm = map(int, t.split(":"))
    mins = hh * 60 + mm - TL_START_H * 60
    mins = max(0, min(mins, TL_MINUTES))
    return int(TOP + (mins / TL_MINUTES) * TL_HEIGHT)


def _font(size: int, bold=False):
    candidates = [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'Bold' if bold else ''}.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationSans-{'Bold' if bold else 'Regular'}.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for p in candidates:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def render_card(
    schedule: list[dict],
    date_str: str,
    ramadan_day: int,
    mood: str,
    prayer_streak: int = 0,
    quran_progress: str = "On track",
    output_path: str = SCHEDULE_CARD_PATH,
) -> str:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # subtle gradient background
    for y in range(H):
        r = int(BG[0] + (y / H) * 8)
        g = int(BG[1] + (y / H) * 12)
        b = int(BG[2] + (y / H) * 20)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # ── Header ───────────────────────────────────────────────────────────────
    f_title = _font(40, bold=True)
    f_sub   = _font(17)
    f_sm    = _font(13)
    f_blk   = _font(11, bold=True)
    f_time  = _font(10)

    draw.text((LEFT, 28), "◈ YAWM AI", font=f_title, fill=_hex(ACCENT))

    dt_obj = datetime.strptime(date_str, "%Y-%m-%d")
    draw.text((LEFT, 82),  dt_obj.strftime("%A, %B %-d %Y"), font=f_sub, fill=TEXT_LIGHT)
    draw.text((LEFT, 110), f"Ramadan Day {ramadan_day}  ·  Mood: {mood}", font=f_sm, fill=TEXT_DIM)

    stats = [f"🔥 {prayer_streak}d streak", f"📖 {quran_progress}", f"⏰ {len(schedule)} blocks"]
    for i, s in enumerate(stats):
        draw.text((LEFT + i * 250, 144), s, font=f_sm, fill=TEXT_LIGHT)

    draw.line([(LEFT, 178), (W - 40, 178)], fill=GRID_LINE, width=1)

    # ── Hour grid ────────────────────────────────────────────────────────────
    for h in range(TL_START_H, TL_END_H + 1, 2):
        y = _t2y(f"{h:02d}:00")
        draw.line([(LEFT - 16, y), (W - 40, y)], fill=GRID_LINE, width=1)
        draw.text((8, y - 8), f"{h:02d}:00", font=f_time, fill=TEXT_DIM)

    # ── Schedule blocks ───────────────────────────────────────────────────────
    for blk in schedule:
        try:
            y1 = _t2y(blk["start"])
            y2 = _t2y(blk["end"])
            if y2 <= y1:
                y2 = y1 + 18
            color_hex = BLOCK_COLORS.get(blk.get("block_type", "flexible"), "#94A3B8")
            c = _hex(color_hex)
            c_dark = tuple(max(0, v - 60) for v in c)

            # filled rect
            draw.rectangle([LEFT, y1, W - 40, y2], fill=(*c_dark, 180))
            # left accent bar
            draw.rectangle([LEFT, y1, LEFT + 4, y2], fill=c)
            # title
            title = blk.get("title", "")
            draw.text((LEFT + 10, y1 + 3), title, font=f_blk, fill=TEXT_LIGHT)
            # time label
            time_label = f"{blk['start']} – {blk['end']}"
            draw.text((LEFT + 10, y1 + 16), time_label, font=f_time, fill=TEXT_DIM)
        except Exception:
            pass

    # ── Legend ────────────────────────────────────────────────────────────────
    lx, ly = LEFT, H - 48
    for btype, color in list(BLOCK_COLORS.items())[:5]:
        draw.rectangle([lx, ly + 4, lx + 10, ly + 14], fill=_hex(color))
        draw.text((lx + 14, ly + 2), btype.replace("_", " "), font=f_time, fill=TEXT_DIM)
        lx += 120

    img.save(output_path)
    return output_path
