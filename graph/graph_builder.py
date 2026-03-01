"""
graph/graph_builder.py  (UPGRADED)
────────────────────────────────────
Changes from previous version:
  1. Added conflict_checker node (Agent 7.5)
  2. Added conditional edge: conflict_checker → supervisor OR canva_agent
  3. This conditional edge IS the Graph Agent Pattern in your system

Graph topology:
                     START
                       │
              ┌────────▼────────┐
              │  task_collector │  Agent 1
              └────────┬────────┘
                       │
              ┌────────▼────────┐
              │    planner      │  Agent 2
              └────────┬────────┘
                       │
              ┌────────▼────────┐
              │   supervisor    │  Agent 3  ← upgraded: real conditions
              └─┬──────┬────┬──┘            ← also: retry target
                │      │    │
                ▼      ▼    ▼
          [salah]  [dhikr] [quran]    ← parallel fan-out (always runs)
                ╲    │    ╱
                 ╲   │   ╱
              ┌───▼───▼──▼──────┐
              │   day_planner   │  Agent 7  (receives scheduling_mode,
              └────────┬────────┘           quran_mode, deep_work_max)
                       │
              ┌────────▼────────────┐
              │  conflict_checker   │  Agent 7.5  ← NEW
              └────────┬────────────┘
                       │
              ┌────────┴────────────┐
              │                     │
         violations?            clean?
              │                     │
              ▼                     ▼
         supervisor            canva_agent   ← Graph Pattern conditional edge
         (retry, max 2)
                       │
              ┌────────▼────────┐
              │   canva_agent   │  Agent 8
              └────────┬────────┘
                       │
              ┌────────▼────────────┐
              │  deen_podcast_agent │  Agent 8.5
              └────────┬────────────┘
                       │
              ┌────────▼────────┐
              │ calendar_agent  │  Agent 9
              └────────┬────────┘
                      END
"""
from __future__ import annotations
from langgraph.graph              import StateGraph, START, END
from langgraph.checkpoint.memory  import MemorySaver

from graph.state                  import YawmState
from agents.task_collector        import task_collector_node
from agents.planner               import planner_node
from agents.supervisor            import supervisor_node
from agents.salah_guardian        import salah_guardian_node
from agents.dhikr_agent           import dhikr_agent_node
from agents.quran_wird            import quran_wird_node
from agents.day_planner           import day_planner_node
from agents.conflict_checker      import conflict_checker_node, route_after_validation  # NEW
from agents.canva_agent           import canva_agent_node
from agents.deen_podcast_agent    import deen_podcast_node
from agents.calendar_agent        import calendar_agent_node


def build_graph(checkpointer=None) -> StateGraph:
    """Build and compile the upgraded 10-agent LangGraph."""
    g = StateGraph(YawmState)

    # ── Register all nodes ────────────────────────────────────────────────────
    g.add_node("task_collector",     task_collector_node)
    g.add_node("planner",            planner_node)
    g.add_node("supervisor",         supervisor_node)
    g.add_node("salah_guardian",     salah_guardian_node)
    g.add_node("dhikr_agent",        dhikr_agent_node)
    g.add_node("quran_wird",         quran_wird_node)
    g.add_node("day_planner",        day_planner_node)
    g.add_node("conflict_checker",   conflict_checker_node)   # NEW
    g.add_node("canva_agent",        canva_agent_node)
    g.add_node("deen_podcast_agent", deen_podcast_node)
    g.add_node("calendar_agent",     calendar_agent_node)

    # ── Sequential spine ──────────────────────────────────────────────────────
    g.add_edge(START,            "task_collector")
    g.add_edge("task_collector", "planner")
    g.add_edge("planner",        "supervisor")

    # ── Fan-out: 3 Islamic agents always run in parallel ──────────────────────
    g.add_edge("supervisor", "salah_guardian")
    g.add_edge("supervisor", "dhikr_agent")
    g.add_edge("supervisor", "quran_wird")

    # ── Fan-in: DayPlanner waits for all three ────────────────────────────────
    g.add_edge("salah_guardian", "day_planner")
    g.add_edge("dhikr_agent",    "day_planner")
    g.add_edge("quran_wird",     "day_planner")

    # ── DayPlanner → ConflictChecker ──────────────────────────────────────────
    g.add_edge("day_planner", "conflict_checker")

    # ── THE KEY CHANGE: Conditional edge = Graph Agent Pattern ────────────────
    # This is the ONLY true conditional routing in the system.
    # route_after_validation returns either "supervisor" or "canva_agent"
    g.add_conditional_edges(
        "conflict_checker",
        route_after_validation,
        {
            "supervisor":  "supervisor",    # ← feedback loop (violations found)
            "canva_agent": "canva_agent",   # ← proceed (schedule is clean)
        }
    )

    # ── Linear finish ─────────────────────────────────────────────────────────
    g.add_edge("canva_agent",        "deen_podcast_agent")
    g.add_edge("deen_podcast_agent", "calendar_agent")
    g.add_edge("calendar_agent",     END)

    return g.compile(checkpointer=checkpointer or MemorySaver())