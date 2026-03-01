"""
agents/quran_wird.py  (UPGRADED)
──────────────────────────────────
Agent 6: QuranWird
"""
from __future__ import annotations
import json
from langchain_openai        import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from graph.state             import YawmState
from config.settings         import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL
from utils.prayer_times      import is_laylat_al_qadr
from utils.quran_tracker     import QuranTracker
from config.langfuse_setup   import get_langfuse_config

try:
    from langfuse import observe
except ImportError:
    def observe(name=None):
        def decorator(fn): return fn
        return decorator

SYSTEM_PROMPT = """You are the QuranWird agent. Schedule the daily Quran recitation.

Rules:
- Place wird AFTER morning adhkar ends
- On Laylat Al-Qadr nights: extend to 5 pages + add Surah Al-Qadr x3 block
- Never place wird inside a prayer or sleep block
- Use the real progress data provided — do NOT invent progress

Return JSON:
{
  "quran_blocks": [
    {
      "title": "📖 Quran Wird (N pages)",
      "start": "HH:MM",
      "end":   "HH:MM",
      "block_type": "quran",
      "color": "#F9A8D4",
      "fixed": false,
      "note": "optional scheduling note"
    }
  ],
  "quran_progress": "<the exact progress_label string provided to you>",
  "pages_today": N
}
Return ONLY JSON."""


@observe(name="6-QuranWird")
async def quran_wird_node(state: YawmState) -> dict:
    prayer_times = state.get("prayer_times", [])
    ramadan_day  = state.get("ramadan_day", 1)
    routing_cfg  = state.get("routing_config") or {}
    dhikr_blocks = state.get("dhikr_blocks", [])
    is_qadr      = is_laylat_al_qadr(ramadan_day)

    tracker  = QuranTracker()
    progress = tracker.get_progress(ramadan_day)
    pages_today = progress["pages_needed_today"]

    if is_qadr:
        pages_today = max(5, pages_today)

    times_ref = {p["name"]: p["time"] for p in prayer_times}
    fajr_time = times_ref.get("Fajr", "05:30")

    morning_adhkar_end = (
        dhikr_blocks[0]["end"]
        if dhikr_blocks
        else _add(fajr_time, 25)
    )

    llm = ChatOpenAI(model=LLM_MODEL, api_key=OPENAI_API_KEY,
                     base_url=OPENAI_BASE_URL, temperature=0.1)

    msg = (
        f"Ramadan Day: {ramadan_day}, Laylat Al-Qadr: {is_qadr}\n"
        f"Pages to read today (from real tracker): {pages_today}\n"
        f"Real progress: {progress['progress_label']}\n"
        f"Khatm: {progress['khatm_percent']}% complete ({progress['total_pages_read']}/604 pages)\n"
        f"Morning adhkar ends at: {morning_adhkar_end}\n"
        f"Prayer times: {json.dumps(times_ref)}\n\n"
        "Schedule the Quran wird block(s) for today. Use the real progress label exactly."
    )

    resp = await llm.ainvoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=msg),
    ],
        config=get_langfuse_config(state.get("user_date", ""), "6-QuranWird"),
    )

    try:
        raw = resp.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw)
    except Exception:
        end_time = _add(morning_adhkar_end, pages_today * 12)
        parsed = {
            "quran_blocks": [{
                "title":      f"📖 Quran Wird ({pages_today} pages)",
                "start":      morning_adhkar_end,
                "end":        end_time,
                "block_type": "quran",
                "color":      "#F9A8D4",
                "fixed":      False,
            }],
            "quran_progress": progress["progress_label"],
            "pages_today":    pages_today,
        }

    actual_pages = parsed.get("pages_today", pages_today)
    tracker.log_pages(ramadan_day, actual_pages)

    return {
        "quran_blocks":        parsed.get("quran_blocks", []),
        "quran_progress":      parsed.get("quran_progress", progress["progress_label"]),
        "quran_progress_data": progress,
        "quran_done":          True,
    }


def _add(t: str, mins: int) -> str:
    h, m = map(int, t.split(":"))
    total = h * 60 + m + mins
    return f"{(total // 60) % 24:02d}:{total % 60:02d}"