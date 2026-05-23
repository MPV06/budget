from datetime import date

import pandas as pd
import streamlit as st

from services.config import get_settings
from services.db import get_session
from services.dashboard_data import build_dashboard_view, set_manual_balance
from services.paycheck_calendar import generate_paycheck_dates, next_paycheck_after

st.set_page_config(page_title="Dashboard — Budget", layout="wide")
st.title("Dashboard")

s = get_settings()
today = date.today()
cal = generate_paycheck_dates(start=date(today.year, today.month, 1), months=3)
np_ = next_paycheck_after(today, cal)

# Period end = the paycheck AFTER np_ (so this period = today -> np_, next period = np_ -> period_end)
later = [p for p in cal if p.actual_deposit_date > np_.actual_deposit_date]
period_end = later[0].actual_deposit_date if later else np_.actual_deposit_date

with get_session() as session:
    view = build_dashboard_view(
        session,
        today=today,
        next_paycheck=np_.actual_deposit_date,
        paycheck_amount=s.paycheck_net_amount,
        period_end=period_end,
    )

# ─── HEADLINE METRICS ──────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
col1.metric(
    "Guilt-free spending this paycheck",
    f"${view.leftover_this_paycheck:,.2f}",
    help=("Paycheck − bills − BNPL − envelopes. Per finance-psychology standards "
          "(Sethi): once obligations and savings are funded, this money is meant to "
          "be spent — without guilt."),
)
col2.metric(
    "Next paycheck",
    np_.actual_deposit_date.strftime("%a %b %d"),
    f"${view.paycheck_amount:,.2f}",
    help=f"Scheduled {np_.scheduled_date.strftime('%b %d')}",
)
if view.has_balance_source:
    col3.metric(
        "Safe to spend now",
        f"${view.safe_to_spend:,.2f}",
        help=f"Current balance (${view.balance:,.2f}) minus obligations before next paycheck.",
    )
else:
    col3.metric("Safe to spend now", "—",
                help="Enter your current checking balance below to enable.")

# ─── PAYCHECK BREAKDOWN ────────────────────────────────────────────
st.subheader("This paycheck's allocation")
bc1, bc2, bc3, bc4, bc5 = st.columns(5)
bc1.metric("Paycheck", f"${view.paycheck_amount:,.2f}")
bc2.metric("Bills", f"−${view.bills_this_period:,.2f}")
bc3.metric("BNPL", f"−${view.bnpl_this_period:,.2f}")
bc4.metric("Envelopes", f"−${view.envelopes_this_period:,.2f}")
bc5.metric("Guilt-free", f"${view.leftover_this_paycheck:,.2f}",
           delta_color="normal" if view.leftover_this_paycheck >= 0 else "inverse")

if view.leftover_this_paycheck < 0:
    st.error(
        f"⚠ You're **${abs(view.leftover_this_paycheck):,.2f} short** this paycheck. "
        "Trim envelopes, defer a BNPL, or reduce a discretionary bill."
    )

# ─── CONSCIOUS SPENDING PLAN (Sethi 4-bucket) ──────────────────────
if view.paycheck_amount > 0:
    st.subheader("Conscious Spending Plan (per Sethi standard)")
    st.caption(
        "Target allocation of net pay: **Fixed Costs 50–60% · Investments 10%+ · "
        "Savings 5–10% · Guilt-Free Spending 20–35%**. The word \"budget\" is taboo "
        "here — this is values-aligned spending, not restriction."
    )
    fixed_costs = view.bills_this_period + view.envelopes_this_period + view.bnpl_this_period
    fc_pct = fixed_costs / view.paycheck_amount * 100
    # In this app, we don't track separate investment / savings flows yet — show
    # the guilt-free pool and prompt the user to allocate from it.
    gf_pct = max(0, view.leftover_this_paycheck) / view.paycheck_amount * 100
    csp_df = pd.DataFrame([
        {"bucket": "Fixed Costs (bills + envelopes + BNPL)",
         "target": "50–60%", "actual_%": round(fc_pct, 1),
         "amount": round(fixed_costs, 2)},
        {"bucket": "Investments + Savings (allocate from guilt-free below)",
         "target": "15–20%", "actual_%": 0.0,
         "amount": 0.0},
        {"bucket": "Guilt-Free Spending (left after obligations)",
         "target": "20–35%", "actual_%": round(gf_pct, 1),
         "amount": round(max(0, view.leftover_this_paycheck), 2)},
    ])
    st.dataframe(csp_df, use_container_width=True, hide_index=True)
    if fc_pct > 60:
        st.warning(
            f"Fixed costs are **{fc_pct:.0f}%** of your paycheck — above the 60% ceiling. "
            "Per finance-psychology standards, this is the lever to pull: housing, debt, "
            "or subscriptions. Trimming a $5 latte won't fix a 70% fixed-cost ratio."
        )

# ─── 50/30/20 BREAKDOWN ─────────────────────────────────────────────
if view.fifty_thirty_twenty:
    st.subheader("50/30/20 check")
    f = view.fifty_thirty_twenty
    df = pd.DataFrame([
        {"bucket": "Needs", "target_%": 50.0, "actual_%": f.needs_pct,
         "amount": view.needs_total,
         "on_target": "✓" if f.on_target_needs else "✗"},
        {"bucket": "Wants", "target_%": 30.0, "actual_%": f.wants_pct,
         "amount": view.wants_total,
         "on_target": "✓" if f.on_target_wants else "✗"},
        {"bucket": "Savings", "target_%": 20.0, "actual_%": f.savings_pct,
         "amount": view.savings_total,
         "on_target": "✓" if f.on_target_savings else "✗"},
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)
    if not (f.on_target_needs and f.on_target_wants and f.on_target_savings):
        st.caption("✗ means you're more than 5 percentage points off the 50/30/20 target.")

# ─── UPCOMING BILLS / BNPL ─────────────────────────────────────────
left, right = st.columns(2)
with left:
    st.subheader(f"Bills before {np_.actual_deposit_date}")
    if view.upcoming_bills:
        st.dataframe(pd.DataFrame([
            {"due": b.due_date, "label": b.label, "amount": b.amount}
            for b in view.upcoming_bills
        ]), use_container_width=True, hide_index=True)
    else:
        st.info("No bills due before next paycheck.")
with right:
    st.subheader(f"BNPL before {np_.actual_deposit_date}")
    if view.upcoming_bnpl:
        st.dataframe(pd.DataFrame([
            {"due": i.due_date, "label": i.label, "amount": i.amount}
            for i in view.upcoming_bnpl
        ]), use_container_width=True, hide_index=True)
    else:
        st.info("No BNPL installments due before next paycheck.")

# ─── MANUAL BALANCE ENTRY (when not using Plaid) ───────────────────
with st.expander("Update current checking balance" + ("" if view.has_balance_source else "  ⚠ needed for safe-to-spend"),
                 expanded=not view.has_balance_source):
    st.write(
        "If you're not syncing real bank data via Plaid, enter your Chase checking balance "
        "here. Update it whenever you remember to keep \"safe to spend\" accurate."
    )
    new_bal = st.number_input("Current balance ($)",
                              min_value=0.0, step=10.0, value=float(view.balance))
    if st.button("Save balance"):
        with get_session() as session:
            set_manual_balance(session, new_bal)
        st.success(f"Balance saved: ${new_bal:,.2f}")
        st.rerun()
