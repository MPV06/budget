from datetime import date

import streamlit as st
from sqlmodel import select

from models.schema import Envelope
from services.budget_engine import (
    EnvelopeSpend, envelope_status, auto_budget_from_history
)
from services.db import get_session
from services.envelope_data import current_period_spend, monthly_totals_for_envelope
from services.paycheck_calendar import generate_paycheck_dates, next_paycheck_after

st.set_page_config(page_title="Envelopes — Budget", layout="wide")
st.title("Envelopes")

today = date.today()
cal = generate_paycheck_dates(start=date(today.year, today.month, 1), months=2)
next_pay = next_paycheck_after(today, cal).actual_deposit_date
prev = max((p for p in cal if p.actual_deposit_date <= today),
           key=lambda p: p.actual_deposit_date, default=None)
period_start = prev.actual_deposit_date if prev else date(today.year, today.month, 1)

with get_session() as session:
    envelopes = session.exec(select(Envelope)).all()
    if not envelopes:
        st.warning("No envelopes yet. Default envelopes will be created on first sync.")
        if st.button("Create default envelopes (Groceries / Restaurants / Gas)"):
            for n, pfc, bucket in [
                ("Groceries", "FOOD_AND_DRINK_GROCERIES", "needs"),
                ("Restaurants", "FOOD_AND_DRINK_RESTAURANTS", "wants"),
                ("Gas", "TRANSPORTATION_GAS", "needs"),
            ]:
                session.add(Envelope(name=n, current_budget_per_paycheck=0.0,
                                     plaid_category_filter=pfc, bucket=bucket))
            session.commit()
            st.rerun()
        st.stop()

    for env in envelopes:
        st.subheader(env.name)
        spent = current_period_spend(session, env.id, period_start, next_pay)
        budget = env.user_override if env.user_override is not None else env.current_budget_per_paycheck
        status = envelope_status(EnvelopeSpend(name=env.name, spent=spent, budget=budget))

        cols = st.columns([2, 2, 2, 2])
        cols[0].metric("Spent", f"${status.spent:,.2f}")
        cols[1].metric("Budget", f"${status.budget:,.2f}")
        cols[2].metric("Remaining", f"${status.remaining:,.2f}")
        color = {"OK": "green", "WARN": "orange", "OVER": "red"}[status.status]
        cols[3].markdown(f"### :{color}[{status.status}]")

        if status.budget > 0:
            st.progress(min(1.0, status.spent / status.budget))

        history = monthly_totals_for_envelope(session, env.id, months_back=3, today=today)
        suggested = auto_budget_from_history(history)
        st.caption(f"3-mo monthly totals: {history} -> suggested ${suggested:.2f}/paycheck")

        c1, c2 = st.columns([1, 1])
        if c1.button(f"Apply suggested (${suggested:.2f})", key=f"app_{env.id}"):
            env.current_budget_per_paycheck = suggested
            env.user_override = None
            session.add(env); session.commit(); st.rerun()
        override = c2.number_input("Manual override ($/paycheck)", value=float(env.user_override or 0.0),
                                    step=10.0, key=f"ov_{env.id}")
        if c2.button("Save override", key=f"sav_{env.id}"):
            env.user_override = override if override > 0 else None
            session.add(env); session.commit(); st.rerun()
