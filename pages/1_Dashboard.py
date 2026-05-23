from datetime import date

import pandas as pd
import streamlit as st

from services.db import get_session
from services.dashboard_data import build_dashboard_view
from services.paycheck_calendar import generate_paycheck_dates, next_paycheck_after

st.set_page_config(page_title="Dashboard — Budget", layout="wide")
st.title("Dashboard")

today = date.today()
calendar = generate_paycheck_dates(start=date(today.year, today.month, 1), months=2)
np_ = next_paycheck_after(today, calendar)

with get_session() as session:
    view = build_dashboard_view(session, today=today, next_paycheck=np_.actual_deposit_date)

col1, col2, col3 = st.columns(3)
col1.metric("Safe to spend", f"${view.safe_to_spend:,.2f}",
            help=f"Balance minus obligations before {np_.actual_deposit_date}.")
col2.metric("Checking balance", f"${view.balance:,.2f}")
col3.metric("Next paycheck", np_.actual_deposit_date.strftime("%a %b %d"),
            help=f"Scheduled {np_.scheduled_date.strftime('%b %d')}")

st.subheader(f"Upcoming bills before {np_.actual_deposit_date}")
if view.upcoming_bills:
    st.dataframe(pd.DataFrame([
        {"due": b.due_date, "label": b.label, "amount": b.amount}
        for b in view.upcoming_bills
    ]), use_container_width=True, hide_index=True)
else:
    st.info("No bills due before next paycheck.")

st.subheader(f"Upcoming BNPL installments before {np_.actual_deposit_date}")
if view.upcoming_bnpl:
    st.dataframe(pd.DataFrame([
        {"due": i.due_date, "label": i.label, "amount": i.amount}
        for i in view.upcoming_bnpl
    ]), use_container_width=True, hide_index=True)
else:
    st.info("No BNPL installments due before next paycheck.")
