
#mcp_servers/aladhan_mcp.py
#───────────────────────────
#MCP Server wrapping the AlAdhan Prayer Times API (free, no key needed).
#https://aladhan.com/prayer-times-api

from __future__ import annotations
import os, json, requests
from datetime import date
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

app = Server("aladhan-mcp")

BASE = os.getenv("ALADHAN_API_URL", "https://api.aladhan.com/v1")
CORE_PRAYERS = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_prayer_times",
            description=(
                "Fetch accurate Islamic prayer times for a city/country and date "
                "using the AlAdhan API. Returns Fajr, Sunrise, Dhuhr, Asr, Maghrib, Isha."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "date":    {"type": "string", "description": "YYYY-MM-DD (defaults to today)"},
                    "city":    {"type": "string", "default": "Casablanca"},
                    "country": {"type": "string", "default": "Morocco"},
                    "method":  {"type": "integer", "default": 2,
                                "description": "Calculation method (2=ISNA, 3=MWL, 4=Makkah)"},
                },
            },
        ),
        Tool(
            name="get_hijri_date",
            description="Convert a Gregorian date to Hijri and return Ramadan info.",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["date"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:

    if name == "get_prayer_times":
        d = arguments.get("date") or date.today().isoformat()
        city    = arguments.get("city",    os.getenv("PRAYER_CITY", "Casablanca"))
        country = arguments.get("country", os.getenv("PRAYER_COUNTRY", "Morocco"))
        method  = arguments.get("method",  int(os.getenv("PRAYER_METHOD", "2")))

        day, month, year = d.split("-")[2], d.split("-")[1], d.split("-")[0]
        url = f"{BASE}/timingsByCity/{day}-{month}-{year}?city={city}&country={country}&method={method}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        timings = resp.json()["data"]["timings"]
        filtered = {k: v[:5] for k, v in timings.items() if k in CORE_PRAYERS}
        return [TextContent(type="text", text=json.dumps(filtered))]

    elif name == "get_hijri_date":
        d = arguments["date"]
        day, month, year = d.split("-")[2], d.split("-")[1], d.split("-")[0]
        url = f"{BASE}/gToH/{day}-{month}-{year}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        hijri = resp.json()["data"]["hijri"]
        return [TextContent(type="text", text=json.dumps({
            "hijri_date": hijri["date"],
            "hijri_month": hijri["month"]["en"],
            "hijri_day": int(hijri["day"]),
            "hijri_year": int(hijri["year"]),
            "is_ramadan": hijri["month"]["number"] == 9,
        }))]

    return [TextContent(type="text", text=json.dumps({"error": f"Unknown: {name}"}))]


async def run():
    async with stdio_server() as (r, w):
        await app.run(r, w, app.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
