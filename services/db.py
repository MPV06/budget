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
    """Return the (cached) SQLAlchemy engine. Safe to call repeatedly."""
    global _engine
    try:
        # Inside Streamlit: cached resource is reused across reruns
        _engine = _create_cached_engine(get_settings().db_path)
    except Exception:
        # Outside Streamlit (e.g., pytest with overridden settings): fall back to module global
        if _engine is None:
            path = get_settings().db_path
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            _engine = create_engine(
                f"sqlite:///{path}",
                connect_args={"check_same_thread": False},
                pool_pre_ping=True,
            )
            SQLModel.metadata.create_all(_engine)
    return _engine


def get_session() -> Session:
    """Create a new session bound to the cached engine."""
    return Session(get_engine())
