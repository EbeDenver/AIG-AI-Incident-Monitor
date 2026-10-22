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
    """Verify that Alembic migrations upgrade to head, downgrade to base, and re-upgrade cleanly.

    Also tests Binding Correction 10: downgrade from 003 removes only 003 objects and preserves
    all earlier layers.
    """
    alembic_cfg, db_url, db_path = temp_alembic_config
    engine = create_engine(db_url)

    foundation_tables = {
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
        "severity_assessments",
        "alembic_version",
    }

    governance_tables = {
        "framework_reference_sets",
        "framework_controls",
        "incident_framework_mappings",
        "eu_legal_relevance_screens",
        "mapping_evidence_links",
        "governance_audit_logs",
    }

    all_expected_tables = foundation_tables | governance_tables

    # 1. Upgrade to 002 (Phase 5 Increment 1 state)
    command.upgrade(alembic_cfg, "002")
    inspector_002 = inspect(engine)
    tables_002 = set(inspector_002.get_table_names())
    assert foundation_tables.issubset(tables_002)
    assert len(governance_tables.intersection(tables_002)) == 0, "003 tables should not exist yet"

    # 2. Upgrade to head (004)
    command.upgrade(alembic_cfg, "head")
    inspector_head = inspect(engine)
    created_tables = set(inspector_head.get_table_names())
    assert all_expected_tables.issubset(created_tables), f"Missing tables: {all_expected_tables - created_tables}"

    # Verify 004 columns exist on incident_framework_mappings
    mapping_cols = {col["name"] for col in inspector_head.get_columns("incident_framework_mappings")}
    assert "rule_id" in mapping_cols, "rule_id column must exist after 004 upgrade"
    assert "rule_version" in mapping_cols, "rule_version column must exist after 004 upgrade"

    # Verify foreign key check passes on head
    with engine.connect() as conn:
        fk_violations = conn.execute(text("PRAGMA foreign_key_check;")).fetchall()
        assert len(fk_violations) == 0, f"Foreign key check violations: {fk_violations}"

    # 3. Test selective downgrade: 004 -> 003
    command.downgrade(alembic_cfg, "003")
    inspector_down_to_003 = inspect(engine)
    mapping_cols_003 = {col["name"] for col in inspector_down_to_003.get_columns("incident_framework_mappings")}
    assert "rule_id" not in mapping_cols_003, "rule_id column must be dropped by 004 downgrade"
    assert "rule_version" not in mapping_cols_003, "rule_version column must be dropped by 004 downgrade"
    assert all_expected_tables.issubset(set(inspector_down_to_003.get_table_names())), "003 tables must remain intact"

    # 4. Test selective downgrade: 003 -> 002 (Binding Correction 10)
    # Must remove ONLY objects created by migration 003, leaving earlier records intact
    command.downgrade(alembic_cfg, "002")
    inspector_down_to_002 = inspect(engine)
    tables_after_002_down = set(inspector_down_to_002.get_table_names())
    assert foundation_tables.issubset(tables_after_002_down), "Prior foundation tables must remain intact"
    for gov_table in governance_tables:
        assert gov_table not in tables_after_002_down, f"Table {gov_table} must be dropped by 003 downgrade"

    # 5. Downgrade from 002 to base
    command.downgrade(alembic_cfg, "base")
    inspector_after_down = inspect(engine)
    tables_after_down = set(inspector_after_down.get_table_names())
    data_tables_remaining = tables_after_down - {"alembic_version"}
    assert len(data_tables_remaining) == 0, f"Tables remained after downgrade to base: {data_tables_remaining}"

    # 6. Re-upgrade to head (idempotency verification)
    command.upgrade(alembic_cfg, "head")
    inspector_reup = inspect(engine)
    recreated_tables = set(inspector_reup.get_table_names())
    assert all_expected_tables.issubset(recreated_tables)
    recreated_mapping_cols = {col["name"] for col in inspector_reup.get_columns("incident_framework_mappings")}
    assert "rule_id" in recreated_mapping_cols
    assert "rule_version" in recreated_mapping_cols

    with engine.connect() as conn:
        fk_violations = conn.execute(text("PRAGMA foreign_key_check;")).fetchall()
        assert len(fk_violations) == 0, f"Foreign key check violations on re-upgrade: {fk_violations}"

    engine.dispose()
