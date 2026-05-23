from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from services.config import get_settings
from services.db import get_session
from services.dashboard_data import build_dashboard_view, set_manual_balance
from services.paycheck_calendar import generate_paycheck_dates, next_paycheck_after
from services.paycheck_view import build_paycheck_breakdowns, average_guilt_free

st.set_page_config(page_title="Dashboard — Budget", layout="wide")
st.title("Dashboard")

s = get_settings()
today = date.today()
cal = generate_paycheck_dates(start=date(today.year, today.month, 1), months=4)
np_ = next_paycheck_after(today, cal)

later = [p for p in cal if p.actual_deposit_date > np_.actual_deposit_date]
period_end = later[0].actual_deposit_date if later else np_.actual_deposit_date

with get_session() as session:
    view = build_dashboard_view(
        session, today=today, next_paycheck=np_.actual_deposit_date,
        paycheck_amount=s.paycheck_net_amount, period_end=period_end,
    )
    breakdowns = build_paycheck_breakdowns(
        session, cal, today=today, paycheck_amount=s.paycheck_net_amount, n=4,
    )

avg_gf = average_guilt_free(breakdowns)

# ─── HEADLINE METRICS ──────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
col1.metric(
    "Avg guilt-free / paycheck",
    f"${avg_gf:,.2f}",
    help=("Average leftover across the next 4 paychecks AFTER bills, BNPL, and "
          "envelope budgets. This is your typical savings power per paycheck. "
          "Individual paychecks vary because rent hits one and not the other."),
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
                help="Enter your current checking balance at the bottom.")

st.markdown("---")

# ─── PER-PAYCHECK BREAKDOWN ───────────────────────────────────────
st.subheader("Per-paycheck breakdown")
st.caption(
    "Bills don't hit every paycheck evenly — rent likely lands on one of your two "
    "monthly paychecks, not both. The columns below show **what each upcoming "
    "paycheck actually has to cover** and what's left over."
)

if breakdowns:
    chart_rows = []
    for b in breakdowns:
        label = b.deposit_date.strftime("%b %d")
        chart_rows.extend([
            {"paycheck": label, "category": "Bills", "amount": b.bills_total, "order": 1},
            {"paycheck": label, "category": "BNPL", "amount": b.bnpl_total, "order": 2},
            {"paycheck": label, "category": "Envelopes", "amount": b.envelopes_allocated, "order": 3},
            {"paycheck": label, "category": "Guilt-free",
             "amount": max(0, b.guilt_free), "order": 4},
        ])
    chart_df = pd.DataFrame(chart_rows)

    color_scale = alt.Scale(
        domain=["Bills", "BNPL", "Envelopes", "Guilt-free"],
        range=["#ef4444", "#f97316", "#eab308", "#22c55e"],
    )
    chart = (
        alt.Chart(chart_df)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("amount:Q", title="Dollars", axis=alt.Axis(format="$,.0f")),
            y=alt.Y("paycheck:N", title="Paycheck (deposit date)",
                    sort=[b.deposit_date.strftime("%b %d") for b in breakdowns]),
            color=alt.Color("category:N", scale=color_scale,
                            sort=["Bills", "BNPL", "Envelopes", "Guilt-free"],
                            legend=alt.Legend(title="Allocation")),
            order=alt.Order("order:Q"),
            tooltip=["paycheck", "category", alt.Tooltip("amount:Q", format="$,.2f")],
        )
        .properties(height=max(220, 60 * len(breakdowns)))
    )

    # Reference line for paycheck total
    rule = (
        alt.Chart(pd.DataFrame({"x": [s.paycheck_net_amount]}))
        .mark_rule(strokeDash=[4, 4], color="#475569", strokeWidth=2)
        .encode(x="x:Q")
    )
    st.altair_chart(chart + rule, use_container_width=True)
    st.caption(
        f"Dashed line = your full paycheck (${s.paycheck_net_amount:,.2f}). "
        "If the colored bars exceed that line, that paycheck is short."
    )

# ─── PER-PAYCHECK DETAIL ──────────────────────────────────────────
for i, b in enumerate(breakdowns):
    is_short = b.guilt_free < 0
    badge = "🔴" if is_short else "🟢"
    title = (
        f"{badge}  Paycheck {i+1}: **{b.deposit_date.strftime('%a %b %d')}** "
        f"(scheduled {b.scheduled_date.strftime('%b %d')})  ·  "
        f"Guilt-free: **${b.guilt_free:,.2f}**"
    )
    with st.expander(title, expanded=(i == 0)):
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Paycheck", f"${b.paycheck_amount:,.2f}")
        m2.metric("Bills", f"−${b.bills_total:,.2f}")
        m3.metric("BNPL", f"−${b.bnpl_total:,.2f}")
        m4.metric("Envelopes", f"−${b.envelopes_allocated:,.2f}")
        m5.metric("Guilt-free", f"${b.guilt_free:,.2f}",
                  delta_color="normal" if not is_short else "inverse")

        if is_short:
            st.error(
                f"This paycheck is **${abs(b.guilt_free):,.2f} short**. "
                "Cover it from prior-paycheck leftover, defer a BNPL, or trim an envelope."
            )

        l, r = st.columns(2)
        with l:
            st.markdown("**Bills hitting this paycheck:**")
            if b.bills:
                st.dataframe(pd.DataFrame([
                    {"due": x.due_date, "name": x.label, "amount": x.amount}
                    for x in b.bills
                ]), use_container_width=True, hide_index=True)
            else:
                st.caption("None.")
        with r:
            st.markdown("**BNPL installments hitting this paycheck:**")
            if b.bnpl:
                st.dataframe(pd.DataFrame([
                    {"due": x.due_date, "name": x.label, "amount": x.amount}
                    for x in b.bnpl
                ]), use_container_width=True, hide_index=True)
            else:
                st.caption("None.")

st.markdown("---")

# ─── CONSCIOUS SPENDING PLAN ──────────────────────────────────────
if view.paycheck_amount > 0:
    st.subheader("Conscious Spending Plan (per Sethi standard, averaged)")
    st.caption(
        "Target allocation of net pay: **Fixed Costs 50–60% · Investments 10%+ · "
        "Savings 5–10% · Guilt-Free Spending 20–35%**. Computed against the average "
        "across upcoming paychecks (not just the next one)."
    )
    avg_bills = sum(b.bills_total for b in breakdowns) / max(len(breakdowns), 1)
    avg_bnpl = sum(b.bnpl_total for b in breakdowns) / max(len(breakdowns), 1)
    avg_env = sum(b.envelopes_allocated for b in breakdowns) / max(len(breakdowns), 1)
    fixed_costs = avg_bills + avg_bnpl + avg_env
    fc_pct = fixed_costs / view.paycheck_amount * 100
    gf_pct = max(0, avg_gf) / view.paycheck_amount * 100
    csp_df = pd.DataFrame([
        {"bucket": "Fixed Costs (avg bills + envelopes + BNPL)",
         "target": "50–60%", "actual_%": round(fc_pct, 1), "amount": round(fixed_costs, 2)},
        {"bucket": "Guilt-Free Spending (avg leftover, allocate to investments/savings first)",
         "target": "20–35%", "actual_%": round(gf_pct, 1), "amount": round(max(0, avg_gf), 2)},
    ])
    st.dataframe(csp_df, use_container_width=True, hide_index=True)
    if fc_pct > 60:
        st.warning(
            f"Average fixed costs are **{fc_pct:.0f}%** of your paycheck — above the 60% ceiling. "
            "The biggest lever is housing, debt, or subscriptions — not coffee."
        )

# ─── 50/30/20 CHECK (next paycheck specific) ──────────────────────
if view.fifty_thirty_twenty:
    st.subheader("50/30/20 check (next paycheck)")
    f = view.fifty_thirty_twenty
    df = pd.DataFrame([
        {"bucket": "Needs", "target_%": 50.0, "actual_%": f.needs_pct,
         "amount": view.needs_total, "on_target": "✓" if f.on_target_needs else "✗"},
        {"bucket": "Wants", "target_%": 30.0, "actual_%": f.wants_pct,
         "amount": view.wants_total, "on_target": "✓" if f.on_target_wants else "✗"},
        {"bucket": "Savings", "target_%": 20.0, "actual_%": f.savings_pct,
         "amount": view.savings_total, "on_target": "✓" if f.on_target_savings else "✗"},
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)
    if not (f.on_target_needs and f.on_target_wants and f.on_target_savings):
        st.caption("✗ means more than 5 percentage points off the 50/30/20 target.")

# ─── MANUAL BALANCE ENTRY ─────────────────────────────────────────
st.markdown("---")
with st.expander(
    "Update current checking balance" + ("" if view.has_balance_source else "  ⚠ needed for safe-to-spend"),
    expanded=not view.has_balance_source,
):
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
