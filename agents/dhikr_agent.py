"""
agents/dhikr_agent.py
──────────────────────
Agent 5: DhikrAgent
"""
from __future__ import annotations
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from graph.state import YawmState
from config.settings import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL
from utils.prayer_times import is_laylat_al_qadr
from config.langfuse_setup import get_langfuse_config

try:
    from langfuse import observe
except ImportError:
    def observe(name=None):
        def decorator(fn): return fn
        return decorator


SYSTEM_PROMPT = """You are the DhikrAgent. Your job:
Generate adhkar (Islamic remembrance) schedule blocks for the day.

Standard schedule:
- Morning adhkar: 20 min after Fajr (Ayat Al-Kursi, Tasbih x33, Tahmid x33, Takbir x33)
- Evening adhkar: 20 min after Asr (same sequence)
- On Laylat Al-Qadr: add extra 30 min after Maghrib for special dhikr

Return JSON:
{
  "dhikr_blocks": [
    {"title":"📿 Morning Adhkar","start":"HH:MM","end":"HH:MM","block_type":"dhikr","color":"#6EE7B7","fixed":false},
    ...
  ],
  "adhkar_list": ["Ayat Al-Kursi", "Subhan Allah x33", ...]
}

Return ONLY JSON."""


@observe(name="5-DhikrAgent")
async def dhikr_agent_node(state: YawmState) -> dict:
    prayer_times = state.get("prayer_times", [])
    ramadan_day  = state.get("ramadan_day", 1)
    is_qadr      = is_laylat_al_qadr(ramadan_day)

    times_ref = {p["name"]: p["time"] for p in prayer_times} if prayer_times else {}

    llm = ChatOpenAI(model=LLM_MODEL, api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    msg = (
        f"Prayer times today: {json.dumps(times_ref)}\n"
        f"Ramadan Day: {ramadan_day}, Laylat Al-Qadr: {is_qadr}\n\n"
        "Generate the adhkar blocks. Morning adhkar goes 5 min after Fajr end. "
        "Evening adhkar goes 10 min after Asr end."
    )

    resp = await llm.ainvoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=msg),
    ],
        config=get_langfuse_config(state.get("user_date", ""), "5-DhikrAgent"),
    )

    try:
        raw = resp.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw)
    except Exception:
        fajr_end = times_ref.get("Fajr", "05:30")
        asr_end  = times_ref.get("Asr",  "16:10")
        parsed = {
            "dhikr_blocks": [
                {"title": "📿 Morning Adhkar", "start": fajr_end,
                 "end": _add(fajr_end, 20), "block_type": "dhikr", "color": "#6EE7B7", "fixed": False},
                {"title": "📿 Evening Adhkar", "start": _add(asr_end, 10),
                 "end": _add(asr_end, 30), "block_type": "dhikr", "color": "#6EE7B7", "fixed": False},
            ]
        }

    return {
        "dhikr_blocks": parsed.get("dhikr_blocks", []),
        "dhikr_done":   True,
    }


def _add(t: str, mins: int) -> str:
    h, m = map(int, t.split(":"))
    total = h * 60 + m + mins
    return f"{(total//60)%24:02d}:{total%60:02d}"