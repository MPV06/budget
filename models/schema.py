from datetime import date, datetime
from typing import Optional
from sqlmodel import SQLModel, Field


_TARGS = {"extend_existing": True}  # allow Streamlit hot-reload to re-import safely


class Account(SQLModel, table=True):
    __table_args__ = _TARGS
    id: Optional[int] = Field(default=None, primary_key=True)
    plaid_account_id: str = Field(unique=True, index=True)
    name: str
    type: str
    subtype: str
    current_balance: float
    available_balance: float
    last_synced_at: Optional[datetime] = None


class Transaction(SQLModel, table=True):
    __table_args__ = _TARGS
    id: Optional[int] = Field(default=None, primary_key=True)
    plaid_transaction_id: str = Field(unique=True, index=True)
    account_id: int = Field(foreign_key="account.id")
    posted_date: date = Field(index=True)
    amount: float
    merchant_name: Optional[str] = None
    name: str
    plaid_category: Optional[str] = None
    plaid_detailed: Optional[str] = None
    pending: bool = False
    envelope_id: Optional[int] = Field(default=None, foreign_key="envelope.id")
    bill_id: Optional[int] = Field(default=None, foreign_key="recurringbill.id")
    bnpl_installment_id: Optional[int] = Field(default=None, foreign_key="bnplinstallment.id")


class RecurringBill(SQLModel, table=True):
    __table_args__ = _TARGS
    id: Optional[int] = Field(default=None, primary_key=True)
    source: str
    plaid_stream_id: Optional[str] = Field(default=None, unique=True)
    merchant_name: str
    display_name: str
    amount: float
    cadence: str
    next_due_date: date
    category: str
    is_active: bool = True
    confidence: str = "MEDIUM"
    confirmed_by_user: bool = False
    notes: str = ""


class BNPLPlan(SQLModel, table=True):
    __table_args__ = _TARGS
    id: Optional[int] = Field(default=None, primary_key=True)
    source: str
    provider: str
    merchant_name: str
    original_amount: float
    total_payments: int
    payment_amount: float
    cadence: str
    start_date: date
    is_active: bool = True


class BNPLInstallment(SQLModel, table=True):
    __table_args__ = _TARGS
    id: Optional[int] = Field(default=None, primary_key=True)
    plan_id: int = Field(foreign_key="bnplplan.id")
    installment_number: int
    due_date: date = Field(index=True)
    amount: float
    status: str = "scheduled"
    paid_transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")


class Envelope(SQLModel, table=True):
    __table_args__ = _TARGS
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    rolling_window_days: int = 90
    current_budget_per_paycheck: float
    user_override: Optional[float] = None
    plaid_category_filter: str
    bucket: str


class Paycheck(SQLModel, table=True):
    __table_args__ = _TARGS
    id: Optional[int] = Field(default=None, primary_key=True)
    scheduled_date: date = Field(index=True)
    actual_deposit_date: date = Field(index=True)
    amount: float
    is_projected: bool = True


class SyncState(SQLModel, table=True):
    __table_args__ = _TARGS
    key: str = Field(primary_key=True)
    value: str
