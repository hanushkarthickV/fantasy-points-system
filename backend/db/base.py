"""
Database engine, session factory, and declarative Base for SQLAlchemy.

Connection string is read from DATABASE_URL env variable.
Engine is created lazily — the app can start without a DATABASE_URL for V1-only mode.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

DATABASE_URL = os.getenv("DATABASE_URL", "")

if DATABASE_URL.startswith("postgres://"):
    # SQLAlchemy 2.x requires postgresql:// prefix
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine: Engine | None = None
SessionLocal: sessionmaker | None = None


def _init_engine():
    """Create the engine and session factory (called once when DATABASE_URL is set)."""
    global engine, SessionLocal
    if not DATABASE_URL:
        return
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        echo=False,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


# Initialize immediately if URL is available
if DATABASE_URL:
    _init_engine()


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a DB session and closes it after request."""
    if SessionLocal is None:
        from fastapi import HTTPException
        raise HTTPException(503, "Database not configured")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
