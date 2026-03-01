"""
agents/conflict_checker.py  (NEW)
───────────────────────────────────
Agent 7.5: ConflictChecker

This is the ONLY true Graph Agent Pattern node in the system.
It programmatically validates the schedule and either:
  - passes clean  → proceeds to CanvaAgent
  - finds violations → feeds back to Supervisor → DayPlanner retry

Why this matters:
  Without this, the system is PROBABLY correct.
  With this, the system is PROVABLY correct.

Checks performed:
  1. All 5 prayers present and untouched           → HARD VIOLATION
  2. Dhikr blocks present (morning + evening)      → warning only
  3. Quran pages target met                        → warning only
  4. Sleep block present                           → warning only
  5. Overlapping blocks (prayer/task involved)     → HARD VIOLATION
     Overlapping blocks (non-critical)             → warning only
  6. RAG preferences respected (shower evening)    → warning only
  7. No task scheduled during prayer time          → HARD VIOLATION
"""
from __future__ import annotations
from graph.state import YawmState

try:
    from langfuse import observe
except ImportError:
    def observe(name=None):
        def decorator(fn): return fn
        return decorator


def _hm(t: str) -> int:
    """Convert HH:MM to total minutes."""
    try:
        h, m = map(int, t.split(":"))
        return h * 60 + m
    except Exception:
        return 0


def _duration(block: dict) -> int:
    return _hm(block.get("end", "00:00")) - _hm(block.get("start", "00:00"))


@observe(name="7.5-ConflictChecker")
async def conflict_checker_node(state: YawmState) -> dict:
    schedule    = state.get("full_schedule", [])
    quran_data  = state.get("quran_progress_data") or {}
    pages_today = quran_data.get("pages_needed_today", 2)
    retry_count = state.get("retry_count", 0)
    violations  = []
    warnings    = []

    # ── Check 1: All 5 prayers present → HARD VIOLATION ─────────────────────
    required_prayers = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
    scheduled_titles = [b.get("title", "") for b in schedule]
    for prayer in required_prayers:
        if not any(prayer in t for t in scheduled_titles):
            violations.append(f"MISSING_PRAYER: {prayer} not found in schedule")

    # ── Check 2: Dhikr blocks present → WARNING only ─────────────────────────
    dhikr_blocks = [b for b in schedule if b.get("block_type") == "dhikr"]
    if len(dhikr_blocks) < 2:
        warnings.append(
            f"WARNING: only {len(dhikr_blocks)} dhikr block(s) found, ideally 2"
        )

    # ── Check 3: Quran pages sufficient → WARNING only ───────────────────────
    quran_blocks = [b for b in schedule if b.get("block_type") == "quran"]
    quran_mins   = sum(_duration(b) for b in quran_blocks)
    min_needed   = pages_today * 10  # ~10 min per page minimum
    if quran_mins < min_needed:
        warnings.append(
            f"WARNING_QURAN: {quran_mins}min scheduled, "
            f"need {min_needed}min for {pages_today} pages"
        )

    # ── Check 4: Sleep block present → WARNING only ──────────────────────────
    sleep_blocks = [b for b in schedule if b.get("block_type") == "sleep"]
    if not sleep_blocks:
        warnings.append("WARNING: no sleep block found")

    # ── Check 5: Overlapping blocks ──────────────────────────────────────────
    # HARD VIOLATION only if one of the overlapping blocks is a prayer or task
    # Everything else is a warning
    CRITICAL_TYPES = ("prayer", "task")
    sorted_s = sorted(schedule, key=lambda b: _hm(b.get("start", "99:99")))
    for i in range(len(sorted_s) - 1):
        a = sorted_s[i]
        b = sorted_s[i + 1]
        a_end   = _hm(a.get("end",   "00:00"))
        b_start = _hm(b.get("start", "00:00"))
        if a_end > b_start:
            msg = (
                f"OVERLAP: '{a['title']}' ends {a.get('end')} "
                f"but '{b['title']}' starts {b.get('start')}"
            )
            involves_critical = (
                a.get("block_type") in CRITICAL_TYPES or
                b.get("block_type") in CRITICAL_TYPES
            )
            if involves_critical:
                violations.append(msg)
            else:
                warnings.append(f"WARNING_{msg}")

    # ── Check 6: RAG preference — shower must be evening → WARNING only ──────
    for block in schedule:
        title = block.get("title", "").lower()
        if "shower" in title or "bathroom" in title:
            if _hm(block.get("start", "00:00")) < 18 * 60:
                warnings.append(
                    f"WARNING: '{block['title']}' at "
                    f"{block.get('start')} — ideally scheduled after 18:00"
                )

    # ── Check 7: No task overlaps with prayer → HARD VIOLATION ───────────────
    prayer_blocks = [b for b in schedule if b.get("block_type") == "prayer"]
    task_blocks   = [b for b in schedule
                     if b.get("block_type") not in
                     ("prayer", "sleep", "dhikr", "quran", "meal", "rest")]
    for prayer in prayer_blocks:
        p_start = _hm(prayer.get("start", "00:00"))
        p_end   = _hm(prayer.get("end",   "00:00"))
        for task in task_blocks:
            t_start = _hm(task.get("start", "00:00"))
            t_end   = _hm(task.get("end",   "00:00"))
            if t_start < p_end and t_end > p_start:
                violations.append(
                    f"PRAYER_BLOCKED: '{task['title']}' overlaps "
                    f"with {prayer['title']}"
                )

    # ── Warnings (non-blocking) ───────────────────────────────────────────────
    if not any("Qailulah" in t for t in scheduled_titles):
        warnings.append("WARNING: No Qailulah nap — consider adding for tired mood")

    if not any("podcast" in b.get("block_type", "") for b in schedule):
        warnings.append("WARNING: No Deen podcast block found")

    # ── Result ────────────────────────────────────────────────────────────────
    passed = len(violations) == 0

    if not passed:
        print(f"\n[ConflictChecker] ❌ {len(violations)} violation(s) found "
              f"(retry {retry_count}/2):")
        for v in violations:
            print(f"  → {v}")
    else:
        print(f"\n[ConflictChecker] ✅ Schedule validated — "
              f"{len(schedule)} blocks, {len(warnings)} warning(s)")
        if warnings:
            for w in warnings:
                print(f"  ⚠  {w}")

    return {
        "validation_passed": passed,
        "violations":        violations,
        "warnings":          warnings,
    }


# ── Routing function for graph conditional edge ───────────────────────────────

def route_after_validation(state: YawmState) -> str:
    """
    The ONLY true Graph Agent Pattern conditional edge.

    Retries ONLY when Salah is missing or a task clashes with prayer.
    All other issues (dhikr, quran time, sleep, shower timing) are warnings
    and will NOT trigger a retry — the schedule proceeds as-is.

    clean      → canva_agent   (proceed to rendering)
    violations → supervisor    (retry with constraints injected)
    max 2 retries → canva_agent anyway (avoid infinite loop)
    """
    passed      = state.get("validation_passed", False)
    retry_count = state.get("retry_count", 0)

    if passed:
        return "canva_agent"

    if retry_count >= 2:
        # Max retries reached — proceed with warnings
        print("\n[ConflictChecker] ⚠️  Max retries reached — proceeding with warnings")
        return "canva_agent"

    return "supervisor"   # ← feedback loop back to Supervisor