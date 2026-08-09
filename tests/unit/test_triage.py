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


def test_payment_settlement_rule_uses_most_specific_catalog_match():
    result = build_triage_result(
        "Investigate settlement timing",
        "Payments and settlement records reduce the invoice balance when funds settle.",
    )

    assert result.rules[0].domain == "Payments"
    assert result.rules[0].asset_urn.endswith("astervale.payments.settlements,PROD)")


def test_fully_unmapped_input_has_no_asset_referencing_outputs():
    result = build_triage_result("Investigate", "Use lunar weather color.")

    assert result.sql == ""
    assert result.validation_sql == ""
    assert result.datahub_steps == ()


def test_evidence_mode_identifies_bundled_synthetic_metadata():
    result = build_triage_result(SAMPLE_INCIDENT_QUESTION, SAMPLE_SRS_TEXT)

    assert "Bundled synthetic DataHub-shaped metadata" in result.evidence_mode


def test_running_balance_excludes_order_total_and_keeps_order_comparison_separate():
    result = build_triage_result(SAMPLE_INCIDENT_QUESTION, SAMPLE_SRS_TEXT)
    balance_sql = result.sql.split("), running_balance AS (", 1)[1].split(
        "), reconciliation_exceptions AS (", 1
    )[0]

    assert "FROM normalized_events" in balance_sql
    assert "order_total" not in balance_sql
    assert "'ORDER'" not in balance_sql
    assert "order_comparison AS (" in result.sql
    assert (
        "SELECT event_id, customer_id, event_at, amount, 'INVOICE' FROM invoice_events"
        in result.sql
    )
    assert "UNION ALL SELECT event_id, customer_id, event_at, amount, 'PAYMENT'" in result.sql
    assert "UNION ALL SELECT event_id, customer_id, event_at, amount, 'REFUND'" in result.sql


def test_more_than_twenty_rules_is_rejected():
    requirements = "\n".join(f"Unknown rule {index}" for index in range(21))

    with pytest.raises(ValueError, match="maximum of 20 rules"):
        build_triage_result("Investigate", requirements)
