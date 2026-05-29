"""SQLAlchemy engine + session management.

Two storage modes, selected automatically by config:

  1. PERSISTENT (Postgres) — when DATABASE_URL is set in env / st.secrets.
     Recommended for Streamlit Cloud (Supabase free tier has a persistent DB,
     unlike /tmp/budget.db which wipes when the container sleeps).
  2. EPHEMERAL (SQLite) — fallback when DATABASE_URL is empty. Used for local
     dev (./data/budget.db) and one-shot Streamlit Cloud trials.

Engine is cached via @st.cache_resource so it survives reruns. metadata.create_all
runs on every get_engine() call (idempotent — creates only missing tables) so
new model classes take effect even when the engine is held in cache across deploys.
"""
from pathlib import Path

import streamlit as st
from sqlmodel import SQLModel, Session, create_engine

from services.config import get_settings

import models.schema  # noqa: F401  -- register tables before create_all


# Module-level singleton kept as a safety net when imported outside Streamlit
# (e.g., from tests).
_engine = None


def _build_engine(database_url: str, db_path: str):
    """Create a SQLAlchemy engine from either a Postgres URL or a SQLite path."""
    if database_url:
        # Postgres / external DB — let SQLAlchemy parse and validate the URL.
        # pool_pre_ping handles connections that go stale during idle periods
        # (common on hosted Postgres tiers like Supabase free).
        return create_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=1800,  # recycle connections every 30 min
        )
    # SQLite fallback
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )


@st.cache_resource(show_spinner=False)
def _create_cached_engine(database_url: str, db_path: str):
    """Cached by (database_url, db_path) so swapping either creates a fresh engine."""
    return _build_engine(database_url, db_path)


def get_engine():
    """Return the (cached) SQLAlchemy engine. Safe to call repeatedly.

    Always re-runs SQLModel.metadata.create_all() — that's idempotent (creates
    only missing tables, microsecond cost) and ensures new schema migrations
    take effect even when the engine is held in @st.cache_resource across deploys.
    """
    global _engine
    s = get_settings()
    try:
        _engine = _create_cached_engine(s.database_url, s.db_path)
    except Exception:
        # Outside Streamlit (e.g., pytest with overridden settings)
        if _engine is None:
            _engine = _build_engine(s.database_url, s.db_path)
    # Ensure ALL currently-registered tables exist.
    SQLModel.metadata.create_all(_engine)
    return _engine


def get_session() -> Session:
    """Create a new session bound to the cached engine."""
    return Session(get_engine())
