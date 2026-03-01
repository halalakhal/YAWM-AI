"""
agents/planner.py
──────────────────
Agent 2: Planner
"""
from __future__ import annotations
import json
from datetime import date, datetime
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from graph.state import YawmState
from config.settings import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL
from tools.mcp_client import get_mcp_client
from utils.prayer_times import is_laylat_al_qadr
from config.langfuse_setup import get_langfuse_config

try:
    from langfuse import observe
except ImportError:
    def observe(name=None):
        def decorator(fn): return fn
        return decorator

SYSTEM_PROMPT = """You are the Planner agent. Your job:
Given the user's Ramadan day, mood, current time, and task list, produce a routing_config JSON.

The routing_config must have these keys:
{
  "ramadan_day": int,
  "mood": str,
  "is_laylat_al_qadr": bool,
  "energy_level": "high"|"medium"|"low",
  "enable_salah": true,
  "enable_dhikr": true,
  "enable_quran": true,
  "quran_pages": int,
  "deep_work_window": "morning"|"afternoon"|"evening",
  "rest_after_dhuhr": bool,
  "prayer_alert_min_before": int
}

Reasoning rules:
- mood=tired → energy_level=low, deep_work_window=morning
- mood=energized → energy_level=high, more quran pages
- Laylat Al-Qadr → quran_pages=5, prayer_alert_min_before=15
- Always enable_salah=true

Return ONLY the JSON object."""


@observe(name="2-Planner")
async def planner_node(state: YawmState) -> dict:
    ramadan_day = state.get("ramadan_day", 1)
    mood        = state.get("mood", "focused")
    tasks       = state.get("normalized_task_list", [])
    target_date = state.get("user_date") or date.today().isoformat()
    now         = datetime.now().strftime("%H:%M")

    client        = get_mcp_client()
    aladhan_tools = await client.get_tools(server_name="aladhan")

    llm   = ChatOpenAI(model=LLM_MODEL, api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    agent = create_react_agent(llm, aladhan_tools)

    msg = (
        f"Date: {target_date}, Current time: {now}\n"
        f"Ramadan Day: {ramadan_day}, Mood: {mood}\n"
        f"Tasks to schedule: {json.dumps(tasks[:10])}\n\n"
        "First call get_hijri_date to verify the Hijri context.\n"
        "Then return the routing_config JSON as described in your system prompt."
    )

    result = await agent.ainvoke({
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=msg),
        ]
    },
        config=get_langfuse_config(target_date, "2-Planner"),
    )
    last = result["messages"][-1].content

    try:
        raw = last.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        routing = json.loads(raw)
    except Exception:
        routing = {
            "ramadan_day": ramadan_day,
            "mood": mood,
            "is_laylat_al_qadr": is_laylat_al_qadr(ramadan_day),
            "energy_level": "medium",
            "enable_salah": True,
            "enable_dhikr": True,
            "enable_quran": True,
            "quran_pages": 2,
            "deep_work_window": "morning",
            "rest_after_dhuhr": True,
            "prayer_alert_min_before": 10,
        }

    return {
        "routing_config": routing,
        "planner_done":   True,
        "messages":       result["messages"],
    }