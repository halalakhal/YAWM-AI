# mcp_servers/todoist_mcp.py
# ───────────────────────────
# MCP Server for Todoist task retrieval.

from __future__ import annotations
import os, json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from todoist_api_python.api import TodoistAPI

app = Server("todoist-mcp")

PRIORITY_MAP = {4: "high", 3: "high", 2: "medium", 1: "low"}


def _api():
    return TodoistAPI(os.getenv("TODOIST_API_TOKEN", ""))


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="todoist_list_tasks",
            description="Fetch today's or overdue Todoist tasks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 20},
                },
            },
        ),
        Tool(
            name="todoist_complete_task",
            description="Mark a Todoist task as complete.",
            inputSchema={
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "required": ["task_id"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    api = _api()

    if name == "todoist_list_tasks":
        raw = list(api.get_tasks())
        limit = arguments.get("limit", 20)

        # v3.x returns a list of pages, each page is a list of dicts
        tasks = []
        for item in raw:
            if isinstance(item, list):
                tasks.extend(item)
            elif isinstance(item, dict):
                tasks.append(item)
            else:
                # object-style (older SDK)
                tasks.append(item)

        result = []
        for t in tasks[:limit]:
            if isinstance(t, dict):
                due = t.get("due") or {}
                result.append({
                    "id":                t.get("id"),
                    "title":             t.get("content"),
                    "priority":          PRIORITY_MAP.get(t.get("priority", 1), "medium"),
                    "estimated_minutes": 30,
                    "deadline":          due.get("date") if due else None,
                    "source":            "todoist",
                })
            else:
                result.append({
                    "id":                t.id,
                    "title":             t.content,
                    "priority":          PRIORITY_MAP.get(t.priority, "medium"),
                    "estimated_minutes": 30,
                    "deadline":          t.due.date if t.due else None,
                    "source":            "todoist",
                })

        return [TextContent(type="text", text=json.dumps(result))]

    elif name == "todoist_complete_task":
        api.close_task(arguments["task_id"])
        return [TextContent(type="text", text=json.dumps({"completed": True}))]

    return [TextContent(type="text", text=json.dumps({"error": f"Unknown: {name}"}))]


async def run():
    async with stdio_server() as (r, w):
        await app.run(r, w, app.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())