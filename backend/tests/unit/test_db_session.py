"""Unit tests for database session lifecycle and engine configuration."""

from __future__ import annotations

import os
from collections.abc import Generator
from unittest.mock import patch

import pytest
from sqlalchemy import Column, ForeignKey, Integer, String, text
from sqlalchemy.exc import IntegrityError

from ai_incident_monitor.db.base import POSTGRES_SQLITE_NAMING_CONVENTION, Base
from ai_incident_monitor.db.session import (
    get_database_url,
    get_db_session,
    get_engine,
    get_session_factory,
)


class ParentTestModel(Base):
    __tablename__ = "parent_test"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)


class ChildTestModel(Base):
    __tablename__ = "child_test"
    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey("parent_test.id"), nullable=False)


@pytest.fixture
def memory_engine() -> Generator[None, None, None]:
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_naming_convention_present() -> None:
    """Verify standard constraint naming conventions are configured on metadata."""
    assert Base.metadata.naming_convention is not None
    assert Base.metadata.naming_convention["pk"] == "pk_%(table_name)s"
    assert Base.metadata.naming_convention["fk"] == "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
    assert Base.metadata.naming_convention["uq"] == "uq_%(table_name)s_%(column_0_name)s"
    assert Base.metadata.naming_convention["ck"] == "ck_%(table_name)s_%(constraint_name)s"
    assert Base.metadata.naming_convention["ix"] == "ix_%(column_0_label)s"


def test_get_database_url_normalization() -> None:
    """Verify postgresql URLs are normalized to psycopg driver."""
    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://usr:pwd@localhost:5432/db"}):
        url = get_database_url()
        assert url == "postgresql+psycopg://usr:pwd@localhost:5432/db"

    with patch.dict(os.environ, {"DATABASE_URL": "postgres://usr:pwd@localhost:5432/db"}):
        url = get_database_url()
        assert url == "postgresql+psycopg://usr:pwd@localhost:5432/db"

    with patch.dict(os.environ, {"DATABASE_URL": "postgresql+psycopg://usr:pwd@localhost:5432/db"}):
        url = get_database_url()
        assert url == "postgresql+psycopg://usr:pwd@localhost:5432/db"


def test_get_database_url_default_sqlite() -> None:
    """Verify default database URL points to .data/dev.db in repo root."""
    with patch.dict(os.environ, {}, clear=True):
        url = get_database_url(default_sqlite=True)
        assert url.startswith("sqlite:///")
        assert url.endswith(".data/dev.db")


def test_get_database_url_raises_when_no_default() -> None:
    """Verify ValueError is raised if default_sqlite=False and no DATABASE_URL set."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="DATABASE_URL environment variable is not configured"):
            get_database_url(default_sqlite=False)


def test_sqlite_foreign_keys_pragma_enabled(memory_engine: Any) -> None:
    """Verify SQLite connection pragma enforces foreign_keys = ON."""
    with memory_engine.connect() as conn:
        result = conn.execute(text("PRAGMA foreign_keys;")).scalar()
        assert result == 1


def test_sqlite_foreign_key_violation_enforced(memory_engine: Any) -> None:
    """Verify that foreign key violations raise IntegrityError in SQLite."""
    factory = get_session_factory(memory_engine)
    with factory() as session:
        # Attempt to insert child with non-existent parent
        child = ChildTestModel(id=1, parent_id=999)
        session.add(child)
        with pytest.raises(IntegrityError):
            session.commit()


def test_get_db_session_commit_and_rollback(memory_engine: Any) -> None:
    """Verify transaction commit on normal exit and rollback on exception."""
    factory = get_session_factory(memory_engine)

    # Test commit
    with get_db_session(memory_engine) as session:
        parent = ParentTestModel(id=1, name="Parent 1")
        session.add(parent)

    with factory() as session:
        persisted = session.get(ParentTestModel, 1)
        assert persisted is not None
        assert persisted.name == "Parent 1"

    # Test rollback on error
    with pytest.raises(RuntimeError, match="Simulation error"):
        with get_db_session(memory_engine) as session:
            parent2 = ParentTestModel(id=2, name="Parent 2")
            session.add(parent2)
            raise RuntimeError("Simulation error")

    with factory() as session:
        persisted2 = session.get(ParentTestModel, 2)
        assert persisted2 is None
