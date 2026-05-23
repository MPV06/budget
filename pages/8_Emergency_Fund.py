"""Emergency fund sizing and runway tracker (3-6 months of essentials)."""
from datetime import date

import streamlit as st
from sqlmodel import select

from models.schema import RecurringBill, Envelope, SyncState
from services.db import get_session
from services.emergency_fund import size_emergency_fund, months_of_runway
from services.ui_theme import apply_app_chrome

apply_app_chrome("Emergency Fund — Budget", "🛡️")
st.markdown("# 🛡️ Emergency Fund")
st.caption(
    "3–6 months of *essential* expenses (housing, food, utilities, insurance, "
    "transportation, minimum debt payments) — NOT total spending. Exclude dining out, "
    "subscriptions you can cancel, entertainment, and shopping."
)

ESSENTIALS_KEY = "monthly_essentials_override"
EF_BALANCE_KEY = "emergency_fund_balance"
EF_STABILITY_KEY = "income_stability"

with get_session() as session:
    # Auto-compute monthly essentials from bills marked 'needs' + envelope 'needs' buckets
    bills = session.exec(select(RecurringBill).where(RecurringBill.is_active == True)).all()  # noqa: E712

    def _to_monthly(amount: float, cadence: str) -> float:
        c = (cadence or "monthly").lower()
        if c == "monthly":
            return amount
        if c == "weekly":
            return amount * 52 / 12
        if c == "biweekly":
            return amount * 26 / 12
        if c == "semi_monthly":
            return amount * 2
        if c == "annual":
            return amount / 12
        return amount

    auto_essentials = sum(
        _to_monthly(b.amount, b.cadence) for b in bills if b.category == "needs"
    )
    envelopes = session.exec(select(Envelope)).all()
    auto_essentials += sum(
        ((e.user_override if e.user_override is not None else e.current_budget_per_paycheck) * 2)
        for e in envelopes if e.bucket == "needs"
    )

    # Persisted override / stability
    override_row = session.exec(select(SyncState).where(SyncState.key == ESSENTIALS_KEY)).first()
    monthly_essentials = float(override_row.value) if override_row else round(auto_essentials, 2)

    bal_row = session.exec(select(SyncState).where(SyncState.key == EF_BALANCE_KEY)).first()
    ef_balance = float(bal_row.value) if bal_row else 0.0

    stab_row = session.exec(select(SyncState).where(SyncState.key == EF_STABILITY_KEY)).first()
    stability = stab_row.value if stab_row else "single_stable"

# ─── INPUTS ─────────────────────────────────────────────────────────
with st.form("ef_inputs"):
    st.subheader("Inputs")
    c1, c2 = st.columns(2)
    monthly_essentials_in = c1.number_input(
        "Monthly essential expenses ($)",
        min_value=0.0, step=50.0, value=float(monthly_essentials),
        help=f"Auto-computed from 'needs' bills + envelopes: ${auto_essentials:,.2f}. Override if needed.",
    )
    ef_balance_in = c2.number_input(
        "Current emergency-fund balance ($)",
        min_value=0.0, step=100.0, value=float(ef_balance),
    )
    stability_options = {
        "dual_stable": "Dual income, both stable",
        "single_stable": "Single income, stable job",
        "variable": "Variable income (commission/freelance/gig)",
        "high_risk": "High job-search risk (executive/niche)",
    }
    stability_in = st.selectbox(
        "Income stability",
        options=list(stability_options.keys()),
        index=list(stability_options.keys()).index(stability),
        format_func=lambda k: stability_options[k],
    )
    if st.form_submit_button("Save"):
        with get_session() as s:
            for key, val in [
                (ESSENTIALS_KEY, monthly_essentials_in),
                (EF_BALANCE_KEY, ef_balance_in),
                (EF_STABILITY_KEY, stability_in),
            ]:
                row = s.exec(select(SyncState).where(SyncState.key == key)).first()
                if row is None:
                    s.add(SyncState(key=key, value=str(val)))
                else:
                    row.value = str(val)
                    s.add(row)
            s.commit()
        st.success("Saved.")
        st.rerun()

# ─── TARGET ─────────────────────────────────────────────────────────
target = size_emergency_fund(monthly_essentials=monthly_essentials, stability=stability)
runway = months_of_runway(balance=ef_balance, monthly_essentials=monthly_essentials)
progress = min(1.0, ef_balance / target.target_amount) if target.target_amount > 0 else 0.0

st.subheader("Target")
st.caption(target.rationale)

c1, c2, c3 = st.columns(3)
c1.metric("Recommended target", f"${target.target_amount:,.2f}",
          f"{target.months_recommended} months of essentials")
c2.metric("Current balance", f"${ef_balance:,.2f}",
          f"{runway:.1f} months of runway" if runway != float("inf") else "∞")
c3.metric("To go", f"${max(0, target.target_amount - ef_balance):,.2f}",
          f"{(progress*100):.0f}% funded")
st.progress(progress)

if ef_balance < target.target_low:
    st.error(
        f"⚠ Below the minimum ({target.months_low} months = ${target.target_low:,.2f}). "
        "Per emergency-fund standards, this is the **highest-priority savings goal** — "
        "fund this before investing or paying extra on low-rate debt."
    )
elif ef_balance < target.target_amount:
    st.warning(f"Between minimum and recommended. Keep building toward ${target.target_amount:,.2f}.")
else:
    st.success(f"At or above recommended. Excess can flow to other goals or investments.")

# ─── TIERED STRUCTURE ─────────────────────────────────────────────
st.subheader("Tiered allocation (recommended)")
tier1 = monthly_essentials * 1
tier2 = monthly_essentials * 3
tier3 = max(0, target.target_amount - tier1 - tier2)
st.markdown(
    f"""
| Tier | Vehicle | Amount | Liquidity | Why |
|---|---|---|---|---|
| **1 — Immediate** | Checking / regular savings | **${tier1:,.0f}** (1 mo) | Instant | Sudden expenses |
| **2 — Short-term** | High-yield savings (HYSA) ~4-5% APY | **${tier2:,.0f}** (3 mo) | 1–2 business days | Core reserves |
| **3 — Extended** | T-bill ladder or short-term CDs | **${tier3:,.0f}** | Days to weeks | Higher yield |
"""
)
st.caption("Don't keep your emergency fund in stocks, long-term bonds, or crypto — those can lose value when you need them most.")

# ─── REPLENISHMENT ─────────────────────────────────────────────
if ef_balance < target.target_amount:
    shortfall = target.target_amount - ef_balance
    st.subheader("Replenishment plan")
    months_to_full = st.slider("Months to rebuild", 3, 36, value=12)
    monthly_contribution = shortfall / months_to_full
    st.info(
        f"Save **${monthly_contribution:,.2f}/month** for {months_to_full} months "
        f"to reach the ${target.target_amount:,.2f} target. "
        "Pause discretionary savings and redirect windfalls (tax refund, bonus) to accelerate."
    )
