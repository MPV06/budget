import streamlit as st

from services.config import get_settings

st.set_page_config(page_title="Settings — Budget", layout="wide")
st.title("Settings")

try:
    s = get_settings()
except Exception as exc:
    st.error(f"Cannot load settings: {exc}")
    st.stop()

st.subheader("Configuration (read-only — edit `.env` to change)")
cfg = {
    "PLAID_ENV": s.plaid_env,
    "PLAID_CLIENT_ID": "set" if s.plaid_client_id else "missing",
    "PLAID_SECRET": "set" if s.plaid_secret else "missing",
    "PLAID_ACCESS_TOKEN": "set" if s.plaid_access_token else "missing",
    "PAYCHECK_NET_AMOUNT": f"${s.paycheck_net_amount:,.2f}",
    "DB_PATH": s.db_path,
}
st.table([{"key": k, "value": v} for k, v in cfg.items()])

st.subheader("Plaid Link onboarding")
st.markdown(
    """
    1. Get sandbox credentials at https://dashboard.plaid.com.
    2. Set `PLAID_CLIENT_ID`, `PLAID_SECRET`, `PLAID_ENV=sandbox` in `.env`.
    3. Run `python -m scripts.plaid_link` — it prints an `access_token`.
    4. Paste it into `.env` as `PLAID_ACCESS_TOKEN`, restart this app.
    """
)

st.subheader("Pay-date rules (informational)")
st.markdown(
    """
    - **Scheduled** pay dates: **15th** and **last day of month**.
    - If scheduled date is Saturday/Sunday → deposit the previous Friday.
    - If scheduled date is a US federal holiday → deposit the previous business day
      (this also covers the "Monday holiday → Saturday morning availability" case).
    """
)

st.subheader("Sync")
if st.button("Sync now"):
    if not s.plaid_access_token:
        st.error("PLAID_ACCESS_TOKEN missing — run `python -m scripts.plaid_link` first.")
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
        with get_session() as session:
            with st.spinner("Syncing…"):
                sync_all(session, client, s.plaid_access_token)
        st.success("Synced.")
