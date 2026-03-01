"""
utils/quran_tracker.py
───────────────────────
Persistent Quran progress tracker.
Stores pages read per Ramadan day in a local JSON file.
This replaces the hallucinated progress from the LLM.

Usage:
  from utils.quran_tracker import QuranTracker
  tracker = QuranTracker()
  tracker.log_pages(ramadan_day=21, pages=2)
  progress = tracker.get_progress(ramadan_day=21)
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from datetime import datetime

TRACKER_FILE = Path(__file__).parent.parent / "data" / "quran_progress.json"
TOTAL_PAGES  = 604   # standard Mushaf pages
PAGES_PER_JUZ = 20


def _load() -> dict:
    TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
    if TRACKER_FILE.exists():
        try:
            return json.loads(TRACKER_FILE.read_text())
        except Exception:
            pass
    return {"days": {}, "total_pages_read": 0, "last_updated": ""}


def _save(data: dict):
    TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
    data["last_updated"] = datetime.now().isoformat()
    TRACKER_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


class QuranTracker:
    def __init__(self):
        self._data = _load()

    def log_pages(self, ramadan_day: int, pages: int):
        """Record pages read for a given Ramadan day (additive)."""
        key = str(ramadan_day)
        self._data["days"][key] = self._data["days"].get(key, 0) + pages
        self._data["total_pages_read"] = sum(self._data["days"].values())
        _save(self._data)

    def get_pages_for_day(self, ramadan_day: int) -> int:
        return self._data["days"].get(str(ramadan_day), 0)

    def get_total_pages_read(self) -> int:
        return self._data.get("total_pages_read", 0)

    def get_progress(self, ramadan_day: int) -> dict:
        """
        Returns a structured progress dict for QuranWird agent.
        {
          "total_pages_read": int,
          "pages_needed_today": int,
          "juz_completed": int,
          "on_track": bool,
          "catch_up_pages": int,
          "progress_label": str,
          "khatm_percent": float
        }
        """
        total_read    = self.get_total_pages_read()
        expected_total = ramadan_day * (TOTAL_PAGES / 30)   # pages expected by today
        pages_needed  = max(0, round(expected_total - total_read))
        juz_completed = total_read // PAGES_PER_JUZ
        on_track      = total_read >= (expected_total - PAGES_PER_JUZ)
        khatm_pct     = round((total_read / TOTAL_PAGES) * 100, 1)

        # Pages to assign today to stay/get back on track
        remaining_days  = 30 - ramadan_day + 1
        remaining_pages = max(0, TOTAL_PAGES - total_read)
        pages_today     = max(2, -(-remaining_pages // remaining_days))  # ceiling div

        if on_track:
            label = f"Day {ramadan_day} · Juz {juz_completed} complete · {khatm_pct}% ✅"
        else:
            label = (
                f"Day {ramadan_day} · Behind by {pages_needed} pages · "
                f"Need {pages_today} today to catch up ⚠️"
            )

        return {
            "total_pages_read": total_read,
            "pages_needed_today": pages_today,
            "juz_completed": juz_completed,
            "on_track": on_track,
            "catch_up_pages": pages_needed,
            "progress_label": label,
            "khatm_percent": khatm_pct,
        }

    def get_all_days(self) -> dict:
        return dict(self._data.get("days", {}))
