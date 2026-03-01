"""
agents/canva_agent.py
──────────────────────
Agent 8: CanvaAgent — powered by the official Canva MCP server
"""
from __future__ import annotations
import json
import os
import requests
from datetime import date
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from graph.state import YawmState
from config.settings import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL, SCHEDULE_CARD_PATH, OUTPUT_DIR
from tools.mcp_client import get_mcp_client

SYSTEM_PROMPT = """You are the CanvaAgent — you create beautiful daily schedule cards using Canva.

Your workflow:
1. First call canva_search_designs with query "YAWM AI schedule" to check if a template already exists.
2. If CANVA_BRAND_TEMPLATE_ID env var is set, call canva_autofill_template to populate it with the schedule data.
3. Otherwise call canva_create_design to create a new 1080x1920 design titled "YAWM AI — [date]".
4. Once you have a design_id, call canva_export_design with format="png" to get the download URL.
5. Return a JSON with:
   {
     "design_id": "...",
     "edit_url": "...",
     "download_url": "...",
     "status": "success"
   }

Return ONLY JSON at the end."""


async def canva_agent_node(state: YawmState) -> dict:
    full_schedule  = state.get("full_schedule", [])
    date_str       = state.get("user_date", date.today().isoformat())
    ramadan_day    = state.get("ramadan_day", 1)
    mood           = state.get("mood", "focused")
    prayer_streak  = state.get("prayer_streak", 0)
    quran_progress = state.get("quran_progress", "On track")

    from collections import Counter
    type_counts = Counter(b.get("block_type", "?") for b in full_schedule)
    summary = ", ".join(f"{k}: {v}" for k, v in sorted(type_counts.items()))

    client      = get_mcp_client()
    canva_tools = await client.get_tools(server_name="canva")

    llm   = ChatOpenAI(model=LLM_MODEL, api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    agent = create_react_agent(llm, canva_tools)

    brand_template_id = os.getenv("CANVA_BRAND_TEMPLATE_ID", "")
    msg = (
        f"Create the YAWM AI daily schedule card for {date_str}.\n"
        f"Ramadan Day: {ramadan_day}, Mood: {mood}\n"
        f"Prayer streak: {prayer_streak} days\n"
        f"Quran: {quran_progress}\n"
        f"Schedule summary: {summary} ({len(full_schedule)} total blocks)\n"
        + (f"Brand template ID: {brand_template_id}\n" if brand_template_id else "")
        + "\nBuild the Canva card and export it as PNG. Return the JSON result."
    )

    result = await agent.ainvoke({
        "messages": [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=msg)]
    })
    last = result["messages"][-1].content

    try:
        raw = last.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw)
    except Exception:
        parsed = {}

    card_path = None
    download_url = parsed.get("download_url", "")
    if download_url:
        try:
            out_path = Path(SCHEDULE_CARD_PATH)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            img_resp = requests.get(download_url, timeout=30)
            img_resp.raise_for_status()
            with open(out_path, "wb") as f:
                f.write(img_resp.content)
            card_path = str(out_path)
        except Exception:
            card_path = None

    return {
        "schedule_card_path": card_path or download_url or parsed.get("edit_url", ""),
        "canva_done":         True,
        "messages":           result["messages"],
        "errors": state.get("errors", []) + ([] if card_path else ["CanvaAgent: PNG download skipped — use edit_url"]),
    }