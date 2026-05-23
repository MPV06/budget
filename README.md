# 💰 Budget

Personal-finance dashboard built with Streamlit + Plaid (Chase, read-only).

Dark theme, glass-morphism UI, semi-monthly paycheck math, recurring-bill
projection, BNPL tracking, envelope budgets, named savings goals, emergency
fund + DTI calculators, and bcrypt-gated login. Single-user app.

---

## Local development

```powershell
# Windows
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]

# Set up secrets
cp .env.example .env             # fill in Plaid sandbox creds + paycheck amount
python -m scripts.set_password   # generates an APP_PASSWORD_HASH — paste into .env

# Onboard Plaid (one time)
python -m scripts.plaid_link     # opens browser, prints PLAID_ACCESS_TOKEN

# Run
streamlit run app.py
```

App boots at `http://localhost:8501`. Sign in with the password you set.

## Tests

```powershell
.venv\Scripts\pytest               # all tests with coverage
.venv\Scripts\pytest --no-cov -v   # faster, no coverage report
```

---

## Deploying to Streamlit Community Cloud

1. **Push to GitHub** (a fresh repo or your existing one — must be public for the free tier).
   - `.env`, `data/budget.db`, and `.streamlit/secrets.toml` are gitignored. Verify with `git status` before pushing.

2. **Connect the repo** at https://share.streamlit.io → New app → pick your repo + branch + `app.py`.

3. **Set secrets** in App Settings → Secrets. Paste this (filling in your values):

   ```toml
   # Auth — generate with: python -m scripts.set_password
   APP_PASSWORD_HASH = "$2b$12$..."

   # Plaid
   PLAID_CLIENT_ID = "..."
   PLAID_SECRET = "..."
   PLAID_ENV = "sandbox"
   PLAID_ACCESS_TOKEN = ""

   # App
   PAYCHECK_NET_AMOUNT = 2890.00
   DB_PATH = "/tmp/budget.db"     # Streamlit Cloud's ephemeral file storage
   ```

4. **Deploy**. The app auto-builds.

5. **Open the URL** → sign in with your password.

### ⚠️ Streamlit Cloud caveats

- **Filesystem is ephemeral.** Every deploy wipes `/tmp/budget.db`. For persistent data, swap to Postgres (Supabase free tier works well — replace `sqlite:///` with `postgresql://` in `services/db.py`).
- **Public repo required** (paid tier supports private). Keep ALL secrets in the dashboard, NEVER commit `.env` or `secrets.toml`.
- **Plaid Production access** is paid (~$1–3/month for one account). Sandbox is free but data is fake.
- **Custom domain**: supported in app settings. Add a CNAME record per Streamlit's docs.

---

## Security model

- **Login gate**: bcrypt-hashed password, 30-minute idle timeout, 5 failed attempts → 15-min lockout
- **Plaid read-only enforcement**: `services/plaid_client.PlaidReadOnlyClient` whitelist wrapper raises `ReadOnlyViolation` on any non-allowed endpoint
- **Secrets resolution order**: `st.secrets` → keyring (Plaid token only) → env / `.env`
- **App binds to 127.0.0.1** locally; Streamlit Cloud terminates TLS at the edge

To revoke access: rotate the password (`python -m scripts.set_password` → new hash → update secrets) AND revoke at https://my.plaid.com (deauthorizes your bank link).

---

See [`docs/superpowers/specs/2026-05-23-budget-app-design.md`](docs/superpowers/specs/2026-05-23-budget-app-design.md) for the original design and [`docs/superpowers/plans/2026-05-23-budget-app.md`](docs/superpowers/plans/2026-05-23-budget-app.md) for the implementation plan.
