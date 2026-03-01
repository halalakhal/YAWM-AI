"""
graph/graph_runner.py  (UPGRADED + LANGFUSE)
─────────────────────────────────────────────
Exact same file as original — only 3 Langfuse lines added:
  1. import os                                    (line added to imports)
  2. from config.langfuse_setup import get_langfuse_config  (line added to imports)
  3. Langfuse status print after the Panel        (cosmetic, safe)
  4. Langfuse link at end of _print_summary       (cosmetic, safe)

Everything else: _merge_state, run_pipeline, _render_table,
_print_summary — 100% identical to original.
"""
from __future__ import annotations
import asyncio
import os                                                    # ← ADDED (for env check)
from datetime import date
from rich.console import Console
from rich.panel   import Panel
from rich.live    import Live
from rich.table   import Table
from rich         import box

from graph.state                import YawmState
from graph.graph_builder        import build_graph
from config.langfuse_setup      import get_langfuse_config  # ← ADDED

console = Console()

AGENT_LABELS = {
    "task_collector":     ("1",   "TaskCollector",     "🔍"),
    "planner":            ("2",   "Planner",            "🧠"),
    "supervisor":         ("3",   "Supervisor",         "🎯"),
    "salah_guardian":     ("4",   "SalahGuardian",     "🕌"),
    "dhikr_agent":        ("5",   "DhikrAgent",        "📿"),
    "quran_wird":         ("6",   "QuranWird",          "📖"),
    "day_planner":        ("7",   "DayPlanner",         "⚡"),
    "canva_agent":        ("8",   "CanvaAgent",         "🎨"),
    "deen_podcast_agent": ("8.5", "DeenPodcast",        "🎧"),
    "calendar_agent":     ("9",   "CalendarAgent",      "📅"),
}

AGENT_COLORS = {
    "task_collector":     "cyan",
    "planner":            "magenta",
    "supervisor":         "yellow",
    "salah_guardian":     "green",
    "dhikr_agent":        "blue",
    "quran_wird":         "pink1",
    "day_planner":        "orange1",
    "canva_agent":        "purple",
    "deen_podcast_agent": "gold1",
    "calendar_agent":     "bright_green",
}


def _merge_state(final_state: dict, node_output: dict) -> None:
    """
    Merge node_output into final_state intelligently.
    - full_schedule: merge by (title, start) key — never overwrite with smaller list
    - errors: append, never overwrite
    - messages: append, never overwrite
    - everything else: normal overwrite
    """
    for key, value in node_output.items():

        if key == "full_schedule":
            existing = final_state.get("full_schedule", [])
            if not existing:
                final_state[key] = value
            else:
                # Merge by (title, start) — later values win for same block
                merged = {(b.get("title",""), b.get("start","")): b for b in existing}
                for b in (value or []):
                    merged[(b.get("title",""), b.get("start",""))] = b
                final_state[key] = sorted(
                    merged.values(),
                    key=lambda b: b.get("start", "99:99")
                )

        elif key == "errors":
            existing = final_state.get("errors", [])
            final_state[key] = existing + [e for e in (value or []) if e not in existing]

        elif key == "messages":
            existing = final_state.get("messages", [])
            final_state[key] = existing + (value or [])

        else:
            final_state[key] = value


async def run_pipeline(
    user_date:   str | None = None,
    mood:        str = "focused",
    ramadan_day: int = 21,
    voice_note:  str | None = None,
    timezone:    str = "Africa/Casablanca",
) -> YawmState:
    console.print(Panel.fit(
        "[bold magenta]◈ YAWM AI[/bold magenta]  "
        "[dim]10-Agent Daily Planner · Ramadan Edition[/dim]",
        border_style="magenta",
    ))

    # ── ADDED: show Langfuse status (safe — just a print, nothing else) ───────
    if os.getenv("LANGFUSE_PUBLIC_KEY"):
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        target_date = user_date or date.today().isoformat()
        console.print(
            f"[dim]🔍 Langfuse ON · session: yawm-{target_date} · "
            f"{host}[/dim]\n"
        )
    # ── END ADDED ─────────────────────────────────────────────────────────────

    initial_state: YawmState = {
        "user_date":     user_date or date.today().isoformat(),
        "user_timezone": timezone,
        "mood":          mood,
        "ramadan_day":   ramadan_day,
        "voice_note":    voice_note,
        "errors":        [],
        "messages":      [],
    }

    graph          = build_graph()
    agent_statuses = {k: "idle" for k in AGENT_LABELS}
    final_state: dict = {}

    def _render_table():
        t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        t.add_column("",      width=4)
        t.add_column("Agent", width=18)
        t.add_column("Status", width=12)
        for key, (num, label, icon) in AGENT_LABELS.items():
            status = agent_statuses[key]
            color  = AGENT_COLORS[key]
            if status == "running":
                badge = f"[{color}]◈ running[/{color}]"
            elif status == "done":
                badge = f"[{color}]✓ done[/{color}]"
            else:
                badge = "[dim]· idle[/dim]"
            t.add_row(f"[dim]{num}[/dim]", f"{icon} {label}", badge)
        return t

    agent_keys = list(AGENT_LABELS.keys())

    with Live(_render_table(), console=console, refresh_per_second=4) as live:
        config = {"configurable": {"thread_id": "yawm-main"}}
        async for event in graph.astream(initial_state, config=config, stream_mode="updates"):
            for node_name, node_output in event.items():
                if node_name in agent_statuses:
                    agent_statuses[node_name] = "done"
                    idx = agent_keys.index(node_name)
                    if idx + 1 < len(agent_keys):
                        agent_statuses[agent_keys[idx + 1]] = "running"
                    live.update(_render_table())
                if node_output is not None:
                    _merge_state(final_state, node_output)

    _print_summary(final_state)
    return final_state


def _print_summary(state: YawmState):
    console.print()
    console.rule("[bold magenta]✨ Pipeline Complete[/bold magenta]")

    # ── Schedule overview ─────────────────────────────────────────────────────
    blocks = state.get("full_schedule", [])
    console.print(f"\n[bold]📅 Schedule:[/bold] {len(blocks)} blocks built")
    from collections import Counter
    type_counts = Counter(b.get("block_type", "?") for b in blocks)
    for btype, count in sorted(type_counts.items()):
        console.print(f"   [dim]→[/dim] {btype:<14} {count} block(s)")

    # ── Sleep window ──────────────────────────────────────────────────────────
    sw = state.get("sleep_window", {})
    if sw:
        console.print(
            f"\n[bold blue]😴 Sleep:[/bold blue] "
            f"Bedtime {sw.get('bedtime','?')} → "
            f"{sw.get('cycles','?')} cycles ({sw.get('total_sleep_min','?')} min)"
        )
        if sw.get("warning"):
            console.print(f"   [yellow]{sw['warning']}[/yellow]")

    # ── Canva card ────────────────────────────────────────────────────────────
    card_path = state.get("schedule_card_path")
    if card_path:
        console.print(f"\n[bold green]🖼  Schedule card:[/bold green] {card_path}")

    # ── Deen Podcast notification ─────────────────────────────────────────────
    video = state.get("podcast_video", {})
    if video:
        console.print(f"\n[bold yellow]🎧 Deen Podcast:[/bold yellow] {video.get('title','')}")
        console.print(f"   [dim]Channel:[/dim] {video.get('channel','')}")
        console.print(f"   [dim]URL:[/dim]     {video.get('url','')}")
        block = state.get("podcast_block", {})
        if block:
            console.print(f"   [dim]Scheduled:[/dim] {block.get('start','')}–{block.get('end','')}")
    if state.get("podcast_notify_done"):
        console.print("   [green]✓ Notification sent (Gmail / WhatsApp)[/green]")

    # ── Google Calendar ───────────────────────────────────────────────────────
    written = state.get("written_event_ids", [])
    if written:
        console.print(f"\n[bold green]📤 Google Calendar:[/bold green] {len(written)} events written")

    # ── Prayer streak ─────────────────────────────────────────────────────────
    streak = state.get("prayer_streak", 0)
    if streak:
        console.print(f"\n[bold yellow]🔥 Prayer streak:[/bold yellow] {streak} days — keep it up!")

    # ── Quran progress (real data) ────────────────────────────────────────────
    qp = state.get("quran_progress_data", {})
    if qp:
        console.print(f"\n[bold cyan]📖 Quran Khatm:[/bold cyan] {qp.get('progress_label','')}")
        console.print(
            f"   [dim]Total read:[/dim] {qp.get('total_pages_read',0)}/604 pages "
            f"({qp.get('khatm_percent',0)}%) · "
            f"Juz {qp.get('juz_completed',0)}/30"
        )
    elif state.get("quran_progress"):
        console.print(f"\n[bold cyan]📖 Quran:[/bold cyan] {state['quran_progress']}")

    # ── Errors ────────────────────────────────────────────────────────────────
    errors = state.get("errors", [])
    if errors:
        console.print(f"\n[bold red]⚠ Errors ({len(errors)}):[/bold red]")
        for e in errors:
            console.print(f"  [red]• {e}[/red]")

    # ── ADDED: Langfuse link (safe — only shows if key is set) ────────────────
    if os.getenv("LANGFUSE_PUBLIC_KEY"):
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        date_str = state.get("user_date", date.today().isoformat())
        console.print(
            f"\n[dim]🔍 Langfuse trace → {host}/sessions/yawm-{date_str}[/dim]"
        )
    # ── END ADDED ─────────────────────────────────────────────────────────────

    console.print()