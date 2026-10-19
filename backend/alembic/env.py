"""Alembic migration environment with dual PostgreSQL / SQLite batching support."""

from __future__ import annotations

import logging
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import Engine, pool, text

from ai_incident_monitor.db.base import Base
import ai_incident_monitor.db.models  # Ensure all models are registered in metadata
from ai_incident_monitor.db.session import get_database_url, get_engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL and not an Engine.
    """
    url = config.get_main_option("sqlalchemy.url") or get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite"),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Enforces DEC-P3-004 Refined:
    - PostgreSQL is the primary target with standard native DDL.
    - SQLite uses batch mode, foreign key deactivation during alteration,
      reactivation, and mandatory PRAGMA foreign_key_check integrity verification.
    """
    connectable = config.attributes.get("connection", None)

    if connectable is None:
        url = config.get_main_option("sqlalchemy.url") or get_database_url()
        connectable = get_engine(url)

    if isinstance(connectable, Engine):
        with connectable.connect() as connection:
            _run_online_with_connection(connection)
    else:
        _run_online_with_connection(connectable)


def _run_online_with_connection(connection: Any) -> None:
    is_sqlite = connection.dialect.name == "sqlite"

    if is_sqlite:
        connection.execute(text("PRAGMA foreign_keys = OFF;"))

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=is_sqlite,
    )

    try:
        with context.begin_transaction():
            context.run_migrations()
        connection.commit()

        if is_sqlite:
            connection.execute(text("PRAGMA foreign_keys = ON;"))
            fk_check = connection.execute(text("PRAGMA foreign_key_check;")).fetchall()
            if fk_check:
                raise RuntimeError(f"SQLite foreign key check failed after migration: {fk_check}")
    finally:
        if is_sqlite:
            connection.execute(text("PRAGMA foreign_keys = ON;"))


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
