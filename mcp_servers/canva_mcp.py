from __future__ import annotations
import sys
import logging
import os, json, time, requests
from dotenv import load_dotenv
load_dotenv()

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

logging.basicConfig(stream=sys.stderr)

CANVA_API = "https://api.canva.com/rest/v1"
CLIENT_ID = os.getenv("CANVA_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("CANVA_CLIENT_SECRET", "")

app = Server("canva-mcp")


def _refresh_token() -> str:
    """Use refresh token to get a new access token, update .env, return new token."""
    refresh = os.getenv("CANVA_REFRESH_TOKEN", "")
    if not refresh:
        return ""
    resp = requests.post("https://api.canva.com/rest/v1/oauth/token", data={
        "grant_type": "refresh_token",
        "refresh_token": refresh,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    })
    data = resp.json()
    new_token = data.get("access_token", "")
    if new_token:
        os.environ["CANVA_ACCESS_TOKEN"] = new_token
        # Update .env file
        try:
            env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
            with open(env_path, "r") as f:
                content = f.read()
            import re
            content = re.sub(r"CANVA_ACCESS_TOKEN=.*", f"CANVA_ACCESS_TOKEN={new_token}", content)
            with open(env_path, "w") as f:
                f.write(content)
        except Exception:
            pass
    return new_token


def _headers() -> dict:
    token = os.getenv("CANVA_ACCESS_TOKEN", "").strip()
    if not token or token == "skip":
        token = _refresh_token()
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }


def _request(method: str, path: str, **kwargs):
    """Make API request, auto-refresh token on 401."""
    resp = requests.request(method, f"{CANVA_API}{path}", headers=_headers(), timeout=10, **kwargs)
    if resp.status_code == 401:
        # Token expired — refresh and retry once
        new_token = _refresh_token()
        if new_token:
            headers = _headers()
            resp = requests.request(method, f"{CANVA_API}{path}", headers=headers, timeout=10, **kwargs)
    resp.raise_for_status()
    return resp


def _poll_job(job_url: str, max_wait: int = 30) -> dict:
    for _ in range(max_wait):
        resp = requests.get(job_url, headers=_headers(), timeout=10)
        data = resp.json()
        status = data.get("job", {}).get("status") or data.get("status", "")
        if status in ("success", "failed", "complete"):
            return data
        time.sleep(1)
    return {"status": "timeout"}


@app.list_tools()
async def list_tools():
    return [
        Tool(name="canva_search_designs",
             description="Search your Canva designs by keyword.",
             inputSchema={"type": "object", "properties": {
                 "query": {"type": "string"},
                 "limit": {"type": "integer", "default": 10}
             }, "required": ["query"]}),
        Tool(name="canva_get_design",
             description="Get metadata for a specific Canva design.",
             inputSchema={"type": "object", "properties": {
                 "design_id": {"type": "string"}
             }, "required": ["design_id"]}),
        Tool(name="canva_create_design",
             description="Create a new blank Canva design.",
             inputSchema={"type": "object", "properties": {
                 "title": {"type": "string"},
                 "width": {"type": "integer", "default": 1080},
                 "height": {"type": "integer", "default": 1920},
                 "design_type": {"type": "string", "default": "custom"}
             }, "required": ["title"]}),
        Tool(name="canva_autofill_template",
             description="Autofill a Canva brand template.",
             inputSchema={"type": "object", "properties": {
                 "brand_template_id": {"type": "string"},
                 "title": {"type": "string"},
                 "data": {"type": "object"}
             }, "required": ["brand_template_id", "data"]}),
        Tool(name="canva_export_design",
             description="Export a Canva design as PNG, JPG, or PDF.",
             inputSchema={"type": "object", "properties": {
                 "design_id": {"type": "string"},
                 "format": {"type": "string", "enum": ["png", "jpg", "pdf"], "default": "png"},
                 "quality": {"type": "string", "enum": ["regular", "pro"], "default": "regular"}
             }, "required": ["design_id"]}),
        Tool(name="canva_upload_asset",
             description="Upload a local image file to Canva.",
             inputSchema={"type": "object", "properties": {
                 "file_path": {"type": "string"},
                 "asset_name": {"type": "string"}
             }, "required": ["file_path", "asset_name"]}),
        Tool(name="canva_create_folder",
             description="Create a folder in Canva.",
             inputSchema={"type": "object", "properties": {
                 "name": {"type": "string"},
                 "parent_id": {"type": "string", "default": "root"}
             }, "required": ["name"]}),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:

    if name == "canva_search_designs":
        params = {"query": arguments["query"], "limit": arguments.get("limit", 10)}
        resp = _request("GET", "/designs", params=params)
        items = resp.json().get("items", [])
        results = [{"id": d["id"], "title": d.get("title", ""), "edit_url": d.get("urls", {}).get("edit_url", "")}
                   for d in items]
        return [TextContent(type="text", text=json.dumps(results))]

    elif name == "canva_get_design":
        resp = _request("GET", f"/designs/{arguments['design_id']}")
        d = resp.json().get("design", {})
        return [TextContent(type="text", text=json.dumps({
            "id": d.get("id"), "title": d.get("title"),
            "edit_url": d.get("urls", {}).get("edit_url"),
            "view_url": d.get("urls", {}).get("view_url"),
            "thumbnail": d.get("thumbnail", {}).get("url"),
        }))]

    elif name == "canva_create_design":
        design_type = arguments.get("design_type", "custom")
        payload = {"title": arguments["title"]}
        if design_type == "custom":
            payload["design_type"] = {"type": "custom", "width": arguments.get("width", 1080), "height": arguments.get("height", 1920)}
        else:
            payload["design_type"] = {"type": design_type}
        resp = _request("POST", "/designs", json=payload)
        d = resp.json().get("design", {})
        return [TextContent(type="text", text=json.dumps({
            "design_id": d.get("id"), "edit_url": d.get("urls", {}).get("edit_url"), "title": d.get("title")
        }))]

    elif name == "canva_autofill_template":
        payload = {"brand_template_id": arguments["brand_template_id"],
                   "title": arguments.get("title", "YAWM AI Schedule"), "data": arguments["data"]}
        resp = _request("POST", "/autofills", json=payload)
        job_id = resp.json().get("job", {}).get("id", "")
        result = _poll_job(f"{CANVA_API}/autofills/{job_id}")
        design_id = result.get("job", {}).get("result", {}).get("design", {}).get("id", "")
        return [TextContent(type="text", text=json.dumps({
            "job_id": job_id, "design_id": design_id, "status": result.get("job", {}).get("status", "unknown")
        }))]

    elif name == "canva_export_design":
        payload = {"design_id": arguments["design_id"], "format": arguments.get("format", "png").upper(),
                   "export_quality": arguments.get("quality", "regular")}
        resp = _request("POST", "/exports", json=payload)
        job_id = resp.json().get("job", {}).get("id", "")
        result = _poll_job(f"{CANVA_API}/exports/{job_id}")
        urls = result.get("job", {}).get("result", {}).get("urls", [])
        return [TextContent(type="text", text=json.dumps({
            "job_id": job_id, "download_urls": urls, "status": result.get("job", {}).get("status", "unknown")
        }))]

    elif name == "canva_upload_asset":
        file_path = arguments["file_path"]
        asset_name = arguments.get("asset_name", os.path.basename(file_path))
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        import base64
        headers = _headers()
        headers.pop("Content-Type")
        headers["Asset-Upload-Metadata"] = json.dumps({"name_base64": base64.b64encode(asset_name.encode()).decode()})
        resp = requests.post(f"{CANVA_API}/asset-uploads", headers=headers, data=file_bytes, timeout=30)
        resp.raise_for_status()
        job_id = resp.json().get("job", {}).get("id", "")
        result = _poll_job(f"{CANVA_API}/asset-uploads/{job_id}")
        return [TextContent(type="text", text=json.dumps({
            "asset_id": result.get("job", {}).get("asset", {}).get("id", ""),
            "status": result.get("job", {}).get("status", "unknown")
        }))]

    elif name == "canva_create_folder":
        payload = {"name": arguments["name"], "parent_id": arguments.get("parent_id", "root")}
        resp = _request("POST", "/folders", json=payload)
        folder = resp.json().get("folder", {})
        return [TextContent(type="text", text=json.dumps({"folder_id": folder.get("id"), "name": folder.get("name")}))]

    return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


async def run():
    async with stdio_server() as (r, w):
        await app.run(r, w, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(run())