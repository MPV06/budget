"""Budget app entry. Streamlit auto-discovers pages/ — this file shows the home banner."""
import streamlit as st

from services.config import get_settings
from services.db import get_engine

st.set_page_config(page_title="Budget", page_icon=":dollar:", layout="wide")

st.title("Budget")
st.write("Local Streamlit budget app — Plaid (Chase, read-only).")

try:
    s = get_settings()
    get_engine()  # only after settings load successfully
    st.success(f"Configured. Plaid env: **{s.plaid_env}**. Paycheck: **${s.paycheck_net_amount:,.2f}**.")
    if not s.plaid_access_token:
        st.warning("No PLAID_ACCESS_TOKEN yet. Go to Settings to onboard Plaid Link.")
except Exception as exc:
    st.error(f"Config error — fill out `.env` (see `.env.example`). Details: {exc}")

st.markdown(
    "**Use the sidebar to navigate to Dashboard, Bills, Envelopes, BNPL, Goals, "
    "Transactions, Settings.**"
)
