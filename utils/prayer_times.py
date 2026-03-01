"""
utils/prayer_times.py
──────────────────────
Utility functions for prayer times, Ramadan context,
and Laylat Al-Qadr detection.
"""
from __future__ import annotations
import requests
from datetime import date, datetime
from config.settings import (
    ALADHAN_API_URL, PRAYER_CITY, PRAYER_COUNTRY, PRAYER_METHOD
)

LAYLAT_AL_QADR_NIGHTS = {21, 23, 25, 27, 29}

PRAYER_COLORS = {
    "Fajr":    "#A78BFA",  # violet
    "Dhuhr":   "#34D399",  # green
    "Asr":     "#60A5FA",  # blue
    "Maghrib": "#FB923C",  # orange (Iftar)
    "Isha":    "#818CF8",  # indigo
}

# Base duration in minutes per prayer (extended in Ramadan)
PRAYER_DURATION_BASE = {"Fajr": 20, "Dhuhr": 20, "Asr": 20, "Maghrib": 30, "Isha": 25}
PRAYER_DURATION_RAMADAN = {"Fajr": 25, "Dhuhr": 20, "Asr": 20, "Maghrib": 60, "Isha": 30}
PRAYER_DURATION_QADR    = {"Fajr": 25, "Dhuhr": 20, "Asr": 20, "Maghrib": 60, "Isha": 120}


def add_minutes(time_str: str, minutes: int) -> str:
    """Add minutes to HH:MM string and return new HH:MM."""
    h, m = map(int, time_str.split(":"))
    total = h * 60 + m + minutes
    return f"{(total // 60) % 24:02d}:{total % 60:02d}"


def fetch_prayer_times(target_date: date | None = None, city=PRAYER_CITY,
                        country=PRAYER_COUNTRY, method=PRAYER_METHOD) -> dict:
    """Fetch prayer times from AlAdhan API. Returns {name: "HH:MM"}."""
    if target_date is None:
        target_date = date.today()
    d, mo, y = target_date.day, target_date.month, target_date.year
    url = f"{ALADHAN_API_URL}/timingsByCity/{d}-{mo}-{y}?city={city}&country={country}&method={method}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    timings = resp.json()["data"]["timings"]
    core = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]
    return {k: v[:5] for k, v in timings.items() if k in core}


def is_laylat_al_qadr(ramadan_day: int) -> bool:
    return ramadan_day in LAYLAT_AL_QADR_NIGHTS


def build_prayer_blocks(timings: dict, ramadan_day: int | None = None) -> list[dict]:
    """Convert raw prayer timings into ScheduleBlock dicts."""
    is_ramadan = ramadan_day is not None
    is_qadr    = is_laylat_al_qadr(ramadan_day) if ramadan_day else False

    durations = (
        PRAYER_DURATION_QADR if is_qadr else
        PRAYER_DURATION_RAMADAN if is_ramadan else
        PRAYER_DURATION_BASE
    )

    blocks = []
    for name, start in timings.items():
        if name == "Sunrise":
            continue
        dur = durations.get(name, 20)

        # Friendly label
        if is_ramadan and name == "Maghrib":
            label = "🌙 Maghrib + Iftar"
        elif is_qadr and name == "Isha":
            label = "✨ Isha + Taraweeh + Qiyam"
        else:
            label = f"🕌 {name}"

        blocks.append({
            "title":      label,
            "start":      start,
            "end":        add_minutes(start, dur),
            "block_type": "prayer",
            "color":      PRAYER_COLORS.get(name, "#34D399"),
            "fixed":      True,
        })
    return blocks
