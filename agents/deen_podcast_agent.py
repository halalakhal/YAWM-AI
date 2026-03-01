"""
agents/deen_podcast_agent.py  — FIXED
──────────────────────────────────────
Agent 8.5: DeenPodcastAgent
"""
from __future__ import annotations
import json
import os
from langchain_openai         import ChatOpenAI
from langchain_core.messages  import HumanMessage, SystemMessage
from langgraph.prebuilt       import create_react_agent

from graph.state      import YawmState
from config.settings  import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL
from tools.mcp_client import get_mcp_client
from config.langfuse_setup import get_langfuse_config

try:
    from langfuse import observe
except ImportError:
    def observe(name=None):
        def decorator(fn): return fn
        return decorator


SYSTEM_PROMPT = """You are the DeenPodcastAgent. Execute these steps in order:

1. Call search_deen_youtube with the topic and mood provided to you.

2. Call send_gmail_notify with:
   - video_title, video_url, video_channel from step 1
   - scheduled_time = the slot time provided
   - ramadan_day = the day number provided
   - schedule_image_path = the image path provided

3. Only call send_whatsapp_notify if notify_channel is 'whatsapp' or 'both'.

After all tool calls return ONLY this JSON, nothing else:
{
  "podcast_block": {
    "title": "🎧 Deen Podcast — <short title>",
    "start": "HH:MM",
    "end": "HH:MM",
    "block_type": "podcast",
    "color": "#F59E0B",
    "fixed": false
  },
  "video": {
    "title": "...",
    "channel": "...",
    "url": "..."
  },
  "notifications": {
    "gmail_sent": true,
    "whatsapp_sent": false,
    "errors": []
  }
}"""


def _get_topic(ramadan_day: int, mood: str) -> str:
    if ramadan_day <= 10:
        return "sincerity and intention in Ramadan"
    elif ramadan_day <= 20:
        return "gratitude shukr and barakah"
    elif ramadan_day <= 29:
        return "maximising the last ten nights"
    else:
        return "farewell to Ramadan and sustaining good deeds"


def _find_best_slot(full_schedule: list[dict], prayer_times: dict) -> tuple[str, str]:
    def hm(t: str) -> int:
        try:
            h, m = map(int, t.split(":")); return h * 60 + m
        except Exception:
            return 0

    def fmt(mins: int) -> str:
        return f"{(mins // 60) % 24:02d}:{mins % 60:02d}"

    occupied = [
        (hm(b["start"]), hm(b["end"]))
        for b in full_schedule
        if "start" in b and "end" in b
    ]

    def is_free(start_m: int, dur: int = 35) -> bool:
        end_m = start_m + dur
        return not any(s < end_m and e > start_m for s, e in occupied)

    asr_time   = prayer_times.get("Asr",    "16:28")
    dhuhr_time = prayer_times.get("Dhuhr",  "13:14")
    isha_time  = prayer_times.get("Isha",   "20:58")

    candidates = [
        hm(asr_time)   + 35,
        hm(dhuhr_time) + 60,
        hm(isha_time)  - 40,
        hm("20:30"),
    ]

    for start_m in candidates:
        if is_free(start_m):
            return fmt(start_m), fmt(start_m + 35)

    return "20:30", "21:05"


@observe(name="8.5-DeenPodcast")
async def deen_podcast_node(state: YawmState) -> dict:
    ramadan_day    = state.get("ramadan_day", 1)
    mood           = state.get("mood", "focused")
    full_schedule  = list(state.get("full_schedule", []))
    prayer_times   = {p["name"]: p["time"] for p in state.get("prayer_times", [])}
    schedule_image = state.get("schedule_card_path", "") or ""
    notify_channel = os.getenv("NOTIFY_CHANNEL", "gmail").lower()

    slot_start, slot_end = _find_best_slot(full_schedule, prayer_times)
    topic = _get_topic(ramadan_day, mood)

    client = get_mcp_client()
    tools  = await client.get_tools(server_name="deen_notify")

    llm = ChatOpenAI(
        model       = LLM_MODEL,
        api_key     = OPENAI_API_KEY,
        base_url    = OPENAI_BASE_URL,
        temperature = 0.3,
    )
    agent = create_react_agent(llm, tools)

    user_msg = (
        f"Ramadan Day: {ramadan_day}\n"
        f"Mood: {mood}\n"
        f"Topic: {topic}\n"
        f"Podcast slot: {slot_start} to {slot_end}\n"
        f"Schedule image path: {schedule_image}\n"
        f"Notify channel: {notify_channel}\n\n"
        "Please execute all steps now and return the JSON."
    )

    result = await agent.ainvoke({
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ]
    },
        config=get_langfuse_config(state.get("user_date", ""), "8.5-DeenPodcast"),
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
        parsed = {
            "podcast_block": {
                "title":      "🎧 Deen Podcast",
                "start":      slot_start,
                "end":        slot_end,
                "block_type": "podcast",
                "color":      "#F59E0B",
                "fixed":      False,
            },
            "video":         {},
            "notifications": {
                "gmail_sent":     False,
                "whatsapp_sent":  False,
                "errors":         ["json_parse_error"],
            },
        }

    podcast_block = parsed.get("podcast_block", {})
    notifications = parsed.get("notifications", {})

    full_schedule.append(podcast_block)
    full_schedule.sort(key=lambda b: b.get("start", "99:99"))

    errors = list(state.get("errors", []))
    for e in notifications.get("errors", []):
        errors.append(f"DeenPodcast: {e}")

    return {
        "full_schedule":       full_schedule,
        "podcast_block":       podcast_block,
        "podcast_video":       parsed.get("video", {}),
        "podcast_notify_done": True,
        "errors":              errors,
        "messages":            result["messages"],
    }