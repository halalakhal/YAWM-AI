# mcp_servers/notion_mcp.py
# ──────────────────────────
# MCP Server wrapping Notion database queries.
# Uses raw requests instead of notion-client SDK for compatibility.

from __future__ import annotations
import os, json, requests
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

app = Server("notion-mcp")

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _headers() -> dict:
    token = os.getenv("NOTION_API_KEY", "")
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="notion_list_tasks",
            description="Fetch pending tasks from a Notion tasks database.",
            inputSchema={
                "type": "object",
                "properties": {
                    "status_filter": {
                        "type": "string",
                        "description": "Filter by status e.g. 'Todo' or 'In progress'",
                        "default": "",
                    },
                    "limit": {"type": "integer", "default": 20},
                },
            },
        ),
        Tool(
            name="notion_complete_task",
            description="Mark a Notion task page as Done.",
            inputSchema={
                "type": "object",
                "properties": {"page_id": {"type": "string"}},
                "required": ["page_id"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    db_id = os.getenv("NOTION_DATABASE_ID", "")

    if name == "notion_list_tasks":
        payload: dict = {"page_size": arguments.get("limit", 20)}

        # Only apply filter if explicitly requested — default fetches all
        status = arguments.get("status_filter", "")
        if status:
            payload["filter"] = {
                "property": "Status",
                "status": {"equals": status}
            }

        resp = requests.post(
            f"{NOTION_API}/databases/{db_id}/query",
            headers=_headers(),
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()

        tasks = []
        for page in resp.json().get("results", []):
            props = page.get("properties", {})

            # Title — column is called "Task"
            title_raw = (
                props.get("Task") or
                props.get("Name") or
                props.get("Title") or {}
            ).get("title", [])
            title = "".join(t.get("plain_text", "") for t in title_raw)

            # Skip empty rows
            if not title.strip():
                continue

            # Priority — strip leading emoji e.g. "🔴 high" → "high"
            priority_raw = (
                (props.get("Priority", {}).get("select") or {}).get("name", "medium")
            ).lower()
            priority = priority_raw.split(" ")[-1].strip()

            # Type — "Work" or "Personal"
            ttype = (
                (props.get("Type", {}).get("select") or {}).get("name", "flexible")
            )

            # Estimated time — column is "Estimated time"
            estimate = (
                props.get("Estimated time", {}).get("number") or
                props.get("Estimate (min)", {}).get("number") or
                30
            )

            # Deadline — stored as rich_text e.g. "before 14:00" or "EOD"
            deadline_rich = props.get("Deadline", {}).get("rich_text") or []
            deadline = deadline_rich[0].get("plain_text") if deadline_rich else None

            # Status
            status_val = (
                (props.get("Status", {}).get("status") or {}).get("name", "")
            )

            tasks.append({
                "id":                page["id"],
                "title":             title,
                "priority":          priority,
                "estimated_minutes": int(estimate),
                "deadline":          deadline,
                "source":            "notion",
                "type":              ttype,
                "status":            status_val,
            })

        return [TextContent(type="text", text=json.dumps(tasks))]

    elif name == "notion_complete_task":
        resp = requests.patch(
            f"{NOTION_API}/pages/{arguments['page_id']}",
            headers=_headers(),
            json={"properties": {"Status": {"status": {"name": "Done"}}}},
            timeout=10,
        )
        resp.raise_for_status()
        return [TextContent(type="text", text=json.dumps({"updated": True}))]

    return [TextContent(type="text", text=json.dumps({"error": f"Unknown: {name}"}))]


async def run():
    async with stdio_server() as (r, w):
        await app.run(r, w, app.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())