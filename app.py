"""
app.py
───────
YAWM AI — Web Interface
FastAPI + WebSockets.

Fix: _extract_params now guards against null mood from LLM
     when user types a question instead of a planning statement.
"""
from __future__ import annotations
import asyncio
import json
from datetime import date
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from langchain_openai        import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from graph.state             import YawmState
from graph.graph_builder     import build_graph
from config.settings         import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL

from agents.router              import classify_intent
from agents.direct_query_agents import (
    answer_quran_query,
    answer_dhikr_query,
    answer_salah_query,
    answer_sleep_query,
    answer_general_query,
)

app = FastAPI()

RAMADAN_START = date(2026, 2, 18)
RAMADAN_END   = date(2026, 3, 19)

AGENT_LABELS = {
    "task_collector":     ("1",   "TaskCollector",  "🔍"),
    "planner":            ("2",   "Planner",         "🧠"),
    "supervisor":         ("3",   "Supervisor",      "🎯"),
    "salah_guardian":     ("4",   "SalahGuardian",  "🕌"),
    "dhikr_agent":        ("5",   "DhikrAgent",     "📿"),
    "quran_wird":         ("6",   "QuranWird",       "📖"),
    "day_planner":        ("7",   "DayPlanner",      "⚡"),
    "canva_agent":        ("8",   "CanvaAgent",      "🎨"),
    "deen_podcast_agent": ("8.5", "DeenPodcast",     "🎧"),
    "calendar_agent":     ("9",   "CalendarAgent",   "📅"),
}

EXTRACT_PROMPT = """Extract planning parameters from the user message. Return ONLY JSON:
{
  "mood": "focused"|"tired"|"anxious"|"energized",
  "ramadan_day": <int or null>,
  "voice_note": "<extra context or null>",
  "timezone": "Africa/Casablanca"
}
Only set ramadan_day if explicitly mentioned, else null.
mood must ALWAYS be one of: focused, tired, anxious, energized — never null.
If mood is not mentioned, default to "focused".
Do not include questions about dhikr or Quran in voice_note."""


def _compute_ramadan_day() -> int:
    today = date.today()
    if RAMADAN_START <= today <= RAMADAN_END:
        return (today - RAMADAN_START).days + 1
    return 1


async def _extract_params(user_input: str) -> dict:
    llm = ChatOpenAI(
        model=LLM_MODEL, api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL, temperature=0,
    )
    resp = await llm.ainvoke([
        SystemMessage(content=EXTRACT_PROMPT),
        HumanMessage(content=user_input),
    ])
    try:
        raw = resp.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        params = json.loads(raw)
    except Exception:
        params = {
            "mood":        "focused",
            "ramadan_day": None,
            "voice_note":  user_input,
            "timezone":    "Africa/Casablanca",
        }

    # ── FIX: guard against null/invalid mood ─────────────────────────────────
    valid_moods = {"focused", "tired", "anxious", "energized"}
    if not params.get("mood") or params["mood"] not in valid_moods:
        params["mood"] = "focused"

    # ── FIX: guard against null timezone ─────────────────────────────────────
    if not params.get("timezone"):
        params["timezone"] = "Africa/Casablanca"

    # ── Auto-compute ramadan day if missing ───────────────────────────────────
    if not params.get("ramadan_day"):
        params["ramadan_day"] = _compute_ramadan_day()
        params["_day_auto"]   = True
    else:
        params["_day_auto"] = False

    return params


def _merge(final_state: dict, node_output: dict):
    """Same merge logic as graph_runner.py — unchanged."""
    for key, value in node_output.items():
        if key == "full_schedule":
            existing = final_state.get("full_schedule", [])
            if not existing:
                final_state[key] = value
            else:
                merged = {
                    (b.get("title", ""), b.get("start", "")): b
                    for b in existing
                }
                for b in (value or []):
                    merged[(b.get("title", ""), b.get("start", ""))] = b
                final_state[key] = sorted(
                    merged.values(),
                    key=lambda b: b.get("start", "99:99"),
                )
        elif key == "errors":
            existing = final_state.get("errors", [])
            final_state[key] = existing + [
                e for e in (value or []) if e not in existing
            ]
        elif key == "messages":
            existing = final_state.get("messages", [])
            final_state[key] = existing + (value or [])
        else:
            final_state[key] = value


async def _run_pipeline_ws(
    ws:          WebSocket,
    mood:        str,
    ramadan_day: int,
    voice_note:  str | None,
    timezone:    str,
):
    async def send(type: str, **kwargs):
        await ws.send_json({"type": type, **kwargs})

    await send("status", message="Pipeline starting...")

    initial_state: YawmState = {
        "user_date":     date.today().isoformat(),
        "user_timezone": timezone,
        "mood":          mood,
        "ramadan_day":   ramadan_day,
        "voice_note":    voice_note,
        "errors":        [],
        "messages":      [],
    }

    graph          = build_graph()
    agent_statuses = {k: "idle" for k in AGENT_LABELS}
    final_state    = {}
    agent_keys     = list(AGENT_LABELS.keys())

    await send("agents", statuses=agent_statuses)

    config = {"configurable": {"thread_id": "yawm-web"}}

    try:
        async for event in graph.astream(
            initial_state, config=config, stream_mode="updates"
        ):
            for node_name, node_output in event.items():
                if node_name in agent_statuses:
                    agent_statuses[node_name] = "done"
                    idx = agent_keys.index(node_name)
                    if idx + 1 < len(agent_keys):
                        next_key = agent_keys[idx + 1]
                        agent_statuses[next_key] = "running"

                    num, label, icon = AGENT_LABELS[node_name]
                    await send("agent_done",
                               node     = node_name,
                               label    = label,
                               icon     = icon,
                               num      = num,
                               statuses = dict(agent_statuses))
                    await send("log",
                               message  = f"{icon} Agent {num} · {label} done")

                if node_output is not None:
                    _merge(final_state, node_output)

    except Exception as e:
        await send("error", message=str(e))
        return

    from collections import Counter
    blocks      = final_state.get("full_schedule", [])
    type_counts = Counter(b.get("block_type", "?") for b in blocks)

    await send("summary",
        blocks_total   = len(blocks),
        block_types    = dict(type_counts),
        written_events = len(final_state.get("written_event_ids", [])),
        prayer_streak  = final_state.get("prayer_streak", 0),
        sleep_window   = final_state.get("sleep_window", {}),
        quran_progress = final_state.get("quran_progress_data", {}),
        podcast_video  = final_state.get("podcast_video", {}),
        podcast_block  = final_state.get("podcast_block", {}),
        schedule_card  = final_state.get("schedule_card_path", ""),
        errors         = final_state.get("errors", []),
    )
    await send("done", message="Pipeline complete!")


async def _handle_direct_query_ws(
    ws:          WebSocket,
    message:     str,
    ramadan_day: int,
    mood:        str,
):
    async def send(type: str, **kwargs):
        await ws.send_json({"type": type, **kwargs})

    intent_result = await classify_intent(message, ramadan_day)
    intent        = intent_result.get("intent", "general")
    confidence    = intent_result.get("confidence", 0.5)

    await send("intent", intent=intent, confidence=confidence)
    await send("status", message=f"Routing to {intent} agent...")

    if intent == "full_plan":
        await _run_pipeline_ws(
            ws          = ws,
            mood        = mood,
            ramadan_day = ramadan_day,
            voice_note  = message,
            timezone    = "Africa/Casablanca",
        )
        return

    elif intent == "quran":
        response = await answer_quran_query(message, ramadan_day, mood)
    elif intent == "dhikr":
        response = await answer_dhikr_query(message, ramadan_day, mood=mood)
    elif intent == "salah":
        response = await answer_salah_query(message, ramadan_day, mood=mood)
    elif intent == "sleep":
        response = await answer_sleep_query(message, ramadan_day, mood)
    else:
        response = await answer_general_query(message, ramadan_day, mood)

    await send("query_response", intent=intent, response=response)
    await send("done", message="Done!")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
async def index():
    return HTMLResponse(Path("ui/index.html").read_text(encoding="utf-8"))


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_json()

            if data.get("action") == "extract":
                params = await _extract_params(data["message"])
                await ws.send_json({"type": "params", "params": params})

            elif data.get("action") == "run":
                await _run_pipeline_ws(
                    ws          = ws,
                    mood        = data.get("mood", "focused"),
                    ramadan_day = int(data.get("ramadan_day", 1)),
                    voice_note  = data.get("voice_note"),
                    timezone    = data.get("timezone", "Africa/Casablanca"),
                )

            elif data.get("action") == "query":
                await _handle_direct_query_ws(
                    ws          = ws,
                    message     = data.get("message", ""),
                    ramadan_day = int(data.get("ramadan_day", _compute_ramadan_day())),
                    mood        = data.get("mood", "focused"),
                )

    except WebSocketDisconnect:
        pass