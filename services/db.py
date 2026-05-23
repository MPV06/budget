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
