"""SQLAlchemy engine, session factory and declarative base."""
from __future__ import annotations

from collections.abc import Generator
from datetime import datetime

from sqlalchemy import DateTime, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    # Section 7: "TIMESTAMPTZ for all times" -- every bare Mapped[datetime]
    # column gets timezone=True automatically, instead of SQLAlchemy's
    # naive-by-default DateTime().
    type_annotation_map = {
        datetime: DateTime(timezone=True),
    }


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
