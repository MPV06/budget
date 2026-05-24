"""SQLite engine + session management.

Performance per `python-performance-optimization` standard:
  - Engine cached via Streamlit's @st.cache_resource so it survives reruns
    AND only one engine exists for the entire app lifetime
  - Sessions are cheap to create from a cached engine (SQLite connection pool reuses connections)
  - `models.schema` imported once at module load to register all tables before
    SQLModel.metadata.create_all runs
"""
from pathlib import Path

import streamlit as st
from sqlmodel import SQLModel, Session, create_engine

from services.config import get_settings

import models.schema  # noqa: F401  -- register tables before create_all


# Module-level singleton kept as a safety net when imported outside Streamlit
# (e.g., from tests). When inside Streamlit, @st.cache_resource is the primary mechanism.
_engine = None


@st.cache_resource(show_spinner=False)
def _create_cached_engine(db_path: str):
    """Cached by db_path so changing it in settings creates a fresh engine."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False allows Streamlit's background threads to share connections
    eng = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        # Enable connection pooling — small pool for single-user app
        pool_pre_ping=True,
    )
    SQLModel.metadata.create_all(eng)
    return eng


def get_engine():
    """Return the (cached) SQLAlchemy engine. Safe to call repeatedly.

    Always re-runs SQLModel.metadata.create_all() — that's idempotent (creates
    only missing tables, microsecond cost) and ensures new schema migrations
    take effect even when the engine is held in @st.cache_resource across deploys.
    """
    global _engine
    try:
        _engine = _create_cached_engine(get_settings().db_path)
    except Exception:
        # Outside Streamlit (e.g., pytest with overridden settings)
        if _engine is None:
            path = get_settings().db_path
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            _engine = create_engine(
                f"sqlite:///{path}",
                connect_args={"check_same_thread": False},
                pool_pre_ping=True,
            )
    # Always ensure ALL currently-registered tables exist. Catches the case
    # where the engine was cached before a new model class was added.
    SQLModel.metadata.create_all(_engine)
    return _engine


def get_session() -> Session:
    """Create a new session bound to the cached engine."""
    return Session(get_engine())
