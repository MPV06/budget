"""One-time fixup: roll back next_due_date for bills that were accidentally
marked Paid (before the Undo banner existed).

Specifically:
  - Claude: 2026-07-27 -> 2026-05-27 (clicked twice, +2 months)
  - Chase Credit Card: 2026-07-01 -> 2026-06-01 (clicked once, +1 month)

Save stays at 2026-06-07 because that one was a legitimate paid click.

Run once:  python -m scripts.fixup_marked_paid
"""
from datetime import date
from sqlmodel import select

from models.schema import RecurringBill
from services.db import get_session

ROLLBACKS = {
    "Claude":            date(2026, 5, 27),
    "Chase Credit Card": date(2026, 6, 1),
}


def main():
    with get_session() as session:
        for name, target_date in ROLLBACKS.items():
            bill = session.exec(
                select(RecurringBill).where(
                    RecurringBill.display_name == name,
                    RecurringBill.is_active == True,  # noqa: E712
                )
            ).first()
            if bill is None:
                print(f"  ✗ {name}: not found")
                continue
            old = bill.next_due_date
            bill.next_due_date = target_date
            session.add(bill)
            print(f"  ✓ {name}: {old} -> {target_date}")
        session.commit()
    print("\nDone. Refresh the app to see updated dates.")


if __name__ == "__main__":
    main()
