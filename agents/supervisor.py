"""
agents/supervisor.py
─────────────────────
Agent 3: Supervisor
Pure logic node — no LLM needed.
"""
from __future__ import annotations
from graph.state import YawmState
from config.langfuse_setup import get_langfuse_config

try:
    from langfuse import observe
except ImportError:
    def observe(name=None):
        def decorator(fn): return fn
        return decorator


@observe(name="3-Supervisor")
async def supervisor_node(state: YawmState) -> dict:
    cfg = state.get("routing_config") or {}

    order = []
    if cfg.get("enable_salah", True):
        order.append("salah_guardian")
    if cfg.get("enable_dhikr", True):
        order.append("dhikr_agent")
    if cfg.get("enable_quran", True):
        order.append("quran_wird")
    order.append("day_planner")
    order.append("canva_agent")
    order.append("calendar_agent")

    return {
        "agent_execution_order": order,
        "supervisor_done": True,
    }


def should_run_salah(state: YawmState) -> str:
    cfg = state.get("routing_config") or {}
    return "salah_guardian" if cfg.get("enable_salah", True) else "skip_salah"

def should_run_dhikr(state: YawmState) -> str:
    cfg = state.get("routing_config") or {}
    return "dhikr_agent" if cfg.get("enable_dhikr", True) else "skip_dhikr"

def should_run_quran(state: YawmState) -> str:
    cfg = state.get("routing_config") or {}
    return "quran_wird" if cfg.get("enable_quran", True) else "skip_quran"