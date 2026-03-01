#mcp_servers/google_calendar_mcp.py
#────────────────────────────────────
#Standalone MCP server that wraps the Google Calendar API.
#LangChain agents connect to this via MCPClient and use the
#exposed tools just like any other LangChain tool.

#Run standalone:  python mcp_servers/google_calendar_mcp.py
from __future__ import annotations
import os, json, pickle
from datetime import date
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Google Calendar color palette
COLOR_IDS = {
    "green":    "2",   # Sage     → prayers
    "blue":     "7",   # Peacock  → deep work
    "red":      "11",  # Tomato   → rest
    "lavender": "1",   # Lavender → sleep
    "yellow":   "5",   # Banana   → flexible
    "orange":   "6",   # Tangerine→ meals / iftar
    "teal":     "8",   # Graphite → meetings
    "purple":   "3",   # Grape    → quran / dhikr
}

app = Server("google-calendar-mcp")


def _get_service():
    creds = None
    token = os.getenv("GOOGLE_TOKEN_PATH", "./config/google_token.json")
    creds_file = os.getenv("GOOGLE_CREDENTIALS_PATH", "./config/google_credentials.json")
    if os.path.exists(token):
        with open(token, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token, "wb") as f:
            pickle.dump(creds, f)
    return build("calendar", "v3", credentials=creds)


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="gcal_list_events",
            description="List all Google Calendar events for a given date (returns fixed unmovable blocks).",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                    "max_results": {"type": "integer", "default": 30},
                },
                "required": ["date"],
            },
        ),
        Tool(
            name="gcal_create_event",
            description="Create a new timed event in Google Calendar with a color label.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title":       {"type": "string"},
                    "date":        {"type": "string", "description": "YYYY-MM-DD"},
                    "start_time":  {"type": "string", "description": "HH:MM (24h)"},
                    "end_time":    {"type": "string", "description": "HH:MM (24h)"},
                    "color":       {"type": "string", "enum": list(COLOR_IDS.keys()), "default": "blue"},
                    "description": {"type": "string", "default": ""},
                    "timezone":    {"type": "string", "default": "Africa/Casablanca"},
                },
                "required": ["title", "date", "start_time", "end_time"],
            },
        ),
        Tool(
            name="gcal_delete_event",
            description="Delete a Google Calendar event by its event ID.",
            inputSchema={
                "type": "object",
                "properties": {"event_id": {"type": "string"}},
                "required": ["event_id"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    svc = _get_service()
    cal_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")

    # ── list events ──────────────────────────────────────────────────────────
    if name == "gcal_list_events":
        d = arguments["date"]
        res = svc.events().list(
            calendarId=cal_id,
            timeMin=f"{d}T00:00:00Z",
            timeMax=f"{d}T23:59:59Z",
            maxResults=arguments.get("max_results", 30),
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = []
        for e in res.get("items", []):
            start = e["start"].get("dateTime", e["start"].get("date", ""))
            end   = e["end"].get("dateTime",   e["end"].get("date", ""))
            events.append({
                "id":          e["id"],
                "title":       e.get("summary", "Untitled"),
                "start":       start[11:16] if "T" in start else start,
                "end":         end[11:16]   if "T" in end   else end,
                "fixed":       True,
                "source":      "google",
                "description": e.get("description", ""),
            })
        return [TextContent(type="text", text=json.dumps(events))]

    # ── create event ─────────────────────────────────────────────────────────
    elif name == "gcal_create_event":
        tz = arguments.get("timezone", "Africa/Casablanca")
        d  = arguments["date"]
        body = {
            "summary":     arguments["title"],
            "description": arguments.get("description", "Created by YAWM AI"),
            "start": {"dateTime": f"{d}T{arguments['start_time']}:00", "timeZone": tz},
            "end":   {"dateTime": f"{d}T{arguments['end_time']}:00",   "timeZone": tz},
        }
        color = arguments.get("color", "blue")
        if color in COLOR_IDS:
            body["colorId"] = COLOR_IDS[color]
        created = svc.events().insert(calendarId=cal_id, body=body).execute()
        return [TextContent(type="text", text=json.dumps({"event_id": created["id"], "link": created.get("htmlLink", "")}))]

    # ── delete event ─────────────────────────────────────────────────────────
    elif name == "gcal_delete_event":
        svc.events().delete(calendarId=cal_id, eventId=arguments["event_id"]).execute()
        return [TextContent(type="text", text=json.dumps({"deleted": True}))]

    return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


async def run():
    async with stdio_server() as (r, w):
        await app.run(r, w, app.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
