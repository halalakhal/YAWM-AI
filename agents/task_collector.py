"""
agents/task_collector.py
─────────────────────────
Agent 1: TaskCollector
"""
from __future__ import annotations
import json
from datetime import date
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from graph.state import YawmState
from config.settings import OPENAI_API_KEY, LLM_MODEL
from tools.mcp_client import get_mcp_client
from config.langfuse_setup import get_langfuse_config

try:
    from langfuse import observe
except ImportError:
    def observe(name=None):
        def decorator(fn): return fn
        return decorator


SYSTEM_PROMPT = """You are the TaskCollector agent. Your job:
1. Call notion_list_tasks with no status filter to get ALL pending tasks
2. Call todoist_list_tasks to get today's Todoist tasks
3. If a voice note is provided, parse it for additional tasks

Return ONLY this JSON:
{
  "calendar_events": [],
  "tasks": [
    {"id":"...","title":"...","priority":"high/medium/low",
     "estimated_minutes":60,"deadline":"HH:MM or null",
     "source":"notion","type":"Work"}
  ]
}

Do NOT call gcal_list_events. Google Calendar is write-only."""


def _to_list(val) -> list:
    if val is None:
        return []
    if isinstance(val, list):
        result = []
        for item in val:
            if isinstance(item, dict):
                result.append(item)
            elif isinstance(item, list):
                result.extend(i for i in item if isinstance(i, dict))
        return result
    if isinstance(val, dict):
        items = list(val.values())
        return [i for i in items if isinstance(i, dict)]
    return []


@observe(name="1-TaskCollector")
async def task_collector_node(state: YawmState) -> dict:
    """LangGraph node for Agent 1."""
    target_date = state.get("user_date") or date.today().isoformat()
    voice_note  = state.get("voice_note", "")

    client = get_mcp_client()
    tools  = await client.get_tools()

    llm   = ChatOpenAI(model=LLM_MODEL, api_key=OPENAI_API_KEY)
    agent = create_react_agent(llm, tools)

    user_msg = (
        f"Today is {target_date}.\n"
        f"Step 1: Call notion_list_tasks with no status filter.\n"
        f"Step 2: Call todoist_list_tasks for today.\n"
        + (f"Step 3: Add this voice note as a task: '{voice_note}'\n" if voice_note else "")
        + "\nReturn JSON with 'calendar_events': [] and 'tasks': [list of real tasks]."
    )

    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=user_msg)]},
        config=get_langfuse_config(target_date, "1-TaskCollector"),
    )
    last = result["messages"][-1].content
    print(f"\n[DEBUG] LLM final response: {last[:1000]}")

    try:
        raw = last.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw)
    except Exception as e:
        print(f"\n[DEBUG] JSON parse failed: {e}")
        print(f"[DEBUG] LLM raw response: {last[:500]}")
        parsed = {"calendar_events": [], "tasks": []}

    calendar_events = _to_list(parsed.get("calendar_events", []))
    tasks           = _to_list(parsed.get("tasks", []))
    normalized      = calendar_events + tasks

    return {
        "raw_calendar_events":  calendar_events,
        "raw_tasks":            tasks,
        "normalized_task_list": normalized,
        "task_collector_done":  True,
        "messages":             result["messages"],
    }