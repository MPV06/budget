"""Debt tracker with avalanche/snowball comparison and DTI ratios."""
import streamlit as st
import pandas as pd
from sqlmodel import select

from models.schema import DebtAccount
from services.config import get_settings
from services.db import get_session
from services.debt_payoff import (
    Debt, simulate_payoff,
    front_end_dti, back_end_dti, dti_status,
)

st.set_page_config(page_title="Debt — Budget", layout="wide")
st.title("Debt")
st.caption(
    "Track debts, compare avalanche (mathematically optimal) vs snowball "
    "(psychologically optimal) payoff strategies, and check your DTI ratios."
)

with get_session() as session:
    debts = session.exec(
        select(DebtAccount).where(DebtAccount.is_active == True)  # noqa: E712
    ).all()

    # ─── DEBT LIST ────────────────────────────────────────────────
    st.subheader(f"Active debts ({len(debts)})")
    if debts:
        rows = [{
            "name": d.name, "balance": d.balance, "apr_%": d.apr_pct,
            "min_payment": d.min_payment,
        } for d in debts]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        total_balance = sum(d.balance for d in debts)
        total_min = sum(d.min_payment for d in debts)
        c1, c2 = st.columns(2)
        c1.metric("Total balance", f"${total_balance:,.2f}")
        c2.metric("Total minimum / month", f"${total_min:,.2f}")
    else:
        st.info("No debts entered. Add one below.")

    # ─── ADD DEBT ────────────────────────────────────────────────
    with st.expander("Add a debt"):
        with st.form("add_debt"):
            name = st.text_input("Name (e.g., 'Chase Sapphire', 'Sallie Mae')")
            balance = st.number_input("Current balance ($)", min_value=0.0, step=100.0)
            apr = st.number_input("APR (%)", min_value=0.0, max_value=50.0, step=0.1)
            min_pay = st.number_input("Minimum monthly payment ($)", min_value=0.0, step=10.0)
            if st.form_submit_button("Add"):
                session.add(DebtAccount(name=name, balance=balance, apr_pct=apr,
                                         min_payment=min_pay, is_active=True))
                session.commit()
                st.success(f"Added {name}.")
                st.rerun()

    # ─── EDIT/DELETE EXISTING ────────────────────────────────────
    if debts:
        st.subheader("Edit / delete")
        for d in debts:
            with st.expander(f"{d.name} — ${d.balance:,.2f} @ {d.apr_pct}% APR"):
                with st.form(f"edit_debt_{d.id}"):
                    name_e = st.text_input("Name", value=d.name)
                    bal_e = st.number_input("Balance", min_value=0.0, step=10.0, value=float(d.balance))
                    apr_e = st.number_input("APR", min_value=0.0, max_value=50.0, step=0.1, value=float(d.apr_pct))
                    min_e = st.number_input("Min payment", min_value=0.0, step=5.0, value=float(d.min_payment))
                    c1, c2 = st.columns(2)
                    if c1.form_submit_button("Save"):
                        d.name = name_e
                        d.balance = bal_e
                        d.apr_pct = apr_e
                        d.min_payment = min_e
                        session.add(d); session.commit(); st.rerun()
                    if c2.form_submit_button("Delete", type="secondary"):
                        session.delete(d); session.commit(); st.rerun()

# ─── PAYOFF COMPARISON ────────────────────────────────────────
if debts:
    st.subheader("Payoff strategy comparison")
    extra = st.number_input(
        "Extra monthly payment ABOVE minimums ($)",
        min_value=0.0, step=25.0, value=100.0,
        help="The total monthly outlay = sum of minimums + this extra.",
    )

    debt_objs = [Debt(d.name, d.balance, d.apr_pct, d.min_payment) for d in debts]
    aval = simulate_payoff(debt_objs, extra_monthly=extra, strategy="avalanche")
    snow = simulate_payoff(debt_objs, extra_monthly=extra, strategy="snowball")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Avalanche (highest APR first)")
        st.caption("Mathematically optimal — saves the most interest.")
        if aval.months_to_debt_free > 0:
            st.metric("Debt-free in", f"{aval.months_to_debt_free} months ({aval.months_to_debt_free/12:.1f} yrs)")
            st.metric("Total interest paid", f"${aval.total_interest_paid:,.2f}")
            st.write("**Payoff order:** " + " → ".join(aval.order))
        else:
            st.warning("Not paid off within 50 years at this rate — increase payment.")

    with c2:
        st.markdown("### Snowball (smallest balance first)")
        st.caption("Psychologically optimal — quick wins build momentum (Kellogg study: higher adherence).")
        if snow.months_to_debt_free > 0:
            st.metric("Debt-free in", f"{snow.months_to_debt_free} months ({snow.months_to_debt_free/12:.1f} yrs)")
            st.metric("Total interest paid", f"${snow.total_interest_paid:,.2f}")
            st.write("**Payoff order:** " + " → ".join(snow.order))
        else:
            st.warning("Not paid off within 50 years at this rate — increase payment.")

    if aval.months_to_debt_free > 0 and snow.months_to_debt_free > 0:
        diff_interest = snow.total_interest_paid - aval.total_interest_paid
        diff_months = snow.months_to_debt_free - aval.months_to_debt_free
        st.info(
            f"**Tradeoff:** Avalanche saves **${diff_interest:,.2f}** in interest and finishes "
            f"**{diff_months} months earlier**. Snowball gives you your first paid-off debt sooner — "
            "pick avalanche if you'll stick with it, snowball if you need motivation."
        )

# ─── DTI ──────────────────────────────────────────────────────
st.subheader("Debt-to-Income (DTI) ratios")
st.caption("Mortgage lenders use these to qualify you. Targets: front-end <28%, back-end <36% (FHA up to 43%).")

s = get_settings()
# Annual gross approx = paycheck * 24 / 0.78 (assume 22% to taxes for gross)
default_gross_monthly = s.paycheck_net_amount * 2 / 0.78
with st.form("dti_form"):
    gross_monthly = st.number_input(
        "Gross monthly income (before tax) ($)",
        min_value=0.0, step=100.0, value=round(default_gross_monthly, 2),
    )
    housing_monthly = st.number_input("Housing PITI (rent/mortgage + tax + insurance, $)",
                                       min_value=0.0, step=50.0, value=0.0)
    other_debt_monthly = st.number_input(
        "Other monthly debt payments ($)",
        min_value=0.0,
        step=10.0,
        value=float(sum(d.min_payment for d in debts)) if debts else 0.0,
        help="Auto-filled from debt minimums above.",
    )
    if st.form_submit_button("Compute DTI"):
        fe = front_end_dti(housing_monthly, gross_monthly)
        be = back_end_dti(housing_monthly + other_debt_monthly, gross_monthly)
        fe_status = dti_status(fe, "front")
        be_status = dti_status(be, "back")
        color = {"OK": "green", "WARN": "orange", "OVER": "red"}
        c1, c2 = st.columns(2)
        c1.metric("Front-end DTI (housing)", f"{fe}%")
        c1.markdown(f"### :{color[fe_status]}[{fe_status}]")
        c1.caption("Target < 28%")
        c2.metric("Back-end DTI (all debt)", f"{be}%")
        c2.markdown(f"### :{color[be_status]}[{be_status}]")
        c2.caption("Target < 36% (FHA up to 43%)")
