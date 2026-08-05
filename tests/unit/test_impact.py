from __future__ import annotations

from collections.abc import Callable

from changeproof.impact import assess_impact
from changeproof.models import Confidence, MetadataEvidence


def test_fresh_column_lineage_with_owners_is_high_confidence(
    fresh_complete_evidence: Callable[[], MetadataEvidence],
) -> None:
    result = assess_impact(fresh_complete_evidence())

    assert result.confidence is Confidence.HIGH
    assert result.required_reviewers == [
        "analytics@sonicledger.demo",
        "finance@sonicledger.demo",
    ]
    assert result.critical_assets == ["artist_payouts"]
    assert result.impacted_assets[0].name == "fct_royalties"


def test_table_lineage_without_owner_coverage_is_medium_confidence(
    fresh_complete_evidence: Callable[[], MetadataEvidence],
) -> None:
    evidence = fresh_complete_evidence().model_copy(
        update={
            "column_lineage_available": False,
            "downstream": [
                node.model_copy(update={"owners": []})
                for node in fresh_complete_evidence().downstream
            ],
            "owners": [],
            "missing": ["column_lineage", "owner_coverage"],
        }
    )

    result = assess_impact(evidence)

    assert result.confidence is Confidence.MEDIUM
    assert result.required_reviewers == []
    assert "column lineage" in " ".join(result.reasons).lower()


def test_owner_coverage_gap_with_fresh_column_lineage_is_medium_confidence(
    fresh_complete_evidence: Callable[[], MetadataEvidence],
) -> None:
    evidence = fresh_complete_evidence().model_copy(
        update={
            "downstream": [
                node.model_copy(update={"owners": []})
                for node in fresh_complete_evidence().downstream
            ],
            "missing": ["owner_coverage"],
        }
    )

    result = assess_impact(evidence)

    assert result.confidence is Confidence.MEDIUM
    assert result.required_reviewers == ["analytics@sonicledger.demo"]
    assert "owner coverage" in " ".join(result.reasons).lower()
    assert "column lineage" not in " ".join(result.reasons).lower()


def test_stale_or_missing_column_lineage_lowers_confidence(
    stale_evidence: Callable[[], MetadataEvidence],
) -> None:
    result = assess_impact(stale_evidence())

    assert result.confidence is Confidence.LOW
    assert "stale" in " ".join(result.reasons).lower()


def test_missing_downstream_lineage_is_low_confidence(
    fresh_complete_evidence: Callable[[], MetadataEvidence],
) -> None:
    evidence = fresh_complete_evidence().model_copy(
        update={
            "column_lineage_available": False,
            "downstream": [],
            "missing": ["column_lineage"],
        }
    )

    result = assess_impact(evidence)

    assert result.confidence is Confidence.LOW
    assert result.impacted_assets == []
    assert "downstream lineage" in " ".join(result.reasons).lower()
