"""
agents/calendar_agent.py
─────────────────────────
Agent 9: CalendarAgent
"""
from __future__ import annotations
import asyncio
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from graph.state import YawmState
from config.settings import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL
from tools.mcp_client import get_mcp_client
from config.langfuse_setup import get_langfuse_config

try:
    from langfuse import observe
except ImportError:
    def observe(name=None):
        def decorator(fn): return fn
        return decorator


BLOCK_TYPE_TO_COLOR = {
    "prayer":    "green",
    "deep_work": "blue",
    "rest":      "red",
    "sleep":     "lavender",
    "meal":      "orange",
    "dhikr":     "purple",
    "quran":     "purple",
    "meeting":   "teal",
    "flexible":  "yellow",
}

CLEANUP_PROMPT = """You are a Google Calendar cleanup agent.
Your ONLY job: delete all of today's YAWM AI generated events.

Steps:
1. Call gcal_list_events for today's date
2. For every event whose description contains "Created by YAWM AI", call gcal_delete_event
3. Once all are deleted, stop.

Do not create or modify any events."""

WRITE_PROMPT = """You are the CalendarAgent. Your job:
For each schedule block provided, call gcal_create_event to write it to Google Calendar.

Use the correct color for each block_type:
- prayer    → green
- deep_work → blue
- rest      → red
- sleep     → lavender
- meal      → orange
- dhikr     → purple
- quran     → purple
- meeting   → teal
- flexible  → yellow

IMPORTANT: Write events ONE AT A TIME, sequentially.

After writing all events return:
{"written": [event_id1, event_id2, ...], "total": N}

Return ONLY JSON at the end."""

BATCH_SIZE  = 5
BATCH_DELAY = 2.0


async def _invoke_with_retry(agent, payload: dict, max_retries: int = 5) -> dict:
    for attempt in range(max_retries):
        try:
            return await agent.ainvoke(payload)
        except Exception as e:
            err = str(e)
            if "rateLimitExceeded" in err or "Rate Limit" in err or "429" in err:
                wait = 2 ** attempt
                print(f"\n  [CalendarAgent] Rate limit — retrying in {wait}s...")
                await asyncio.sleep(wait)
            else:
                raise
    raise RuntimeError("[CalendarAgent] Rate limit exceeded after retries.")


@observe(name="9-CalendarAgent")
async def calendar_agent_node(state: YawmState) -> dict:
    full_schedule = state.get("full_schedule", [])
    target_date   = state.get("user_date", "")
    user_tz       = state.get("user_timezone", "Africa/Casablanca")

    client = get_mcp_client()
    tools  = await client.get_tools(server_name="google_calendar")
    llm    = ChatOpenAI(model=LLM_MODEL, api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

    cleanup_agent = create_react_agent(llm, tools)
    await _invoke_with_retry(cleanup_agent, {"messages": [
        SystemMessage(content=CLEANUP_PROMPT),
        HumanMessage(content=f"Delete all YAWM AI events for {target_date}.")
    ]})

    blocks_to_write = [
        b for b in full_schedule
        if b.get("block_type") != "sleep"
    ]

    if not blocks_to_write:
        return {"written_event_ids": [], "calendar_write_done": True}

    write_agent  = create_react_agent(llm, tools)
    all_written  = []
    all_messages = []

    batches = [
        blocks_to_write[i: i + BATCH_SIZE]
        for i in range(0, len(blocks_to_write), BATCH_SIZE)
    ]

    for batch_num, batch in enumerate(batches):
        block_lines = "\n".join(
            f"- [{b.get('block_type','flexible')}] {b['title']} "
            f"{b['start']}–{b['end']} "
            f"→ color={BLOCK_TYPE_TO_COLOR.get(b.get('block_type','flexible'),'blue')} "
            f"description='Created by YAWM AI'"
            for b in batch
        )

        msg = (
            f"Date: {target_date}, Timezone: {user_tz}\n\n"
            f"Write these {len(batch)} events (batch {batch_num + 1}/{len(batches)}):\n"
            f"{block_lines}\n\n"
            "Write ONE AT A TIME. Set description to 'Created by YAWM AI' for each. "
            "Then return the JSON summary."
        )

        result = await _invoke_with_retry(write_agent, {
            "messages": [SystemMessage(content=WRITE_PROMPT), HumanMessage(content=msg)]
        })

        last = result["messages"][-1].content
        all_messages.extend(result["messages"])

        try:
            raw = last.strip()
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            parsed = json.loads(raw)
            all_written.extend(parsed.get("written", []))
        except Exception:
            pass

        if batch_num < len(batches) - 1:
            await asyncio.sleep(BATCH_DELAY)

    return {
        "written_event_ids":   all_written,
        "calendar_write_done": True,
        "messages":            all_messages,
    }