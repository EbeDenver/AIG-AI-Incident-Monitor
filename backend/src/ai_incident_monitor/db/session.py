"""Database engine configuration and session lifecycle management."""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def get_repo_root() -> Path:
    """Resolve repository root path without hardcoding user directories."""
    repo_root_env = os.getenv("REPO_ROOT")
    if repo_root_env:
        return Path(repo_root_env).resolve()
    # session.py -> db -> ai_incident_monitor -> src -> backend -> repo root
    return Path(__file__).resolve().parents[4]


def get_database_url(default_sqlite: bool = True) -> str:
    """Resolve the active database URL from environment or fallback default.

    Normalizes 'postgresql://' or 'postgres://' to 'postgresql+psycopg://'.
    When no environment variable is provided and default_sqlite is True,
    falls back to a local SQLite database in $REPO_ROOT/.data/dev.db.
    """
    raw_url = os.getenv("DATABASE_URL")
    if raw_url:
        normalized = raw_url.strip()
        if normalized.startswith("postgres://"):
            return "postgresql+psycopg://" + normalized[len("postgres://") :]
        if normalized.startswith("postgresql://") and "+psycopg" not in normalized:
            return "postgresql+psycopg://" + normalized[len("postgresql://") :]
        return normalized

    if default_sqlite:
        data_dir = get_repo_root() / ".data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{data_dir / 'dev.db'}"

    raise ValueError("DATABASE_URL environment variable is not configured.")


def get_engine(
    url: str | None = None,
    echo: bool = False,
    **engine_kwargs: Any,
) -> Engine:
    """Create a configured SQLAlchemy Engine for PostgreSQL or SQLite.

    Enforces SQLite foreign key constraints via PRAGMA foreign_keys = ON.
    Enforces connection pooling and pre-ping for PostgreSQL.
    """
    resolved_url = url or get_database_url()

    if resolved_url.startswith("sqlite"):
        connect_args = engine_kwargs.pop("connect_args", {})
        if "check_same_thread" not in connect_args:
            connect_args["check_same_thread"] = False

        engine = create_engine(
            resolved_url,
            echo=echo,
            connect_args=connect_args,
            **engine_kwargs,
        )

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys = ON;")
            cursor.close()

        return engine

    # PostgreSQL configuration
    pool_size = engine_kwargs.pop("pool_size", 10)
    max_overflow = engine_kwargs.pop("max_overflow", 20)
    pool_pre_ping = engine_kwargs.pop("pool_pre_ping", True)

    return create_engine(
        resolved_url,
        echo=echo,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=pool_pre_ping,
        **engine_kwargs,
    )


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a thread-safe sessionmaker bound to the given engine."""
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


@contextmanager
def get_db_session(engine: Engine | None = None) -> Generator[Session, None, None]:
    """Context manager for managing transactional session lifecycle.

    Commits on successful completion, rolls back on error, and always closes.
    """
    eng = engine or get_engine()
    factory = get_session_factory(eng)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
