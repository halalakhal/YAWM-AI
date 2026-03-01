"""
agents/direct_query_agents.py
──────────────────────────────
Lightweight agents that answer specific questions directly
WITHOUT running the full 9-agent pipeline.

Each function is an "Agent as Tool" — called by the router
when user asks a targeted question.

Agents:
  answer_quran_query   — Juz, pages, progress, khatm status
  answer_dhikr_query   — what adhkar to do, morning/evening list
  answer_salah_query   — prayer times, streak, next prayer
  answer_sleep_query   — bedtime, wake time, cycles
  answer_tasks_query   — today's tasks, priorities
  answer_general_query — fallback for general Ramadan questions
"""
from __future__ import annotations
import json
from datetime import date, datetime
from langchain_openai        import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from config.settings         import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL
from utils.quran_tracker     import QuranTracker
from utils.sleep_calculator  import calculate_sleep_window
from utils.prayer_times      import is_laylat_al_qadr

try:
    from langfuse import observe
except ImportError:
    def observe(name=None):
        def decorator(fn): return fn
        return decorator


def _get_llm():
    return ChatOpenAI(
        model=LLM_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        temperature=0.3,
    )


# ─────────────────────────────────────────────────────────────────────────────
@observe(name="DirectQuery-Quran")
async def answer_quran_query(
    user_message: str,
    ramadan_day:  int,
    mood:         str = "focused",
) -> str:
    """
    Answer any Quran-related question using real tracker data.
    Examples:
      "What Juz am I at?"
      "How many pages do I need today?"
      "Am I on track to finish by Eid?"
      "How much of the Quran have I read?"
    """
    tracker  = QuranTracker()
    progress = tracker.get_progress(ramadan_day)
    is_qadr  = is_laylat_al_qadr(ramadan_day)

    system = """You are the YAWM AI Quran advisor.
Answer the user's question about their Quran progress using the real data provided.
Be encouraging, specific, and Islamic in tone.
If they are behind, motivate them with the reward of completing the Quran in Ramadan.
Keep response under 150 words."""

    context = f"""
Real Quran Progress Data:
- Ramadan Day: {ramadan_day}
- Total pages read so far: {progress['total_pages_read']} / 604
- Juz completed: {progress['juz_completed']} / 30
- Khatm completion: {progress['khatm_percent']}%
- On track: {progress['on_track']}
- Pages needed today: {progress['pages_today'] if hasattr(progress, 'pages_today') else progress['pages_needed_today']}
- Pages behind: {progress['catch_up_pages']}
- Progress label: {progress['progress_label']}
- Tonight is Laylat Al-Qadr candidate: {is_qadr}

User question: {user_message}
"""

    resp = await _get_llm().ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=context),
    ])
    return resp.content


# ─────────────────────────────────────────────────────────────────────────────
@observe(name="DirectQuery-Dhikr")
async def answer_dhikr_query(
    user_message: str,
    ramadan_day:  int,
    prayer_times: dict | None = None,
    mood:         str = "focused",
) -> str:
    """
    Answer adhkar questions with actual dhikr content.
    Examples:
      "What adhkar should I do this morning?"
      "What is the evening adhkar?"
      "Give me today's dhikr list"
      "What should I read after Fajr?"
    """
    is_qadr = is_laylat_al_qadr(ramadan_day)
    now_hour = datetime.now().hour
    time_of_day = "morning" if now_hour < 12 else ("evening" if now_hour < 20 else "night")

    system = """You are the YAWM AI Dhikr advisor.
Provide the actual Arabic adhkar with transliteration and translation.
Structure your response clearly with morning or evening sections as relevant.
Include the count (x33, x1, etc.) for each dhikr.
On Laylat Al-Qadr nights, add the special Qadr dua.
Keep it practical and actionable."""

    context = f"""
Ramadan Day: {ramadan_day}
Current time of day: {time_of_day}
Laylat Al-Qadr night: {is_qadr}
Mood: {mood}
Prayer times available: {json.dumps(prayer_times or {})}

User question: {user_message}

Provide the relevant adhkar list with:
1. Arabic text
2. Transliteration  
3. Translation
4. Count/repetition
5. Best time to read
"""

    resp = await _get_llm().ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=context),
    ])
    return resp.content


# ─────────────────────────────────────────────────────────────────────────────
@observe(name="DirectQuery-Salah")
async def answer_salah_query(
    user_message: str,
    ramadan_day:  int,
    prayer_times: dict | None = None,
    prayer_streak: int = 0,
    mood:          str = "focused",
) -> str:
    """
    Answer prayer-related questions.
    Examples:
      "What's my prayer streak?"
      "When is Asr today?"
      "Which prayer is next?"
      "How much time until Maghrib?"
    """
    now     = datetime.now().strftime("%H:%M")
    is_qadr = is_laylat_al_qadr(ramadan_day)

    system = """You are the YAWM AI Salah advisor.
Answer prayer questions using the real data provided.
Be precise with times, encouraging about the streak.
On Laylat Al-Qadr nights, remind the user of the special value of Isha/Taraweeh.
Keep response concise and actionable."""

    context = f"""
Current time: {now}
Ramadan Day: {ramadan_day}
Prayer streak: {prayer_streak} days
Laylat Al-Qadr night: {is_qadr}
Today's prayer times: {json.dumps(prayer_times or {})}

User question: {user_message}
"""

    resp = await _get_llm().ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=context),
    ])
    return resp.content


# ─────────────────────────────────────────────────────────────────────────────
@observe(name="DirectQuery-Sleep")
async def answer_sleep_query(
    user_message: str,
    ramadan_day:  int,
    mood:         str = "focused",
) -> str:
    """
    Answer sleep questions using real sleep calculator.
    Examples:
      "When should I sleep tonight?"
      "How many sleep cycles can I get?"
      "What's my optimal bedtime?"
      "Should I take a nap today?"
    """
    sleep_win = calculate_sleep_window(suhoor_time="03:30", mood=mood)

    system = """You are the YAWM AI sleep advisor.
Answer sleep questions using the real calculated data.
Explain the sleep cycle math clearly.
Always mention the Qailulah (Dhuhr nap) as a Sunnah compensation strategy.
Keep response under 120 words."""

    context = f"""
Ramadan Day: {ramadan_day}
Mood: {mood}
Calculated sleep window:
- Recommended bedtime: {sleep_win.bedtime}
- Estimated sleep onset: {sleep_win.sleep_time}
- Wake time (for Suhoor): {sleep_win.wake_time}
- Complete sleep cycles: {sleep_win.cycles}
- Total sleep: {sleep_win.total_sleep_min} minutes
- Warning: {sleep_win.warning or 'None'}

Suhoor time: 03:30
User question: {user_message}
"""

    resp = await _get_llm().ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=context),
    ])
    return resp.content


# ─────────────────────────────────────────────────────────────────────────────
@observe(name="DirectQuery-General")
async def answer_general_query(
    user_message: str,
    ramadan_day:  int,
    mood:         str = "focused",
) -> str:
    """
    Fallback for general Ramadan questions.
    Examples:
      "Give me a Ramadan tip for today"
      "What should I focus on this week?"
      "How do I stay productive in Ramadan?"
    """
    is_qadr = is_laylat_al_qadr(ramadan_day)

    system = """You are YAWM AI — an intelligent Ramadan daily planner assistant.
Answer the user's general question with Islamic wisdom and practical advice.
Be warm, encouraging, and specific to their Ramadan day and mood.
Keep response under 200 words."""

    context = f"""
Ramadan Day: {ramadan_day}
Mood: {mood}
Laylat Al-Qadr night: {is_qadr}
Current date: {date.today().isoformat()}

User question: {user_message}
"""

    resp = await _get_llm().ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=context),
    ])
    return resp.content
