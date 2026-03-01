"""
agents/canva_agent.py
──────────────────────
Agent 8: CanvaAgent — Built-in schedule card renderer (no external API)
"""
from __future__ import annotations
import json
from collections import Counter
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from graph.state import YawmState
from config.settings import SCHEDULE_CARD_PATH
from config.langfuse_setup import get_langfuse_config

try:
    from langfuse import observe
except ImportError:
    def observe(name=None):
        def decorator(fn): return fn
        return decorator

# ── Colour palette ─────────────────────────────────────────────────────────────
BG_TOP    = (15,  20,  40)
BG_BOT    = (25,  35,  65)
ACCENT    = (130, 80, 220)
GOLD      = (255, 200,  80)
WHITE     = (255, 255, 255)
MUTED     = (160, 170, 200)
CARD_BG   = (30,  40,  70)

BLOCK_COLORS: dict[str, tuple] = {
    "prayer":     (100, 210, 140),
    "dhikr":      (130,  80, 220),
    "quran":      ( 80, 160, 255),
    "deep_work":  (255, 160,  60),
    "meeting":    (255,  90,  90),
    "break":      (160, 200, 220),
    "meal":       (255, 200,  80),
    "sleep":      ( 70,  90, 140),
    "iftar":      (255, 150,  50),
    "suhoor":     (200, 140, 255),
}
DEFAULT_BLOCK_COLOR = (120, 130, 160)

W, H = 1080, 1920


def _gradient_bg(draw: ImageDraw.ImageDraw):
    for y in range(H):
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * y / H)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * y / H)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * y / H)
        draw.line([(0, y), (W, y)], fill=(r, g, b))


def _try_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
        ]
        if bold else
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
        ]
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _rounded_rect(draw: ImageDraw.ImageDraw, xy, radius: int, fill):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill)


def _pill(draw: ImageDraw.ImageDraw, x: int, y: int, color: tuple, label: str, font):
    tw = draw.textlength(label, font=font)
    px, py = 14, 6
    _rounded_rect(draw, [x, y, x + tw + px * 2, y + 28], radius=14, fill=color)
    draw.text((x + px, y + py), label, font=font, fill=WHITE)
    return x + tw + px * 2 + 10


def render_schedule_card(
    full_schedule:  list[dict],
    date_str:       str,
    ramadan_day:    int,
    mood:           str,
    prayer_streak:  int,
    quran_progress: str,
    out_path:       str,
) -> str:
    img  = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    _gradient_bg(draw)

    f_title  = _try_font(64, bold=True)
    f_sub    = _try_font(34)
    f_med    = _try_font(28)
    f_sm     = _try_font(22)
    f_xs     = _try_font(18)

    draw.rectangle([0, 0, 8, 260], fill=ACCENT)
    draw.text((40, 40),  "◈ YAWM AI",        font=f_title, fill=ACCENT)
    draw.text((40, 115), "Daily Schedule",    font=f_sub,   fill=WHITE)
    draw.text((40, 158), date_str,            font=f_med,   fill=MUTED)

    _rounded_rect(draw, [40, 200, 320, 248], radius=12, fill=ACCENT)
    draw.text((56, 210), f"🌙  Ramadan Day {ramadan_day}", font=f_sm, fill=WHITE)

    mood_colors = {
        "focused":   (80, 160, 255),
        "energized": (100, 210, 140),
        "tired":     (120, 130, 160),
        "anxious":   (255, 160, 60),
    }
    mc = mood_colors.get(mood, DEFAULT_BLOCK_COLOR)
    _rounded_rect(draw, [330, 200, 530, 248], radius=12, fill=mc)
    draw.text((346, 210), f"Mood: {mood}", font=f_sm, fill=WHITE)

    draw.rectangle([40, 268, W - 40, 272], fill=ACCENT)

    y_stats = 290
    draw.text((40,  y_stats), "🔥", font=f_med, fill=GOLD)
    draw.text((80,  y_stats), f"Prayer streak: {prayer_streak}d", font=f_med, fill=WHITE)
    draw.text((400, y_stats), "📖", font=f_med, fill=(80, 160, 255))
    draw.text((440, y_stats), quran_progress[:28], font=f_med, fill=WHITE)

    y_cursor  = 360
    BLOCK_H   = 72
    BLOCK_GAP = 8
    PAD_L     = 40
    BAR_W     = 6
    max_visible = min(len(full_schedule), 18)

    if full_schedule:
        draw.text((PAD_L, y_cursor), "Today's Plan", font=f_sub, fill=WHITE)
        y_cursor += 44

        for block in full_schedule[:max_visible]:
            btype  = block.get("block_type", "task")
            color  = BLOCK_COLORS.get(btype, DEFAULT_BLOCK_COLOR)
            title  = block.get("title", "")[:38]
            start  = block.get("start", "")
            end    = block.get("end", "")
            time_s = f"{start} – {end}" if start and end else start

            _rounded_rect(draw,
                [PAD_L, y_cursor, W - PAD_L, y_cursor + BLOCK_H],
                radius=12, fill=CARD_BG)
            draw.rectangle(
                [PAD_L, y_cursor, PAD_L + BAR_W, y_cursor + BLOCK_H],
                fill=color)

            cx, cy = PAD_L + BAR_W + 20, y_cursor + BLOCK_H // 2
            draw.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=color)
            draw.text((cx + 18, y_cursor + 10),  title,  font=f_med, fill=WHITE)
            draw.text((cx + 18, y_cursor + 40),  time_s, font=f_xs,  fill=MUTED)

            pill_label = btype.replace("_", " ")
            pl_w = draw.textlength(pill_label, font=f_xs)
            pill_x = W - PAD_L - pl_w - 28
            _rounded_rect(draw,
                [pill_x - 6, y_cursor + 20, W - PAD_L - 6, y_cursor + 50],
                radius=8, fill=(*color, 80))
            draw.text((pill_x, y_cursor + 24), pill_label, font=f_xs, fill=color)

            y_cursor += BLOCK_H + BLOCK_GAP

        if len(full_schedule) > max_visible:
            remaining = len(full_schedule) - max_visible
            draw.text((PAD_L, y_cursor + 6),
                       f"+ {remaining} more blocks…", font=f_sm, fill=MUTED)
            y_cursor += 36

    legend_y = max(y_cursor + 20, H - 220)
    draw.rectangle([40, legend_y, W - 40, legend_y + 2], fill=(50, 60, 90))
    legend_y += 14

    type_counts = Counter(b.get("block_type", "?") for b in full_schedule)
    x_leg = PAD_L
    for btype, count in sorted(type_counts.items()):
        color = BLOCK_COLORS.get(btype, DEFAULT_BLOCK_COLOR)
        label = f"{btype.replace('_',' ')} ×{count}"
        lw = draw.textlength(label, font=f_xs) + 28
        if x_leg + lw > W - PAD_L:
            x_leg = PAD_L
            legend_y += 34
        draw.ellipse([x_leg, legend_y + 6, x_leg + 12, legend_y + 18], fill=color)
        draw.text((x_leg + 18, legend_y + 4), label, font=f_xs, fill=MUTED)
        x_leg += lw + 16

    footer_y = H - 60
    draw.rectangle([0, footer_y - 2, W, footer_y], fill=ACCENT)
    draw.text((40, footer_y + 6),
              f"Generated by YAWM AI  •  {date_str}",
              font=f_xs, fill=MUTED)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, format="PNG", optimize=True)
    return str(out)


@observe(name="8-CanvaAgent")
async def canva_agent_node(state: YawmState) -> dict:
    full_schedule  = state.get("full_schedule", [])
    date_str       = state.get("user_date", date.today().isoformat())
    ramadan_day    = state.get("ramadan_day", 1)
    mood           = state.get("mood", "focused")
    prayer_streak  = state.get("prayer_streak", 0)
    quran_progress = state.get("quran_progress", "On track")

    errors = list(state.get("errors", []))
    card_path: str | None = None

    try:
        card_path = render_schedule_card(
            full_schedule  = full_schedule,
            date_str       = date_str,
            ramadan_day    = ramadan_day,
            mood           = mood,
            prayer_streak  = prayer_streak,
            quran_progress = quran_progress,
            out_path       = SCHEDULE_CARD_PATH,
        )
    except Exception as exc:
        errors.append(f"CanvaAgent: render failed — {exc}")

    return {
        "schedule_card_path": card_path,
        "canva_done":         True,
        "errors":             errors,
    }