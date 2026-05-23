"""Budget app entry. Streamlit auto-discovers pages/ — this file shows the home banner."""
import streamlit as st

from services.config import get_settings
from services.db import get_engine
from services.ui_theme import apply_app_chrome, section_header, render_status_pill

apply_app_chrome("Budget", "💰")

st.markdown("# 💰 Budget")
st.caption("Local personal-finance tracker · Plaid (Chase, read-only) · 100% on your machine")

st.markdown("<br/>", unsafe_allow_html=True)

try:
    s = get_settings()
    get_engine()  # only after settings load successfully
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        render_status_pill(f"ENV · {s.plaid_env.upper()}", "info")
    with c2:
        render_status_pill("CONFIGURED", "ok")
    st.markdown("<br/>", unsafe_allow_html=True)
    st.success(
        f"Paycheck: **${s.paycheck_net_amount:,.2f}** every semi-monthly deposit. "
        f"DB at `{s.db_path}`."
    )
    if not s.plaid_access_token:
        st.warning(
            "No PLAID_ACCESS_TOKEN yet. Go to **Settings** to onboard Plaid Link, "
            "or use the **Dashboard's manual balance entry**."
        )
except Exception as exc:
    render_status_pill("CONFIG MISSING", "over")
    st.error(f"Fill out `.env` (see `.env.example`). Details: {exc}")

section_header("🧭", "Navigation", "Sidebar")
st.markdown(
    """
    | Page | Purpose |
    |---|---|
    | 📊 **Dashboard** | Per-paycheck math, charts, safe-to-spend |
    | 🧾 **Bills** | Recurring bills with on/off toggles |
    | ✉️ **Envelopes** | Variable-category budgets (gas, groceries, restaurants) |
    | 💳 **BNPL** | Affirm, Chase Pay-in-4, Klarna installments |
    | 🎯 **Goals** | Named savings goals with required PMT math |
    | 💎 **Save** | All savings activity + savings-rate benchmark |
    | 🛡 **Emergency Fund** | 3–6 months essentials sizing + runway |
    | ⚖️ **Debt** | Avalanche/snowball + DTI |
    | 📜 **Transactions** | Searchable Plaid-synced transaction list |
    | ⚙️ **Settings** | Plaid onboarding, security, data controls |
    """
)
