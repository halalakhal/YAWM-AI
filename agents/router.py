"""
agents/router.py
─────────────────
The entry point for ALL user interactions.

Classifies user intent and routes to either:
  1. Full pipeline   — "plan my day", "schedule my tasks"
  2. Direct agent    — "what adhkar today?", "what juz am I at?"

This implements the Agents as Tools Pattern for direct queries,
combined with the existing Hierarchical Pipeline for full planning.
"""
from __future__ import annotations
import json
from datetime import date
from langchain_openai        import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from config.settings         import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL

try:
    from langfuse import observe
except ImportError:
    def observe(name=None):
        def decorator(fn): return fn
        return decorator


ROUTER_PROMPT = """You are the YAWM AI router. Classify the user's intent into exactly one category.

Categories:
  full_plan     — user wants full daily schedule ("plan my day", "schedule everything", "create my plan")
  quran         — anything about Quran pages, Juz, progress, khatm, wird ("what juz", "how many pages", "quran progress", "am I on track")
  dhikr         — anything about adhkar, dhikr, remembrance ("what adhkar", "morning dhikr", "what should I read")
  salah         — anything about prayer times, streak, which prayer is next ("prayer times", "my streak", "when is Asr")
  sleep         — anything about sleep, bedtime, wake time, cycles ("when should I sleep", "bedtime", "sleep cycles")
  tasks         — anything about today's tasks, todolist, what to work on ("what are my tasks", "what should I work on")
  general       — greetings, general Ramadan questions, anything else

Return ONLY this JSON:
{
  "intent": "full_plan|quran|dhikr|salah|sleep|tasks|general",
  "confidence": 0.0-1.0,
  "extracted_context": "any relevant info from the query (date, day number, etc.)"
}"""


INTENT_TO_AGENT = {
    "full_plan": "pipeline",
    "quran":     "quran_agent",
    "dhikr":     "dhikr_agent",
    "salah":     "salah_agent",
    "sleep":     "sleep_agent",
    "tasks":     "tasks_agent",
    "general":   "general_agent",
}


@observe(name="0-Router")
async def classify_intent(user_message: str, ramadan_day: int = 1) -> dict:
    """Classify user intent. Returns intent dict."""
    llm = ChatOpenAI(
        model=LLM_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        temperature=0,
    )

    resp = await llm.ainvoke([
        SystemMessage(content=ROUTER_PROMPT),
        HumanMessage(content=f"Ramadan Day: {ramadan_day}\nUser message: {user_message}"),
    ])

    try:
        raw = resp.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception:
        return {"intent": "general", "confidence": 0.5, "extracted_context": ""}
