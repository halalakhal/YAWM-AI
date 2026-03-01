"""
main.py
────────
YAWM AI — Entry Point
Run the 9-agent daily planning pipeline.

Original usage (unchanged):
  python main.py
  python main.py --mood tired --ramadan-day 27
  python main.py --voice "Don't forget to prepare the iftar talk tonight"
  python main.py --date 2025-03-17 --mood energized --ramadan-day 17

New usage (added):
  python main.py --ask "What Juz am I at?"
  python main.py --ask "What adhkar should I do this morning?" --ramadan-day 21
  python main.py --ask "When should I sleep tonight?" --mood tired
  python main.py --demo
"""
from __future__ import annotations
import argparse
import asyncio
from datetime import date

from graph.graph_runner         import run_pipeline
from agents.router              import classify_intent
from agents.direct_query_agents import (
    answer_quran_query,
    answer_dhikr_query,
    answer_salah_query,
    answer_sleep_query,
    answer_general_query,
)

# ── 3 assessment demo prompts ─────────────────────────────────────────────────
DEMO_PROMPTS = [
    {
        "label":   "Prompt 1 — Full Daily Plan",
        "message": "Plan my day. I have a lot of tasks and I'm feeling tired.",
        "mood":    "tired",
        "day":     21,
    },
    {
        "label":   "Prompt 2 — Quran Progress",
        "message": "Am I on track to finish the Quran by Eid? What Juz am I at?",
        "mood":    "focused",
        "day":     21,
    },
    {
        "label":   "Prompt 3 — Morning Adhkar",
        "message": "What adhkar should I do this morning after Fajr?",
        "mood":    "focused",
        "day":     21,
    },
]


async def handle_query(
    message:     str,
    ramadan_day: int = 21,
    mood:        str = "focused",
    user_date:   str = None,
    voice_note:  str = None,
    timezone:    str = "Africa/Casablanca",
) -> str:
    """
    Route any user message to the correct handler.
    Called only when --ask is used.
    """
    # Classify intent
    intent_result = await classify_intent(message, ramadan_day)
    intent        = intent_result.get("intent", "general")
    confidence    = intent_result.get("confidence", 0.5)

    print(f"\n{'='*55}")
    print(f"You    : {message}")
    print(f"Intent : {intent}  (confidence: {confidence})")
    print(f"{'='*55}\n")

    if intent == "full_plan":
        # Falls back to original pipeline behavior
        await run_pipeline(
            user_date   = user_date,
            mood        = mood,
            ramadan_day = ramadan_day,
            voice_note  = voice_note,
            timezone    = timezone,
        )
        return "Schedule created and written to Google Calendar."

    elif intent == "quran":
        response = await answer_quran_query(message, ramadan_day, mood)

    elif intent == "dhikr":
        response = await answer_dhikr_query(message, ramadan_day, mood=mood)

    elif intent == "salah":
        response = await answer_salah_query(message, ramadan_day, mood=mood)

    elif intent == "sleep":
        response = await answer_sleep_query(message, ramadan_day, mood)

    else:
        response = await answer_general_query(message, ramadan_day, mood)

    print(f"YAWM AI:\n{response}\n")
    return response


async def run_demo():
    """Run all 3 demo prompts for assessment."""
    print("\n" + "=" * 55)
    print("  YAWM AI - Assessment Demo")
    print("=" * 55 + "\n")

    for i, demo in enumerate(DEMO_PROMPTS, 1):
        print(f"\n{'─'*55}")
        print(f"  DEMO {i}/{len(DEMO_PROMPTS)}: {demo['label']}")
        print(f"{'─'*55}")

        await handle_query(
            message     = demo["message"],
            ramadan_day = demo["day"],
            mood        = demo["mood"],
        )

        if i < len(DEMO_PROMPTS):
            input("\n  Press Enter for next prompt...\n")

    print("\nDemo complete\n")


# ── Exact original parse_args — only 2 new args added at the bottom ───────────
def parse_args():
    p = argparse.ArgumentParser(
        description="◈ YAWM AI — 9-Agent Ramadan Daily Planner"
    )
    # ── Original args (byte-for-byte identical) ───────────────────────────────
    p.add_argument("--date",        default=None,      help="Date YYYY-MM-DD (default: today)")
    p.add_argument("--mood",        default="focused", choices=["focused", "tired", "anxious", "energized"],
                   help="Your mood today (affects scheduling)")
    p.add_argument("--ramadan-day", default=21, type=int, dest="ramadan_day",
                   help="Ramadan day number 1-30")
    p.add_argument("--voice",       default=None,      help="Optional voice note / extra context")
    p.add_argument("--timezone",    default="Africa/Casablanca", help="Your timezone")

    # ── New args (additive only) ──────────────────────────────────────────────
    p.add_argument("--ask",  default=None,        help="Ask a direct question without running full pipeline")
    p.add_argument("--demo", action="store_true", help="Run 3 demo prompts for assessment")

    return p.parse_args()


async def main():
    args = parse_args()

    if args.demo:
        # Assessment mode
        await run_demo()

    elif args.ask:
        # Direct question mode
        await handle_query(
            message     = args.ask,
            ramadan_day = args.ramadan_day,
            mood        = args.mood,
            user_date   = args.date,
            voice_note  = args.voice,
            timezone    = args.timezone,
        )

    else:
        # ── Original behavior — byte-for-byte identical ───────────────────────
        await run_pipeline(
            user_date   = args.date,
            mood        = args.mood,
            ramadan_day = args.ramadan_day,
            voice_note  = args.voice,
            timezone    = args.timezone,
        )


if __name__ == "__main__":
    asyncio.run(main())