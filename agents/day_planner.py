"""
agents/day_planner.py  (FIXED + RAG)
───────────────────────────────────
Agent 7: DayPlanner — THE GENIUS SCHEDULER
"""
from __future__ import annotations
import json
from langchain_openai        import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from graph.state             import YawmState
from config.settings         import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL
from utils.sleep_calculator  import calculate_sleep_window, get_dhuhr_nap_block
from config.langfuse_setup   import get_langfuse_config

try:
    from langfuse import observe
except ImportError:
    def observe(name=None):
        def decorator(fn): return fn
        return decorator

SYSTEM_PROMPT = """You are the DayPlanner — a genius AI scheduler for Ramadan.

Your job: build a COMPLETE, conflict-free daily schedule from 03:00 to 23:59.

FIXED blocks — NEVER move or overlap these:
- Prayer blocks (Fajr, Dhuhr, Asr, Maghrib, Isha)
- Dhikr blocks (morning/evening adhkar)
- Quran wird blocks
- Sleep/Suhoor blocks (computed by sleep calculator)
- Qailulah nap (after Dhuhr)
- Google Calendar events marked fixed:true

FLEXIBLE tasks: schedule in remaining gaps intelligently.

CRITICAL RULES FOR TASK TITLES:
- Use the EXACT title from the task list — NEVER rename tasks to generic names like
  "Flexible Task 1", "Flexible Task 2", "Deep Work Session", etc.
- Every flexible task must appear in the schedule with its original title
- Respect deadlines: tasks with "before HH:MM" must END before that time
- High priority tasks → schedule earlier in the day, inside the deep_work_window
- Estimate duration from estimated_minutes if provided, otherwise use 60–90 min for
  Work tasks and 30–45 min for Personal tasks
- Group related tasks back-to-back when possible (e.g. two Work tasks)

SCHEDULING RULES:
1. NO overlaps — ever. Check every slot before placing.
2. High priority Work tasks → deep_work_window (morning or afternoon per config)
3. Suhoor: 03:30–04:15 (meal block, fixed)
4. Use the EXACT bedtime from sleep_window — not a hardcoded time
5. podcast block → schedule it in a light window (post-Asr or post-Isha)
6. Leave 5-min breathing room between blocks where possible
7. Tired mood → shorter deep work sessions (45 min max), more rest breaks
8. After Isha → wind-down only: light reading, podcast, dhikr — no deep work

BLOCK COLORS:
- prayer    → #10B981 (green)
- deep_work → #3B82F6 (blue)
- rest      → #EF4444 (red)
- sleep     → #4C1D95 (dark purple)
- meal      → #F97316 (orange)
- dhikr     → #8B5CF6 (purple)
- quran     → #8B5CF6 (purple)
- meeting   → #FBBF24 (yellow)
- podcast   → #F59E0B (amber)
- flexible  → #6B7280 (gray)

block_type values: prayer | deep_work | rest | sleep | meal | dhikr | quran |
                   meeting | podcast | flexible

Output JSON:
{
  "full_schedule": [
    {
      "title":      str,
      "start":      "HH:MM",
      "end":        "HH:MM",
      "block_type": str,
      "color":      "#hex",
      "fixed":      bool,
      "task_id":    str
    }
  ]
}

Sort by start time. Return ONLY valid JSON, no explanation."""


@observe(name="7-DayPlanner")
async def day_planner_node(state: YawmState) -> dict:
    target_date   = state.get("user_date", "")
    routing_cfg   = state.get("routing_config") or {}
    cal_events    = state.get("raw_calendar_events", [])
    tasks         = state.get("raw_tasks", [])
    prayer_blocks = state.get("prayer_blocks", [])
    dhikr_blocks  = state.get("dhikr_blocks", [])
    quran_blocks  = state.get("quran_blocks", [])
    mood          = state.get("mood", "focused")
    ramadan_day   = state.get("ramadan_day", 1)
    prayer_times  = {p["name"]: p["time"] for p in state.get("prayer_times", [])}

    suhoor_time = "03:30"
    sleep_win   = calculate_sleep_window(suhoor_time=suhoor_time, mood=mood)

    sleep_blocks = [
        {
            "title":      f"😴 Sleep ({sleep_win.cycles} cycles · {sleep_win.total_sleep_min} min)",
            "start":      sleep_win.bedtime,
            "end":        "03:30",
            "block_type": "sleep",
            "color":      "#4C1D95",
            "fixed":      True,
            "note":       sleep_win.warning or f"Bedtime for {sleep_win.cycles} complete cycles",
        },
        {
            "title":      "🌙 Suhoor",
            "start":      "03:30",
            "end":        "04:15",
            "block_type": "meal",
            "color":      "#F97316",
            "fixed":      True,
        },
    ]

    dhuhr_end = None
    for b in prayer_blocks:
        if "Dhuhr" in b.get("title", ""):
            dhuhr_end = b.get("end")
            break
    if not dhuhr_end and prayer_times.get("Dhuhr"):
        dhuhr_end = _add(prayer_times["Dhuhr"], 15)

    qailulah_block = get_dhuhr_nap_block(dhuhr_end) if dhuhr_end else None

    all_fixed = (
        prayer_blocks
        + dhikr_blocks
        + quran_blocks
        + sleep_blocks
        + ([qailulah_block] if qailulah_block else [])
        + [
            {
                **e,
                "title":      e.get("title", "Meeting"),
                "block_type": "meeting",
                "color":      "#FBBF24",
                "fixed":      True,
            }
            for e in cal_events
        ]
    )

    task_lines = ""
    for t in tasks:
        deadline = t.get("deadline") or t.get("due") or "flexible"
        priority = t.get("priority", "medium")
        mins     = t.get("estimated_minutes") or t.get("estimated_time", "?")
        ttype    = t.get("type") or t.get("source", "flexible")
        tid      = t.get("id", "")
        task_lines += (
            f"  - id={tid} [{priority.upper()}] \"{t['title']}\" "
            f"| type={ttype} | deadline={deadline} | est={mins}min\n"
        )

    prefs_text = "  None stored yet."
    try:
        from rag.store import retrieve_preferences
        prefs = retrieve_preferences(
            query     = f"scheduling tasks mood={mood} duration timing preferences",
            n_results = 8,
        )
        if prefs:
            prefs_text = "\n".join(f"  - {p}" for p in prefs)
    except Exception:
        pass

    llm = ChatOpenAI(
        model=LLM_MODEL, api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL, temperature=0.2,
    )

    msg = (
        f"Date: {target_date}, Ramadan Day: {ramadan_day}, Mood: {mood}\n"
        f"Energy: {routing_cfg.get('energy_level', 'medium')}, "
        f"Deep work window: {routing_cfg.get('deep_work_window', 'morning')}\n\n"
        f"SLEEP WINDOW (from calculator):\n"
        f"  Bedtime: {sleep_win.bedtime} → Wake: {sleep_win.wake_time}\n"
        f"  Cycles: {sleep_win.cycles} × 90 min = {sleep_win.total_sleep_min} min sleep\n"
        f"  {sleep_win.warning}\n\n"
        f"PERSONAL PREFERENCES (from RAG — MUST be respected):\n"
        f"{prefs_text}\n\n"
        f"FIXED BLOCKS ({len(all_fixed)}):\n"
        f"{json.dumps(all_fixed, indent=2)}\n\n"
        f"FLEXIBLE TASKS TO SCHEDULE ({len(tasks)}):\n"
        f"{task_lines}\n"
        f"⚠️  IMPORTANT: Use the EXACT task titles shown above.\n"
        f"   Do NOT rename them to 'Flexible Task 1' or 'Deep Work Session'.\n"
        f"   Every task listed above MUST appear in the schedule.\n"
        f"   RESPECT all personal preferences listed above.\n\n"
        "Build the complete conflict-free daily schedule. Use the computed bedtime exactly."
    )

    resp = await llm.ainvoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=msg),
    ],
        config=get_langfuse_config(target_date, "7-DayPlanner"),
    )

    try:
        raw = resp.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed   = json.loads(raw)
        schedule = parsed.get("full_schedule", [])
    except Exception as e:
        print(f"\n[DEBUG PLANNER] parse failed: {e}", flush=True)
        print(f"\n[DEBUG PLANNER] raw: {resp.content[:300]}", flush=True)
        fallback_tasks = [
            {
                "title":      t.get("title", "Task"),
                "start":      "09:00",
                "end":        "10:00",
                "block_type": "flexible",
                "color":      "#6B7280",
                "fixed":      False,
                "task_id":    t.get("id", ""),
            }
            for t in tasks
        ]
        schedule = all_fixed + fallback_tasks

    schedule.sort(key=lambda b: _hm(b.get("start", "99:99")))

    return {
        "full_schedule": schedule,
        "sleep_window": {
            "bedtime":         sleep_win.bedtime,
            "wake_time":       sleep_win.wake_time,
            "cycles":          sleep_win.cycles,
            "total_sleep_min": sleep_win.total_sleep_min,
            "warning":         sleep_win.warning,
        },
        "day_planner_done": True,
    }


def _add(t: str, mins: int) -> str:
    h, m = map(int, t.split(":"))
    total = h * 60 + m + mins
    return f"{(total // 60) % 24:02d}:{total % 60:02d}"


def _hm(t: str) -> int:
    try:
        h, m = map(int, t.split(":"))
        return h * 60 + m
    except Exception:
        return 9999