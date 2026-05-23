from datetime import date, timedelta

import streamlit as st
import pandas as pd
from sqlmodel import select

from models.schema import RecurringBill, BNPLInstallment, Envelope
from services.config import get_settings
from services.budget_engine import paycheck_leftover
from services.db import get_session
from services.paycheck_calendar import generate_paycheck_dates

st.set_page_config(page_title="Goals — Budget", layout="wide")
st.title("Goals — Leftover Tracker")

s = get_settings()
today = date.today()
cal = generate_paycheck_dates(start=date(today.year, today.month, 1), months=12)

with get_session() as session:
    envelopes = session.exec(select(Envelope)).all()
    envelopes_total_per_pay = sum(
        (e.user_override if e.user_override is not None else e.current_budget_per_paycheck)
        for e in envelopes
    )

    rows = []
    for p in cal[:12]:
        period_start = p.actual_deposit_date
        try:
            next_p = next(x for x in cal if x.actual_deposit_date > period_start)
            period_end = next_p.actual_deposit_date
        except StopIteration:
            period_end = period_start + timedelta(days=15)
        bills = session.exec(
            select(RecurringBill).where(RecurringBill.is_active == True)  # noqa: E712
        ).all()
        bills_in = sum(b.amount for b in bills
                       if period_start <= b.next_due_date < period_end)
        installments = session.exec(
            select(BNPLInstallment).where(BNPLInstallment.status == "scheduled")
        ).all()
        bnpl_in = sum(i.amount for i in installments
                      if period_start <= i.due_date < period_end)
        leftover = paycheck_leftover(
            paycheck_amount=s.paycheck_net_amount,
            bills_in_period=bills_in,
            bnpl_in_period=bnpl_in,
            envelopes_allocated=envelopes_total_per_pay,
            debt_payments=0.0,
        )
        rows.append({
            "paycheck": period_start, "amount": s.paycheck_net_amount,
            "bills": round(bills_in, 2), "bnpl": round(bnpl_in, 2),
            "envelopes": round(envelopes_total_per_pay, 2), "leftover": leftover,
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.metric("Projected 6-month leftover (savings)",
              f"${df.head(12)['leftover'].sum():,.2f}")
