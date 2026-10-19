"""Base declarative class and constraint naming conventions for SQLAlchemy 2.0 ORM."""

from __future__ import annotations

from typing import Any

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Constraint naming conventions ensure identical, deterministic constraint names
# across PostgreSQL and SQLite, required for Alembic batch migrations.
POSTGRES_SQLITE_NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base declarative class with explicit constraint naming conventions."""

    metadata = MetaData(naming_convention=POSTGRES_SQLITE_NAMING_CONVENTION)

    def to_dict(self) -> dict[str, Any]:
        """Convert table column attributes to a shallow dictionary."""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
