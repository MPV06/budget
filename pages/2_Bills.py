import streamlit as st
import pandas as pd
from sqlmodel import select

from models.schema import RecurringBill
from services.db import get_session

st.set_page_config(page_title="Bills — Budget", layout="wide")
st.title("Bills")

with get_session() as session:
    bills = session.exec(select(RecurringBill)).all()

    unconfirmed = [b for b in bills if b.source == "plaid_auto" and not b.confirmed_by_user]
    confirmed = [b for b in bills if b.confirmed_by_user or b.source == "manual"]

    st.subheader(f"Unconfirmed auto-detected ({len(unconfirmed)})")
    if unconfirmed:
        for b in unconfirmed:
            cols = st.columns([3, 2, 2, 1, 1])
            cols[0].write(b.display_name)
            cols[1].write(f"${b.amount:,.2f} {b.cadence}")
            cols[2].write(f"next: {b.next_due_date}")
            if cols[3].button("Confirm", key=f"conf_{b.id}"):
                b.confirmed_by_user = True
                session.add(b); session.commit()
                st.rerun()
            if cols[4].button("Reject", key=f"rej_{b.id}"):
                b.is_active = False
                b.confirmed_by_user = True
                session.add(b); session.commit()
                st.rerun()
    else:
        st.info("Nothing pending.")

    st.subheader(f"Active bills ({len([b for b in confirmed if b.is_active])})")
    rows = [{
        "name": b.display_name, "amount": b.amount, "cadence": b.cadence,
        "next_due": b.next_due_date, "category": b.category,
        "source": b.source, "active": b.is_active,
    } for b in confirmed]
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.subheader("Add manual bill")
    with st.form("add_bill"):
        name = st.text_input("Name")
        amount = st.number_input("Amount", min_value=0.0, step=1.0)
        cadence = st.selectbox("Cadence", ["weekly", "biweekly", "semi_monthly", "monthly", "annual"])
        next_due = st.date_input("Next due date")
        category = st.selectbox("50/30/20 bucket", ["needs", "wants", "savings"])
        if st.form_submit_button("Add"):
            session.add(RecurringBill(
                source="manual", merchant_name=name, display_name=name,
                amount=amount, cadence=cadence, next_due_date=next_due,
                category=category, is_active=True, confirmed_by_user=True,
            ))
            session.commit()
            st.success("Added.")
            st.rerun()
