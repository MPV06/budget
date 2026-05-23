# Budget App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Streamlit budget app with Plaid (Chase read-only) integration, semi-monthly paycheck calendar, recurring bill auto-detect, BNPL tracking, envelope budgets, and 50/30/20 view.

**Architecture:** Streamlit monolith. UI pages call into a pure-Python `services/` layer (paycheck_calendar, plaid_sync, categorizer, bnpl_detector, budget_engine) that is fully unit-testable. SQLite via SQLModel for storage. Plaid access is whitelisted to four read endpoints by a wrapper.

**Tech Stack:** Python 3.11+, Streamlit ≥1.32, plaid-python ≥22, SQLModel, pydantic-settings, pandas, python-dateutil, holidays, pytest.

**Spec:** [`docs/superpowers/specs/2026-05-23-budget-app-design.md`](../specs/2026-05-23-budget-app-design.md)

---

## File Structure

```
budget/
  app.py                          # Streamlit entry point + Home redirect
  pyproject.toml                  # deps + tool config
  .env.example
  .gitignore
  README.md
  pages/
    1_Dashboard.py                # Safe-to-spend hero + summary
    2_Bills.py                    # Recurring bills mgmt
    3_Envelopes.py                # Groceries/Restaurants/Gas
    4_BNPL.py                     # Affirm / Chase Pay-in-4
    5_Goals.py                    # Leftover tracker + named goals
    6_Transactions.py             # Filterable txn table
    7_Settings.py                 # Plaid Link onboarding + paycheck cfg
  services/
    __init__.py
    config.py                     # Settings (pydantic-settings)
    db.py                         # SQLModel engine + session
    paycheck_calendar.py          # pay date calc + 12mo generation
    plaid_client.py               # PlaidReadOnlyClient whitelist wrapper
    plaid_sync.py                 # /transactions/sync + recurring + balance
    categorizer.py                # PFC → envelope mapping
    bnpl_detector.py              # Affirm/ChasePayIn4 detection + schedule
    budget_engine.py              # safe_to_spend, leftover, envelope_status, fifty_thirty_twenty
  models/
    __init__.py
    schema.py                     # SQLModel table definitions
  data/                           # gitignored — SQLite lives here
  tests/
    conftest.py                   # in-memory DB fixture, frozen time
    fixtures/
      plaid_transactions.json
      plaid_recurring.json
      plaid_accounts.json
    test_paycheck_calendar.py
    test_plaid_readonly.py
    test_plaid_sync.py
    test_categorizer.py
    test_bnpl_detector.py
    test_budget_engine.py
```

---

## Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`
- Create: `services/__init__.py`, `models/__init__.py`, `pages/.gitkeep`, `tests/__init__.py`, `data/.gitkeep`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "budget"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "streamlit>=1.32",
  "plaid-python>=22.0.0",
  "sqlmodel>=0.0.16",
  "pydantic-settings>=2.2",
  "python-dotenv>=1.0",
  "python-dateutil>=2.9",
  "holidays>=0.45",
  "pandas>=2.2",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
  "pytest-cov>=4.1",
  "freezegun>=1.4",
  "ruff>=0.3",
  "black>=24.3",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --cov=services --cov=models --cov-report=term-missing"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.black]
line-length = 100
target-version = ["py311"]
```

- [ ] **Step 2: Create .gitignore**

```
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.env
data/*.db
data/*.db-journal
.coverage
htmlcov/
.pytest_cache/
.ruff_cache/
.streamlit/secrets.toml
```

- [ ] **Step 3: Create .env.example**

```
# Plaid credentials — get from https://dashboard.plaid.com
PLAID_CLIENT_ID=
PLAID_SECRET=
PLAID_ENV=sandbox            # sandbox | development | production
PLAID_ACCESS_TOKEN=          # filled in after first Plaid Link onboarding

# App settings
PAYCHECK_NET_AMOUNT=         # e.g. 2500.00
DB_PATH=./data/budget.db
```

- [ ] **Step 4: Create README.md**

```markdown
# Budget

Local Streamlit budget app with Plaid (Chase read-only) integration.

## Setup

1. `python -m venv .venv && .venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (Unix)
2. `pip install -e .[dev]`
3. `cp .env.example .env` and fill in Plaid credentials
4. `streamlit run app.py`

## Tests

`pytest`

See [`docs/superpowers/specs/2026-05-23-budget-app-design.md`](docs/superpowers/specs/2026-05-23-budget-app-design.md) for design.
```

- [ ] **Step 5: Create package init files**

Create empty files: `services/__init__.py`, `models/__init__.py`, `tests/__init__.py`. Create `pages/.gitkeep` and `data/.gitkeep` as empty placeholders.

- [ ] **Step 6: Install and verify**

Run: `python -m venv .venv && .venv\Scripts\python -m pip install -e .[dev]`
Expected: install succeeds, `.venv\Scripts\pytest --version` prints a version.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore .env.example README.md services/ models/ pages/ tests/ data/
git commit -m "feat: project scaffold for budget app"
```

---

## Task 2: Config service (pydantic-settings)

**Files:**
- Create: `services/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing test**

`tests/test_config.py`:
```python
import os
from services.config import Settings


def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("PLAID_CLIENT_ID", "id123")
    monkeypatch.setenv("PLAID_SECRET", "secret123")
    monkeypatch.setenv("PLAID_ENV", "sandbox")
    monkeypatch.setenv("PAYCHECK_NET_AMOUNT", "2500.00")
    monkeypatch.setenv("DB_PATH", "./data/test.db")

    s = Settings()
    assert s.plaid_client_id == "id123"
    assert s.plaid_secret == "secret123"
    assert s.plaid_env == "sandbox"
    assert s.paycheck_net_amount == 2500.00
    assert s.db_path == "./data/test.db"


def test_settings_rejects_invalid_env(monkeypatch):
    monkeypatch.setenv("PLAID_CLIENT_ID", "id")
    monkeypatch.setenv("PLAID_SECRET", "sec")
    monkeypatch.setenv("PLAID_ENV", "garbage")
    monkeypatch.setenv("PAYCHECK_NET_AMOUNT", "100")
    monkeypatch.setenv("DB_PATH", "./x")
    import pytest
    with pytest.raises(ValueError):
        Settings()
```

- [ ] **Step 2: Verify test fails**

Run: `.venv\Scripts\pytest tests/test_config.py -v`
Expected: ImportError for services.config.

- [ ] **Step 3: Implement Settings**

`services/config.py`:
```python
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    plaid_client_id: str = Field(min_length=1)
    plaid_secret: str = Field(min_length=1)
    plaid_env: Literal["sandbox", "development", "production"]
    plaid_access_token: str = ""
    paycheck_net_amount: float = Field(gt=0)
    db_path: str = "./data/budget.db"


def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Verify tests pass**

Run: `.venv\Scripts\pytest tests/test_config.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add services/config.py tests/test_config.py
git commit -m "feat(config): typed settings via pydantic-settings"
```

---

## Task 3: Database schema (SQLModel)

**Files:**
- Create: `models/schema.py`
- Create: `services/db.py`
- Create: `tests/conftest.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write failing test**

`tests/conftest.py`:
```python
import pytest
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s
```

`tests/test_db.py`:
```python
from datetime import date
from sqlmodel import select
from models.schema import Account, Transaction, RecurringBill, BNPLPlan, BNPLInstallment, Envelope, Paycheck


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
```

- [ ] **Step 2: Verify test fails**

Run: `.venv\Scripts\pytest tests/test_db.py -v`
Expected: ImportError on models.schema.

- [ ] **Step 3: Implement schema**

`models/schema.py`:
```python
from datetime import date, datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class Account(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    plaid_account_id: str = Field(unique=True, index=True)
    name: str
    type: str
    subtype: str
    current_balance: float
    available_balance: float
    last_synced_at: Optional[datetime] = None


class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    plaid_transaction_id: str = Field(unique=True, index=True)
    account_id: int = Field(foreign_key="account.id")
    posted_date: date = Field(index=True)
    amount: float                          # positive = money out (Plaid convention)
    merchant_name: Optional[str] = None
    name: str
    plaid_category: Optional[str] = None
    plaid_detailed: Optional[str] = None
    pending: bool = False
    envelope_id: Optional[int] = Field(default=None, foreign_key="envelope.id")
    bill_id: Optional[int] = Field(default=None, foreign_key="recurringbill.id")
    bnpl_installment_id: Optional[int] = Field(default=None, foreign_key="bnplinstallment.id")


class RecurringBill(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source: str                             # 'plaid_auto' | 'manual'
    plaid_stream_id: Optional[str] = Field(default=None, unique=True)
    merchant_name: str
    display_name: str
    amount: float
    cadence: str                            # monthly/weekly/biweekly/semi_monthly
    next_due_date: date
    category: str                           # needs/wants/savings
    is_active: bool = True
    confidence: str = "MEDIUM"              # HIGH/MEDIUM/LOW
    confirmed_by_user: bool = False
    notes: str = ""


class BNPLPlan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source: str                             # 'plaid_auto' | 'manual'
    provider: str                           # affirm | chase_pay_in_4 | klarna | afterpay
    merchant_name: str
    original_amount: float
    total_payments: int
    payment_amount: float
    cadence: str                            # biweekly | monthly
    start_date: date
    is_active: bool = True


class BNPLInstallment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    plan_id: int = Field(foreign_key="bnplplan.id")
    installment_number: int
    due_date: date = Field(index=True)
    amount: float
    status: str = "scheduled"               # scheduled | paid | missed
    paid_transaction_id: Optional[int] = Field(default=None, foreign_key="transaction.id")


class Envelope(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    rolling_window_days: int = 90
    current_budget_per_paycheck: float
    user_override: Optional[float] = None
    plaid_category_filter: str              # comma-separated PFC values
    bucket: str                             # needs | wants


class Paycheck(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    scheduled_date: date = Field(index=True)
    actual_deposit_date: date = Field(index=True)
    amount: float
    is_projected: bool = True
```

- [ ] **Step 4: Implement db.py**

`services/db.py`:
```python
from pathlib import Path
from sqlmodel import SQLModel, Session, create_engine
from services.config import get_settings

import models.schema  # noqa: F401  -- register tables

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        path = get_settings().db_path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(f"sqlite:///{path}")
        SQLModel.metadata.create_all(_engine)
    return _engine


def get_session() -> Session:
    return Session(get_engine())
```

- [ ] **Step 5: Verify tests pass**

Run: `.venv\Scripts\pytest tests/test_db.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add models/ services/db.py tests/conftest.py tests/test_db.py
git commit -m "feat(db): SQLModel schema for accounts, txns, bills, BNPL, envelopes, paychecks"
```

---

## Task 4: Paycheck calendar — weekend/holiday adjustment

**Files:**
- Create: `services/paycheck_calendar.py`
- Create: `tests/test_paycheck_calendar.py`

- [ ] **Step 1: Write failing tests**

`tests/test_paycheck_calendar.py`:
```python
from datetime import date
from services.paycheck_calendar import adjust_for_weekend_and_holiday, generate_paycheck_dates


def test_weekday_unchanged():
    assert adjust_for_weekend_and_holiday(date(2026, 5, 15)) == date(2026, 5, 15)  # Friday


def test_saturday_moves_to_friday():
    # 2026-05-16 is Saturday
    assert adjust_for_weekend_and_holiday(date(2026, 5, 16)) == date(2026, 5, 15)


def test_sunday_moves_to_friday():
    # 2026-05-17 is Sunday
    assert adjust_for_weekend_and_holiday(date(2026, 5, 17)) == date(2026, 5, 15)


def test_july_4_2026_is_saturday_moves_to_friday():
    # Independence Day 2026-07-04 falls on Saturday
    assert adjust_for_weekend_and_holiday(date(2026, 7, 4)) == date(2026, 7, 3)


def test_christmas_2026_friday_observed_unchanged():
    # 2026-12-25 is Friday and a holiday — moves to Thursday 24th
    assert adjust_for_weekend_and_holiday(date(2026, 12, 25)) == date(2026, 12, 24)


def test_new_years_day_2026_thursday_unchanged():
    # 2026-01-01 is Thursday and a holiday — moves to 2025-12-31 Wed
    assert adjust_for_weekend_and_holiday(date(2026, 1, 1)) == date(2025, 12, 31)


def test_generate_paycheck_dates_12_months():
    dates = generate_paycheck_dates(start=date(2026, 1, 1), months=12)
    # 24 paychecks: 15th + last day each month
    assert len(dates) == 24
    # First two
    assert dates[0].scheduled_date == date(2026, 1, 15)
    assert dates[1].scheduled_date == date(2026, 1, 31)
    # Verify last-day handling across months with different lengths
    feb_last = next(d for d in dates if d.scheduled_date.month == 2 and d.scheduled_date.day > 14)
    assert feb_last.scheduled_date == date(2026, 2, 28)  # 2026 is not a leap year


def test_generate_includes_actual_deposit_date():
    dates = generate_paycheck_dates(start=date(2026, 5, 1), months=1)
    # 2026-05-15 is Friday — unchanged
    may_15 = next(d for d in dates if d.scheduled_date == date(2026, 5, 15))
    assert may_15.actual_deposit_date == date(2026, 5, 15)
    # 2026-05-31 is Sunday — moves to Friday 2026-05-29
    may_31 = next(d for d in dates if d.scheduled_date == date(2026, 5, 31))
    assert may_31.actual_deposit_date == date(2026, 5, 29)
```

- [ ] **Step 2: Verify tests fail**

Run: `.venv\Scripts\pytest tests/test_paycheck_calendar.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement paycheck_calendar**

`services/paycheck_calendar.py`:
```python
import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List

import holidays

US_HOLIDAYS = holidays.country_holidays("US")


@dataclass
class PaycheckDate:
    scheduled_date: date
    actual_deposit_date: date


def adjust_for_weekend_and_holiday(d: date) -> date:
    """Roll back to previous business day if d is weekend or US federal holiday."""
    cur = d
    while cur.weekday() >= 5 or cur in US_HOLIDAYS:
        cur -= timedelta(days=1)
    return cur


def _last_day_of_month(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def generate_paycheck_dates(start: date, months: int) -> List[PaycheckDate]:
    """Generate semi-monthly pay dates (15th + last day) for `months` months from `start`."""
    out: List[PaycheckDate] = []
    # Normalize to start of month
    cur = date(start.year, start.month, 1)
    for _ in range(months):
        mid = date(cur.year, cur.month, 15)
        last = _last_day_of_month(cur.year, cur.month)
        out.append(PaycheckDate(scheduled_date=mid, actual_deposit_date=adjust_for_weekend_and_holiday(mid)))
        out.append(PaycheckDate(scheduled_date=last, actual_deposit_date=adjust_for_weekend_and_holiday(last)))
        # advance one month
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)
    return out


def next_paycheck_after(d: date, calendar_: List[PaycheckDate]) -> PaycheckDate:
    """Return the next PaycheckDate strictly after `d` (using actual_deposit_date)."""
    for p in calendar_:
        if p.actual_deposit_date > d:
            return p
    raise ValueError("No paycheck found after the given date — extend the calendar")
```

- [ ] **Step 4: Verify tests pass**

Run: `.venv\Scripts\pytest tests/test_paycheck_calendar.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add services/paycheck_calendar.py tests/test_paycheck_calendar.py
git commit -m "feat(paycheck): semi-monthly calendar w/ weekend+holiday rollback"
```

---

## Task 5: Plaid read-only client wrapper

**Files:**
- Create: `services/plaid_client.py`
- Create: `tests/test_plaid_readonly.py`

- [ ] **Step 1: Write failing tests**

`tests/test_plaid_readonly.py`:
```python
import pytest
from unittest.mock import MagicMock
from services.plaid_client import PlaidReadOnlyClient, ReadOnlyViolation, ALLOWED_METHODS


def test_allowed_methods_exact_set():
    assert ALLOWED_METHODS == frozenset({
        "accounts_get",
        "transactions_sync",
        "transactions_recurring_get",
        "item_get",
    })


def test_allowed_method_proxies_call():
    raw = MagicMock()
    raw.accounts_get.return_value = {"accounts": []}
    client = PlaidReadOnlyClient(raw)
    result = client.accounts_get({"access_token": "x"})
    assert result == {"accounts": []}
    raw.accounts_get.assert_called_once()


def test_forbidden_method_raises():
    raw = MagicMock()
    client = PlaidReadOnlyClient(raw)
    with pytest.raises(ReadOnlyViolation, match="transfer_create"):
        client.transfer_create({"foo": "bar"})


def test_other_forbidden_methods_raise():
    raw = MagicMock()
    client = PlaidReadOnlyClient(raw)
    for name in ["auth_get", "processor_token_create", "sandbox_item_fire_webhook",
                 "item_remove", "payment_initiation_payment_create"]:
        with pytest.raises(ReadOnlyViolation):
            getattr(client, name)({})
```

- [ ] **Step 2: Verify tests fail**

Run: `.venv\Scripts\pytest tests/test_plaid_readonly.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement plaid_client**

`services/plaid_client.py`:
```python
from typing import Any

ALLOWED_METHODS = frozenset({
    "accounts_get",
    "transactions_sync",
    "transactions_recurring_get",
    "item_get",
})


class ReadOnlyViolation(RuntimeError):
    pass


class PlaidReadOnlyClient:
    """Whitelist wrapper around plaid.ApiClient. Only ALLOWED_METHODS proxy through."""

    def __init__(self, raw_client: Any):
        self._raw = raw_client

    def __getattr__(self, name: str):
        if name in ALLOWED_METHODS:
            return getattr(self._raw, name)
        raise ReadOnlyViolation(
            f"Method '{name}' is not in the read-only whitelist. "
            f"Allowed: {sorted(ALLOWED_METHODS)}"
        )
```

- [ ] **Step 4: Verify tests pass**

Run: `.venv\Scripts\pytest tests/test_plaid_readonly.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add services/plaid_client.py tests/test_plaid_readonly.py
git commit -m "feat(plaid): read-only whitelist wrapper enforces 4 allowed endpoints"
```

---

## Task 6: Categorizer — Plaid PFC → envelope

**Files:**
- Create: `services/categorizer.py`
- Create: `tests/test_categorizer.py`

- [ ] **Step 1: Write failing tests**

`tests/test_categorizer.py`:
```python
from services.categorizer import categorize, DEFAULT_PFC_MAP


def test_groceries_maps_to_groceries():
    assert categorize("FOOD_AND_DRINK_GROCERIES", merchant="Trader Joe's") == "Groceries"


def test_restaurants_and_coffee_map_to_restaurants():
    assert categorize("FOOD_AND_DRINK_RESTAURANTS", merchant="Chipotle") == "Restaurants"
    assert categorize("FOOD_AND_DRINK_FAST_FOOD", merchant="McDonald's") == "Restaurants"
    assert categorize("FOOD_AND_DRINK_COFFEE", merchant="Starbucks") == "Restaurants"


def test_gas_maps_to_gas():
    assert categorize("TRANSPORTATION_GAS", merchant="Shell") == "Gas"


def test_unknown_returns_none():
    assert categorize("ENTERTAINMENT_MOVIES", merchant="AMC") is None


def test_merchant_override_takes_precedence():
    overrides = {"Costco Wholesale": "Groceries"}
    # Costco is GENERAL_MERCHANDISE by default but user calls it groceries
    assert categorize("GENERAL_MERCHANDISE", merchant="Costco Wholesale",
                      merchant_overrides=overrides) == "Groceries"


def test_default_map_has_expected_keys():
    assert "FOOD_AND_DRINK_GROCERIES" in DEFAULT_PFC_MAP
    assert DEFAULT_PFC_MAP["FOOD_AND_DRINK_GROCERIES"] == "Groceries"
```

- [ ] **Step 2: Verify tests fail**

Run: `.venv\Scripts\pytest tests/test_categorizer.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement categorizer**

`services/categorizer.py`:
```python
from typing import Dict, Optional

DEFAULT_PFC_MAP: Dict[str, str] = {
    "FOOD_AND_DRINK_GROCERIES": "Groceries",
    "FOOD_AND_DRINK_RESTAURANTS": "Restaurants",
    "FOOD_AND_DRINK_FAST_FOOD": "Restaurants",
    "FOOD_AND_DRINK_COFFEE": "Restaurants",
    "FOOD_AND_DRINK_BEER_WINE_AND_LIQUOR": "Restaurants",
    "TRANSPORTATION_GAS": "Gas",
}


def categorize(
    plaid_category: str,
    merchant: Optional[str] = None,
    merchant_overrides: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """Return envelope name or None.

    Precedence:
        1. merchant_overrides exact match on merchant
        2. DEFAULT_PFC_MAP lookup
        3. None
    """
    if merchant and merchant_overrides and merchant in merchant_overrides:
        return merchant_overrides[merchant]
    return DEFAULT_PFC_MAP.get(plaid_category)
```

- [ ] **Step 4: Verify tests pass**

Run: `.venv\Scripts\pytest tests/test_categorizer.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add services/categorizer.py tests/test_categorizer.py
git commit -m "feat(categorizer): map Plaid PFC to envelopes with merchant overrides"
```

---

## Task 7: BNPL detector + schedule projection

**Files:**
- Create: `services/bnpl_detector.py`
- Create: `tests/test_bnpl_detector.py`

- [ ] **Step 1: Write failing tests**

`tests/test_bnpl_detector.py`:
```python
from datetime import date, timedelta
from services.bnpl_detector import detect_provider, project_schedule


def test_detect_affirm():
    assert detect_provider("AFFIRM PURCHASE") == "affirm"
    assert detect_provider("Affirm Inc") == "affirm"


def test_detect_chase_pay_in_4():
    assert detect_provider("CHASE PAY IN 4 PMT") == "chase_pay_in_4"
    assert detect_provider("Chase Pay-in-4 Installment") == "chase_pay_in_4"


def test_detect_klarna_afterpay():
    assert detect_provider("KLARNA*PURCHASE") == "klarna"
    assert detect_provider("AFTERPAY US INC") == "afterpay"


def test_detect_none_for_normal_merchant():
    assert detect_provider("STARBUCKS #1234") is None


def test_project_schedule_4_biweekly():
    start = date(2026, 5, 1)  # Friday
    plan = project_schedule(start=start, total_payments=4, payment_amount=25.00,
                            cadence="biweekly")
    assert len(plan) == 4
    assert plan[0].due_date == date(2026, 5, 1)
    assert plan[1].due_date == date(2026, 5, 15)
    assert plan[2].due_date == date(2026, 5, 29)
    assert plan[3].due_date == date(2026, 6, 12)
    assert all(p.amount == 25.00 for p in plan)
    assert [p.installment_number for p in plan] == [1, 2, 3, 4]


def test_project_schedule_monthly():
    start = date(2026, 5, 1)
    plan = project_schedule(start=start, total_payments=3, payment_amount=100.00,
                            cadence="monthly")
    assert [p.due_date for p in plan] == [date(2026, 5, 1), date(2026, 6, 1), date(2026, 7, 1)]
```

- [ ] **Step 2: Verify tests fail**

Run: `.venv\Scripts\pytest tests/test_bnpl_detector.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement bnpl_detector**

`services/bnpl_detector.py`:
```python
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional

from dateutil.relativedelta import relativedelta

_PATTERNS = [
    (re.compile(r"\baffirm\b", re.I), "affirm"),
    (re.compile(r"chase\s*pay[\s\-]?in[\s\-]?4", re.I), "chase_pay_in_4"),
    (re.compile(r"\bklarna\b", re.I), "klarna"),
    (re.compile(r"\bafterpay\b", re.I), "afterpay"),
]


def detect_provider(description: str) -> Optional[str]:
    for pattern, provider in _PATTERNS:
        if pattern.search(description):
            return provider
    return None


@dataclass
class ProjectedInstallment:
    installment_number: int
    due_date: date
    amount: float


def project_schedule(
    start: date,
    total_payments: int,
    payment_amount: float,
    cadence: str,
) -> List[ProjectedInstallment]:
    if cadence not in {"biweekly", "monthly"}:
        raise ValueError(f"Unsupported cadence: {cadence}")
    result = []
    for i in range(total_payments):
        if cadence == "biweekly":
            due = start + timedelta(days=14 * i)
        else:  # monthly
            due = start + relativedelta(months=i)
        result.append(ProjectedInstallment(
            installment_number=i + 1,
            due_date=due,
            amount=round(payment_amount, 2),
        ))
    return result
```

- [ ] **Step 4: Verify tests pass**

Run: `.venv\Scripts\pytest tests/test_bnpl_detector.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add services/bnpl_detector.py tests/test_bnpl_detector.py
git commit -m "feat(bnpl): detect Affirm/ChasePayIn4/Klarna/Afterpay + project schedule"
```

---

## Task 8: Budget engine — safe-to-spend

**Files:**
- Create: `services/budget_engine.py` (initial)
- Create: `tests/test_budget_engine.py`

- [ ] **Step 1: Write failing tests**

`tests/test_budget_engine.py`:
```python
from datetime import date
from services.budget_engine import safe_to_spend, ObligationItem


def test_safe_to_spend_no_obligations():
    assert safe_to_spend(balance=1000.0, obligations=[]) == 1000.0


def test_safe_to_spend_subtracts_obligations_before_cutoff():
    obs = [
        ObligationItem(due_date=date(2026, 5, 20), amount=100.0, label="Electric"),
        ObligationItem(due_date=date(2026, 5, 25), amount=50.0, label="Phone"),
    ]
    # cutoff = next paycheck deposit date
    assert safe_to_spend(balance=1000.0, obligations=obs,
                         next_paycheck_date=date(2026, 5, 29)) == 850.0


def test_safe_to_spend_ignores_obligations_after_cutoff():
    obs = [
        ObligationItem(due_date=date(2026, 5, 20), amount=100.0, label="Electric"),
        ObligationItem(due_date=date(2026, 6, 5), amount=999.0, label="Rent next month"),
    ]
    assert safe_to_spend(balance=1000.0, obligations=obs,
                         next_paycheck_date=date(2026, 5, 29)) == 900.0


def test_safe_to_spend_can_go_negative():
    obs = [ObligationItem(due_date=date(2026, 5, 20), amount=1500.0, label="Rent")]
    assert safe_to_spend(balance=1000.0, obligations=obs,
                         next_paycheck_date=date(2026, 5, 29)) == -500.0


def test_obligation_on_cutoff_date_is_included():
    obs = [ObligationItem(due_date=date(2026, 5, 29), amount=100.0, label="Edge")]
    # Convention: obligations strictly before next_paycheck deposit are counted.
    # Same-day-as-paycheck obligations are NOT counted (you'll have the money).
    assert safe_to_spend(balance=500.0, obligations=obs,
                         next_paycheck_date=date(2026, 5, 29)) == 500.0
```

- [ ] **Step 2: Verify tests fail**

Run: `.venv\Scripts\pytest tests/test_budget_engine.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement safe_to_spend**

`services/budget_engine.py`:
```python
from dataclasses import dataclass
from datetime import date
from typing import List, Optional


@dataclass
class ObligationItem:
    due_date: date
    amount: float
    label: str


def safe_to_spend(
    balance: float,
    obligations: List[ObligationItem],
    next_paycheck_date: Optional[date] = None,
) -> float:
    """balance minus obligations strictly before next_paycheck_date.

    If next_paycheck_date is None, no cutoff is applied (all obligations counted).
    """
    if next_paycheck_date is None:
        relevant = obligations
    else:
        relevant = [o for o in obligations if o.due_date < next_paycheck_date]
    total = sum(o.amount for o in relevant)
    return round(balance - total, 2)
```

- [ ] **Step 4: Verify tests pass**

Run: `.venv\Scripts\pytest tests/test_budget_engine.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add services/budget_engine.py tests/test_budget_engine.py
git commit -m "feat(engine): safe_to_spend computes balance minus pre-paycheck obligations"
```

---

## Task 9: Budget engine — paycheck leftover + envelope status

**Files:**
- Modify: `services/budget_engine.py` (add functions)
- Modify: `tests/test_budget_engine.py` (add tests)

- [ ] **Step 1: Append failing tests**

Append to `tests/test_budget_engine.py`:
```python
from services.budget_engine import paycheck_leftover, envelope_status, EnvelopeSpend


def test_paycheck_leftover_basic():
    result = paycheck_leftover(
        paycheck_amount=2500.0,
        bills_in_period=800.0,
        bnpl_in_period=100.0,
        envelopes_allocated=600.0,
        debt_payments=300.0,
    )
    assert result == 700.0


def test_paycheck_leftover_can_be_negative():
    result = paycheck_leftover(
        paycheck_amount=1000.0,
        bills_in_period=800.0,
        bnpl_in_period=100.0,
        envelopes_allocated=600.0,
        debt_payments=0.0,
    )
    assert result == -500.0


def test_envelope_status_ok():
    s = envelope_status(EnvelopeSpend(name="Groceries", spent=100.0, budget=200.0))
    assert s.remaining == 100.0
    assert s.percent_used == 50.0
    assert s.status == "OK"


def test_envelope_status_warn_at_80():
    s = envelope_status(EnvelopeSpend(name="Gas", spent=80.0, budget=100.0))
    assert s.status == "WARN"


def test_envelope_status_over_at_101():
    s = envelope_status(EnvelopeSpend(name="Restaurants", spent=101.0, budget=100.0))
    assert s.status == "OVER"
    assert s.remaining == -1.0


def test_envelope_status_zero_budget_is_over_if_any_spend():
    s = envelope_status(EnvelopeSpend(name="X", spent=1.0, budget=0.0))
    assert s.status == "OVER"
```

- [ ] **Step 2: Verify tests fail**

Run: `.venv\Scripts\pytest tests/test_budget_engine.py -v`
Expected: ImportError for paycheck_leftover/envelope_status.

- [ ] **Step 3: Append implementation**

Append to `services/budget_engine.py`:
```python
@dataclass
class EnvelopeSpend:
    name: str
    spent: float
    budget: float


@dataclass
class EnvelopeStatusResult:
    name: str
    spent: float
    budget: float
    remaining: float
    percent_used: float
    status: str  # OK | WARN | OVER


def paycheck_leftover(
    paycheck_amount: float,
    bills_in_period: float,
    bnpl_in_period: float,
    envelopes_allocated: float,
    debt_payments: float,
) -> float:
    return round(
        paycheck_amount - bills_in_period - bnpl_in_period
        - envelopes_allocated - debt_payments,
        2,
    )


def envelope_status(spend: EnvelopeSpend) -> EnvelopeStatusResult:
    remaining = round(spend.budget - spend.spent, 2)
    pct = (spend.spent / spend.budget * 100.0) if spend.budget > 0 else float("inf")
    if spend.spent > spend.budget:
        status = "OVER"
    elif spend.budget > 0 and spend.spent >= 0.8 * spend.budget:
        status = "WARN"
    else:
        status = "OK"
    return EnvelopeStatusResult(
        name=spend.name,
        spent=round(spend.spent, 2),
        budget=round(spend.budget, 2),
        remaining=remaining,
        percent_used=round(pct, 1) if pct != float("inf") else float("inf"),
        status=status,
    )
```

- [ ] **Step 4: Verify tests pass**

Run: `.venv\Scripts\pytest tests/test_budget_engine.py -v`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add services/budget_engine.py tests/test_budget_engine.py
git commit -m "feat(engine): paycheck_leftover + envelope_status (OK/WARN/OVER)"
```

---

## Task 10: Budget engine — 50/30/20 view + auto-budget

**Files:**
- Modify: `services/budget_engine.py`
- Modify: `tests/test_budget_engine.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/test_budget_engine.py`:
```python
from services.budget_engine import fifty_thirty_twenty, auto_budget_from_history


def test_503020_balanced():
    result = fifty_thirty_twenty(
        income=1000.0, needs=500.0, wants=300.0, savings_or_debt=200.0
    )
    assert result.needs_pct == 50.0
    assert result.wants_pct == 30.0
    assert result.savings_pct == 20.0
    assert result.on_target_needs is True
    assert result.on_target_wants is True
    assert result.on_target_savings is True


def test_503020_off_target():
    result = fifty_thirty_twenty(
        income=1000.0, needs=700.0, wants=200.0, savings_or_debt=100.0
    )
    assert result.needs_pct == 70.0
    # Off by >5pp on all three
    assert result.on_target_needs is False
    assert result.on_target_wants is False
    assert result.on_target_savings is False


def test_503020_within_5pp_is_on_target():
    # needs 54% is within 5pp of 50
    result = fifty_thirty_twenty(
        income=1000.0, needs=540.0, wants=280.0, savings_or_debt=180.0
    )
    assert result.on_target_needs is True
    assert result.on_target_wants is True
    assert result.on_target_savings is True


def test_503020_zero_income_safe():
    result = fifty_thirty_twenty(income=0.0, needs=0.0, wants=0.0, savings_or_debt=0.0)
    assert result.needs_pct == 0.0


def test_auto_budget_3_month_average_per_paycheck():
    # 3 months of spend: $400, $440, $420 ⇒ avg $420/mo ⇒ $210/paycheck
    result = auto_budget_from_history(monthly_totals=[400.0, 440.0, 420.0])
    assert result == 210.0


def test_auto_budget_empty_history_returns_zero():
    assert auto_budget_from_history(monthly_totals=[]) == 0.0
```

- [ ] **Step 2: Verify tests fail**

Run: `.venv\Scripts\pytest tests/test_budget_engine.py::test_503020_balanced -v`
Expected: ImportError.

- [ ] **Step 3: Append implementation**

Append to `services/budget_engine.py`:
```python
@dataclass
class FiftyThirtyTwentyResult:
    needs_pct: float
    wants_pct: float
    savings_pct: float
    on_target_needs: bool
    on_target_wants: bool
    on_target_savings: bool


def fifty_thirty_twenty(
    income: float, needs: float, wants: float, savings_or_debt: float
) -> FiftyThirtyTwentyResult:
    def pct(x):
        return round(x / income * 100.0, 1) if income > 0 else 0.0
    np_, wp_, sp_ = pct(needs), pct(wants), pct(savings_or_debt)
    within = lambda actual, target: abs(actual - target) <= 5.0  # noqa: E731
    return FiftyThirtyTwentyResult(
        needs_pct=np_,
        wants_pct=wp_,
        savings_pct=sp_,
        on_target_needs=within(np_, 50.0),
        on_target_wants=within(wp_, 30.0),
        on_target_savings=within(sp_, 20.0),
    )


def auto_budget_from_history(monthly_totals: List[float]) -> float:
    """Return per-paycheck budget from a list of monthly spend totals.

    Semi-monthly = 2 paychecks per month, so per-paycheck = monthly_avg / 2.
    """
    if not monthly_totals:
        return 0.0
    avg = sum(monthly_totals) / len(monthly_totals)
    return round(avg / 2.0, 2)
```

- [ ] **Step 4: Verify tests pass**

Run: `.venv\Scripts\pytest tests/test_budget_engine.py -v`
Expected: 17 passed.

- [ ] **Step 5: Commit**

```bash
git add services/budget_engine.py tests/test_budget_engine.py
git commit -m "feat(engine): 50/30/20 view + auto_budget_from_history"
```

---

## Task 11: Plaid sync — transactions sync cursor handling

**Files:**
- Create: `services/plaid_sync.py`
- Create: `tests/fixtures/plaid_sync_page1.json`
- Create: `tests/fixtures/plaid_sync_page2.json`
- Create: `tests/test_plaid_sync.py`

- [ ] **Step 1: Create fixtures**

`tests/fixtures/plaid_sync_page1.json`:
```json
{
  "added": [
    {"transaction_id": "tx_001", "account_id": "acct_1", "date": "2026-05-01",
     "amount": 12.50, "name": "Starbucks", "merchant_name": "Starbucks",
     "personal_finance_category": {"primary": "FOOD_AND_DRINK_COFFEE", "detailed": "FOOD_AND_DRINK_COFFEE"},
     "pending": false},
    {"transaction_id": "tx_002", "account_id": "acct_1", "date": "2026-05-02",
     "amount": 65.00, "name": "Shell Oil", "merchant_name": "Shell",
     "personal_finance_category": {"primary": "TRANSPORTATION_GAS", "detailed": "TRANSPORTATION_GAS"},
     "pending": false}
  ],
  "modified": [],
  "removed": [],
  "next_cursor": "cursor_v1",
  "has_more": true
}
```

`tests/fixtures/plaid_sync_page2.json`:
```json
{
  "added": [
    {"transaction_id": "tx_003", "account_id": "acct_1", "date": "2026-05-03",
     "amount": 88.20, "name": "Trader Joe's", "merchant_name": "Trader Joe's",
     "personal_finance_category": {"primary": "FOOD_AND_DRINK_GROCERIES", "detailed": "FOOD_AND_DRINK_GROCERIES"},
     "pending": false}
  ],
  "modified": [],
  "removed": [{"transaction_id": "tx_001"}],
  "next_cursor": "cursor_v2",
  "has_more": false
}
```

- [ ] **Step 2: Write failing tests**

`tests/test_plaid_sync.py`:
```python
import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

from sqlmodel import select

from models.schema import Account, Transaction
from services.plaid_sync import sync_transactions

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_sync_handles_paginated_added_and_removed(session):
    # Seed an account so FK works
    a = Account(plaid_account_id="acct_1", name="Chase", type="depository",
                subtype="checking", current_balance=0, available_balance=0)
    session.add(a); session.commit(); session.refresh(a)

    page1 = _load("plaid_sync_page1.json")
    page2 = _load("plaid_sync_page2.json")
    raw = MagicMock()
    raw.transactions_sync.side_effect = [page1, page2]

    final_cursor = sync_transactions(
        session=session,
        plaid_client=raw,
        access_token="atok",
        initial_cursor=None,
    )

    assert final_cursor == "cursor_v2"
    # tx_001 was added then removed → must not be in DB
    # tx_002 and tx_003 should remain
    rows = session.exec(select(Transaction)).all()
    plaid_ids = {r.plaid_transaction_id for r in rows}
    assert plaid_ids == {"tx_002", "tx_003"}


def test_sync_is_idempotent_on_replay(session):
    a = Account(plaid_account_id="acct_1", name="Chase", type="depository",
                subtype="checking", current_balance=0, available_balance=0)
    session.add(a); session.commit()

    page = {
        "added": [{"transaction_id": "tx_x", "account_id": "acct_1",
                   "date": "2026-05-01", "amount": 10.0, "name": "X",
                   "merchant_name": "X",
                   "personal_finance_category": {"primary": "X", "detailed": "X"},
                   "pending": False}],
        "modified": [], "removed": [],
        "next_cursor": "c1", "has_more": False,
    }
    raw = MagicMock()
    raw.transactions_sync.side_effect = [page, page]

    sync_transactions(session, raw, "atok", initial_cursor=None)
    sync_transactions(session, raw, "atok", initial_cursor=None)

    assert len(session.exec(select(Transaction)).all()) == 1
```

- [ ] **Step 3: Verify tests fail**

Run: `.venv\Scripts\pytest tests/test_plaid_sync.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement sync**

`services/plaid_sync.py`:
```python
from datetime import date
from typing import Optional

from sqlmodel import Session, select

from models.schema import Account, Transaction


def _parse_date(s: str) -> date:
    y, m, d = s.split("-")
    return date(int(y), int(m), int(d))


def _upsert_transaction(session: Session, payload: dict) -> None:
    plaid_id = payload["transaction_id"]
    existing = session.exec(
        select(Transaction).where(Transaction.plaid_transaction_id == plaid_id)
    ).first()
    account = session.exec(
        select(Account).where(Account.plaid_account_id == payload["account_id"])
    ).first()
    if account is None:
        raise ValueError(f"Unknown account {payload['account_id']} — sync accounts first")

    pfc = payload.get("personal_finance_category") or {}
    if existing is None:
        t = Transaction(
            plaid_transaction_id=plaid_id,
            account_id=account.id,
            posted_date=_parse_date(payload["date"]),
            amount=float(payload["amount"]),
            merchant_name=payload.get("merchant_name"),
            name=payload.get("name", ""),
            plaid_category=pfc.get("primary"),
            plaid_detailed=pfc.get("detailed"),
            pending=bool(payload.get("pending", False)),
        )
        session.add(t)
    else:
        existing.posted_date = _parse_date(payload["date"])
        existing.amount = float(payload["amount"])
        existing.merchant_name = payload.get("merchant_name")
        existing.name = payload.get("name", "")
        existing.plaid_category = pfc.get("primary")
        existing.plaid_detailed = pfc.get("detailed")
        existing.pending = bool(payload.get("pending", False))
        session.add(existing)


def _remove_transaction(session: Session, plaid_id: str) -> None:
    existing = session.exec(
        select(Transaction).where(Transaction.plaid_transaction_id == plaid_id)
    ).first()
    if existing is not None:
        session.delete(existing)


def sync_transactions(
    session: Session,
    plaid_client,
    access_token: str,
    initial_cursor: Optional[str],
) -> str:
    """Pull all pages from /transactions/sync; returns final cursor."""
    cursor = initial_cursor
    while True:
        req = {"access_token": access_token}
        if cursor is not None:
            req["cursor"] = cursor
        resp = plaid_client.transactions_sync(req)

        for tx in resp.get("added", []):
            _upsert_transaction(session, tx)
        for tx in resp.get("modified", []):
            _upsert_transaction(session, tx)
        for tx in resp.get("removed", []):
            _remove_transaction(session, tx["transaction_id"])

        session.commit()
        cursor = resp["next_cursor"]
        if not resp.get("has_more", False):
            break
    return cursor
```

- [ ] **Step 5: Verify tests pass**

Run: `.venv\Scripts\pytest tests/test_plaid_sync.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add services/plaid_sync.py tests/test_plaid_sync.py tests/fixtures/
git commit -m "feat(plaid): transactions_sync handles paginated added/modified/removed"
```

---

## Task 12: Plaid sync — accounts + balance refresh

**Files:**
- Modify: `services/plaid_sync.py`
- Modify: `tests/test_plaid_sync.py`
- Create: `tests/fixtures/plaid_accounts.json`

- [ ] **Step 1: Create accounts fixture**

`tests/fixtures/plaid_accounts.json`:
```json
{
  "accounts": [
    {"account_id": "acct_1", "name": "Chase Total Checking",
     "type": "depository", "subtype": "checking",
     "balances": {"current": 1523.45, "available": 1450.00}}
  ]
}
```

- [ ] **Step 2: Append failing test**

Append to `tests/test_plaid_sync.py`:
```python
from services.plaid_sync import sync_accounts


def test_sync_accounts_inserts_and_updates_balance(session):
    raw = MagicMock()
    raw.accounts_get.return_value = _load("plaid_accounts.json")

    sync_accounts(session, raw, access_token="atok")
    rows = session.exec(select(Account)).all()
    assert len(rows) == 1
    assert rows[0].current_balance == 1523.45
    assert rows[0].available_balance == 1450.00

    # Second sync with updated balance
    raw.accounts_get.return_value = {
        "accounts": [{"account_id": "acct_1", "name": "Chase Total Checking",
                      "type": "depository", "subtype": "checking",
                      "balances": {"current": 1000.00, "available": 950.00}}]
    }
    sync_accounts(session, raw, access_token="atok")
    rows = session.exec(select(Account)).all()
    assert len(rows) == 1  # no duplicate
    assert rows[0].current_balance == 1000.00
```

- [ ] **Step 3: Verify test fails**

Run: `.venv\Scripts\pytest tests/test_plaid_sync.py::test_sync_accounts_inserts_and_updates_balance -v`
Expected: ImportError.

- [ ] **Step 4: Implement sync_accounts**

Append to `services/plaid_sync.py`:
```python
from datetime import datetime


def sync_accounts(session: Session, plaid_client, access_token: str) -> None:
    resp = plaid_client.accounts_get({"access_token": access_token})
    now = datetime.utcnow()
    for a in resp.get("accounts", []):
        existing = session.exec(
            select(Account).where(Account.plaid_account_id == a["account_id"])
        ).first()
        balances = a.get("balances", {})
        if existing is None:
            session.add(Account(
                plaid_account_id=a["account_id"],
                name=a["name"],
                type=a["type"],
                subtype=a.get("subtype", ""),
                current_balance=float(balances.get("current") or 0.0),
                available_balance=float(balances.get("available") or 0.0),
                last_synced_at=now,
            ))
        else:
            existing.name = a["name"]
            existing.current_balance = float(balances.get("current") or 0.0)
            existing.available_balance = float(balances.get("available") or 0.0)
            existing.last_synced_at = now
            session.add(existing)
    session.commit()
```

- [ ] **Step 5: Verify tests pass**

Run: `.venv\Scripts\pytest tests/test_plaid_sync.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add services/plaid_sync.py tests/test_plaid_sync.py tests/fixtures/plaid_accounts.json
git commit -m "feat(plaid): sync_accounts upserts balances"
```

---

## Task 13: Plaid sync — recurring streams reconciliation

**Files:**
- Modify: `services/plaid_sync.py`
- Modify: `tests/test_plaid_sync.py`
- Create: `tests/fixtures/plaid_recurring.json`

- [ ] **Step 1: Create recurring fixture**

`tests/fixtures/plaid_recurring.json`:
```json
{
  "outflow_streams": [
    {"stream_id": "stream_a", "merchant_name": "Netflix",
     "description": "NETFLIX.COM",
     "average_amount": {"amount": 15.99},
     "last_amount": {"amount": 15.99},
     "frequency": "MONTHLY",
     "predicted_next_date": "2026-06-05",
     "is_active": true,
     "category": ["Service", "Subscription"],
     "personal_finance_category": {"primary": "ENTERTAINMENT", "detailed": "ENTERTAINMENT_TV_AND_MOVIES"},
     "status": "MATURE"},
    {"stream_id": "stream_b", "merchant_name": "Con Edison",
     "description": "CONED ELECTRIC",
     "average_amount": {"amount": 87.50},
     "last_amount": {"amount": 92.10},
     "frequency": "MONTHLY",
     "predicted_next_date": "2026-06-12",
     "is_active": true,
     "category": ["Service", "Utilities"],
     "personal_finance_category": {"primary": "RENT_AND_UTILITIES", "detailed": "RENT_AND_UTILITIES_GAS_AND_ELECTRICITY"},
     "status": "MATURE"}
  ],
  "inflow_streams": []
}
```

- [ ] **Step 2: Append failing test**

Append to `tests/test_plaid_sync.py`:
```python
from models.schema import RecurringBill
from services.plaid_sync import sync_recurring


def test_sync_recurring_inserts_new_streams_unconfirmed(session):
    raw = MagicMock()
    raw.transactions_recurring_get.return_value = _load("plaid_recurring.json")

    sync_recurring(session, raw, access_token="atok")
    rows = session.exec(select(RecurringBill)).all()
    assert len(rows) == 2
    netflix = next(r for r in rows if r.merchant_name == "Netflix")
    assert netflix.amount == 15.99
    assert netflix.cadence == "monthly"
    assert netflix.source == "plaid_auto"
    assert netflix.confirmed_by_user is False
    assert netflix.next_due_date == date(2026, 6, 5)


def test_sync_recurring_updates_existing_stream(session):
    raw = MagicMock()
    raw.transactions_recurring_get.return_value = _load("plaid_recurring.json")
    sync_recurring(session, raw, "atok")

    # Modify amount and re-sync
    updated = _load("plaid_recurring.json")
    updated["outflow_streams"][0]["last_amount"]["amount"] = 17.99
    updated["outflow_streams"][0]["predicted_next_date"] = "2026-07-05"
    raw.transactions_recurring_get.return_value = updated
    sync_recurring(session, raw, "atok")

    netflix = session.exec(
        select(RecurringBill).where(RecurringBill.merchant_name == "Netflix")
    ).one()
    assert netflix.amount == 17.99
    assert netflix.next_due_date == date(2026, 7, 5)
```

- [ ] **Step 3: Verify tests fail**

Run: `.venv\Scripts\pytest tests/test_plaid_sync.py::test_sync_recurring_inserts_new_streams_unconfirmed -v`
Expected: ImportError.

- [ ] **Step 4: Implement sync_recurring**

Append to `services/plaid_sync.py`:
```python
from models.schema import RecurringBill

_CADENCE_MAP = {
    "WEEKLY": "weekly",
    "BIWEEKLY": "biweekly",
    "SEMI_MONTHLY": "semi_monthly",
    "MONTHLY": "monthly",
    "ANNUALLY": "annual",
    "UNKNOWN": "monthly",
}


def _categorize_pfc_for_503020(pfc_primary: str) -> str:
    """Default 50/30/20 bucket mapping for recurring bills."""
    needs = {"RENT_AND_UTILITIES", "LOAN_PAYMENTS", "TRANSPORTATION", "MEDICAL",
             "GENERAL_SERVICES", "FOOD_AND_DRINK_GROCERIES"}
    if pfc_primary in needs:
        return "needs"
    return "wants"


def sync_recurring(session: Session, plaid_client, access_token: str) -> None:
    resp = plaid_client.transactions_recurring_get({"access_token": access_token})
    for stream in resp.get("outflow_streams", []):
        stream_id = stream["stream_id"]
        last_amt = float(stream["last_amount"]["amount"])
        pfc = (stream.get("personal_finance_category") or {}).get("primary", "")
        existing = session.exec(
            select(RecurringBill).where(RecurringBill.plaid_stream_id == stream_id)
        ).first()
        next_due = _parse_date(stream["predicted_next_date"])
        if existing is None:
            session.add(RecurringBill(
                source="plaid_auto",
                plaid_stream_id=stream_id,
                merchant_name=stream.get("merchant_name") or stream.get("description", ""),
                display_name=stream.get("merchant_name") or stream.get("description", ""),
                amount=last_amt,
                cadence=_CADENCE_MAP.get(stream.get("frequency", "UNKNOWN"), "monthly"),
                next_due_date=next_due,
                category=_categorize_pfc_for_503020(pfc),
                is_active=bool(stream.get("is_active", True)),
                confidence="HIGH" if stream.get("status") == "MATURE" else "MEDIUM",
                confirmed_by_user=False,
            ))
        else:
            existing.amount = last_amt
            existing.next_due_date = next_due
            existing.is_active = bool(stream.get("is_active", True))
            session.add(existing)
    session.commit()
```

- [ ] **Step 5: Verify tests pass**

Run: `.venv\Scripts\pytest tests/test_plaid_sync.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add services/plaid_sync.py tests/test_plaid_sync.py tests/fixtures/plaid_recurring.json
git commit -m "feat(plaid): sync_recurring reconciles outflow streams unconfirmed"
```

---

## Task 14: Streamlit app entry + Settings page (paycheck config)

**Files:**
- Create: `app.py`
- Create: `pages/7_Settings.py`

- [ ] **Step 1: Write app.py**

`app.py`:
```python
"""Budget app entry. Streamlit auto-discovers pages/ — this file shows the home banner."""
import streamlit as st

from services.config import get_settings
from services.db import get_engine

st.set_page_config(page_title="Budget", page_icon=":dollar:", layout="wide")

# Touch the engine so tables exist
get_engine()

st.title("Budget")
st.write("Local Streamlit budget app — Plaid (Chase, read-only).")

try:
    s = get_settings()
    st.success(f"Configured. Plaid env: **{s.plaid_env}**. Paycheck: **${s.paycheck_net_amount:,.2f}**.")
    if not s.plaid_access_token:
        st.warning("No PLAID_ACCESS_TOKEN yet. Go to Settings to onboard Plaid Link.")
except Exception as exc:
    st.error(f"Config error — fill out `.env` (see `.env.example`). Details: {exc}")

st.markdown("**Use the sidebar to navigate to Dashboard, Bills, Envelopes, BNPL, Goals, Transactions, Settings.**")
```

- [ ] **Step 2: Write Settings page**

`pages/7_Settings.py`:
```python
import streamlit as st

from services.config import get_settings

st.set_page_config(page_title="Settings — Budget", layout="wide")
st.title("Settings")

try:
    s = get_settings()
except Exception as exc:
    st.error(f"Cannot load settings: {exc}")
    st.stop()

st.subheader("Configuration (read-only — edit `.env` to change)")
cfg = {
    "PLAID_ENV": s.plaid_env,
    "PLAID_CLIENT_ID": "set" if s.plaid_client_id else "missing",
    "PLAID_SECRET": "set" if s.plaid_secret else "missing",
    "PLAID_ACCESS_TOKEN": "set" if s.plaid_access_token else "missing",
    "PAYCHECK_NET_AMOUNT": f"${s.paycheck_net_amount:,.2f}",
    "DB_PATH": s.db_path,
}
st.table([{"key": k, "value": v} for k, v in cfg.items()])

st.subheader("Plaid Link onboarding")
st.markdown(
    """
    1. Get sandbox credentials at https://dashboard.plaid.com.
    2. Set `PLAID_CLIENT_ID`, `PLAID_SECRET`, `PLAID_ENV=sandbox` in `.env`.
    3. Run the Plaid Link flow via `python scripts/plaid_link.py` (added in a later task)
       — it prints an `access_token` you paste into `.env` as `PLAID_ACCESS_TOKEN`.
    4. Restart this app.
    """
)

st.subheader("Pay-date rules (informational)")
st.markdown(
    """
    - **Scheduled** pay dates: **15th** and **last day of month**.
    - If scheduled date is Saturday/Sunday → deposit the previous Friday.
    - If scheduled date is a US federal holiday → deposit the previous business day
      (this also covers the "Monday holiday → Saturday morning availability" case).
    """
)
```

- [ ] **Step 3: Smoke-run Streamlit**

Run (from a separate terminal): `.venv\Scripts\streamlit run app.py --server.address=127.0.0.1 --server.headless=true`
Expected: starts on http://127.0.0.1:8501 without errors. Verify Settings page renders the table (with PAYCHECK_NET_AMOUNT pulled from `.env`). Stop with Ctrl-C.

- [ ] **Step 4: Commit**

```bash
git add app.py pages/7_Settings.py
git commit -m "feat(ui): app entry + Settings page (config display + pay rules)"
```

---

## Task 15: Plaid Link helper script (CLI onboarding)

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/plaid_link.py`

This is the only place that calls `/link/token/create` and `/item/public_token/exchange` — *outside* the read-only wrapper, intentionally. It runs once.

- [ ] **Step 1: Create script**

`scripts/__init__.py`: empty file.

`scripts/plaid_link.py`:
```python
"""One-time Plaid Link onboarding. Run: python -m scripts.plaid_link

Prints an access_token you paste into .env as PLAID_ACCESS_TOKEN.

This script intentionally uses Plaid endpoints NOT in the read-only whitelist
(link/token/create, item/public_token/exchange) — these are setup-time only and
do not grant write access to the bank account.
"""
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from plaid.api import plaid_api
from plaid.configuration import Configuration
from plaid.api_client import ApiClient
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest

from services.config import get_settings


def _build_client():
    s = get_settings()
    host = {
        "sandbox": "https://sandbox.plaid.com",
        "development": "https://development.plaid.com",
        "production": "https://production.plaid.com",
    }[s.plaid_env]
    config = Configuration(host=host, api_key={"clientId": s.plaid_client_id,
                                               "secret": s.plaid_secret})
    return plaid_api.PlaidApi(ApiClient(config))


HTML_TEMPLATE = """<!doctype html>
<html><head><title>Plaid Link</title>
<script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
</head><body>
<h2>Connecting to Chase via Plaid…</h2>
<script>
  const handler = Plaid.create({{
    token: '{link_token}',
    onSuccess: (public_token, metadata) => {{
      fetch('/callback?public_token=' + encodeURIComponent(public_token));
      document.body.innerHTML = '<h2>Done — return to terminal.</h2>';
    }},
    onExit: () => {{ document.body.innerHTML = '<h2>Exited.</h2>'; }},
  }});
  handler.open();
</script>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    link_token = ""
    public_token = None

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            html = HTML_TEMPLATE.format(link_token=Handler.link_token).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html)
        elif parsed.path == "/callback":
            qs = parse_qs(parsed.query)
            Handler.public_token = qs["public_token"][0]
            self.send_response(200); self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404); self.end_headers()

    def log_message(self, *_): pass


def main():
    client = _build_client()
    req = LinkTokenCreateRequest(
        products=[Products("transactions")],
        client_name="Budget App (local)",
        country_codes=[CountryCode("US")],
        language="en",
        user=LinkTokenCreateRequestUser(client_user_id="local-user"),
    )
    link_token = client.link_token_create(req).link_token
    Handler.link_token = link_token

    server = HTTPServer(("127.0.0.1", 8765), Handler)
    print("Opening browser to http://127.0.0.1:8765 — sign in with Chase via Plaid Link.")
    webbrowser.open("http://127.0.0.1:8765")
    while Handler.public_token is None:
        server.handle_request()

    exchange = client.item_public_token_exchange(
        ItemPublicTokenExchangeRequest(public_token=Handler.public_token)
    )
    print()
    print("=" * 60)
    print("SUCCESS. Paste the following into your .env file:")
    print(f"PLAID_ACCESS_TOKEN={exchange.access_token}")
    print("=" * 60)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify imports**

Run: `.venv\Scripts\python -c "import scripts.plaid_link"`
Expected: no output, exit code 0.

- [ ] **Step 3: Commit**

```bash
git add scripts/__init__.py scripts/plaid_link.py
git commit -m "feat(plaid): one-time CLI Plaid Link onboarding script"
```

---

## Task 16: Sync facade — single "Sync now" entry point

**Files:**
- Modify: `services/plaid_sync.py`
- Modify: `tests/test_plaid_sync.py`
- Create: `services/sync_state.py` (tiny key/value table for cursor)

- [ ] **Step 1: Add sync_state model field**

Append to `models/schema.py`:
```python
class SyncState(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str
```

- [ ] **Step 2: Write failing test**

Append to `tests/test_plaid_sync.py`:
```python
from services.plaid_sync import sync_all


def test_sync_all_runs_accounts_then_transactions_then_recurring(session):
    raw = MagicMock()
    raw.accounts_get.return_value = _load("plaid_accounts.json")
    raw.transactions_sync.side_effect = [_load("plaid_sync_page1.json"),
                                          _load("plaid_sync_page2.json")]
    raw.transactions_recurring_get.return_value = _load("plaid_recurring.json")

    sync_all(session, raw, access_token="atok")

    assert len(session.exec(select(Account)).all()) == 1
    # tx_001 added then removed; tx_002, tx_003 remain
    plaid_ids = {t.plaid_transaction_id for t in session.exec(select(Transaction)).all()}
    assert plaid_ids == {"tx_002", "tx_003"}
    assert len(session.exec(select(RecurringBill)).all()) == 2
```

- [ ] **Step 3: Verify test fails**

Run: `.venv\Scripts\pytest tests/test_plaid_sync.py::test_sync_all_runs_accounts_then_transactions_then_recurring -v`
Expected: ImportError for sync_all.

- [ ] **Step 4: Implement sync_all + cursor persistence**

Append to `services/plaid_sync.py`:
```python
from models.schema import SyncState

_CURSOR_KEY = "transactions_sync_cursor"


def _load_cursor(session: Session) -> Optional[str]:
    row = session.exec(select(SyncState).where(SyncState.key == _CURSOR_KEY)).first()
    return row.value if row else None


def _save_cursor(session: Session, cursor: str) -> None:
    row = session.exec(select(SyncState).where(SyncState.key == _CURSOR_KEY)).first()
    if row is None:
        session.add(SyncState(key=_CURSOR_KEY, value=cursor))
    else:
        row.value = cursor
        session.add(row)
    session.commit()


def sync_all(session: Session, plaid_client, access_token: str) -> None:
    """One-shot full sync: accounts → transactions → recurring."""
    sync_accounts(session, plaid_client, access_token)
    cursor = _load_cursor(session)
    new_cursor = sync_transactions(session, plaid_client, access_token, cursor)
    _save_cursor(session, new_cursor)
    sync_recurring(session, plaid_client, access_token)
```

- [ ] **Step 5: Verify tests pass**

Run: `.venv\Scripts\pytest tests/test_plaid_sync.py -v`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add models/schema.py services/plaid_sync.py tests/test_plaid_sync.py
git commit -m "feat(plaid): sync_all orchestrator + persisted transactions_sync cursor"
```

---

## Task 17: Dashboard page

**Files:**
- Create: `pages/1_Dashboard.py`
- Create: `services/dashboard_data.py`
- Create: `tests/test_dashboard_data.py`

- [ ] **Step 1: Write failing test for data layer**

`tests/test_dashboard_data.py`:
```python
from datetime import date, timedelta

from models.schema import Account, RecurringBill, BNPLPlan, BNPLInstallment
from services.dashboard_data import build_dashboard_view


def test_dashboard_view_sums_bills_and_bnpl_before_next_paycheck(session):
    a = Account(plaid_account_id="acct_1", name="Chase", type="depository",
                subtype="checking", current_balance=2000.0, available_balance=2000.0)
    session.add(a); session.commit(); session.refresh(a)

    session.add(RecurringBill(source="plaid_auto", merchant_name="Con Ed",
                              display_name="Con Ed", amount=100.0, cadence="monthly",
                              next_due_date=date(2026, 5, 25), category="needs",
                              is_active=True, confirmed_by_user=True))
    session.add(RecurringBill(source="plaid_auto", merchant_name="Rent",
                              display_name="Rent", amount=1200.0, cadence="monthly",
                              next_due_date=date(2026, 6, 1), category="needs",
                              is_active=True, confirmed_by_user=True))

    plan = BNPLPlan(source="manual", provider="affirm", merchant_name="Best Buy",
                    original_amount=200.0, total_payments=4, payment_amount=50.0,
                    cadence="biweekly", start_date=date(2026, 5, 1), is_active=True)
    session.add(plan); session.commit(); session.refresh(plan)
    session.add(BNPLInstallment(plan_id=plan.id, installment_number=2,
                                due_date=date(2026, 5, 22), amount=50.0,
                                status="scheduled"))
    session.commit()

    view = build_dashboard_view(session, today=date(2026, 5, 16),
                                next_paycheck=date(2026, 5, 29))
    assert view.balance == 2000.0
    assert view.bills_due_before_paycheck == 100.0   # Con Ed; rent excluded (after 5/29)
    assert view.bnpl_due_before_paycheck == 50.0
    assert view.safe_to_spend == 1850.0
```

- [ ] **Step 2: Verify test fails**

Run: `.venv\Scripts\pytest tests/test_dashboard_data.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement dashboard_data**

`services/dashboard_data.py`:
```python
from dataclasses import dataclass
from datetime import date
from typing import List

from sqlmodel import Session, select

from models.schema import Account, RecurringBill, BNPLInstallment
from services.budget_engine import ObligationItem, safe_to_spend


@dataclass
class DashboardView:
    balance: float
    bills_due_before_paycheck: float
    bnpl_due_before_paycheck: float
    safe_to_spend: float
    upcoming_bills: List[ObligationItem]
    upcoming_bnpl: List[ObligationItem]


def build_dashboard_view(session: Session, today: date, next_paycheck: date) -> DashboardView:
    balance = sum(a.current_balance for a in session.exec(
        select(Account).where(Account.subtype == "checking")
    ).all())

    bills = session.exec(
        select(RecurringBill).where(RecurringBill.is_active == True)  # noqa: E712
    ).all()
    upcoming_bills = [
        ObligationItem(due_date=b.next_due_date, amount=b.amount, label=b.display_name)
        for b in bills
        if today <= b.next_due_date < next_paycheck
    ]

    installments = session.exec(
        select(BNPLInstallment).where(BNPLInstallment.status == "scheduled")
    ).all()
    upcoming_bnpl = [
        ObligationItem(due_date=i.due_date, amount=i.amount, label=f"BNPL #{i.installment_number}")
        for i in installments
        if today <= i.due_date < next_paycheck
    ]

    obligations = upcoming_bills + upcoming_bnpl
    sts = safe_to_spend(balance, obligations, next_paycheck_date=next_paycheck)

    return DashboardView(
        balance=round(balance, 2),
        bills_due_before_paycheck=round(sum(o.amount for o in upcoming_bills), 2),
        bnpl_due_before_paycheck=round(sum(o.amount for o in upcoming_bnpl), 2),
        safe_to_spend=sts,
        upcoming_bills=upcoming_bills,
        upcoming_bnpl=upcoming_bnpl,
    )
```

- [ ] **Step 4: Verify test passes**

Run: `.venv\Scripts\pytest tests/test_dashboard_data.py -v`
Expected: 1 passed.

- [ ] **Step 5: Implement Dashboard page**

`pages/1_Dashboard.py`:
```python
from datetime import date

import pandas as pd
import streamlit as st

from services.config import get_settings
from services.db import get_session
from services.dashboard_data import build_dashboard_view
from services.paycheck_calendar import generate_paycheck_dates, next_paycheck_after

st.set_page_config(page_title="Dashboard — Budget", layout="wide")
st.title("Dashboard")

today = date.today()
calendar = generate_paycheck_dates(start=date(today.year, today.month, 1), months=2)
np_ = next_paycheck_after(today, calendar)

with get_session() as session:
    view = build_dashboard_view(session, today=today, next_paycheck=np_.actual_deposit_date)

col1, col2, col3 = st.columns(3)
col1.metric("Safe to spend", f"${view.safe_to_spend:,.2f}",
            help=f"Balance minus obligations before {np_.actual_deposit_date}.")
col2.metric("Checking balance", f"${view.balance:,.2f}")
col3.metric("Next paycheck", np_.actual_deposit_date.strftime("%a %b %d"),
            help=f"Scheduled {np_.scheduled_date.strftime('%b %d')}")

st.subheader(f"Upcoming bills before {np_.actual_deposit_date}")
if view.upcoming_bills:
    st.dataframe(pd.DataFrame([
        {"due": b.due_date, "label": b.label, "amount": b.amount}
        for b in view.upcoming_bills
    ]), use_container_width=True, hide_index=True)
else:
    st.info("No bills due before next paycheck.")

st.subheader(f"Upcoming BNPL installments before {np_.actual_deposit_date}")
if view.upcoming_bnpl:
    st.dataframe(pd.DataFrame([
        {"due": i.due_date, "label": i.label, "amount": i.amount}
        for i in view.upcoming_bnpl
    ]), use_container_width=True, hide_index=True)
else:
    st.info("No BNPL installments due before next paycheck.")
```

- [ ] **Step 6: Smoke-run Streamlit**

Run: `.venv\Scripts\streamlit run app.py --server.headless=true`
Expected: Dashboard renders without crash. Stop with Ctrl-C.

- [ ] **Step 7: Commit**

```bash
git add pages/1_Dashboard.py services/dashboard_data.py tests/test_dashboard_data.py
git commit -m "feat(ui): Dashboard w/ safe-to-spend hero + upcoming bills + BNPL"
```

---

## Task 18: Bills page

**Files:**
- Create: `pages/2_Bills.py`

- [ ] **Step 1: Write Bills page**

`pages/2_Bills.py`:
```python
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
```

- [ ] **Step 2: Smoke-run Streamlit**

Run: `.venv\Scripts\streamlit run app.py --server.headless=true`
Expected: Bills page loads without crash; "Add manual bill" form is functional. Stop with Ctrl-C.

- [ ] **Step 3: Commit**

```bash
git add pages/2_Bills.py
git commit -m "feat(ui): Bills page — confirm/reject auto + add manual"
```

---

## Task 19: Envelopes page

**Files:**
- Create: `pages/3_Envelopes.py`
- Create: `services/envelope_data.py`
- Create: `tests/test_envelope_data.py`

- [ ] **Step 1: Write failing test**

`tests/test_envelope_data.py`:
```python
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

    # In period, matched
    session.add(Transaction(plaid_transaction_id="t1", account_id=a.id,
                            posted_date=date(2026, 5, 5), amount=50.0,
                            name="TJ", plaid_category="FOOD_AND_DRINK_GROCERIES",
                            envelope_id=e.id))
    # In period, NOT matched (different envelope)
    session.add(Transaction(plaid_transaction_id="t2", account_id=a.id,
                            posted_date=date(2026, 5, 6), amount=12.0,
                            name="Shell", plaid_category="TRANSPORTATION_GAS"))
    # Out of period
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
    # months_back=3 from May 2026 means Feb, Mar, Apr
    assert totals == [150.0, 80.0, 120.0]
```

- [ ] **Step 2: Verify test fails**

Run: `.venv\Scripts\pytest tests/test_envelope_data.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement envelope_data**

`services/envelope_data.py`:
```python
from collections import defaultdict
from datetime import date
from typing import List

from dateutil.relativedelta import relativedelta
from sqlmodel import Session, select

from models.schema import Transaction


def current_period_spend(session: Session, envelope_id: int,
                         start: date, end: date) -> float:
    rows = session.exec(
        select(Transaction).where(
            Transaction.envelope_id == envelope_id,
            Transaction.posted_date >= start,
            Transaction.posted_date <= end,
        )
    ).all()
    return round(sum(r.amount for r in rows), 2)


def monthly_totals_for_envelope(session: Session, envelope_id: int,
                                 months_back: int, today: date) -> List[float]:
    """Return spend totals for the last `months_back` complete months before `today`."""
    end = date(today.year, today.month, 1) - relativedelta(days=1)        # last day of prior month
    start = (end.replace(day=1)) - relativedelta(months=months_back - 1)

    rows = session.exec(
        select(Transaction).where(
            Transaction.envelope_id == envelope_id,
            Transaction.posted_date >= start,
            Transaction.posted_date <= end,
        )
    ).all()
    buckets = defaultdict(float)
    for r in rows:
        key = (r.posted_date.year, r.posted_date.month)
        buckets[key] += r.amount

    out = []
    cur = start
    for _ in range(months_back):
        out.append(round(buckets[(cur.year, cur.month)], 2))
        cur = cur + relativedelta(months=1)
    return out
```

- [ ] **Step 4: Verify tests pass**

Run: `.venv\Scripts\pytest tests/test_envelope_data.py -v`
Expected: 2 passed.

- [ ] **Step 5: Write Envelopes page**

`pages/3_Envelopes.py`:
```python
from datetime import date

import streamlit as st
from sqlmodel import select

from models.schema import Envelope
from services.budget_engine import (
    EnvelopeSpend, envelope_status, auto_budget_from_history
)
from services.db import get_session
from services.envelope_data import current_period_spend, monthly_totals_for_envelope
from services.paycheck_calendar import generate_paycheck_dates, next_paycheck_after

st.set_page_config(page_title="Envelopes — Budget", layout="wide")
st.title("Envelopes")

today = date.today()
cal = generate_paycheck_dates(start=date(today.year, today.month, 1), months=2)
next_pay = next_paycheck_after(today, cal).actual_deposit_date
# Period start = most recent past paycheck
prev = max((p for p in cal if p.actual_deposit_date <= today),
           key=lambda p: p.actual_deposit_date, default=None)
period_start = prev.actual_deposit_date if prev else date(today.year, today.month, 1)

with get_session() as session:
    envelopes = session.exec(select(Envelope)).all()
    if not envelopes:
        st.warning("No envelopes yet. Default envelopes will be created on first sync.")
        if st.button("Create default envelopes (Groceries / Restaurants / Gas)"):
            for n, pfc, bucket in [
                ("Groceries", "FOOD_AND_DRINK_GROCERIES", "needs"),
                ("Restaurants", "FOOD_AND_DRINK_RESTAURANTS", "wants"),
                ("Gas", "TRANSPORTATION_GAS", "needs"),
            ]:
                session.add(Envelope(name=n, current_budget_per_paycheck=0.0,
                                     plaid_category_filter=pfc, bucket=bucket))
            session.commit()
            st.rerun()
        st.stop()

    for env in envelopes:
        st.subheader(env.name)
        spent = current_period_spend(session, env.id, period_start, next_pay)
        budget = env.user_override if env.user_override is not None else env.current_budget_per_paycheck
        status = envelope_status(EnvelopeSpend(name=env.name, spent=spent, budget=budget))

        cols = st.columns([2, 2, 2, 2])
        cols[0].metric("Spent", f"${status.spent:,.2f}")
        cols[1].metric("Budget", f"${status.budget:,.2f}")
        cols[2].metric("Remaining", f"${status.remaining:,.2f}")
        color = {"OK": "green", "WARN": "orange", "OVER": "red"}[status.status]
        cols[3].markdown(f"### :{color}[{status.status}]")

        if status.budget > 0:
            st.progress(min(1.0, status.spent / status.budget))

        history = monthly_totals_for_envelope(session, env.id, months_back=3, today=today)
        suggested = auto_budget_from_history(history)
        st.caption(f"3-mo monthly totals: {history} ⇒ suggested ${suggested:.2f}/paycheck")

        c1, c2 = st.columns([1, 1])
        if c1.button(f"Apply suggested (${suggested:.2f})", key=f"app_{env.id}"):
            env.current_budget_per_paycheck = suggested
            env.user_override = None
            session.add(env); session.commit(); st.rerun()
        override = c2.number_input("Manual override ($/paycheck)", value=float(env.user_override or 0.0),
                                    step=10.0, key=f"ov_{env.id}")
        if c2.button("Save override", key=f"sav_{env.id}"):
            env.user_override = override if override > 0 else None
            session.add(env); session.commit(); st.rerun()
```

- [ ] **Step 6: Smoke-run Streamlit**

Run: `.venv\Scripts\streamlit run app.py --server.headless=true`
Expected: Envelopes page loads; offer to create default envelopes if empty.

- [ ] **Step 7: Commit**

```bash
git add pages/3_Envelopes.py services/envelope_data.py tests/test_envelope_data.py
git commit -m "feat(ui): Envelopes page w/ status + 3mo auto-budget suggestion"
```

---

## Task 20: BNPL page

**Files:**
- Create: `pages/4_BNPL.py`

- [ ] **Step 1: Write BNPL page**

`pages/4_BNPL.py`:
```python
from datetime import date

import streamlit as st
import pandas as pd
from sqlmodel import select

from models.schema import BNPLPlan, BNPLInstallment
from services.bnpl_detector import project_schedule
from services.db import get_session

st.set_page_config(page_title="BNPL — Budget", layout="wide")
st.title("Buy Now, Pay Later")

with get_session() as session:
    plans = session.exec(select(BNPLPlan).where(BNPLPlan.is_active == True)).all()  # noqa: E712

    st.subheader(f"Active plans ({len(plans)})")
    for plan in plans:
        with st.expander(f"{plan.provider.replace('_', ' ').title()} — {plan.merchant_name} (${plan.original_amount:,.2f})"):
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
```

- [ ] **Step 2: Smoke-run Streamlit**

Run: `.venv\Scripts\streamlit run app.py --server.headless=true`
Expected: BNPL page loads.

- [ ] **Step 3: Commit**

```bash
git add pages/4_BNPL.py
git commit -m "feat(ui): BNPL page w/ manual plan + projected installments"
```

---

## Task 21: Goals + Transactions pages

**Files:**
- Create: `pages/5_Goals.py`
- Create: `pages/6_Transactions.py`

- [ ] **Step 1: Write Goals page**

`pages/5_Goals.py`:
```python
from datetime import date, timedelta

import streamlit as st
import pandas as pd
from sqlmodel import select

from models.schema import Account, RecurringBill, BNPLInstallment, Envelope
from services.config import get_settings
from services.budget_engine import paycheck_leftover
from services.db import get_session
from services.paycheck_calendar import generate_paycheck_dates

st.set_page_config(page_title="Goals — Budget", layout="wide")
st.title("Goals — Leftover Tracker")

s = get_settings()
today = date.today()
cal = generate_paycheck_dates(start=date(today.year, today.month, 1), months=12)

with get_session() as session:
    envelopes = session.exec(select(Envelope)).all()
    envelopes_total_per_pay = sum(
        (e.user_override if e.user_override is not None else e.current_budget_per_paycheck)
        for e in envelopes
    )

    rows = []
    for p in cal[:12]:
        period_start = p.actual_deposit_date
        try:
            next_p = next(x for x in cal if x.actual_deposit_date > period_start)
            period_end = next_p.actual_deposit_date
        except StopIteration:
            period_end = period_start + timedelta(days=15)
        bills = session.exec(
            select(RecurringBill).where(RecurringBill.is_active == True)  # noqa: E712
        ).all()
        bills_in = sum(b.amount for b in bills
                       if period_start <= b.next_due_date < period_end)
        installments = session.exec(
            select(BNPLInstallment).where(BNPLInstallment.status == "scheduled")
        ).all()
        bnpl_in = sum(i.amount for i in installments
                      if period_start <= i.due_date < period_end)
        leftover = paycheck_leftover(
            paycheck_amount=s.paycheck_net_amount,
            bills_in_period=bills_in,
            bnpl_in_period=bnpl_in,
            envelopes_allocated=envelopes_total_per_pay,
            debt_payments=0.0,
        )
        rows.append({
            "paycheck": period_start, "amount": s.paycheck_net_amount,
            "bills": round(bills_in, 2), "bnpl": round(bnpl_in, 2),
            "envelopes": round(envelopes_total_per_pay, 2), "leftover": leftover,
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.metric("Projected 6-month leftover (savings)",
              f"${df.head(12)['leftover'].sum():,.2f}")
```

- [ ] **Step 2: Write Transactions page**

`pages/6_Transactions.py`:
```python
import streamlit as st
import pandas as pd
from sqlmodel import select

from models.schema import Transaction, Envelope
from services.db import get_session

st.set_page_config(page_title="Transactions — Budget", layout="wide")
st.title("Transactions")

with get_session() as session:
    rows = session.exec(
        select(Transaction).order_by(Transaction.posted_date.desc()).limit(500)
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
```

- [ ] **Step 3: Smoke-run Streamlit**

Run: `.venv\Scripts\streamlit run app.py --server.headless=true`
Expected: Goals and Transactions pages load.

- [ ] **Step 4: Commit**

```bash
git add pages/5_Goals.py pages/6_Transactions.py
git commit -m "feat(ui): Goals (leftover forecast) + Transactions (searchable)"
```

---

## Task 22: Sync button + categorizer auto-apply on new transactions

**Files:**
- Modify: `pages/7_Settings.py`
- Modify: `services/plaid_sync.py`
- Modify: `tests/test_plaid_sync.py`

- [ ] **Step 1: Write failing test for auto-categorization**

Append to `tests/test_plaid_sync.py`:
```python
from models.schema import Envelope


def test_sync_transactions_auto_assigns_envelope(session):
    # Seed account + envelopes
    a = Account(plaid_account_id="acct_1", name="Chase", type="depository",
                subtype="checking", current_balance=0, available_balance=0)
    session.add(a); session.commit()
    for n, pfc, bucket in [
        ("Groceries", "FOOD_AND_DRINK_GROCERIES", "needs"),
        ("Restaurants", "FOOD_AND_DRINK_RESTAURANTS", "wants"),
        ("Gas", "TRANSPORTATION_GAS", "needs"),
    ]:
        session.add(Envelope(name=n, current_budget_per_paycheck=0.0,
                             plaid_category_filter=pfc, bucket=bucket))
    session.commit()

    raw = MagicMock()
    raw.transactions_sync.side_effect = [_load("plaid_sync_page1.json"),
                                          _load("plaid_sync_page2.json")]

    sync_transactions(session, raw, "atok", None)

    by_id = {t.plaid_transaction_id: t for t in session.exec(select(Transaction)).all()}
    # tx_002 = TRANSPORTATION_GAS → Gas
    gas_env = session.exec(select(Envelope).where(Envelope.name == "Gas")).one()
    assert by_id["tx_002"].envelope_id == gas_env.id
    # tx_003 = FOOD_AND_DRINK_GROCERIES → Groceries
    grocery_env = session.exec(select(Envelope).where(Envelope.name == "Groceries")).one()
    assert by_id["tx_003"].envelope_id == grocery_env.id
```

- [ ] **Step 2: Verify test fails**

Run: `.venv\Scripts\pytest tests/test_plaid_sync.py::test_sync_transactions_auto_assigns_envelope -v`
Expected: assertion error (envelope_id is None).

- [ ] **Step 3: Apply categorizer inside `_upsert_transaction`**

Edit `services/plaid_sync.py` — replace the existing `_upsert_transaction` with this version:
```python
from models.schema import Envelope as _Envelope
from services.categorizer import categorize


def _resolve_envelope_id(session: Session, plaid_category: Optional[str],
                         merchant: Optional[str]) -> Optional[int]:
    if not plaid_category:
        return None
    envelope_name = categorize(plaid_category, merchant=merchant)
    if envelope_name is None:
        return None
    env = session.exec(select(_Envelope).where(_Envelope.name == envelope_name)).first()
    return env.id if env else None


def _upsert_transaction(session: Session, payload: dict) -> None:
    plaid_id = payload["transaction_id"]
    existing = session.exec(
        select(Transaction).where(Transaction.plaid_transaction_id == plaid_id)
    ).first()
    account = session.exec(
        select(Account).where(Account.plaid_account_id == payload["account_id"])
    ).first()
    if account is None:
        raise ValueError(f"Unknown account {payload['account_id']} — sync accounts first")

    pfc = payload.get("personal_finance_category") or {}
    pfc_primary = pfc.get("primary")
    merchant = payload.get("merchant_name")
    env_id = _resolve_envelope_id(session, pfc_primary, merchant)

    if existing is None:
        session.add(Transaction(
            plaid_transaction_id=plaid_id,
            account_id=account.id,
            posted_date=_parse_date(payload["date"]),
            amount=float(payload["amount"]),
            merchant_name=merchant,
            name=payload.get("name", ""),
            plaid_category=pfc_primary,
            plaid_detailed=pfc.get("detailed"),
            pending=bool(payload.get("pending", False)),
            envelope_id=env_id,
        ))
    else:
        existing.posted_date = _parse_date(payload["date"])
        existing.amount = float(payload["amount"])
        existing.merchant_name = merchant
        existing.name = payload.get("name", "")
        existing.plaid_category = pfc_primary
        existing.plaid_detailed = pfc.get("detailed")
        existing.pending = bool(payload.get("pending", False))
        if existing.envelope_id is None:  # don't overwrite user-set
            existing.envelope_id = env_id
        session.add(existing)
```

- [ ] **Step 4: Verify all sync tests pass**

Run: `.venv\Scripts\pytest tests/test_plaid_sync.py -v`
Expected: 7 passed.

- [ ] **Step 5: Add Sync button to Settings page**

Append to `pages/7_Settings.py`:
```python
st.subheader("Sync")
if st.button("Sync now"):
    from plaid.api import plaid_api
    from plaid.configuration import Configuration
    from plaid.api_client import ApiClient
    from services.plaid_client import PlaidReadOnlyClient
    from services.plaid_sync import sync_all
    from services.db import get_session

    if not s.plaid_access_token:
        st.error("PLAID_ACCESS_TOKEN missing — run `python -m scripts.plaid_link` first.")
    else:
        host = {
            "sandbox": "https://sandbox.plaid.com",
            "development": "https://development.plaid.com",
            "production": "https://production.plaid.com",
        }[s.plaid_env]
        raw = plaid_api.PlaidApi(ApiClient(Configuration(
            host=host,
            api_key={"clientId": s.plaid_client_id, "secret": s.plaid_secret}
        )))
        client = PlaidReadOnlyClient(raw)
        with get_session() as session:
            with st.spinner("Syncing…"):
                sync_all(session, client, s.plaid_access_token)
        st.success("Synced.")
```

- [ ] **Step 6: Commit**

```bash
git add services/plaid_sync.py tests/test_plaid_sync.py pages/7_Settings.py
git commit -m "feat(sync): auto-categorize on sync + 'Sync now' button on Settings"
```

---

## Task 23: Full test sweep + coverage gate

**Files:** none new — just verification.

- [ ] **Step 1: Run full suite with coverage**

Run: `.venv\Scripts\pytest --cov=services --cov=models --cov-report=term-missing`
Expected: all tests pass. Coverage on `services/` ≥ 85%.

- [ ] **Step 2: If coverage < 85%, add focused tests**

For any service file below 85% coverage, add at least one test covering the uncovered branch. Commit each addition separately:
```bash
git add tests/test_<name>.py
git commit -m "test(<name>): cover <branch>"
```

- [ ] **Step 3: Ruff + black**

Run: `.venv\Scripts\ruff check . && .venv\Scripts\black --check .`
Expected: no errors. If issues found, fix with `ruff check --fix` and `black .`, then commit:
```bash
git add -A
git commit -m "chore: ruff/black cleanup"
```

---

## Task 24: Manual UI verification

Streamlit pages are not unit-tested; verify them by hand.

- [ ] **Step 1: Set up sandbox `.env`**

Copy `.env.example` to `.env`. Fill in Plaid sandbox credentials from https://dashboard.plaid.com. Set `PAYCHECK_NET_AMOUNT=2500.00`.

- [ ] **Step 2: Run Plaid Link onboarding**

Run: `.venv\Scripts\python -m scripts.plaid_link`
Use the Plaid sandbox credentials: username `user_good`, password `pass_good`. Copy the printed `PLAID_ACCESS_TOKEN` into `.env`.

- [ ] **Step 3: Launch app**

Run: `.venv\Scripts\streamlit run app.py --server.address=127.0.0.1`
Open http://127.0.0.1:8501.

- [ ] **Step 4: Walk through each page**

Verify each:
- **Home:** shows configured env and paycheck amount.
- **Settings:** "Sync now" runs without error. After sync, table on Home updates.
- **Bills:** unconfirmed auto-detected bills appear. Confirm one, reject one, add one manually.
- **Envelopes:** default envelopes can be created. Suggested budget reflects synced spending.
- **BNPL:** add a manual Affirm plan with 4 biweekly $50 payments; verify installments appear.
- **Dashboard:** safe-to-spend reflects balance minus the BNPL installment due before next paycheck.
- **Goals:** projected leftover row per upcoming paycheck.
- **Transactions:** search filters work; recent transactions visible.

- [ ] **Step 5: Verify read-only enforcement live**

In a Python shell: `from services.plaid_client import PlaidReadOnlyClient, ReadOnlyViolation; PlaidReadOnlyClient(object()).transfer_create({})`
Expected: raises `ReadOnlyViolation`.

- [ ] **Step 6: Final commit if any tweaks**

If you fixed anything during manual verification, commit each fix atomically.

---

## Done criteria

- All tests pass (`pytest`) with ≥85% coverage on `services/`.
- Ruff and black clean.
- Manual UI walkthrough above completes without errors.
- Read-only enforcement test fires `ReadOnlyViolation` on any non-whitelisted method.
- `.env` is gitignored; no secrets committed.
