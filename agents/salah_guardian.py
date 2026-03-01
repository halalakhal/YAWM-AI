"""
agents/salah_guardian.py
─────────────────────────
Agent 4: SalahGuardian
"""
from __future__ import annotations
import json
from datetime import date
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from graph.state import YawmState
from config.settings import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL
from tools.mcp_client import get_mcp_client
from utils.prayer_times import build_prayer_blocks, is_laylat_al_qadr
from config.langfuse_setup import get_langfuse_config

try:
    from langfuse import observe
except ImportError:
    def observe(name=None):
        def decorator(fn): return fn
        return decorator

SYSTEM_PROMPT = """You are the SalahGuardian agent. Your job:
1. Call get_prayer_times for today's date to get accurate prayer times
2. Return a JSON with:
{
  "prayer_times": [{"name":"Fajr","time":"05:12","color":"#A78BFA"}, ...],
  "prayer_blocks": [{"title":"🕌 Fajr","start":"05:12","end":"05:32","block_type":"prayer","color":"#A78BFA","fixed":true}, ...],
  "prayer_streak": 18,
  "notes": "any special notes e.g. Laylat Al-Qadr"
}

On Laylat Al-Qadr nights (Ramadan days 21,23,25,27,29) extend Isha to 120 minutes.
On Ramadan nights extend Maghrib to 60 minutes for Iftar.
Return ONLY JSON."""


@observe(name="4-SalahGuardian")
async def salah_guardian_node(state: YawmState) -> dict:
    target_date = state.get("user_date") or date.today().isoformat()
    ramadan_day = state.get("ramadan_day", 1)
    routing_cfg = state.get("routing_config") or {}

    client = get_mcp_client()
    tools  = await client.get_tools(server_name="aladhan")

    llm   = ChatOpenAI(model=LLM_MODEL, api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    agent = create_react_agent(llm, tools)

    msg = (
        f"Today: {target_date}, Ramadan Day: {ramadan_day}\n"
        f"Is Laylat Al-Qadr candidate: {is_laylat_al_qadr(ramadan_day)}\n"
        f"Prayer alert before minutes: {routing_cfg.get('prayer_alert_min_before', 10)}\n\n"
        "Fetch prayer times and build the complete prayer blocks schedule."
    )

    result = await agent.ainvoke({
        "messages": [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=msg)]
    },
        config=get_langfuse_config(target_date, "4-SalahGuardian"),
    )
    last = result["messages"][-1].content

    try:
        raw = last.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw)
    except Exception:
        try:
            from utils.prayer_times import fetch_prayer_times
            timings       = fetch_prayer_times()
            prayer_blocks = build_prayer_blocks(timings, ramadan_day)
            prayer_times  = [{"name": k, "time": v} for k, v in timings.items()]
            parsed = {"prayer_times": prayer_times, "prayer_blocks": prayer_blocks, "prayer_streak": 0}
        except Exception:
            parsed = {"prayer_times": [], "prayer_blocks": [], "prayer_streak": 0}

    return {
        "prayer_times":  parsed.get("prayer_times", []),
        "prayer_blocks": parsed.get("prayer_blocks", []),
        "prayer_streak": parsed.get("prayer_streak", 0),
        "salah_done":    True,
        "messages":      result["messages"],
    }