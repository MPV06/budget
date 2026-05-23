from datetime import date

from models.schema import Account, Transaction, Envelope
from services.envelope_data import current_period_spend, monthly_totals_for_envelope


def test_current_period_spend_only_counts_matched(session):
    a = Account(plaid_account_id="acct_1", name="x", type="depository",
                subtype="checking", current_balance=0, available_balance=0)
    session.add(a); session.commit(); session.refresh(a)

    e = Envelope(name="Groceries", current_budget_per_paycheck=200.0,
                 plaid_category_filter="FOOD_AND_DRINK_GROCERIES", bucket="needs")
    session.add(e); session.commit(); session.refresh(e)

    session.add(Transaction(plaid_transaction_id="t1", account_id=a.id,
                            posted_date=date(2026, 5, 5), amount=50.0,
                            name="TJ", plaid_category="FOOD_AND_DRINK_GROCERIES",
                            envelope_id=e.id))
    session.add(Transaction(plaid_transaction_id="t2", account_id=a.id,
                            posted_date=date(2026, 5, 6), amount=12.0,
                            name="Shell", plaid_category="TRANSPORTATION_GAS"))
    session.add(Transaction(plaid_transaction_id="t3", account_id=a.id,
                            posted_date=date(2026, 4, 1), amount=30.0,
                            name="TJ", plaid_category="FOOD_AND_DRINK_GROCERIES",
                            envelope_id=e.id))
    session.commit()

    total = current_period_spend(session, envelope_id=e.id,
                                  start=date(2026, 5, 1), end=date(2026, 5, 15))
    assert total == 50.0


def test_monthly_totals_groups_by_month(session):
    a = Account(plaid_account_id="acct_1", name="x", type="depository",
                subtype="checking", current_balance=0, available_balance=0)
    session.add(a); session.commit(); session.refresh(a)
    e = Envelope(name="Restaurants", current_budget_per_paycheck=100.0,
                 plaid_category_filter="FOOD_AND_DRINK_RESTAURANTS", bucket="wants")
    session.add(e); session.commit(); session.refresh(e)

    for i, (d, amt) in enumerate([
        (date(2026, 2, 5), 100.0), (date(2026, 2, 20), 50.0),
        (date(2026, 3, 10), 80.0), (date(2026, 4, 1), 120.0),
    ]):
        session.add(Transaction(plaid_transaction_id=f"r{i}", account_id=a.id,
                                posted_date=d, amount=amt, name="x",
                                envelope_id=e.id))
    session.commit()

    totals = monthly_totals_for_envelope(session, envelope_id=e.id,
                                         months_back=3, today=date(2026, 5, 1))
    assert totals == [150.0, 80.0, 120.0]
