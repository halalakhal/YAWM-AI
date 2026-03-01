"""
mcp_servers/canva_mcp.py
─────────────────────────
Canva MCP Server integration for YAWM AI.

Canva provides an OFFICIAL remote MCP server at:
  https://mcp.canva.com  (OAuth 2.0 — no API key, user connects once via browser)

This file does two things:
  1. Provides the MCP client config snippet to add to tools/mcp_client.py
  2. Wraps the Canva Connect REST API as a LOCAL stdio MCP server for
     environments that prefer stdio over remote HTTP (e.g. programmatic pipelines)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OPTION A  — Official remote MCP (recommended, zero setup)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Add this to your MCP client config (claude_desktop_config.json etc.):

  {
    "mcpServers": {
      "canva": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-canva"]
      }
    }
  }

Or for the streamable HTTP remote server use the URL:
  https://mcp.canva.com/sse  (SSE transport, OAuth 2.0 flow on first use)

Tools exposed by the official server:
  • generate-design       — Create a new design using an AI prompt
  • create-design         — Create a design from a template or custom dimensions
  • autofill-template     — Autofill a brand template with structured data
  • search-designs        — Search your Canva designs
  • get-design            — Get metadata for a specific design
  • export-design         — Export design as PNG/PDF (returns download URL)
  • create-folder         — Organise designs into folders
  • upload-asset          — Upload an image asset to Canva

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OPTION B  — Local stdio wrapper (this file)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Uses Canva Connect REST API directly with your OAuth token.
Requires: CANVA_ACCESS_TOKEN in .env (obtained via OAuth flow once).

Run standalone:  python mcp_servers/canva_mcp.py
"""

from __future__ import annotations
import os, json, time, requests
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

CANVA_API = "https://api.canva.com/rest/v1"

app = Server("canva-mcp")


def _headers() -> dict:
    token = os.getenv("CANVA_ACCESS_TOKEN", "")
    headers = {"Content-Type": "application/json"}
    if token and token != "skip":
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _poll_job(job_url: str, max_wait: int = 30) -> dict:
    """Poll a Canva async job endpoint until success/failed or timeout."""
    for _ in range(max_wait):
        resp = requests.get(job_url, headers=_headers(), timeout=10)
        data = resp.json()
        status = data.get("job", {}).get("status") or data.get("status", "")
        if status in ("success", "failed", "complete"):
            return data
        time.sleep(1)
    return {"status": "timeout"}


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        # ── Read ──────────────────────────────────────────────────────────────
        Tool(
            name="canva_search_designs",
            description="Search your Canva designs by keyword. Returns design IDs and edit URLs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keyword"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="canva_get_design",
            description="Get metadata and thumbnail for a specific Canva design.",
            inputSchema={
                "type": "object",
                "properties": {"design_id": {"type": "string"}},
                "required": ["design_id"],
            },
        ),
        # ── Create ────────────────────────────────────────────────────────────
        Tool(
            name="canva_create_design",
            description=(
                "Create a new blank Canva design with specified dimensions. "
                "Returns design_id and edit_url."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "title":  {"type": "string", "description": "Design title"},
                    "width":  {"type": "integer", "default": 1080, "description": "Width in px"},
                    "height": {"type": "integer", "default": 1920, "description": "Height in px"},
                    "design_type": {
                        "type": "string",
                        "default": "custom",
                        "description": "Preset type e.g. 'presentation', 'instagram_post', 'custom'",
                    },
                },
                "required": ["title"],
            },
        ),
        Tool(
            name="canva_autofill_template",
            description=(
                "Autofill a Canva brand template with structured schedule data. "
                "Use this to populate a pre-made YAWM AI schedule template."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "brand_template_id": {
                        "type": "string",
                        "description": "Canva brand template ID (from your Canva account)",
                    },
                    "title": {"type": "string"},
                    "data": {
                        "type": "object",
                        "description": "Key-value pairs mapping template fields to schedule data",
                    },
                },
                "required": ["brand_template_id", "data"],
            },
        ),
        # ── Export ────────────────────────────────────────────────────────────
        Tool(
            name="canva_export_design",
            description=(
                "Export a Canva design as PNG or PDF. "
                "Polls the async job and returns the download URL."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "design_id": {"type": "string"},
                    "format":    {"type": "string", "enum": ["png", "pdf", "jpg"], "default": "png"},
                    "quality":   {"type": "string", "enum": ["regular", "pro"], "default": "regular"},
                },
                "required": ["design_id"],
            },
        ),
        # ── Upload ────────────────────────────────────────────────────────────
        Tool(
            name="canva_upload_asset",
            description="Upload a local image file as an asset to your Canva account.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Local path to image file"},
                    "asset_name": {"type": "string"},
                },
                "required": ["file_path", "asset_name"],
            },
        ),
        # ── Folders ──────────────────────────────────────────────────────────
        Tool(
            name="canva_create_folder",
            description="Create a folder in Canva to organise YAWM AI schedules.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name":      {"type": "string"},
                    "parent_id": {"type": "string", "default": "root"},
                },
                "required": ["name"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:

    # ── canva_search_designs ──────────────────────────────────────────────────
    if name == "canva_search_designs":
        params = {"query": arguments["query"], "limit": arguments.get("limit", 10)}
        resp = requests.get(f"{CANVA_API}/designs", headers=_headers(), params=params, timeout=10)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        results = [{"id": d["id"], "title": d.get("title", ""), "edit_url": d.get("urls", {}).get("edit_url", "")}
                   for d in items]
        return [TextContent(type="text", text=json.dumps(results))]

    # ── canva_get_design ──────────────────────────────────────────────────────
    elif name == "canva_get_design":
        resp = requests.get(f"{CANVA_API}/designs/{arguments['design_id']}",
                            headers=_headers(), timeout=10)
        resp.raise_for_status()
        d = resp.json().get("design", {})
        return [TextContent(type="text", text=json.dumps({
            "id":        d.get("id"),
            "title":     d.get("title"),
            "edit_url":  d.get("urls", {}).get("edit_url"),
            "view_url":  d.get("urls", {}).get("view_url"),
            "thumbnail": d.get("thumbnail", {}).get("url"),
            "created":   d.get("created_at"),
        }))]

    # ── canva_create_design ───────────────────────────────────────────────────
    elif name == "canva_create_design":
        payload: dict = {"title": arguments["title"]}
        design_type = arguments.get("design_type", "custom")
        if design_type == "custom":
            payload["design_type"] = {
                "type": "custom",
                "width":  arguments.get("width",  1080),
                "height": arguments.get("height", 1920),
            }
        else:
            payload["design_type"] = {"type": design_type}

        resp = requests.post(f"{CANVA_API}/designs", headers=_headers(),
                             json=payload, timeout=10)
        resp.raise_for_status()
        d = resp.json().get("design", {})
        return [TextContent(type="text", text=json.dumps({
            "design_id": d.get("id"),
            "edit_url":  d.get("urls", {}).get("edit_url"),
            "title":     d.get("title"),
        }))]

    # ── canva_autofill_template ───────────────────────────────────────────────
    elif name == "canva_autofill_template":
        # Start autofill job
        payload = {
            "brand_template_id": arguments["brand_template_id"],
            "title": arguments.get("title", "YAWM AI Schedule"),
            "data": arguments["data"],
        }
        resp = requests.post(f"{CANVA_API}/autofills", headers=_headers(),
                             json=payload, timeout=10)
        resp.raise_for_status()
        job_id = resp.json().get("job", {}).get("id", "")

        # Poll for completion
        result = _poll_job(f"{CANVA_API}/autofills/{job_id}")
        design_id = (result.get("job", {}).get("result", {})
                          .get("design", {}).get("id", ""))
        return [TextContent(type="text", text=json.dumps({
            "job_id":    job_id,
            "design_id": design_id,
            "status":    result.get("job", {}).get("status", "unknown"),
        }))]

    # ── canva_export_design ───────────────────────────────────────────────────
    elif name == "canva_export_design":
        fmt = arguments.get("format", "png").upper()
        payload = {
            "design_id": arguments["design_id"],
            "format":    fmt,
            "export_quality": arguments.get("quality", "regular"),
        }
        resp = requests.post(f"{CANVA_API}/exports", headers=_headers(),
                             json=payload, timeout=10)
        resp.raise_for_status()
        job_id = resp.json().get("job", {}).get("id", "")

        # Poll for download URLs
        result = _poll_job(f"{CANVA_API}/exports/{job_id}")
        urls = (result.get("job", {}).get("result", {})
                      .get("urls", []))
        return [TextContent(type="text", text=json.dumps({
            "job_id":       job_id,
            "download_urls": urls,
            "status":        result.get("job", {}).get("status", "unknown"),
        }))]

    # ── canva_upload_asset ────────────────────────────────────────────────────
    elif name == "canva_upload_asset":
        file_path  = arguments["file_path"]
        asset_name = arguments.get("asset_name", os.path.basename(file_path))
        # Step 1: create upload job
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        headers = _headers()
        headers.pop("Content-Type")  # multipart handles its own
        headers["Asset-Upload-Metadata"] = json.dumps({"name_base64": __import__("base64").b64encode(asset_name.encode()).decode()})
        resp = requests.post(
            f"{CANVA_API}/asset-uploads",
            headers=headers,
            data=file_bytes,
            timeout=30,
        )
        resp.raise_for_status()
        job_id = resp.json().get("job", {}).get("id", "")
        # Step 2: poll
        result = _poll_job(f"{CANVA_API}/asset-uploads/{job_id}")
        asset_id = (result.get("job", {}).get("asset", {}).get("id", ""))
        return [TextContent(type="text", text=json.dumps({
            "asset_id": asset_id,
            "status":   result.get("job", {}).get("status", "unknown"),
        }))]

    # ── canva_create_folder ───────────────────────────────────────────────────
    elif name == "canva_create_folder":
        payload = {
            "name":      arguments["name"],
            "parent_id": arguments.get("parent_id", "root"),
        }
        resp = requests.post(f"{CANVA_API}/folders", headers=_headers(),
                             json=payload, timeout=10)
        resp.raise_for_status()
        folder = resp.json().get("folder", {})
        return [TextContent(type="text", text=json.dumps({
            "folder_id": folder.get("id"),
            "name":      folder.get("name"),
        }))]

    return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


async def run():
    async with stdio_server() as (r, w):
        await app.run(r, w, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
