"""Single-user password auth for the Budget app.

Design:
- bcrypt-hashed password (no plaintext storage)
- Hash resolved from (in order): st.secrets["APP_PASSWORD_HASH"] → env var → ""
  This makes it work on Streamlit Community Cloud (secrets dashboard) AND
  local dev (.env or .streamlit/secrets.toml) without code changes.
- Session state tracks authentication + last-activity timestamp
- 30-minute idle timeout per user request
- Rate limiting: 5 failed attempts → 15-minute lockout
- Logout clears session state and rerun

Per privacy-data-security standards: no plaintext password ever written to
disk or logs; failed-attempt counter scoped to the Streamlit session.
"""
import os
import time
from typing import Optional

import bcrypt
import streamlit as st


# ─── Constants ──────────────────────────────────────────────────────
IDLE_TIMEOUT_SECONDS = 30 * 60                # 30 minutes
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60                     # 15 minutes
HASH_KEY = "APP_PASSWORD_HASH"

# Session state keys
_K_AUTH = "_auth_authenticated"
_K_LAST = "_auth_last_activity_ts"
_K_ATTEMPTS = "_auth_failed_attempts"
_K_LOCKOUT_UNTIL = "_auth_lockout_until_ts"


# ─── Hash storage ──────────────────────────────────────────────────
def get_password_hash() -> str:
    """Resolve the bcrypt hash from secrets sources, in order of preference."""
    # 1. Streamlit secrets (works on Streamlit Cloud + local secrets.toml)
    try:
        if HASH_KEY in st.secrets:
            val = st.secrets[HASH_KEY]
            if val:
                return str(val)
    except Exception:
        # st.secrets unavailable (no secrets.toml and not on Streamlit Cloud)
        pass
    # 2. Environment variable / .env
    return os.environ.get(HASH_KEY, "")


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of `plain`. Use this in scripts to generate the hash."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time password comparison via bcrypt."""
    if not hashed or not plain:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed hash — treat as a failed attempt
        return False


# ─── Session state ──────────────────────────────────────────────────
def _now() -> float:
    return time.time()


def _initialize_state() -> None:
    """Make sure auth state keys exist with safe defaults."""
    for key, default in (
        (_K_AUTH, False),
        (_K_LAST, 0.0),
        (_K_ATTEMPTS, 0),
        (_K_LOCKOUT_UNTIL, 0.0),
    ):
        if key not in st.session_state:
            st.session_state[key] = default


def is_authenticated() -> bool:
    """True iff session is authenticated AND inside the idle window."""
    _initialize_state()
    if not st.session_state[_K_AUTH]:
        return False
    if _now() - st.session_state[_K_LAST] > IDLE_TIMEOUT_SECONDS:
        # Idle timeout — force re-login
        st.session_state[_K_AUTH] = False
        return False
    # Slide the idle window forward on every authenticated render
    st.session_state[_K_LAST] = _now()
    return True


def logout() -> None:
    """Clear auth state and rerun (back to login form)."""
    st.session_state[_K_AUTH] = False
    st.session_state[_K_LAST] = 0.0
    # Don't reset attempts/lockout — those are anti-abuse
    st.rerun()


def _seconds_until_unlock() -> int:
    _initialize_state()
    remaining = st.session_state[_K_LOCKOUT_UNTIL] - _now()
    return max(0, int(remaining))


# ─── Login form ─────────────────────────────────────────────────────
def _render_login(hash_present: bool) -> None:
    """Render the login UI. Calls st.stop() so the page below never executes."""
    # Center the form using narrow columns
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        st.markdown(
            "<div style='text-align:center; padding-top: 3rem;'>"
            "<div style='font-size: 3rem; line-height: 1;'>🔒</div>"
            "<h1 style='margin-top: 1rem; margin-bottom: 0.5rem;'>Budget</h1>"
            "<p style='color: #94a3b8; margin-bottom: 2rem;'>Sign in to continue</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        if not hash_present:
            st.error(
                "🚨 No password configured. The app is currently locked.  \n"
                "Run `python -m scripts.set_password` and set "
                f"`{HASH_KEY}` in your secrets, then refresh."
            )
            st.stop()

        lock_remaining = _seconds_until_unlock()
        if lock_remaining > 0:
            mins, secs = divmod(lock_remaining, 60)
            st.error(
                f"Too many failed attempts. Try again in **{mins} min {secs} sec**."
            )
            st.stop()

        with st.form("login_form", clear_on_submit=False):
            password = st.text_input(
                "Password", type="password", label_visibility="collapsed",
                placeholder="Password", autocomplete="current-password",
            )
            submitted = st.form_submit_button(
                "Sign in", type="primary", use_container_width=True,
            )

        if submitted:
            if verify_password(password, get_password_hash()):
                st.session_state[_K_AUTH] = True
                st.session_state[_K_LAST] = _now()
                st.session_state[_K_ATTEMPTS] = 0
                st.session_state[_K_LOCKOUT_UNTIL] = 0.0
                st.rerun()
            else:
                st.session_state[_K_ATTEMPTS] += 1
                attempts = st.session_state[_K_ATTEMPTS]
                if attempts >= MAX_FAILED_ATTEMPTS:
                    st.session_state[_K_LOCKOUT_UNTIL] = _now() + LOCKOUT_SECONDS
                    st.error(
                        f"Too many failed attempts. Locked out for "
                        f"{LOCKOUT_SECONDS // 60} minutes."
                    )
                else:
                    remaining = MAX_FAILED_ATTEMPTS - attempts
                    st.error(f"Incorrect password. {remaining} attempt(s) remaining.")
                st.stop()

        # Footer
        st.markdown(
            "<div style='text-align:center; margin-top: 3rem; color: #64748b; "
            "font-size: 0.8rem;'>30-minute idle timeout · bcrypt-hashed · "
            f"5 failed attempts → {LOCKOUT_SECONDS // 60}-min lockout</div>",
            unsafe_allow_html=True,
        )

    st.stop()


def require_auth() -> None:
    """Call at the top of every page (after apply_app_chrome's CSS but before content).

    If authenticated: returns immediately.
    Otherwise: renders the login form and st.stop()s.
    """
    _initialize_state()
    hashed = get_password_hash()

    if is_authenticated():
        return

    # Not authenticated — render login (this calls st.stop())
    _render_login(hash_present=bool(hashed))
