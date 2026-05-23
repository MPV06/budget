import streamlit as st
import pandas as pd
from sqlmodel import select

from models.schema import BNPLPlan, BNPLInstallment
from services.bnpl_detector import project_schedule
from services.db import get_session
from services.ui_theme import apply_app_chrome

apply_app_chrome("BNPL — Budget", "💳")
st.markdown("# 💳 Buy Now, Pay Later")
st.caption("Affirm · Chase Pay-in-4 · Klarna · Afterpay installment tracking")

with get_session() as session:
    plans = session.exec(select(BNPLPlan).where(BNPLPlan.is_active == True)).all()  # noqa: E712

    st.subheader(f"Active plans ({len(plans)})")
    for plan in plans:
        with st.expander(
            f"{plan.provider.replace('_', ' ').title()} — {plan.merchant_name} "
            f"(${plan.original_amount:,.2f})"
        ):
            st.write(f"Payment: ${plan.payment_amount:,.2f} × {plan.total_payments} ({plan.cadence})")
            installments = session.exec(
                select(BNPLInstallment).where(BNPLInstallment.plan_id == plan.id)
                .order_by(BNPLInstallment.installment_number)
            ).all()
            if installments:
                st.dataframe(pd.DataFrame([{
                    "#": i.installment_number, "due": i.due_date,
                    "amount": i.amount, "status": i.status,
                } for i in installments]), use_container_width=True, hide_index=True)
            if st.button("Mark plan inactive", key=f"inact_{plan.id}"):
                plan.is_active = False
                session.add(plan); session.commit()
                st.rerun()

    st.subheader("Add plan manually")
    with st.form("add_bnpl"):
        provider = st.selectbox("Provider", ["affirm", "chase_pay_in_4", "klarna", "afterpay"])
        merchant = st.text_input("Merchant")
        original = st.number_input("Total purchase amount", min_value=0.0, step=10.0)
        n = st.number_input("Number of payments", min_value=2, max_value=24, step=1)
        per = st.number_input("Payment amount", min_value=0.0, step=5.0)
        cadence = st.selectbox("Cadence", ["biweekly", "monthly"])
        start = st.date_input("First payment date")
        if st.form_submit_button("Add plan"):
            plan = BNPLPlan(source="manual", provider=provider, merchant_name=merchant,
                            original_amount=original, total_payments=int(n),
                            payment_amount=per, cadence=cadence, start_date=start,
                            is_active=True)
            session.add(plan); session.commit(); session.refresh(plan)
            for inst in project_schedule(start, int(n), per, cadence):
                session.add(BNPLInstallment(plan_id=plan.id,
                                            installment_number=inst.installment_number,
                                            due_date=inst.due_date,
                                            amount=inst.amount,
                                            status="scheduled"))
            session.commit()
            st.success(f"Plan added with {n} installments.")
            st.rerun()
