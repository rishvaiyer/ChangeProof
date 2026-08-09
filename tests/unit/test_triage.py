import pytest

from changeproof.triage import (
    SAMPLE_INCIDENT_QUESTION,
    SAMPLE_SRS_TEXT,
    build_triage_result,
)


def test_sample_srs_maps_cross_domain_rules_and_builds_complex_sql():
    result = build_triage_result(SAMPLE_INCIDENT_QUESTION, SAMPLE_SRS_TEXT)

    assert len(result.domains) >= 6
    assert result.sql.count(" AS (") >= 8
    assert "UNION ALL" in result.sql
    assert "running_balance" in result.sql
    assert len(result.datahub_steps) >= 6


def test_unknown_rule_is_flagged_instead_of_inventing_an_asset():
    result = build_triage_result("Investigate", "Use lunar weather color.")

    assert result.rules[0].status == "UNMAPPED"
    assert result.rules[0].asset_urn is None
    assert result.warnings


def test_input_limits_are_enforced():
    with pytest.raises(ValueError, match="20,000"):
        build_triage_result("Investigate", "x" * 20_001)
