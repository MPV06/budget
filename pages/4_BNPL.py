from collections import defaultdict
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st
from sqlmodel import select

from models.schema import BNPLPlan, BNPLInstallment
from services.bnpl_detector import project_schedule
from services.db import get_session
from services.ui_theme import apply_app_chrome, PALETTE as _P, kpi_card

apply_app_chrome("BNPL — Budget", "💳", current_nav="/BNPL")
st.markdown("# 💳 Buy Now, Pay Later")
st.caption("Affirm · Chase Pay-in-4 · Klarna · Afterpay installment tracking")

today = date.today()

with get_session() as session:
    plans = session.exec(
        select(BNPLPlan).where(BNPLPlan.is_active == True)  # noqa: E712
    ).all()
    installments = session.exec(
        select(BNPLInstallment).where(BNPLInstallment.status == "scheduled")
        .order_by(BNPLInstallment.due_date)
    ).all()
    # Pre-bucket installments by plan_id for fast lookup
    insts_by_plan = defaultdict(list)
    for i in installments:
        insts_by_plan[i.plan_id].append(i)

# ─── PLAN ANALYTICS ────────────────────────────────────────────────
plan_rows = []
for p in plans:
    insts = sorted(insts_by_plan.get(p.id, []), key=lambda x: x.due_date)
    if not insts:
        continue
    paid = p.total_payments - len(insts)
    remaining_amt = sum(i.amount for i in insts)
    payoff_date = insts[-1].due_date
    next_inst = insts[0]
    progress_pct = (paid / p.total_payments * 100) if p.total_payments else 0
    plan_rows.append({
        "plan": p,
        "paid": paid,
        "remaining_count": len(insts),
        "remaining_amount": round(remaining_amt, 2),
        "payoff_date": payoff_date,
        "next_due": next_inst.due_date,
        "next_amount": next_inst.amount,
        "progress_pct": progress_pct,
    })

# ─── HEADLINE KPIs ─────────────────────────────────────────────────
total_remaining = sum(r["remaining_amount"] for r in plan_rows)
total_installments_left = sum(r["remaining_count"] for r in plan_rows)
last_payoff = max((r["payoff_date"] for r in plan_rows), default=None)
months_until_debt_free = (
    (last_payoff.year - today.year) * 12 + (last_payoff.month - today.month)
    if last_payoff else 0
)
# Monthly avg over remaining horizon
horizon_months = max(months_until_debt_free, 1)
monthly_avg = total_remaining / horizon_months if horizon_months else 0

c1, c2, c3, c4 = st.columns(4)
with c1:
    kpi_card(
        "Total BNPL debt",
        f"${total_remaining:,.2f}",
        sub=f"{total_installments_left} installments remaining",
        accent="bnpl",
    )
with c2:
    kpi_card(
        "Active plans",
        f"{len(plans)}",
        sub=f"across {len(set(p.provider for p in plans))} provider(s)",
        accent="violet",
    )
with c3:
    if last_payoff:
        kpi_card(
            "Debt-free by",
            last_payoff.strftime("%b %Y"),
            sub=f"{months_until_debt_free} months from today",
            accent="savings",
            trend="up",
        )
    else:
        kpi_card("Debt-free by", "—", sub="No active plans", accent="muted")
with c4:
    kpi_card(
        "Avg monthly burden",
        f"${monthly_avg:,.2f}",
        sub=f"averaged across {horizon_months} months",
        accent="bills",
    )

st.markdown("---")

# ─── MONTHLY OBLIGATION CHART ──────────────────────────────────────
if installments:
    st.subheader("📅 Monthly BNPL obligations (next 18 months)")
    st.caption(
        "Stacked by provider so you can see when each commitment tapers off. "
        "The line shows the cumulative monthly burden falling as plans complete."
    )

    # Build monthly buckets
    monthly = defaultdict(lambda: defaultdict(float))
    plan_provider = {p.id: p.provider.replace("_", " ").title() for p in plans}
    for inst in installments:
        if inst.due_date < today:
            continue
        month_start = date(inst.due_date.year, inst.due_date.month, 1)
        if (month_start.year - today.year) * 12 + (month_start.month - today.month) >= 18:
            continue
        provider = plan_provider.get(inst.plan_id, "Unknown")
        monthly[month_start][provider] += inst.amount

    rows = []
    for month, providers in sorted(monthly.items()):
        for provider, amount in providers.items():
            rows.append({"month": month, "provider": provider, "amount": round(amount, 2)})

    if rows:
        df = pd.DataFrame(rows)
        # Color palette: warm hues for providers
        provider_colors = {
            "Affirm": _P["bnpl"],
            "Chase Pay In 4": _P["envelopes"],
            "Klarna": _P["violet"],
            "Afterpay": _P["cyan"],
        }
        domain = list(df["provider"].unique())
        range_ = [provider_colors.get(p, _P["muted"]) for p in domain]

        bars = (
            alt.Chart(df)
            .mark_bar(cornerRadiusEnd=3)
            .encode(
                x=alt.X("yearmonth(month):O", title=None,
                        axis=alt.Axis(format="%b %Y", labelAngle=-30)),
                y=alt.Y("amount:Q", title="Dollars due",
                        axis=alt.Axis(format="$,.0f")),
                color=alt.Color("provider:N",
                                scale=alt.Scale(domain=domain, range=range_),
                                legend=alt.Legend(title="Provider")),
                tooltip=[
                    alt.Tooltip("yearmonth(month):O", title="Month", format="%b %Y"),
                    alt.Tooltip("provider:N", title="Provider"),
                    alt.Tooltip("amount:Q", format="$,.2f", title="Total"),
                ],
            )
            .properties(height=320)
        )
        st.altair_chart(bars, use_container_width=True)

# ─── PROVIDER DONUT + PER-PLAN TABLE ───────────────────────────────
if plan_rows:
    donut_col, table_col = st.columns([1, 2])

    with donut_col:
        st.subheader("By provider")
        provider_total = defaultdict(float)
        for r in plan_rows:
            provider_total[r["plan"].provider.replace("_", " ").title()] += r["remaining_amount"]
        donut_df = pd.DataFrame([
            {"provider": k, "amount": round(v, 2)}
            for k, v in provider_total.items()
        ])
        provider_colors = {
            "Affirm": _P["bnpl"],
            "Chase Pay In 4": _P["envelopes"],
            "Klarna": _P["violet"],
            "Afterpay": _P["cyan"],
        }
        domain = donut_df["provider"].tolist()
        range_ = [provider_colors.get(p, _P["muted"]) for p in domain]
        donut = (
            alt.Chart(donut_df)
            .mark_arc(innerRadius=60, outerRadius=120, cornerRadius=3, padAngle=0.02)
            .encode(
                theta=alt.Theta("amount:Q", stack=True),
                color=alt.Color("provider:N",
                                scale=alt.Scale(domain=domain, range=range_),
                                legend=alt.Legend(title=None, orient="bottom")),
                tooltip=["provider", alt.Tooltip("amount:Q", format="$,.2f")],
            )
            .properties(height=300)
        )
        st.altair_chart(donut, use_container_width=True)

    with table_col:
        st.subheader("All plans — summary")
        summary = pd.DataFrame([
            {
                "merchant": r["plan"].merchant_name,
                "provider": r["plan"].provider.replace("_", " ").title(),
                "payment": f"${r['plan'].payment_amount:,.2f}",
                "paid": f"{r['paid']}/{r['plan'].total_payments}",
                "remaining $": f"${r['remaining_amount']:,.2f}",
                "next due": r["next_due"].strftime("%b %d"),
                "payoff": r["payoff_date"].strftime("%b %Y"),
            }
            for r in sorted(plan_rows, key=lambda x: x["payoff_date"])
        ])
        st.dataframe(summary, use_container_width=True, hide_index=True)

st.markdown("---")

# ─── PER-PLAN CARDS WITH PROGRESS ──────────────────────────────────
st.subheader(f"Plan details ({len(plans)})")

with get_session() as session:
    for r in sorted(plan_rows, key=lambda x: x["payoff_date"]):
        p = r["plan"]
        title = (
            f"{p.provider.replace('_', ' ').title()} · {p.merchant_name} · "
            f"**${r['remaining_amount']:,.2f}** remaining · payoff {r['payoff_date'].strftime('%b %d, %Y')}"
        )
        with st.expander(title):
            # Progress bar
            st.progress(r["progress_pct"] / 100,
                        text=f"{r['paid']}/{p.total_payments} payments made · "
                             f"{r['progress_pct']:.0f}% paid off")

            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.metric("Original", f"${p.original_amount:,.2f}")
            mc2.metric("Payment", f"${p.payment_amount:,.2f}",
                       help=f"{p.cadence}")
            mc3.metric("Next due", r["next_due"].strftime("%b %d"),
                       f"${r['next_amount']:,.2f}")
            mc4.metric("Payoff date", r["payoff_date"].strftime("%b %d, %Y"),
                       f"{r['remaining_count']} payments left")

            # Installments table
            insts = sorted(insts_by_plan.get(p.id, []), key=lambda x: x.due_date)
            if insts:
                inst_df = pd.DataFrame([{
                    "#": i.installment_number,
                    "due": i.due_date,
                    "amount": f"${i.amount:,.2f}",
                    "status": "⚠ overdue" if i.due_date < today else "scheduled",
                } for i in insts])
                st.dataframe(inst_df, use_container_width=True, hide_index=True)

            if st.button("Mark plan inactive", key=f"inact_{p.id}",
                         help="Stops counting this plan in budget calculations"):
                bound = session.exec(
                    select(BNPLPlan).where(BNPLPlan.id == p.id)
                ).first()
                if bound:
                    bound.is_active = False
                    session.add(bound); session.commit()
                    st.rerun()

if not plans:
    st.info("No active BNPL plans. Add one below.")

st.markdown("---")

# ─── ADD PLAN FORM ─────────────────────────────────────────────────
st.subheader("Add plan manually")
with st.form("add_bnpl"):
    f1, f2 = st.columns(2)
    provider = f1.selectbox("Provider",
                             ["affirm", "chase_pay_in_4", "klarna", "afterpay"])
    merchant = f2.text_input("Merchant (e.g., 'Amazon', 'Best Buy')")
    f3, f4, f5 = st.columns(3)
    original = f3.number_input("Total purchase", min_value=0.0, step=10.0)
    n = f4.number_input("# payments", min_value=2, max_value=24, step=1, value=4)
    per = f5.number_input("Each payment", min_value=0.0, step=5.0)
    f6, f7 = st.columns(2)
    cadence = f6.selectbox("Cadence", ["biweekly", "monthly"])
    start = f7.date_input("First payment date", value=today)
    if st.form_submit_button("Add plan", type="primary", use_container_width=True):
        with get_session() as session:
            plan = BNPLPlan(source="manual", provider=provider,
                             merchant_name=merchant,
                             original_amount=original,
                             total_payments=int(n),
                             payment_amount=per,
                             cadence=cadence, start_date=start,
                             is_active=True)
            session.add(plan); session.commit(); session.refresh(plan)
            for inst in project_schedule(start, int(n), per, cadence):
                session.add(BNPLInstallment(
                    plan_id=plan.id,
                    installment_number=inst.installment_number,
                    due_date=inst.due_date, amount=inst.amount,
                    status="scheduled",
                ))
            session.commit()
        st.success(f"Plan added with {n} installments. Payoff: "
                   f"{start.strftime('%b %Y')} + {n} {cadence}")
        st.rerun()
