"""Integration tests for Alembic database migration upgrade and downgrade cycles."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
from typing import Generator

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect, text


@pytest.fixture
def temp_alembic_config() -> Generator[tuple[Config, str, Path], None, None]:
    """Provide an isolated Alembic configuration connected to a temporary SQLite database."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_migration.db"
        db_url = f"sqlite:///{db_path}"

        repo_root = Path(__file__).resolve().parents[3]
        ini_path = repo_root / "backend" / "alembic.ini"

        alembic_cfg = Config(str(ini_path))
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        alembic_cfg.set_main_option("script_location", str(repo_root / "backend" / "alembic"))

        yield alembic_cfg, db_url, db_path


def test_alembic_upgrade_downgrade_cycle(temp_alembic_config: tuple[Config, str, Path]) -> None:
    """Verify that Alembic migrations upgrade to head, downgrade to base, and re-upgrade cleanly."""
    alembic_cfg, db_url, db_path = temp_alembic_config
    engine = create_engine(db_url)

    expected_tables = {
        "audit_logs",
        "human_review_records",
        "incidents",
        "source_references",
        "ai_involvement_assessments",
        "claim_records",
        "evidence_records",
        "raw_import_records",
        "uncertainty_records",
        "causal_assessments",
        "claim_evidence_links",
        "dedup_candidates",
        "disputed_facts",
        "quote_spans",
        "alembic_version",
    }

    # 1. Upgrade to head
    command.upgrade(alembic_cfg, "head")

    inspector = inspect(engine)
    created_tables = set(inspector.get_table_names())
    assert expected_tables.issubset(created_tables), f"Missing tables: {expected_tables - created_tables}"

    # Verify foreign key check passes
    with engine.connect() as conn:
        fk_violations = conn.execute(text("PRAGMA foreign_key_check;")).fetchall()
        assert len(fk_violations) == 0, f"Foreign key check violations: {fk_violations}"

    # 2. Downgrade to base
    command.downgrade(alembic_cfg, "base")

    inspector_after_down = inspect(engine)
    tables_after_down = set(inspector_after_down.get_table_names())
    # Only alembic_version might remain or be empty; data tables must be dropped
    data_tables_remaining = tables_after_down - {"alembic_version"}
    assert len(data_tables_remaining) == 0, f"Tables remained after downgrade: {data_tables_remaining}"

    # 3. Re-upgrade to head (idempotency verification)
    command.upgrade(alembic_cfg, "head")
    inspector_reup = inspect(engine)
    recreated_tables = set(inspector_reup.get_table_names())
    assert expected_tables.issubset(recreated_tables)

    engine.dispose()
