"""Tests for UncertaintyRecord and DisputedFact."""

import pytest

from ai_incident_monitor.domain.uncertainty import DisputedFact, UncertaintyRecord
from ai_incident_monitor.domain.vocabularies import UnresolvedReason


def test_valid_disputed_fact():
    df = DisputedFact(
        assertion="The vehicle warning beacon was active at impact.",
        contesting_party="Pedestrian Eyewitness Association",
        supporting_evidence_ids=["EVD-101"],
        contradicting_evidence_ids=["EVD-102"],
    )
    assert len(df.supporting_evidence_ids) == 1
    assert len(df.contradicting_evidence_ids) == 1


def test_valid_uncertainty_record():
    ur = UncertaintyRecord(
        id="UNC-001",
        incident_id="INC-001",
        known_facts=["System triggered emergency stop"],
        unknown_facts=["Operator response latency"],
        missing_evidence=["Internal telemetry dump"],
        conflicting_evidence=["Eyewitness statement contradicts camera telemetry"],
        reason_unresolved=UnresolvedReason.INVESTIGATION_ONGOING,
    )
    assert len(ur.known_facts) == 1
    assert len(ur.unknown_facts) == 1
    # Rule 21: missing evidence is distinct from conflicting evidence
    assert ur.missing_evidence != ur.conflicting_evidence
