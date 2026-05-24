import streamlit as st
import pandas as pd
from sqlmodel import select

from models.schema import RecurringBill
from services.db import get_session
from services.ui_theme import apply_app_chrome

apply_app_chrome("Bills — Budget", "🧾", current_nav="/Bills")
st.markdown("# 🧾 Bills")
st.caption("Recurring obligations · Toggle off to see what cutting them saves you")

with st.expander("ℹ️  How bills assign to paychecks", expanded=False):
    st.markdown(
        """
        **Pick the cadence that matches how you actually pay the bill:**

        | Cadence | What it means | Example |
        |---|---|---|
        | `semi_monthly` | **Once per paycheck** (every check, regardless of date) | Gas $280, Allowance, Save, Haircut |
        | `monthly` | Once per month on a specific date — hits only the paycheck whose period contains that date | Rent (1st), Mortgage, Insurance, Subscriptions |
        | `biweekly` | Every 14 days from `next_due_date` | Some BNPL plans, weekly+ subscriptions |
        | `weekly` | Every 7 days | Daycare, gym day-passes |
        | `annual` | Once a year on a specific date | Property tax, AAA renewal |

        **Common mistakes:**
        - **Gas/Allowance/Haircut every paycheck?** Use `semi_monthly`, NOT `monthly`. Monthly would put it on only one of your two paychecks.
        - **"Save $X per paycheck"?** Add as a manual bill with `cadence=semi_monthly`, `category=savings`.
        - **Don't double-count:** if you have a Gas envelope AND a Gas bill, both deduct. Pick one — envelope (variable spend) OR bill (fixed transfer).

        `next_due_date` is anchoring: for `monthly` it's the next due date (e.g., next Rent date). For `semi_monthly` it doesn't matter much — the bill auto-emits every period.
        """
    )

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

    active = [b for b in confirmed if b.is_active]
    inactive = [b for b in confirmed if not b.is_active]

    # ─── ACTIVE BILLS (toggle ON) ─────────────────────────────────
    st.subheader(f"🟢 Active bills ({len(active)})")
    st.caption(
        "Toggle a bill OFF to see what your budget looks like without it — "
        "great for 'what if I cut this?' experiments. You can always toggle it back ON."
    )
    if active:
        from services.paycheck_view import advance_due_date
        from datetime import date as _date
        _today = _date.today()

        st.caption(
            "Click **✓ Paid** once you've paid a bill — the date advances to the next "
            "instance so it stops counting against your safe-to-spend."
        )
        # Sortable toggle list above the edit expanders
        for b in active:
            row = st.columns([0.5, 2.6, 1.4, 1.6, 1.8, 1.1])
            new_state = row[0].toggle("", value=True, key=f"tog_{b.id}",
                                       label_visibility="collapsed",
                                       help="Toggle OFF to exclude from budget calcs")
            row[1].markdown(f"**{b.display_name}**")
            row[2].markdown(f"${b.amount:,.2f}")
            row[3].markdown(f"`{b.cadence}`")
            overdue_badge = " ⚠" if b.next_due_date < _today else ""
            row[4].markdown(f"next: {b.next_due_date}{overdue_badge}")
            if row[5].button("✓ Paid", key=f"paid_{b.id}",
                              help=f"Advance next_due_date by 1 {b.cadence} period"):
                b.next_due_date = advance_due_date(b.next_due_date, b.cadence)
                session.add(b); session.commit()
                st.toast(f"✓ {b.display_name} marked paid — next due {b.next_due_date}")
                st.rerun()
            if not new_state:
                b.is_active = False
                session.add(b); session.commit()
                st.rerun()

        st.markdown("**Edit / delete individual bills:**")
        for b in active:
            with st.expander(
                f"{b.display_name} — ${b.amount:,.2f} {b.cadence} (next: {b.next_due_date})"
            ):
                with st.form(f"edit_{b.id}"):
                    name = st.text_input("Name", value=b.display_name)
                    amount = st.number_input("Amount", min_value=0.0, step=1.0, value=float(b.amount))
                    cadences = ["weekly", "biweekly", "semi_monthly", "monthly", "annual"]
                    cadence = st.selectbox("Cadence", cadences,
                                           index=cadences.index(b.cadence) if b.cadence in cadences else 3)
                    next_due = st.date_input("Next due date", value=b.next_due_date)
                    buckets = ["needs", "wants", "savings"]
                    category = st.selectbox("50/30/20 bucket", buckets,
                                            index=buckets.index(b.category) if b.category in buckets else 0)
                    c1, c2 = st.columns(2)
                    if c1.form_submit_button("Save changes"):
                        b.display_name = name
                        b.merchant_name = name
                        b.amount = amount
                        b.cadence = cadence
                        b.next_due_date = next_due
                        b.category = category
                        session.add(b); session.commit()
                        st.success("Saved.")
                        st.rerun()
                    if c2.form_submit_button("Delete bill", type="secondary"):
                        session.delete(b); session.commit()
                        st.success("Deleted.")
                        st.rerun()
    else:
        st.info("No active bills yet.")

    # ─── HIDDEN / INACTIVE BILLS (toggle OFF) ─────────────────────
    if inactive:
        # Compute hypothetical savings if all inactive were re-enabled
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

        total_hidden_monthly = sum(_to_monthly(b.amount, b.cadence) for b in inactive)

        st.markdown("---")
        st.subheader(f"🔴 Hidden bills ({len(inactive)})")
        st.success(
            f"💸 By hiding these, you're saving **${total_hidden_monthly:,.2f}/month** "
            f"(**${total_hidden_monthly * 12:,.2f}/year**) in your budget projections."
        )
        st.caption("Toggle ON to add it back to your budget. Or delete permanently.")

        for b in inactive:
            monthly_eq = _to_monthly(b.amount, b.cadence)
            row = st.columns([0.7, 3, 2, 2, 1])
            new_state = row[0].toggle("", value=False, key=f"tog_off_{b.id}",
                                       label_visibility="collapsed",
                                       help="Toggle ON to restore to budget")
            row[1].markdown(f"~~{b.display_name}~~")
            row[2].markdown(f"~~${b.amount:,.2f}~~")
            row[3].markdown(f"_${monthly_eq:,.2f}/mo_")
            if row[4].button("🗑", key=f"del_off_{b.id}", help="Delete permanently"):
                session.delete(b); session.commit()
                st.rerun()
            if new_state:
                b.is_active = True
                session.add(b); session.commit()
                st.rerun()

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
