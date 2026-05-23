# Budget

Local Streamlit budget app with Plaid (Chase read-only) integration.

## Setup

1. `python -m venv .venv && .venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (Unix)
2. `pip install -e .[dev]`
3. `cp .env.example .env` and fill in Plaid credentials
4. `python -m scripts.plaid_link` to onboard Chase via Plaid Link, paste token into `.env`
5. `streamlit run app.py`

## Tests

`pytest`

See [`docs/superpowers/specs/2026-05-23-budget-app-design.md`](docs/superpowers/specs/2026-05-23-budget-app-design.md) for design and [`docs/superpowers/plans/2026-05-23-budget-app.md`](docs/superpowers/plans/2026-05-23-budget-app.md) for the implementation plan.
