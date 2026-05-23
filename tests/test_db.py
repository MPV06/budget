from datetime import date
from sqlmodel import select
from models.schema import Account, Transaction, Envelope, Paycheck


def test_insert_account(session):
    a = Account(plaid_account_id="acct_1", name="Chase Total Checking",
                type="depository", subtype="checking",
                current_balance=1000.0, available_balance=950.0)
    session.add(a)
    session.commit()
    fetched = session.exec(select(Account)).one()
    assert fetched.plaid_account_id == "acct_1"


def test_insert_transaction(session):
    a = Account(plaid_account_id="acct_1", name="x", type="depository",
                subtype="checking", current_balance=0, available_balance=0)
    session.add(a); session.commit(); session.refresh(a)
    t = Transaction(plaid_transaction_id="tx_1", account_id=a.id,
                    posted_date=date(2026, 5, 1), amount=12.50,
                    name="Starbucks", merchant_name="Starbucks",
                    plaid_category="FOOD_AND_DRINK", pending=False)
    session.add(t); session.commit()
    assert session.exec(select(Transaction)).one().amount == 12.50


def test_insert_envelope(session):
    e = Envelope(name="Groceries", rolling_window_days=90,
                 current_budget_per_paycheck=200.0,
                 plaid_category_filter="FOOD_AND_DRINK_GROCERIES",
                 bucket="needs")
    session.add(e); session.commit()
    assert session.exec(select(Envelope)).one().name == "Groceries"


def test_insert_paycheck(session):
    p = Paycheck(scheduled_date=date(2026, 5, 15),
                 actual_deposit_date=date(2026, 5, 15),
                 amount=2500.0, is_projected=True)
    session.add(p); session.commit()
    assert session.exec(select(Paycheck)).one().amount == 2500.0
