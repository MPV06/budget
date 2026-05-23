"""Named savings goals with required-monthly PMT calculations.

Priority order (per savings-goals standard):
  1. Emergency fund (3-6 mo) ── see Emergency Fund page
  2. Employer match
  3. High-interest debt payoff ── see Debt page
  4. HSA
  5. Max retirement
  6. Education funding
  7. Other goals
"""
from datetime import date, timedelta

import streamlit as st
import pandas as pd
from sqlmodel import select

from models.schema import SavingsGoal
from services.db import get_session
from services.savings_goal import build_plan, required_monthly_savings, months_until
from services.ui_theme import apply_app_chrome

apply_app_chrome("Goals — Budget", "🎯")
st.markdown("# 🎯 Savings Goals")
st.caption(
    "Per the savings-goals standard: fund in **priority order** — emergency fund first, "
    "then employer 401(k) match, then high-interest debt, then retirement, then everything else."
)

with st.expander("📋 Priority checklist (the \\$30,000 questions)", expanded=False):
    st.markdown(
        """
        Before optimizing $5 subscriptions, make sure you've done the big-lever moves:

        - [ ] **Emergency fund** at 3–6 months of essentials → see *Emergency Fund* page
        - [ ] **Full employer 401(k) match captured** (50–100% instant return)
        - [ ] **All debt > 6–8% APR being paid down aggressively** → see *Debt* page
        - [ ] **HSA maxed** (if eligible — triple tax advantage)
        - [ ] **Roth IRA contribution** (\\$7,000/year 2025 limit)
        - [ ] **401(k) maxed** beyond the match (\\$23,000/year 2025 limit)
        - [ ] **Named goals below** (home, vacation, etc.) — funded with what remains

        Savings rate benchmark: **15% of gross** is the minimum for retirement on track; 25–50% is FIRE territory.
        """
    )

today = date.today()

with get_session() as session:
    goals = session.exec(
        select(SavingsGoal).where(SavingsGoal.is_active == True)  # noqa: E712
        .order_by(SavingsGoal.priority, SavingsGoal.target_date)
    ).all()

    # ─── ACTIVE GOALS ──────────────────────────────────────────────
    st.subheader(f"Active goals ({len(goals)})")
    if goals:
        rows = []
        for g in goals:
            months = months_until(g.target_date, today)
            pmt = required_monthly_savings(
                target=g.target_amount, current_balance=g.current_balance,
                months=max(months, 1), annual_return_pct=4.0,
            )
            progress = (g.current_balance / g.target_amount * 100) if g.target_amount > 0 else 0
            rows.append({
                "name": g.name,
                "target": g.target_amount,
                "saved": g.current_balance,
                "progress_%": round(progress, 1),
                "deadline": g.target_date,
                "months_left": months,
                "needed_per_mo": pmt,
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        total_pmt = sum(r["needed_per_mo"] for r in rows)
        st.metric("Total required monthly", f"${total_pmt:,.2f}",
                  help="Sum of required monthly contributions across all active goals.")

    # ─── ADD GOAL ──────────────────────────────────────────────────
    with st.expander("Add a goal", expanded=not bool(goals)):
        with st.form("add_goal"):
            name = st.text_input("Goal name (e.g., 'Vacation', 'House down payment')")
            target = st.number_input("Target amount ($, in today's dollars)",
                                      min_value=0.0, step=100.0, value=1000.0)
            current = st.number_input("Already saved ($)", min_value=0.0, step=50.0, value=0.0)
            target_date_in = st.date_input("Target date",
                                            value=today + timedelta(days=365),
                                            min_value=today + timedelta(days=1))
            priority = st.slider("Priority (1 = highest)", min_value=1, max_value=10, value=5)
            notes = st.text_area("Notes (optional)", value="")
            if st.form_submit_button("Add goal"):
                session.add(SavingsGoal(
                    name=name, target_amount=target, current_balance=current,
                    target_date=target_date_in, priority=priority, notes=notes,
                    is_active=True,
                ))
                session.commit()
                st.success(f"Added: {name}")
                st.rerun()

    # ─── EDIT / DELETE ─────────────────────────────────────────────
    if goals:
        st.subheader("Edit / contribute / delete")
        for g in goals:
            with st.expander(f"{g.name} — ${g.current_balance:,.0f} / ${g.target_amount:,.0f} by {g.target_date}"):
                with st.form(f"edit_goal_{g.id}"):
                    name_e = st.text_input("Name", value=g.name)
                    target_e = st.number_input("Target ($)", min_value=0.0, step=100.0,
                                                value=float(g.target_amount))
                    current_e = st.number_input("Currently saved ($)", min_value=0.0, step=10.0,
                                                 value=float(g.current_balance))
                    target_date_e = st.date_input("Target date", value=g.target_date)
                    priority_e = st.slider("Priority", 1, 10, value=int(g.priority))
                    notes_e = st.text_area("Notes", value=g.notes or "")
                    contribute = st.number_input("Quick contribute ($)", min_value=0.0, step=10.0, value=0.0,
                                                  help="Adds to your saved balance (does not deduct from elsewhere).")
                    c1, c2 = st.columns(2)
                    if c1.form_submit_button("Save"):
                        g.name = name_e
                        g.target_amount = target_e
                        g.current_balance = current_e + contribute
                        g.target_date = target_date_e
                        g.priority = priority_e
                        g.notes = notes_e
                        session.add(g); session.commit(); st.rerun()
                    if c2.form_submit_button("Delete", type="secondary"):
                        session.delete(g); session.commit(); st.rerun()

        # ─── PROJECTION DETAIL ────────────────────────────────────
        st.subheader("Goal projections (inflation-adjusted, 4% APY assumed)")
        for g in goals:
            plan = build_plan(
                target_today_dollars=g.target_amount,
                current_balance=g.current_balance,
                target_date=g.target_date,
                today=today,
                affordable_monthly=0.0,  # we just want the calc, not the on_track flag
                annual_return_pct=4.0,
                inflation_pct=3.0,
            )
            st.markdown(
                f"**{g.name}:** target ${plan.target_amount_real:,.0f} today → "
                f"${plan.target_amount:,.0f} in {plan.months} months. "
                f"Need **${plan.required_monthly:,.2f}/month**."
            )
