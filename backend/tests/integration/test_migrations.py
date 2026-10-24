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

    inc2c_tables = {
        "eu_screen_rule_traces",
    }

    editorial_tables = {
        "editorial_dossiers",
        "editorial_dossier_entries",
        "editorial_dossier_reviews",
    }

    all_expected_tables = foundation_tables | governance_tables | inc2c_tables | editorial_tables

    # 1. Upgrade to 002 (Phase 5 Increment 1 state)
    command.upgrade(alembic_cfg, "002")
    inspector_002 = inspect(engine)
    tables_002 = set(inspector_002.get_table_names())
    assert foundation_tables.issubset(tables_002)
    assert len(governance_tables.intersection(tables_002)) == 0, "003 tables should not exist yet"

    # 2. Upgrade to 004 (Phase 5 Increment 2B state)
    command.upgrade(alembic_cfg, "004")
    inspector_004 = inspect(engine)
    tables_004 = set(inspector_004.get_table_names())
    assert (foundation_tables | governance_tables).issubset(tables_004)
    assert len(inc2c_tables.intersection(tables_004)) == 0, "005 tables should not exist at 004"
    screen_cols_004 = {col["name"] for col in inspector_004.get_columns("eu_legal_relevance_screens")}
    assert "screen_version" not in screen_cols_004, "screen_version should not exist at 004"

    # 3. Upgrade to 005 (Phase 5 Increment 2C-1/3B state)
    command.upgrade(alembic_cfg, "005")
    inspector_005 = inspect(engine)
    tables_005 = set(inspector_005.get_table_names())
    assert (foundation_tables | governance_tables | inc2c_tables).issubset(tables_005)
    assert len(editorial_tables.intersection(tables_005)) == 0, "006 tables should not exist at 005"

    # 4. Upgrade to head (006 - Phase 6A state)
    command.upgrade(alembic_cfg, "head")
    inspector_head = inspect(engine)
    created_tables = set(inspector_head.get_table_names())
    assert all_expected_tables.issubset(created_tables), f"Missing tables: {all_expected_tables - created_tables}"

    # Verify 006 columns exist on editorial_dossiers
    dossier_cols = {col["name"] for col in inspector_head.get_columns("editorial_dossiers")}
    expected_006_cols = {
        "id",
        "version",
        "title",
        "scope_type",
        "coverage_period_start",
        "coverage_period_end",
        "status",
        "content_hash",
        "disclaimer_version",
        "disclaimer_text",
        "methodology_notes",
        "summary_json",
        "metadata_json",
        "generated_by",
        "reviewed_by",
        "reviewed_at",
        "supersedes_dossier_id",
        "superseded_by_id",
        "rejection_reason",
    }
    assert expected_006_cols.issubset(dossier_cols), f"Missing 006 columns: {expected_006_cols - dossier_cols}"

    # Verify 004 columns exist on incident_framework_mappings
    mapping_cols = {col["name"] for col in inspector_head.get_columns("incident_framework_mappings")}
    assert "rule_id" in mapping_cols, "rule_id column must exist after 004 upgrade"
    assert "rule_version" in mapping_cols, "rule_version column must exist after 004 upgrade"

    # Verify 005 columns exist on eu_legal_relevance_screens
    screen_cols_head = {col["name"] for col in inspector_head.get_columns("eu_legal_relevance_screens")}
    expected_005_cols = {
        "screen_version",
        "relevance_level",
        "nexus_assessment",
        "ai_system_context",
        "actor_role_confidence",
        "conceptual_risk_areas",
        "potentially_relevant_reference_ids",
        "operational_relevance_areas",
        "timing_assessment",
        "known_facts",
        "unknowns",
        "disputed_facts",
        "follow_up_questions",
        "rationale",
        "disclaimer_version",
        "metadata_json",
    }
    assert expected_005_cols.issubset(screen_cols_head), f"Missing 005 columns: {expected_005_cols - screen_cols_head}"

    # Verify foreign key check passes on head
    with engine.connect() as conn:
        fk_violations = conn.execute(text("PRAGMA foreign_key_check;")).fetchall()
        assert len(fk_violations) == 0, f"Foreign key check violations: {fk_violations}"

    # 5. Test selective downgrade: 006 -> 005
    command.downgrade(alembic_cfg, "005")
    inspector_down_to_005 = inspect(engine)
    tables_down_005 = set(inspector_down_to_005.get_table_names())
    assert (foundation_tables | governance_tables | inc2c_tables).issubset(tables_down_005)
    for ed_table in editorial_tables:
        assert ed_table not in tables_down_005, f"Table {ed_table} must be dropped by 006 downgrade"

    # 6. Test selective downgrade: 005 -> 004
    command.downgrade(alembic_cfg, "004")
    inspector_down_to_004 = inspect(engine)
    tables_down_004 = set(inspector_down_to_004.get_table_names())
    assert (foundation_tables | governance_tables).issubset(tables_down_004)
    assert "eu_screen_rule_traces" not in tables_down_004, "eu_screen_rule_traces must be dropped by 005 downgrade"
    screen_cols_down_004 = {col["name"] for col in inspector_down_to_004.get_columns("eu_legal_relevance_screens")}
    assert "screen_version" not in screen_cols_down_004, "screen_version must be dropped by 005 downgrade"
    assert "relevance_level" not in screen_cols_down_004, "relevance_level must be dropped by 005 downgrade"

    # 5. Test selective downgrade: 004 -> 003
    command.downgrade(alembic_cfg, "003")
    inspector_down_to_003 = inspect(engine)
    mapping_cols_003 = {col["name"] for col in inspector_down_to_003.get_columns("incident_framework_mappings")}
    assert "rule_id" not in mapping_cols_003, "rule_id column must be dropped by 004 downgrade"
    assert "rule_version" not in mapping_cols_003, "rule_version column must be dropped by 004 downgrade"
    assert (foundation_tables | governance_tables).issubset(set(inspector_down_to_003.get_table_names())), "003 tables must remain intact"

    # 6. Test selective downgrade: 003 -> 002 (Binding Correction 10)
    # Must remove ONLY objects created by migration 003, leaving earlier records intact
    command.downgrade(alembic_cfg, "002")
    inspector_down_to_002 = inspect(engine)
    tables_after_002_down = set(inspector_down_to_002.get_table_names())
    assert foundation_tables.issubset(tables_after_002_down), "Prior foundation tables must remain intact"
    for gov_table in governance_tables:
        assert gov_table not in tables_after_002_down, f"Table {gov_table} must be dropped by 003 downgrade"

    # 7. Downgrade from 002 to base
    command.downgrade(alembic_cfg, "base")
    inspector_after_down = inspect(engine)
    tables_after_down = set(inspector_after_down.get_table_names())
    data_tables_remaining = tables_after_down - {"alembic_version"}
    assert len(data_tables_remaining) == 0, f"Tables remained after downgrade to base: {data_tables_remaining}"

    # 8. Re-upgrade to head (idempotency verification)
    command.upgrade(alembic_cfg, "head")
    inspector_reup = inspect(engine)
    recreated_tables = set(inspector_reup.get_table_names())
    assert all_expected_tables.issubset(recreated_tables)
    recreated_mapping_cols = {col["name"] for col in inspector_reup.get_columns("incident_framework_mappings")}
    assert "rule_id" in recreated_mapping_cols
    assert "rule_version" in recreated_mapping_cols
    recreated_screen_cols = {col["name"] for col in inspector_reup.get_columns("eu_legal_relevance_screens")}
    assert expected_005_cols.issubset(recreated_screen_cols)

    with engine.connect() as conn:
        fk_violations = conn.execute(text("PRAGMA foreign_key_check;")).fetchall()
        assert len(fk_violations) == 0, f"Foreign key check violations on re-upgrade: {fk_violations}"

    engine.dispose()
