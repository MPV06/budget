"""One-time Plaid Link onboarding. Run: python -m scripts.plaid_link

Prints an access_token you paste into .env as PLAID_ACCESS_TOKEN.

This script intentionally uses Plaid endpoints NOT in the read-only whitelist
(link/token/create, item/public_token/exchange) — these are setup-time only and
do not grant write access to the bank account.
"""
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from plaid.api import plaid_api
from plaid.configuration import Configuration
from plaid.api_client import ApiClient
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest

from services.config import get_settings


def _build_client():
    s = get_settings()
    host = {
        "sandbox": "https://sandbox.plaid.com",
        "development": "https://development.plaid.com",
        "production": "https://production.plaid.com",
    }[s.plaid_env]
    config = Configuration(host=host, api_key={"clientId": s.plaid_client_id,
                                               "secret": s.plaid_secret})
    return plaid_api.PlaidApi(ApiClient(config))


HTML_TEMPLATE = """<!doctype html>
<html><head><title>Plaid Link</title>
<script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
</head><body>
<h2>Connecting to Chase via Plaid…</h2>
<script>
  const handler = Plaid.create({{
    token: '{link_token}',
    onSuccess: (public_token, metadata) => {{
      fetch('/callback?public_token=' + encodeURIComponent(public_token));
      document.body.innerHTML = '<h2>Done — return to terminal.</h2>';
    }},
    onExit: () => {{ document.body.innerHTML = '<h2>Exited.</h2>'; }},
  }});
  handler.open();
</script>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    link_token = ""
    public_token = None

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            html = HTML_TEMPLATE.format(link_token=Handler.link_token).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html)
        elif parsed.path == "/callback":
            qs = parse_qs(parsed.query)
            Handler.public_token = qs["public_token"][0]
            self.send_response(200); self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404); self.end_headers()

    def log_message(self, *_): pass


def main():
    client = _build_client()
    req = LinkTokenCreateRequest(
        products=[Products("transactions")],
        client_name="Budget App (local)",
        country_codes=[CountryCode("US")],
        language="en",
        user=LinkTokenCreateRequestUser(client_user_id="local-user"),
    )
    link_token = client.link_token_create(req).link_token
    Handler.link_token = link_token

    server = HTTPServer(("127.0.0.1", 8765), Handler)
    print("Opening browser to http://127.0.0.1:8765 — sign in with Chase via Plaid Link.")
    webbrowser.open("http://127.0.0.1:8765")
    while Handler.public_token is None:
        server.handle_request()

    exchange = client.item_public_token_exchange(
        ItemPublicTokenExchangeRequest(public_token=Handler.public_token)
    )
    print()
    print("=" * 60)
    print("SUCCESS. Paste the following into your .env file:")
    print(f"PLAID_ACCESS_TOKEN={exchange.access_token}")
    print("=" * 60)


if __name__ == "__main__":
    main()
