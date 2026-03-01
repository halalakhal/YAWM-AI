"""tools/canva_auth.py — PKCE-compatible Canva OAuth"""
import os, webbrowser, urllib.parse, requests, base64, hashlib, secrets
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv, set_key

load_dotenv()

CLIENT_ID    = os.getenv("CANVA_CLIENT_ID")
REDIRECT_URI = "http://127.0.0.1:8888/callback"  # use 127.0.0.1 not localhost

if not CLIENT_ID:
    print("❌ CANVA_CLIENT_ID must be set in .env!")
    exit(1)

# Generate PKCE code verifier and challenge
code_verifier  = secrets.token_urlsafe(64)
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode()).digest()
).rstrip(b"=").decode()

auth_url = (
    "https://www.canva.com/api/oauth/authorize"
    f"?response_type=code"
    f"&client_id={CLIENT_ID}"
    f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
    f"&scope=design:content:read+design:content:write+asset:read+asset:write"
    f"&code_challenge={code_challenge}"
    f"&code_challenge_method=S256"
)

print("Opening browser for Canva OAuth...")
webbrowser.open(auth_url)

code = None

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global code
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        code = params.get("code", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Auth complete! You can close this tab.")
    def log_message(self, *args): pass

print("Waiting for callback on http://127.0.0.1:8888 ...")
HTTPServer(("127.0.0.1", 8888), Handler).handle_request()

# Exchange code for token (PKCE — no client_secret needed)
CLIENT_SECRET = os.getenv("CANVA_CLIENT_SECRET", "")

resp = requests.post(
    "https://api.canva.com/rest/v1/oauth/token",
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    data={
        "grant_type":    "authorization_code",
        "code":          code,
        "redirect_uri":  REDIRECT_URI,
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code_verifier": code_verifier,
    }
)

data = resp.json()
token = data.get("access_token")

if token:
    set_key(".env", "CANVA_ACCESS_TOKEN", token)
    set_key(".env", "CANVA_API_TOKEN", token)
    print("✅ Token saved to .env successfully!")
else:
    print(f"❌ Failed: {data}")

