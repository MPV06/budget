import streamlit as st
import pandas as pd
from sqlmodel import select, desc

from models.schema import Transaction, Envelope
from services.db import get_session

st.set_page_config(page_title="Transactions — Budget", layout="wide")
st.title("Transactions")

with get_session() as session:
    rows = session.exec(
        select(Transaction).order_by(desc(Transaction.posted_date)).limit(500)
    ).all()
    envs = {e.id: e.name for e in session.exec(select(Envelope)).all()}

    df = pd.DataFrame([{
        "date": t.posted_date, "merchant": t.merchant_name or t.name,
        "amount": t.amount, "plaid_cat": t.plaid_category,
        "envelope": envs.get(t.envelope_id, ""), "pending": t.pending,
    } for t in rows])

    search = st.text_input("Search merchant")
    if search and not df.empty:
        df = df[df["merchant"].str.contains(search, case=False, na=False)]

    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"Showing {len(df)} of last 500.")
