"""
Xero OAuth2 authorisation flow.

Opens the Xero consent page in your browser and starts a local server on
port 8080 to automatically intercept the callback and capture the code.
Exchanges the code for tokens and saves them to xero_tokens.json.

Usage:
    python3 xero_auth.py
"""

import json
import os
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

SCRIPT_DIR   = Path(__file__).parent
TOKENS_FILE  = SCRIPT_DIR / "xero_tokens.json"
REDIRECT_URI = "http://localhost:8080/callback"
TOKEN_URL    = "https://identity.xero.com/connect/token"
AUTH_URL     = "https://login.xero.com/identity/connect/authorize"
SCOPES       = (
    "openid profile email offline_access "
    "accounting.reports.profitandloss.read "
    "accounting.reports.balancesheet.read "
    "accounting.settings.read "
    "accounting.invoices.read"
)


def make_handler(result: dict):
    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            qs = parse_qs(urlparse(self.path).query)
            result["code"]  = qs.get("code",  [None])[0]
            result["state"] = qs.get("state", [None])[0]
            result["error"] = qs.get("error", [None])[0]

            body = b"<h2>Authorisation received. You can close this tab.</h2>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

            threading.Thread(target=self.server.shutdown, daemon=True).start()

        def log_message(self, *args):
            pass  # suppress access log noise

    return CallbackHandler


def main():
    client_id     = os.environ["XERO_CLIENT_ID"]
    client_secret = os.environ["XERO_CLIENT_SECRET"]

    state = secrets.token_urlsafe(16)

    params = {
        "response_type": "code",
        "client_id":     client_id,
        "redirect_uri":  REDIRECT_URI,
        "scope":         SCOPES,
        "state":         state,
    }
    auth_url = f"{AUTH_URL}?{urlencode(params)}"

    result = {}
    server = HTTPServer(("127.0.0.1", 8080), make_handler(result))

    print("Opening Xero authorisation page in your browser...")
    print(f"\n  {auth_url}\n")
    webbrowser.open(auth_url)

    print("Waiting for callback on http://localhost:8080/callback ...")
    server.serve_forever()  # blocks until handler calls shutdown()

    if result.get("error"):
        print(f"Xero returned an error: {result['error']}")
        return

    if result.get("state") != state:
        print(f"State mismatch — expected {state}, got {result.get('state')}. Aborting.")
        return

    code = result.get("code")
    if not code:
        print("No authorisation code received. Aborting.")
        return

    print(f"Callback received. Exchanging code for tokens...")
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type":   "authorization_code",
            "code":         code,
            "redirect_uri": REDIRECT_URI,
        },
        auth=(client_id, client_secret),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    if not response.ok:
        print(f"Token exchange failed ({response.status_code}): {response.text}")
        return

    tokens = response.json()
    TOKENS_FILE.write_text(json.dumps(tokens, indent=2))
    print(f"\nTokens saved to {TOKENS_FILE}")

    refresh_token = tokens.get("refresh_token", "(not present)")
    print(f"\nRefresh token:\n  {refresh_token}")


if __name__ == "__main__":
    main()
