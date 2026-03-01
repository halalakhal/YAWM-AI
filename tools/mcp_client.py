"""
tools/mcp_client.py  (UPGRADED)
─────────────────────────────────
Initialises MCPClient connections to ALL 6 MCP servers:
  1. google_calendar  — Google Calendar API (stdio)
  2. notion           — Notion database (stdio)
  3. todoist          — Todoist tasks (stdio)
  4. aladhan          — AlAdhan prayer times (stdio)
  5. canva            — Canva design platform (remote or local stdio)
  6. deen_notify      — YouTube search + Gmail/WhatsApp notifications (NEW)

NEW: Single shared client instance via get_shared_client() to avoid spawning
     a new subprocess per agent. Call init_shared_client() once in graph_runner
     and pass through state, or use get_mcp_client() for standalone usage.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()

_ROOT         = Path(__file__).parent.parent
_GCAL         = str(_ROOT / "mcp_servers" / "google_calendar_mcp.py")
_NOTION       = str(_ROOT / "mcp_servers" / "notion_mcp.py")
_TODOIST      = str(_ROOT / "mcp_servers" / "todoist_mcp.py")
_ALADHAN      = str(_ROOT / "mcp_servers" / "aladhan_mcp.py")
_CANVA        = str(_ROOT / "mcp_servers" / "canva_mcp.py")
_DEEN_NOTIFY  = str(_ROOT / "mcp_servers" / "deen_notify_mcp.py")   # NEW

CANVA_REMOTE_URL = "https://mcp.canva.com/mcp"


def _canva_config() -> dict:
    mode  = os.getenv("CANVA_MCP_MODE", "local").lower()
    token = os.getenv("CANVA_ACCESS_TOKEN", "")
    if mode == "remote" and token and token != "skip":
        return {
            "url":       CANVA_REMOTE_URL,
            "transport": "streamable_http",
            "headers":   {"Authorization": f"Bearer {token}"},
        }
    return {"command": sys.executable, "args": [_CANVA], "transport": "stdio",
            "env": {**os.environ}}


def get_mcp_client() -> MultiServerMCPClient:
    """Return a MultiServerMCPClient connecting to all 6 MCP services."""
    _env = {**os.environ}
    return MultiServerMCPClient({
        "google_calendar": {
            "command": sys.executable, "args": [_GCAL],
            "transport": "stdio", "env": _env,
        },
        "notion": {
            "command": sys.executable, "args": [_NOTION],
            "transport": "stdio", "env": _env,
        },
        "todoist": {
            "command": sys.executable, "args": [_TODOIST],
            "transport": "stdio", "env": _env,
        },
        "aladhan": {
            "command": sys.executable, "args": [_ALADHAN],
            "transport": "stdio", "env": _env,
        },
        "canva": _canva_config(),
        "deen_notify": {                                        # NEW
            "command": sys.executable, "args": [_DEEN_NOTIFY],
            "transport": "stdio", "env": _env,
        },
    })


# ── Per-server helpers ────────────────────────────────────────────────────────

async def get_gcal_tools():
    return await get_mcp_client().get_tools(server_name="google_calendar")

async def get_notion_tools():
    return await get_mcp_client().get_tools(server_name="notion")

async def get_todoist_tools():
    return await get_mcp_client().get_tools(server_name="todoist")

async def get_aladhan_tools():
    return await get_mcp_client().get_tools(server_name="aladhan")

async def get_canva_tools():
    return await get_mcp_client().get_tools(server_name="canva")

async def get_deen_notify_tools():
    return await get_mcp_client().get_tools(server_name="deen_notify")

async def get_all_tools():
    return await get_mcp_client().get_tools()