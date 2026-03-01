"""
config/settings.py
Central app configuration loaded from .env
"""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── LLM ──────────────────────────────────────────────────────────────────────
OPENAI_API_KEY:  str = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL")
LLM_MODEL:       str = os.getenv("LLM_MODEL", "gpt-4o")   # gpt-4o | gpt-4o-mini | gpt-4-turbo

# ── Google Calendar ───────────────────────────────────────────────────────────
GOOGLE_CALENDAR_ID:       str = os.getenv("GOOGLE_CALENDAR_ID", "primary")
GOOGLE_CREDENTIALS_PATH:  str = os.getenv("GOOGLE_CREDENTIALS_PATH", "./config/google_credentials.json")
GOOGLE_TOKEN_PATH:        str = os.getenv("GOOGLE_TOKEN_PATH", "./config/google_token.json")

# ── Notion ────────────────────────────────────────────────────────────────────
NOTION_TOKEN:       str = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID: str = os.getenv("NOTION_DATABASE_ID", "")

# ── Todoist ───────────────────────────────────────────────────────────────────
TODOIST_API_TOKEN: str = os.getenv("TODOIST_API_TOKEN", "")

# ── Prayer Times ─────────────────────────────────────────────────────────────
ALADHAN_API_URL: str = os.getenv("ALADHAN_API_URL", "https://api.aladhan.com/v1")
PRAYER_CITY:     str = os.getenv("PRAYER_CITY", "Casablanca")
PRAYER_COUNTRY:  str = os.getenv("PRAYER_COUNTRY", "Morocco")
PRAYER_METHOD:   int = int(os.getenv("PRAYER_METHOD", "2"))

# ── App ───────────────────────────────────────────────────────────────────────
USER_TIMEZONE: str  = os.getenv("USER_TIMEZONE", "Africa/Casablanca")
RAMADAN_DAY:   int  = int(os.getenv("RAMADAN_DAY", "1"))
OUTPUT_DIR:    Path = Path(os.getenv("OUTPUT_DIR", "./output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SCHEDULE_CARD_PATH: str = str(OUTPUT_DIR / "daily_schedule.png")
