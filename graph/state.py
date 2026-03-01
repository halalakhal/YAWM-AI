"""
graph/state.py  (UPGRADED)
───────────────────────────
New fields added:
  Supervisor conditions:
    - scheduling_mode     : strict / normal / relaxed / qadr
    - quran_mode          : normal / catchup / final_push / critical
    - is_qadr             : Laylat Al-Qadr night flag
    - deep_work_max_min   : max deep work block length in minutes
    - pressure_score      : task_load / free_minutes ratio
    - free_minutes        : minutes available after obligations
    - obligation_mins     : total fixed obligation minutes

  ConflictChecker:
    - validation_passed   : bool
    - violations          : list of violation strings
    - warnings            : list of non-blocking warnings
    - retry_count         : how many times DayPlanner has been retried
    - previous_violations : violations from last retry (injected into prompt)
    - force_strict_mode   : forces DayPlanner into strict mode on retry
    - deferred_tasks      : tasks that couldn't fit today
"""
from __future__ import annotations
from typing import Optional, Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class YawmState(TypedDict, total=False):
    # ── User inputs ────────────────────────────────────────────────────────────
    user_date:      str           # "YYYY-MM-DD"
    user_timezone:  str
    mood:           str           # "focused"|"tired"|"anxious"|"energized"
    voice_note:     Optional[str]
    ramadan_day:    int

    # ── Agent 1: TaskCollector ────────────────────────────────────────────────
    raw_calendar_events:  list[dict]
    raw_tasks:            list[dict]
    normalized_task_list: list[dict]
    task_collector_done:  bool

    # ── Agent 2: Planner ──────────────────────────────────────────────────────
    routing_config: dict
    planner_done:   bool

    # ── Agent 3: Supervisor (UPGRADED) ────────────────────────────────────────
    agent_execution_order: list[str]
    supervisor_done:       bool

    # Real scheduling conditions (new)
    scheduling_mode:     str    # "strict" | "normal" | "relaxed" | "qadr"
    quran_mode:          str    # "normal" | "catchup" | "final_push" | "critical"
    is_qadr:             bool   # Laylat Al-Qadr night
    deep_work_max_min:   int    # max minutes for a single deep work block
    pressure_score:      float  # task_load / free_minutes (>1.0 = overloaded)
    free_minutes:        int    # available minutes after obligations
    obligation_mins:     int    # total minutes locked by prayers/sleep/etc

    # ── Agent 4: SalahGuardian ────────────────────────────────────────────────
    prayer_times:  list[dict]
    prayer_blocks: list[dict]
    prayer_streak: int
    salah_done:    bool

    # ── Agent 5: DhikrAgent ───────────────────────────────────────────────────
    dhikr_blocks: list[dict]
    dhikr_done:   bool

    # ── Agent 6: QuranWird ────────────────────────────────────────────────────
    quran_blocks:        list[dict]
    quran_progress:      str
    quran_progress_data: dict
    quran_done:          bool

    # ── Agent 7: DayPlanner ───────────────────────────────────────────────────
    full_schedule:    list[dict]
    deferred_tasks:   list[dict]  # tasks that couldn't fit today (NEW)
    sleep_window:     dict
    day_planner_done: bool

    # ── Agent 7.5: ConflictChecker (NEW) ─────────────────────────────────────
    validation_passed:     bool
    violations:            list[str]   # blocking — triggers retry
    warnings:              list[str]   # non-blocking — shown to user
    retry_count:           int         # incremented each retry (max 2)
    previous_violations:   list[str]   # injected into DayPlanner on retry
    force_strict_mode:     bool        # forces strict scheduling on retry

    # ── Agent 8: CanvaAgent ───────────────────────────────────────────────────
    schedule_card_path: Optional[str]
    canva_done:         bool

    # ── Agent 8.5: DeenPodcastAgent ───────────────────────────────────────────
    podcast_block:        dict
    podcast_video:        dict
    podcast_notify_done:  bool

    # ── Agent 9: CalendarAgent ────────────────────────────────────────────────
    written_event_ids:   list[str]
    calendar_write_done: bool

    # ── Error log ─────────────────────────────────────────────────────────────
    errors: list[str]

    # ── LangGraph message bus ─────────────────────────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages]