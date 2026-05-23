from pathlib import Path

import streamlit as st

from services.config import get_settings
from services.secret_store import (
    get_plaid_access_token, set_plaid_access_token,
    clear_plaid_access_token, is_using_keyring,
)

st.set_page_config(page_title="Settings — Budget", layout="wide")
st.title("Settings")

try:
    s = get_settings()
except Exception as exc:
    st.error(f"Cannot load settings: {exc}")
    st.stop()

# ─── CONFIG TABLE ────────────────────────────────────────────────
st.subheader("Configuration")
token_resolved = get_plaid_access_token()
storage = "Windows Credential Manager (keyring)" if is_using_keyring() else (".env file (fallback)")
cfg = {
    "PLAID_ENV": s.plaid_env,
    "PLAID_CLIENT_ID": "set" if s.plaid_client_id else "missing",
    "PLAID_SECRET": "set" if s.plaid_secret else "missing",
    "PLAID_ACCESS_TOKEN": ("set in " + storage) if token_resolved else "missing",
    "PAYCHECK_NET_AMOUNT": f"${s.paycheck_net_amount:,.2f}",
    "DB_PATH": s.db_path,
}
st.table([{"key": k, "value": v} for k, v in cfg.items()])

# ─── PLAID LINK ONBOARDING ────────────────────────────────────────
st.subheader("Plaid Link onboarding")
st.markdown(
    """
    1. Get sandbox credentials at https://dashboard.plaid.com.
    2. Set `PLAID_CLIENT_ID`, `PLAID_SECRET`, `PLAID_ENV=sandbox` in `.env`.
    3. Run `python -m scripts.plaid_link` — it prints an `access_token`.
    4. Paste it into the field below to store it securely in Windows Credential Manager
       (preferred), or into `.env` as `PLAID_ACCESS_TOKEN` (fallback).
    """
)
with st.form("upgrade_token"):
    new_token = st.text_input(
        "Paste new Plaid access token (will be stored in keyring, NOT in .env)",
        type="password",
    )
    if st.form_submit_button("Save to keyring"):
        if new_token.strip():
            set_plaid_access_token(new_token.strip())
            st.success("Token saved to Windows Credential Manager. You can now clear PLAID_ACCESS_TOKEN from .env.")
            st.rerun()
        else:
            st.error("Empty token — nothing saved.")

# ─── PAY-DATE RULES ───────────────────────────────────────────────
st.subheader("Pay-date rules (informational)")
st.markdown(
    """
    - **Scheduled** pay dates: **15th** and **last day of month**.
    - If scheduled date is Saturday/Sunday → deposit the previous Friday.
    - If scheduled date is a US federal holiday → deposit the previous business day
      (covers the "Monday holiday → Saturday morning availability" case).
    """
)

# ─── SYNC ─────────────────────────────────────────────────────────
st.subheader("Sync")
if st.button("Sync now"):
    token = get_plaid_access_token()
    if not token:
        st.error("PLAID_ACCESS_TOKEN missing — run `python -m scripts.plaid_link` and save it above.")
    else:
        from plaid.api import plaid_api
        from plaid.configuration import Configuration
        from plaid.api_client import ApiClient
        from services.plaid_client import PlaidReadOnlyClient
        from services.plaid_sync import sync_all
        from services.db import get_session

        host = {
            "sandbox": "https://sandbox.plaid.com",
            "development": "https://development.plaid.com",
            "production": "https://production.plaid.com",
        }[s.plaid_env]
        raw = plaid_api.PlaidApi(ApiClient(Configuration(
            host=host,
            api_key={"clientId": s.plaid_client_id, "secret": s.plaid_secret}
        )))
        client = PlaidReadOnlyClient(raw)
        try:
            with get_session() as session:
                with st.spinner("Syncing…"):
                    sync_all(session, client, token)
            st.success("Synced.")
        except Exception as e:
            # Scrub token from any error string before showing it
            msg = str(e).replace(token, "***REDACTED***") if token else str(e)
            st.error(f"Sync failed: {msg}")

# ─── SECURITY / DATA CONTROLS ─────────────────────────────────────
st.subheader("Security & data controls")
st.markdown(
    f"""
    **Where your data lives (this machine only — nothing is uploaded):**

    - **Access token**: {storage}
    - **Transactions & balances**: SQLite at `{s.db_path}` (gitignored)
    - **App binds to**: `127.0.0.1` only when launched with `--server.address=127.0.0.1`
      — otherwise also listens on your LAN IP. For best security, always launch with
      `.venv\\Scripts\\streamlit run app.py --server.address=127.0.0.1`.

    **To revoke this app's access to your Chase account:**

    1. Log into your Chase account at https://chase.com
    2. Profile & settings → Security → Connected apps & websites
    3. Find "Plaid" / "Budget App" and click **Revoke**

    Or revoke from the Plaid side at https://my.plaid.com (manages all your Plaid-connected apps).
    """
)

st.markdown("---")
st.markdown("**Danger zone**")
col1, col2 = st.columns(2)

with col1:
    if st.button("🗑 Clear stored Plaid token", help="Removes token from keyring. You'll need to re-onboard."):
        clear_plaid_access_token()
        st.success("Token cleared from keyring. Note: any token in .env still exists — edit that file manually.")
        st.rerun()

with col2:
    confirm = st.checkbox("I understand this deletes ALL local data")
    if st.button("🔥 Delete local database", disabled=not confirm):
        try:
            db_path = Path(s.db_path)
            if db_path.exists():
                db_path.unlink()
            # Also clear stale engine reference so next page rebuilds tables
            import services.db
            services.db._engine = None
            st.success(f"Deleted {db_path}. Restart the app to recreate an empty database.")
        except Exception as e:
            st.error(f"Couldn't delete: {e}")
