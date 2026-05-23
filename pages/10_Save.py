"""Save tab — everything savings-related in one view."""
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from models.schema import RecurringBill
from services.config import get_settings
from services.db import get_session
from services.savings_summary import (
    build_summary, add_per_paycheck_save_line, savings_rate_pct,
)
from services.ui_theme import apply_app_chrome, PALETTE as _P

apply_app_chrome("Save — Budget", "💎")

# Palette — pulled from shared theme
SAVINGS_GREEN = _P["savings"]
EMERGENCY_BLUE = _P["income"]
GOAL_PURPLE = "#a855f7"   # only used on this page
GENERIC_GRAY = _P["text_muted"]

st.markdown("# 💎 Save")
st.caption(f"All savings activity in one view · As of **{date.today().strftime('%B %d, %Y')}**")

s = get_settings()

with get_session() as session:
    summary = build_summary(session)

# ─── HEADLINE METRICS ─────────────────────────────────────────────
rate = savings_rate_pct(summary.per_paycheck_savings_total, s.paycheck_net_amount)

c1, c2, c3, c4 = st.columns(4)
c1.metric(
    "Per paycheck",
    f"${summary.per_paycheck_savings_total:,.2f}",
    help="Sum of every active bill marked as 'savings', normalized to per-paycheck.",
)
c2.metric(
    "Per month",
    f"${summary.per_month_savings_total:,.2f}",
    help="Per-paycheck × 2 (semi-monthly = 2 paychecks/month).",
)
c3.metric(
    "Per year",
    f"${summary.per_year_savings_total:,.2f}",
    help="Annualized savings rate at your current commitments.",
)
if rate is not None:
    benchmark = "FIRE 🔥" if rate >= 25 else ("on track ✓" if rate >= 15 else "below 15% target")
    c4.metric(
        "Savings rate",
        f"{rate}%",
        delta=benchmark,
        delta_color=("normal" if rate >= 15 else "inverse"),
        help="Savings ÷ gross income. Standard targets: 15% min, 25–50% FIRE.",
    )

# ─── ASSETS ALREADY SAVED ─────────────────────────────────────────
st.markdown("---")
st.subheader("💰 Assets already saved")
a1, a2, a3 = st.columns(3)
a1.metric(
    "Emergency fund",
    f"${summary.emergency_fund_balance:,.2f}",
    f"Target: ${summary.emergency_fund_target:,.2f}" if summary.emergency_fund_target else None,
)
a2.metric(
    "Named goals saved",
    f"${summary.goals_saved_total:,.2f}",
    f"{len(summary.goals)} active goal(s)" if summary.goals else "no goals yet",
)
a3.metric(
    "Total saved",
    f"${summary.total_assets_saved:,.2f}",
    help="Emergency fund + sum of named-goal balances.",
)

# ─── SAVINGS BREAKDOWN DONUT ─────────────────────────────────────
st.markdown("---")
st.subheader("📊 Where your savings live")

donut_rows = []
if summary.emergency_fund_balance > 0:
    donut_rows.append({"category": "Emergency Fund",
                       "amount": summary.emergency_fund_balance,
                       "color": EMERGENCY_BLUE})
for g in summary.goals:
    if g.current_balance > 0:
        donut_rows.append({"category": g.name, "amount": g.current_balance,
                           "color": GOAL_PURPLE})

if donut_rows:
    donut_df = pd.DataFrame(donut_rows)
    donut = (
        alt.Chart(donut_df)
        .mark_arc(innerRadius=80, outerRadius=150, cornerRadius=4, padAngle=0.02)
        .encode(
            theta=alt.Theta("amount:Q", stack=True),
            color=alt.Color(
                "category:N",
                scale=alt.Scale(range=[r["color"] for r in donut_rows]),
                legend=alt.Legend(title="Bucket", orient="right"),
            ),
            tooltip=["category", alt.Tooltip("amount:Q", format="$,.2f")],
        )
        .properties(height=340)
    )
    st.altair_chart(donut, use_container_width=True)
else:
    st.info(
        "Nothing tracked yet. Set up your emergency fund and named goals first — "
        "see the **Emergency Fund** and **Goals** pages."
    )

# ─── PROJECTION CHART ─────────────────────────────────────────────
if summary.per_paycheck_savings_total > 0:
    st.markdown("---")
    st.subheader("📈 Savings projection at current pace")

    horizon_months = st.slider("Project forward how many months?",
                                min_value=3, max_value=60, value=12)
    monthly_save = summary.per_month_savings_total
    starting = summary.total_assets_saved

    projection_rows = []
    cum = starting
    today = date.today()
    for m in range(horizon_months + 1):
        # Compound modestly at 4% APY (HYSA-typical)
        if m > 0:
            cum = cum * (1 + 0.04 / 12) + monthly_save
        projection_rows.append({
            "month": today.replace(day=1) + pd.DateOffset(months=m),
            "balance": round(cum, 2),
            "contributed": round(starting + monthly_save * m, 2),
        })
    proj_df = pd.DataFrame(projection_rows)

    area = (
        alt.Chart(proj_df)
        .mark_area(
            line={"color": SAVINGS_GREEN, "strokeWidth": 3},
            color=alt.Gradient(
                gradient="linear",
                stops=[
                    alt.GradientStop(color="#10b98155", offset=0),
                    alt.GradientStop(color="#10b98100", offset=1),
                ],
                x1=1, x2=1, y1=1, y2=0,
            ),
        )
        .encode(
            x=alt.X("month:T", title="Month", axis=alt.Axis(format="%b %Y")),
            y=alt.Y("balance:Q", title="Balance", axis=alt.Axis(format="$,.0f")),
            tooltip=[
                alt.Tooltip("month:T", format="%b %Y"),
                alt.Tooltip("balance:Q", format="$,.2f", title="With 4% APY"),
                alt.Tooltip("contributed:Q", format="$,.2f", title="Contributions only"),
            ],
        )
        .properties(height=320)
    )
    st.altair_chart(area, use_container_width=True)

    final = proj_df.iloc[-1]
    st.caption(
        f"In {horizon_months} months at this pace, you'll have **${final['balance']:,.2f}** "
        f"(${final['contributed']:,.2f} contributions + ~${final['balance'] - final['contributed']:,.2f} interest at 4% APY)."
    )

# ─── PER-PAYCHECK SAVE LINES (toggle/edit/delete) ────────────────
st.markdown("---")
st.subheader("📝 Your per-paycheck savings transfers")

if summary.per_paycheck_savings_lines:
    st.caption(
        "These are the active 'savings' bills that automatically deduct from each paycheck "
        "and contribute to your savings rate. Manage them on the **Bills** page."
    )
    for line in summary.per_paycheck_savings_lines:
        c1, c2 = st.columns([3, 1])
        c1.markdown(f"💵 **{line.label}** · per paycheck")
        c2.markdown(f"**${line.amount:,.2f}**")
else:
    st.info(
        "No per-paycheck savings transfers yet. Add one below — it's the easiest way "
        "to commit to saving every time you get paid (per finance-psychology 'pay-yourself-first' principle)."
    )

# ─── QUICK ADD ────────────────────────────────────────────────────
with st.expander("➕ Add a per-paycheck savings transfer", expanded=not bool(summary.per_paycheck_savings_lines)):
    st.markdown(
        "**Pay-yourself-first**: schedule a fixed amount to 'save' every paycheck. "
        "It'll appear as a bill on your Bills page with category=`savings` and "
        "cadence=`semi_monthly`, deducting from every paycheck."
    )
    with st.form("quick_save"):
        c1, c2 = st.columns(2)
        save_name = c1.text_input("Name", value="Save",
                                   help="e.g., 'Emergency fund transfer' or 'Vacation fund'")
        save_amt = c2.number_input("Amount per paycheck ($)",
                                     min_value=0.0, step=25.0, value=250.0)
        if st.form_submit_button("Create"):
            if save_amt > 0 and save_name.strip():
                with get_session() as ses2:
                    add_per_paycheck_save_line(ses2, name=save_name.strip(), amount=save_amt)
                st.success(f"Created: {save_name} — ${save_amt:,.2f} every paycheck.")
                st.rerun()
            else:
                st.error("Need both a name and a positive amount.")

# ─── NAMED GOALS PROGRESS ─────────────────────────────────────────
if summary.goals:
    st.markdown("---")
    st.subheader("🎯 Named goals progress")
    for g in summary.goals:
        pct = min(g.current_balance / g.target_amount, 1.0) if g.target_amount > 0 else 0.0
        c1, c2, c3 = st.columns([3, 2, 2])
        c1.markdown(f"**{g.name}**")
        c1.caption(f"Deadline: {g.target_date}")
        c2.metric("Saved", f"${g.current_balance:,.0f}",
                  f"of ${g.target_amount:,.0f}")
        c3.metric("Progress", f"{pct*100:.0f}%")
        st.progress(pct)
    st.caption("👉 Manage / contribute on the **Goals** page.")

# ─── PRIORITY REMINDER ────────────────────────────────────────────
st.markdown("---")
st.subheader("📋 Savings priority (per savings-goals standard)")
st.markdown(
    """
    Fund in this order — each step is cheap insurance against a setback:

    1. **Emergency fund** at 3–6 months of essentials → Emergency Fund page
    2. **Employer 401(k) match** (50–100% instant return — free money)
    3. **Debt > 6–8% APR** paid down aggressively → Debt page
    4. **HSA maxed** (if eligible — triple tax advantage)
    5. **Roth IRA contribution** ($7,000/year 2025)
    6. **401(k) maxed** beyond the match ($23,000/year 2025)
    7. **Named goals** below → Goals page

    Savings rate benchmarks: **15% gross minimum** for retirement on track, 25–50% for FIRE.
    """
)
