"""
add_langfuse_to_agents.py
──────────────────────────
Run this ONCE from your project root.
It automatically adds Langfuse tracing to all 9 agents.

Usage:
    python add_langfuse_to_agents.py

What it does for each agent file:
  1. Adds the import line after existing imports
  2. Finds the agent.ainvoke() or llm.ainvoke() call
  3. Adds config=get_langfuse_config(...) to it

Safe to run multiple times — checks if already patched.
"""
import os
import re

# Maps filename → agent name shown in Langfuse dashboard
AGENTS = {
    "agents/task_collector.py":     "1-TaskCollector",
    "agents/planner.py":            "2-Planner",
    "agents/supervisor.py":         "3-Supervisor",
    "agents/salah_guardian.py":     "4-SalahGuardian",
    "agents/dhikr_agent.py":        "5-DhikrAgent",
    "agents/quran_wird.py":         "6-QuranWird",
    "agents/day_planner.py":        "7-DayPlanner",
    "agents/canva_agent.py":        "8-CanvaAgent",
    "agents/deen_podcast_agent.py": "8.5-DeenPodcast",
    "agents/calendar_agent.py":     "9-CalendarAgent",
}

IMPORT_LINE = "from config.langfuse_setup import get_langfuse_config\n"

def patch_agent(filepath: str, agent_name: str):
    if not os.path.exists(filepath):
        print(f"  ⚠️  Not found: {filepath} — skipping")
        return

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Already patched?
    if "get_langfuse_config" in content:
        print(f"  ✓  Already patched: {filepath}")
        return

    # 1. Add import after the last "from ... import" line
    lines = content.split("\n")
    last_import_idx = 0
    for i, line in enumerate(lines):
        if line.startswith("from ") or line.startswith("import "):
            last_import_idx = i
    lines.insert(last_import_idx + 1, IMPORT_LINE.strip())
    content = "\n".join(lines)

    # 2. Patch agent.ainvoke calls
    # Pattern: await agent.ainvoke({...}) → add config=
    content = re.sub(
        r'(await agent\.ainvoke\(\s*\{[^}]+\}\s*)\)',
        lambda m: m.group(0).rstrip(")")
            + f',\n        config=get_langfuse_config(state.get("user_date",""), "{agent_name}"),\n    )',
        content,
        count=1,
    )

    # 3. Patch llm.ainvoke calls (for agents that don't use create_react_agent)
    content = re.sub(
        r'(await llm\.ainvoke\(\s*\[[^\]]+\]\s*)\)',
        lambda m: m.group(0).rstrip(")")
            + f',\n        config=get_langfuse_config(state.get("user_date",""), "{agent_name}"),\n    )',
        content,
        count=1,
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"  ✅  Patched: {filepath}")


def main():
    print("\n🔍 Adding Langfuse tracing to all YAWM AI agents...\n")
    for filepath, agent_name in AGENTS.items():
        patch_agent(filepath, agent_name)
    print("\n✨ Done! All agents are now traced in Langfuse.")
    print("   Make sure LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are in your .env\n")


if __name__ == "__main__":
    main()
