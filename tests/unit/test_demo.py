from collections.abc import Callable

import pytest

from changeproof.demo import (
    analyze_demo_change,
    build_demo_request,
    compose_analysis,
)
from changeproof.models import ChangeType, Confidence, MetadataEvidence


def test_analyze_demo_type_change_returns_impact_and_safe_plan() -> None:
    result = analyze_demo_change(column="artist_id", old_type="varchar", new_type="bigint")

    assert result.request.change_type is ChangeType.COLUMN_TYPE_CHANGE
    assert result.impact.confidence is Confidence.HIGH
    assert [asset.name for asset in result.impact.impacted_assets] == [
        "fct_royalties",
        "artist_payouts",
        "finance_royalty_dashboard",
    ]
    assert result.plan.strategy == "parallel_typed_field"
    assert result.plan.rollout_steps
    assert result.evidence_source == "Bundled SonicLedger demo metadata"


def test_analyze_demo_rejects_unknown_column() -> None:
    with pytest.raises(ValueError, match="Unknown column 'unknown'"):
        analyze_demo_change(column="unknown", old_type="varchar", new_type="bigint")


def test_build_demo_request_validates_and_classifies_type_change() -> None:
    request = build_demo_request(
        column=" artist_id ", old_type=" varchar ", new_type=" bigint "
    )

    assert request.change_type is ChangeType.COLUMN_TYPE_CHANGE
    assert request.old_type == "varchar"
    assert request.new_type == "bigint"


def test_compose_analysis_uses_supplied_evidence(
    fresh_complete_evidence: Callable[[], MetadataEvidence],
) -> None:
    request = build_demo_request(
        column="artist_id", old_type="varchar", new_type="bigint"
    )
    evidence = fresh_complete_evidence()

    result = compose_analysis(
        request=request,
        evidence=evidence,
        evidence_source="Live DataHub MCP evidence",
    )

    assert result.evidence is evidence
    assert result.evidence_source == "Live DataHub MCP evidence"
    assert [asset.name for asset in result.impact.impacted_assets] == [
        "fct_royalties",
        "artist_payouts",
    ]
    assert result.plan.strategy == "parallel_typed_field"


def test_catalog_scenarios_produce_a_real_spread_of_confidence():
    from changeproof.demo import CATALOG, analyze_demo_change
    from changeproof.models import Confidence

    got = {}
    for name, entry in CATALOG.items():
        analysis = analyze_demo_change(
            column=name, old_type=entry.old_type, new_type=entry.new_type
        )
        got[name] = analysis.impact.confidence

    assert got["artist_id"] is Confidence.HIGH
    assert got["track_id"] is Confidence.HIGH
    assert got["payout_amount"] is Confidence.MEDIUM, "table-level lineage only"
    assert got["stream_ts"] is Confidence.LOW, "stale metadata"
    assert got["listener_email"] is Confidence.LOW, "no downstream observed"
    assert len(set(got.values())) == 3, "demo should show all three confidence levels"


def test_scenarios_have_distinct_blast_radii():
    from changeproof.demo import CATALOG, analyze_demo_change

    radii = {}
    for name, entry in CATALOG.items():
        analysis = analyze_demo_change(
            column=name, old_type=entry.old_type, new_type=entry.new_type
        )
        radii[name] = len(analysis.impact.impacted_assets)

    assert radii["artist_id"] == 3
    assert radii["track_id"] == 2
    assert radii["listener_email"] == 0
    assert len(set(radii.values())) > 1


def test_low_confidence_scenarios_explain_themselves():
    from changeproof.demo import analyze_demo_change

    stale = analyze_demo_change(
        column="stream_ts", old_type="timestamp", new_type="timestamptz"
    )
    assert any("stale" in reason.lower() for reason in stale.impact.reasons)

    orphan = analyze_demo_change(
        column="listener_email", old_type="varchar", new_type="text"
    )
    assert any("no usable downstream" in r.lower() for r in orphan.impact.reasons)


def test_each_scenario_uses_its_own_source_table():
    from changeproof.demo import CATALOG, analyze_demo_change

    seen = set()
    for name, entry in CATALOG.items():
        analysis = analyze_demo_change(
            column=name, old_type=entry.old_type, new_type=entry.new_type
        )
        assert entry.source_table in analysis.evidence.source_urn
        assert analysis.evidence.source_field == name
        seen.add(entry.source_table)

    assert len(seen) > 1, "catalog should span more than one source table"
