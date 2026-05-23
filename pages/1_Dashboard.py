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

# ─── PALETTE ────────────────────────────────────────────────────────
# Consistent across all charts
PALETTE = {
    "Income":     "#3b82f6",   # blue
    "Bills":      "#ef4444",   # red
    "BNPL":       "#f97316",   # orange
    "Envelopes":  "#eab308",   # yellow
    "Guilt-free": "#22c55e",   # green
    "Savings":    "#10b981",   # emerald
}

st.title("💰 Budget Dashboard")
st.caption(f"As of **{date.today().strftime('%A, %B %d, %Y')}**")

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
            {"paycheck": label, "category": "Savings", "amount": b.savings_total, "order": 4},
            {"paycheck": label, "category": "Guilt-free",
             "amount": max(0, b.guilt_free), "order": 5},
        ])
    chart_df = pd.DataFrame(chart_rows)

    color_scale = alt.Scale(
        domain=["Bills", "BNPL", "Envelopes", "Savings", "Guilt-free"],
        range=["#ef4444", "#f97316", "#eab308", "#10b981", "#22c55e"],
    )
    chart = (
        alt.Chart(chart_df)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("amount:Q", title="Dollars", axis=alt.Axis(format="$,.0f")),
            y=alt.Y("paycheck:N", title="Paycheck (deposit date)",
                    sort=[b.deposit_date.strftime("%b %d") for b in breakdowns]),
            color=alt.Color("category:N", scale=color_scale,
                            sort=["Bills", "BNPL", "Envelopes", "Savings", "Guilt-free"],
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

# ─── WHERE YOUR MONEY GOES (donut) + CUMULATIVE SAVINGS (line) ───
if breakdowns:
    st.markdown("---")
    st.subheader("📊 Where your money goes & savings trajectory")

    donut_col, line_col = st.columns([1, 1])

    # ── DONUT: average paycheck allocation ──
    with donut_col:
        st.markdown("**Average paycheck allocation**")
        avg_bills = sum(b.bills_total for b in breakdowns) / len(breakdowns)
        avg_bnpl = sum(b.bnpl_total for b in breakdowns) / len(breakdowns)
        avg_env = sum(b.envelopes_allocated for b in breakdowns) / len(breakdowns)
        avg_sav = sum(b.savings_total for b in breakdowns) / len(breakdowns)
        avg_gf_pos = max(0, avg_gf)
        donut_data = pd.DataFrame([
            {"category": "Bills", "amount": avg_bills},
            {"category": "BNPL", "amount": avg_bnpl},
            {"category": "Envelopes", "amount": avg_env},
            {"category": "Savings", "amount": avg_sav},
            {"category": "Guilt-free", "amount": avg_gf_pos},
        ])
        donut_data = donut_data[donut_data["amount"] > 0]

        donut = (
            alt.Chart(donut_data)
            .mark_arc(innerRadius=70, outerRadius=130, cornerRadius=4, padAngle=0.02)
            .encode(
                theta=alt.Theta("amount:Q", stack=True),
                color=alt.Color(
                    "category:N",
                    scale=alt.Scale(
                        domain=["Bills", "BNPL", "Envelopes", "Savings", "Guilt-free"],
                        range=[PALETTE["Bills"], PALETTE["BNPL"],
                               PALETTE["Envelopes"], PALETTE["Savings"],
                               PALETTE["Guilt-free"]],
                    ),
                    legend=alt.Legend(title="Category", orient="bottom"),
                ),
                tooltip=["category", alt.Tooltip("amount:Q", format="$,.2f")],
            )
            .properties(height=320)
        )
        st.altair_chart(donut, use_container_width=True)

    # ── LINE: cumulative guilt-free / savings projection over next 12 paychecks ──
    with line_col:
        st.markdown("**Cumulative savings projection (12 paychecks)**")
        # Build longer schedule for projection
        long_cal = generate_paycheck_dates(start=date(today.year, today.month, 1), months=12)
        with get_session() as sess2:
            long_breakdowns = build_paycheck_breakdowns(
                sess2, long_cal, today=today,
                paycheck_amount=s.paycheck_net_amount, n=12,
            )
        if long_breakdowns:
            cum_rows = []
            running = 0.0
            for b in long_breakdowns:
                running += b.guilt_free
                cum_rows.append({
                    "paycheck": b.deposit_date,
                    "cumulative": round(running, 2),
                    "per_paycheck": b.guilt_free,
                })
            cum_df = pd.DataFrame(cum_rows)

            line = (
                alt.Chart(cum_df)
                .mark_area(
                    line={"color": PALETTE["Savings"], "strokeWidth": 3},
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
                    x=alt.X("paycheck:T", title="Paycheck deposit date",
                            axis=alt.Axis(format="%b %d")),
                    y=alt.Y("cumulative:Q", title="Cumulative savings",
                            axis=alt.Axis(format="$,.0f")),
                    tooltip=[
                        alt.Tooltip("paycheck:T", format="%b %d, %Y"),
                        alt.Tooltip("cumulative:Q", format="$,.2f", title="Cumulative"),
                        alt.Tooltip("per_paycheck:Q", format="$,.2f", title="This paycheck"),
                    ],
                )
                .properties(height=320)
            )
            zero_line = (
                alt.Chart(pd.DataFrame({"y": [0]}))
                .mark_rule(color="#94a3b8", strokeDash=[3, 3])
                .encode(y="y:Q")
            )
            st.altair_chart(line + zero_line, use_container_width=True)
            total_12 = round(running, 2)
            st.caption(f"**Projected 6-month total: ${total_12:,.2f}** at current pace.")

# ─── PER-PAYCHECK DETAIL — Excel-style transparent math ───────────
for i, b in enumerate(breakdowns):
    is_short = b.guilt_free < 0
    badge = "🔴" if is_short else "🟢"
    title = (
        f"{badge}  Paycheck {i+1}: **{b.deposit_date.strftime('%a %b %d')}** "
        f"(period {b.period_start.strftime('%b %d')} → {b.period_end.strftime('%b %d')}, "
        f"{b.days_in_period} days)  ·  Guilt-free: **${b.guilt_free:,.2f}**"
    )
    with st.expander(title, expanded=(i == 0)):
        # ── Top-line numbers ──
        m1, m2, m3 = st.columns(3)
        m1.metric("Budget (guilt-free)", f"${b.guilt_free:,.2f}",
                  delta_color="normal" if not is_short else "inverse")
        m2.metric("Days left in period", b.days_in_period)
        m3.metric("Daily spending allowance", f"${b.daily_guilt_free:,.2f}",
                  help="Guilt-free ÷ days. If you spend this much per day, you'll exactly hit 0 at next paycheck.")

        if is_short:
            st.error(
                f"This paycheck is **${abs(b.guilt_free):,.2f} short**. "
                "Cover it from prior-paycheck leftover, defer a BNPL, or trim an envelope."
            )

        # ── Transparent math table — every line, then subtotals, then leftover ──
        st.markdown("##### The math")
        rows = [{"category": "Income", "item": "Paycheck",
                 "due": b.deposit_date, "amount": b.paycheck_amount}]
        for bill in b.bills:
            rows.append({"category": "Bills", "item": bill.label,
                         "due": bill.due_date, "amount": -bill.amount})
        for bnpl in b.bnpl:
            rows.append({"category": "BNPL", "item": bnpl.label,
                         "due": bnpl.due_date, "amount": -bnpl.amount})
        for env in b.envelopes:
            rows.append({"category": "Envelopes", "item": env.label,
                         "due": None, "amount": -env.amount})
        for sav in b.savings:
            rows.append({"category": "💎 Savings", "item": sav.label,
                         "due": sav.due_date, "amount": -sav.amount})

        df = pd.DataFrame(rows)
        if not df.empty:
            df["amount_fmt"] = df["amount"].apply(lambda x: f"${x:,.2f}" if x >= 0 else f"−${abs(x):,.2f}")
            display = df[["category", "item", "due", "amount_fmt"]].rename(
                columns={"amount_fmt": "amount"}
            )
            st.dataframe(display, use_container_width=True, hide_index=True)

        # ── Subtotal box — matches user's Excel format ──
        st.markdown("##### Subtotals")
        sub_rows = [
            {"line": "Paycheck", "amount": f"+${b.paycheck_amount:,.2f}"},
            {"line": f"Bills ({len(b.bills)} items)", "amount": f"−${b.bills_total:,.2f}"},
            {"line": f"BNPL ({len(b.bnpl)} items)", "amount": f"−${b.bnpl_total:,.2f}"},
            {"line": f"Envelopes ({len(b.envelopes)} items)", "amount": f"−${b.envelopes_allocated:,.2f}"},
            {"line": f"💎 Savings ({len(b.savings)} items)", "amount": f"−${b.savings_total:,.2f}"},
            {"line": "── TOTAL OBLIGATIONS ──", "amount": f"−${b.obligations_total:,.2f}"},
            {"line": "💰 GUILT-FREE LEFT", "amount": f"${b.guilt_free:,.2f}"},
        ]
        st.dataframe(pd.DataFrame(sub_rows), use_container_width=True, hide_index=True)

        # ── Per-category detail tables — now 4 columns ──
        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            st.markdown(f"**Bills · ${b.bills_total:,.2f}**")
            if b.bills:
                st.dataframe(pd.DataFrame([
                    {"due": x.due_date, "name": x.label, "amount": f"${x.amount:,.2f}"}
                    for x in b.bills
                ]), use_container_width=True, hide_index=True)
            else:
                st.caption("No bills this paycheck.")
        with col_b:
            st.markdown(f"**BNPL · ${b.bnpl_total:,.2f}**")
            if b.bnpl:
                st.dataframe(pd.DataFrame([
                    {"due": x.due_date, "name": x.label, "amount": f"${x.amount:,.2f}"}
                    for x in b.bnpl
                ]), use_container_width=True, hide_index=True)
            else:
                st.caption("No BNPL this paycheck.")
        with col_c:
            st.markdown(f"**Envelopes · ${b.envelopes_allocated:,.2f}**")
            if b.envelopes:
                st.dataframe(pd.DataFrame([
                    {"envelope": x.label, "per_paycheck": f"${x.amount:,.2f}"}
                    for x in b.envelopes
                ]), use_container_width=True, hide_index=True)
            else:
                st.caption("No envelopes set up.")
        with col_d:
            st.markdown(f"**💎 Savings · ${b.savings_total:,.2f}**")
            if b.savings:
                st.dataframe(pd.DataFrame([
                    {"name": x.label, "amount": f"${x.amount:,.2f}"}
                    for x in b.savings
                ]), use_container_width=True, hide_index=True)
            else:
                st.caption("No savings transfers — add some on the Save tab.")

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
