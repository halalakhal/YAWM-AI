"""
utils/sleep_calculator.py
──────────────────────────
Calculates optimal sleep windows based on:
 - Suhoor time (must wake before it)
 - Sleep cycle length (90 min default)
 - Sleep latency (time to fall asleep, ~15 min)
 - Mood (tired → earlier bedtime target)

Returns concrete bedtime and wake-up recommendations
so DayPlanner can use real numbers, not hardcoded 22:30.
"""
from __future__ import annotations
from dataclasses import dataclass


CYCLE_MINUTES   = 90
LATENCY_MINUTES = 15   # average time to fall asleep


@dataclass
class SleepWindow:
    bedtime: str           # "HH:MM" — when to get into bed
    sleep_time: str        # "HH:MM" — estimated actual sleep onset
    wake_time: str         # "HH:MM" — when to wake (= suhoor start)
    cycles: int            # number of complete cycles
    total_sleep_min: int   # actual sleep minutes
    warning: str           # empty or a caution message


def _hm_to_min(t: str) -> int:
    h, m = map(int, t.split(":"))
    return h * 60 + m


def _min_to_hm(m: int) -> str:
    m = m % (24 * 60)
    return f"{m // 60:02d}:{m % 60:02d}"


def calculate_sleep_window(
    suhoor_time: str = "03:30",
    mood: str = "focused",
    max_cycles: int = 5,
) -> SleepWindow:
    """
    Work backward from suhoor_time to find the latest bedtime
    that still allows N complete 90-min cycles.

    Ramadan reality check:
      Suhoor = 03:30  →  wake = 03:15 (15-min buffer to prepare)
      Sleep onset cap = 03:15 - (N × 90) - 15 (latency)
      Max practical: 3 cycles = 03:15 - 270 - 15 = 23:00 → bedtime 23:00
                     4 cycles = 03:15 - 360 - 15 = 21:30 → bedtime 21:30
    """
    wake_min = _hm_to_min(suhoor_time) - 15   # wake 15 min before suhoor

    # Mood → target number of cycles
    mood_cycles = {
        "tired":     4,
        "anxious":   4,
        "focused":   3,
        "energized": 3,
    }
    target_cycles = min(mood_cycles.get(mood, 3), max_cycles)

    warning = ""
    cycles  = target_cycles

    while cycles >= 1:
        sleep_onset = wake_min - (cycles * CYCLE_MINUTES)
        bedtime_min = sleep_onset - LATENCY_MINUTES

        # Sanity: bedtime must be after 20:00 (Isha needs to happen first)
        if bedtime_min % (24 * 60) >= _hm_to_min("20:00") or \
           bedtime_min % (24 * 60) == 0:
            break
        cycles -= 1

    if cycles < target_cycles:
        warning = (
            f"⚠️  Only {cycles} sleep cycle(s) possible before Suhoor. "
            f"Consider a Dhuhr nap (20 min) to compensate."
        )
    if cycles == 0:
        cycles = 1
        sleep_onset = wake_min - CYCLE_MINUTES
        bedtime_min = sleep_onset - LATENCY_MINUTES
        warning = "⚠️  Less than 1 full cycle before Suhoor — prioritise Dhuhr nap strongly."

    return SleepWindow(
        bedtime       = _min_to_hm(bedtime_min),
        sleep_time    = _min_to_hm(sleep_onset),
        wake_time     = _min_to_hm(wake_min),
        cycles        = cycles,
        total_sleep_min = cycles * CYCLE_MINUTES,
        warning       = warning,
    )


def get_dhuhr_nap_block(dhuhr_end: str, duration_min: int = 20) -> dict:
    """
    Returns a short rest block right after Dhuhr prayer ends.
    Capped at 20 min — longer risks disrupting night sleep and entering deep sleep.
    """
    start = _hm_to_min(dhuhr_end) + 5   # 5-min buffer after prayer
    end   = start + min(duration_min, 20)
    return {
        "title":      "😴 Qailulah Nap (20 min)",
        "start":      _min_to_hm(start),
        "end":        _min_to_hm(end),
        "block_type": "rest",
        "color":      "#A78BFA",
        "fixed":      False,
        "note":       "Sunnah nap — aids alertness for Asr/evening ibadah",
    }
