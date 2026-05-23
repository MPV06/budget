# Budget App — Design Spec

**Date:** 2026-05-23
**Status:** Approved
**Author:** sboy06 + Claude

## 1. Problem & Goals

Personal local budget app for a single user paid semi-monthly (fixed salary) by Chase. The app must answer four questions on demand:

1. **Safe-to-spend right now:** current Chase checking balance minus every obligation that hits before the next paycheck.
2. **What's left over each paycheck** after bills, subscriptions, gas, food, debt payments, and BNPL installments.
3. **Are my envelopes (Groceries / Restaurants / Gas) on track** for this pay period.
4. **Where does this fit against 50/30/20** as a sanity check.

Non-goals: investing, net worth, multi-user, mobile, cloud deploy, write/transfer access to bank, anything that isn't a personal local money tracker.

## 2. Constraints

- Plaid is the only bank connection (no public Chase API exists for consumers). Read-only by whitelist.
- Streamlit UI, runs on `localhost`.
- Local-only data. Secrets in `.env` (gitignored).
- Python 3.11+.
- Must work for a Python learner — keep code idiomatic, well-named, tested, and short.

## 3. Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Streamlit App (single process, localhost:8501)          │
│                                                          │
│  Pages:  Dashboard │ Bills │ Envelopes │ BNPL │ Goals   │
│          Transactions │ Settings                         │
│                                                          │
│  Service layer (pure Python, fully unit-testable):      │
│    paycheck_calendar  — pay dates incl. weekend/holiday │
│    plaid_sync         — pulls txns, recurring, balance  │
│    budget_engine      — safe-to-spend, envelopes, 50/30 │
│    categorizer        — Plaid → envelope; BNPL detector │
│                                                          │
│  Storage:  SQLite (./data/budget.db)                    │
│  Secrets:  .env  (PLAID_CLIENT_ID, PLAID_SECRET,        │
│                   PLAID_ACCESS_TOKEN, PLAID_ENV)        │
└─────────────────────────────────────────────────────────┘
```

**Strict layering rule:** Streamlit pages contain NO business logic. They call service functions and render. All math, dates, and Plaid logic live in `services/` modules that are pure Python and unit-testable.

**Read-only enforcement:** A `PlaidReadOnlyClient` wrapper whitelists exactly these four endpoints:
- `/accounts/get`
- `/transactions/sync`
- `/transactions/recurring/get`
- `/item/get`

Any attempt to call anything else raises `ReadOnlyViolation`.

## 4. Tech Stack

- Python 3.11+
- `streamlit ≥ 1.32`
- `plaid-python ≥ 22`
- `pandas`, `python-dateutil`, `holidays` (US federal), `python-dotenv`, `pydantic`
- `sqlmodel` for typed schema + migrations
- `pytest`, `pytest-cov`, `ruff`, `black`

## 5. Data Model (SQLite)

```sql
accounts (
  id PK, plaid_account_id UNIQUE, name, type, subtype,
  current_balance, available_balance, last_synced_at
)

transactions (
  id PK, plaid_transaction_id UNIQUE, account_id FK,
  posted_date, amount,          -- positive = money out (Plaid convention)
  merchant_name, name, plaid_category, plaid_detailed, pending,
  envelope_id FK NULL,          -- user override
  bill_id FK NULL,              -- matched to recurring bill
  bnpl_installment_id FK NULL
)

recurring_bills (
  id PK, source ENUM('plaid_auto','manual'),
  plaid_stream_id NULL, merchant_name, display_name,
  amount, cadence, next_due_date, category,
  is_active, confidence, confirmed_by_user, notes
)

bnpl_plans (
  id PK, source, provider, merchant_name,
  original_amount, total_payments, payment_amount,
  cadence, start_date, is_active
)
bnpl_installments (
  id PK, plan_id FK, installment_number,
  due_date, amount, status, paid_transaction_id FK NULL
)

envelopes (
  id PK, name, rolling_window_days DEFAULT 90,
  current_budget_per_paycheck, user_override NULL,
  plaid_category_filter, bucket  -- needs/wants
)

paychecks (
  id PK, scheduled_date, actual_deposit_date,
  amount, is_projected
)

schema_version (version, applied_at)
```

**Design choices:**

1. **Transactions are immutable.** All categorization is via nullable override FKs. The categorizer can be re-run anytime without data loss.
2. **Bills and BNPL are separate.** BNPL has a finite payment schedule and per-installment status.
3. **Paycheck calendar is precomputed** for the next 12 months on first run and refreshed monthly.
4. **`plaid_transaction_id` is the dedup key.** `/transactions/sync` cursor handles added/modified/removed incrementally.

## 6. Paycheck Calendar Logic

**Pay rules (user-provided):**
- Semi-monthly: scheduled = 15th of month and last day of month.
- If scheduled date is **Saturday or Sunday** → deposit the **previous Friday**.
- If scheduled date is a **US federal holiday** → deposit the **previous business day**.
- *Note on Monday:* user mentioned "Monday → Saturday morning"; treated as: if Monday is a federal holiday (e.g., MLK Day, Presidents Day, Memorial Day), the deposit moves to the **previous business day**, which can be a Friday — and the user perceives the funds as available Saturday morning. Codified as: holiday-adjusted previous business day. *Confirmed in design review.*

**Algorithm:**
```python
def actual_deposit_date(scheduled: date) -> date:
    d = scheduled
    while d.weekday() >= 5 or d in US_FEDERAL_HOLIDAYS:
        d -= timedelta(days=1)
    return d
```

Calendar is generated for 12 months ahead on first run, refreshed monthly via a UI button and on app startup if stale.

## 7. Plaid Sync Flow

**Onboarding (one-time):**
1. Settings page renders Plaid Link via embedded HTML component.
2. User authenticates with Chase in the Plaid Link widget.
3. Browser posts `public_token` back to Streamlit.
4. Server exchanges for `access_token` via `/item/public_token/exchange` (one-time exception in the read-only wrapper, guarded by a setup-mode flag).
5. `access_token` written to `.env` (or printed to terminal for manual paste — safer than file-writing from a web context).
6. Initial pull: 24 months of transactions for category baselines.

**Incremental sync (on-demand via "Sync" button, or scheduled hourly while app is open):**
1. `/transactions/sync` with cursor → added/modified/removed.
2. `/accounts/get` → balance refresh.
3. `/transactions/recurring/get` → recurring streams.
4. Run `categorizer` on new/modified transactions.
5. Run `bnpl_detector` on new transactions.
6. Run `recurring_reconciler` to match Plaid streams against `recurring_bills` table; surface NEW unconfirmed streams for user review.

**Categorizer:**
- Default: map Plaid PFC categories → envelopes via config table.
  - `FOOD_AND_DRINK_GROCERIES` → Groceries
  - `FOOD_AND_DRINK_RESTAURANTS`, `FOOD_AND_DRINK_FAST_FOOD`, `FOOD_AND_DRINK_COFFEE` → Restaurants
  - `TRANSPORTATION_GAS` → Gas
- User can override per-merchant ("always count Costco as Groceries") — stored as merchant→envelope map.
- Per-transaction override stored in `transactions.envelope_id`.

**BNPL detector:**
- Watches merchant names against known BNPL providers: `affirm`, `klarna`, `afterpay`, `chase pay in 4`, and Chase Pay-in-4 descriptor patterns.
- On detection of a new plan, surfaces a prompt: "Detected new Affirm purchase $X — how many payments?" User fills in the schedule.
- Future installments are projected into `bnpl_installments` and counted as upcoming obligations.

## 8. Budget Engine

**Safe-to-spend (the headline number):**
```
safe_to_spend = checking_balance
              - SUM(recurring_bills due before next paycheck and not yet paid)
              - SUM(bnpl_installments due before next paycheck and not yet paid)
```

**Per-paycheck leftover (forward-looking):**
```
leftover_this_paycheck =
    expected_paycheck_amount
  - bills_due_this_pay_period
  - bnpl_due_this_pay_period
  - envelope_budgets_allocated_this_pay_period
  - debt_payments_this_pay_period
```

A pay period = days from this deposit to (but not including) next deposit.

**Envelope status (per envelope, current pay period):**
```
spent_this_period       = SUM(matched transactions, this pay period)
budget_this_period      = envelope.current_budget_per_paycheck
remaining_this_period   = budget - spent
status = OK if spent < 80% of budget
       = WARN if 80–100%
       = OVER if > 100%
```

**Envelope auto-budget (3-month rolling average, recomputed weekly):**
```
budget_per_paycheck = mean(monthly_spend_last_3_months) / 2
                      # 2 paychecks per month
```
With a 7-day cooldown between auto-adjustments to prevent thrash. User override always wins.

**50/30/20 view (analytical secondary):**
- **Needs (50%):** bills with `category='needs'`, gas, groceries
- **Wants (30%):** restaurants, discretionary
- **Savings/Debt (20%):** debt payments, transfers to savings, leftover

Show this as a stacked bar against actual allocation. Highlight buckets that are off-target by >5pp.

## 9. UI Pages

**Dashboard (home):**
- Hero: SAFE-TO-SPEND big number with sub-line "until next paycheck on YYYY-MM-DD".
- Next paycheck card: date, amount, projected leftover.
- Upcoming bills (next 14 days) table.
- Envelope status: 3 progress bars.
- 50/30/20 stacked bar.

**Bills:**
- Table of all recurring bills (auto-detected + manual).
- NEW UNCONFIRMED section at top — Plaid found these streams, user confirms or rejects.
- Add/edit/delete manual bills.

**Envelopes:**
- Per-envelope card with: budget, spent, remaining, suggested-from-history, override input.
- 90-day spending chart per envelope.

**BNPL:**
- Active plans with payment schedule.
- "Add plan manually" form.
- Auto-detected plans pending confirmation.

**Goals (lightweight):**
- "Leftover" is the savings number — show running 6-month total saved.
- Optional named goals (Emergency Fund target, etc.) with progress bars.

**Transactions:**
- Searchable, filterable table of all transactions.
- Per-row envelope override dropdown.

**Settings:**
- Plaid Link onboarding (first run).
- Manual sync button.
- Paycheck amount (net) configuration.
- Pay date rules (read-only display of the algorithm).
- Envelope auto-budget toggle.

## 10. Error Handling

- **Plaid `ITEM_LOGIN_REQUIRED`:** banner on Dashboard with re-auth link via Plaid Link update mode.
- **Plaid rate limits / network errors:** exponential backoff with max 3 retries; last-successful-sync timestamp shown on every page.
- **Missing pay date config:** Settings page blocks all other pages until paycheck amount is entered.
- **DB migration failure:** app refuses to start; prints schema_version vs. expected.
- **Read-only violation:** raises immediately; logged and shown as a banner.

## 11. Testing Strategy

**Test-driven for the services layer.** No UI testing for v1 (Streamlit's testability is limited; manual verification per the user's instructions).

Test files:
- `tests/test_paycheck_calendar.py` — every weekend/holiday combination, leap years, MLK/Memorial/Labor Day, year boundary.
- `tests/test_budget_engine.py` — safe-to-spend with/without bills, with/without BNPL, edge cases (negative balance, pay day = today).
- `tests/test_categorizer.py` — mapping table, user override precedence.
- `tests/test_bnpl_detector.py` — Affirm and Chase Pay-in-4 string matching, schedule projection.
- `tests/test_plaid_readonly.py` — wrapper raises on every non-whitelisted endpoint.
- `tests/test_sync.py` — `/transactions/sync` cursor handling with mocked Plaid responses (added/modified/removed).

Coverage target: ≥85% on `services/`. UI code is excluded from coverage.

## 12. Project Layout

```
budget/
  app.py                      # Streamlit entry point
  pages/
    1_Dashboard.py
    2_Bills.py
    3_Envelopes.py
    4_BNPL.py
    5_Goals.py
    6_Transactions.py
    7_Settings.py
  services/
    __init__.py
    config.py                 # pydantic settings, .env loader
    db.py                     # sqlmodel engine, migrations
    paycheck_calendar.py
    plaid_client.py           # PlaidReadOnlyClient wrapper
    plaid_sync.py
    categorizer.py
    bnpl_detector.py
    budget_engine.py
  models/
    __init__.py
    schema.py                 # sqlmodel table definitions
  data/
    budget.db                 # gitignored
  tests/
    test_paycheck_calendar.py
    test_budget_engine.py
    test_categorizer.py
    test_bnpl_detector.py
    test_plaid_readonly.py
    test_sync.py
    fixtures/                 # plaid response fixtures
  docs/
    superpowers/specs/2026-05-23-budget-app-design.md
  .env.example
  .gitignore
  pyproject.toml
  README.md
```

## 13. Security Notes

- `.env` is in `.gitignore`. So is `data/budget.db`.
- `PLAID_ACCESS_TOKEN` only ever read from env; never logged.
- App binds to `127.0.0.1` only (Streamlit's `--server.address=127.0.0.1`).
- Read-only wrapper enforced via whitelist; tested.
- Plaid `Production` environment (not `Sandbox`) is gated behind an explicit env var `PLAID_ENV=production` so accidental flips don't happen.

## 14. Out of Scope (v1)

- Multi-bank, multi-user, mobile, cloud deploy.
- Investment tracking, net worth.
- Bill pay / transfers.
- Tax categorization beyond Plaid's PFC.
- Predictive ML for spending forecasts.

## 15. Open Questions / Risks

- **Plaid Link inside Streamlit** is the trickiest piece. Fallback: `streamlit-plaid` community component; if unmaintained, embed Plaid's official JS via `st.components.v1.html` and shuttle the `public_token` back via a callback URL. This is the first thing to validate during implementation.
- **Plaid recurring detection** quality varies — confirmation UX is mandatory; don't auto-trust.
- **BNPL via Chase Pay-in-4** posts as a Chase descriptor; pattern matching may need iteration. The detector ships with a small initial pattern set and a "report incorrect detection" path.
