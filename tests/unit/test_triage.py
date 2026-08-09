import pytest

from changeproof.triage import (
    SAMPLE_INCIDENT_QUESTION,
    SAMPLE_SRS_TEXT,
    build_triage_result,
    triage_export_text,
)


def test_sample_srs_maps_cross_domain_rules_and_builds_complex_sql():
    result = build_triage_result(SAMPLE_INCIDENT_QUESTION, SAMPLE_SRS_TEXT)

    assert len(result.domains) >= 6
    assert result.sql.count(" AS (") >= 8
    assert "UNION ALL" in result.sql
    assert "running_balance" in result.sql
    assert len(result.datahub_steps) >= 6
    assert "'INVOICE' AS event_type" in result.sql
    for event_type in ("ORDER", "INVOICE", "PAYMENT", "REFUND", "FULFILLMENT"):
        assert f"'{event_type}' AS event_type" in result.sql
    assert "affects_ar" in result.sql
    assert "ORDER_INVOICE_MISMATCH" in result.sql
    assert "AR_BALANCE_EXCEPTION" in result.sql
    assert "MISSING_JOIN" in result.sql
    assert "LEFT JOIN finance.ar_transactions AS a" in result.sql
    assert "LEFT JOIN commerce.orders AS o" in result.sql
    assert "LEFT JOIN customer_scope AS c" in result.sql


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


def test_running_balance_includes_the_full_timeline_but_sums_only_financial_events():
    result = build_triage_result(SAMPLE_INCIDENT_QUESTION, SAMPLE_SRS_TEXT)
    balance_sql = result.sql.split("), running_balance AS (", 1)[1].split(
        "), order_invoice_mismatches AS (", 1
    )[0]

    assert "FROM normalized_events" in balance_sql
    assert "CASE WHEN affects_ar = 1 THEN amount" in balance_sql
    assert "event_type" in balance_sql
    assert "order_comparison AS (" in result.sql
    assert (
        "SELECT event_id, customer_id, event_at, amount, 'INVOICE' AS event_type, 1 AS affects_ar"
        in result.sql
    )
    assert "'PAYMENT' AS event_type, 1 AS affects_ar" in result.sql
    assert "'REFUND' AS event_type, 1 AS affects_ar" in result.sql


def test_order_comparison_uses_order_id_and_feeds_final_mismatch_results():
    result = build_triage_result(SAMPLE_INCIDENT_QUESTION, SAMPLE_SRS_TEXT)
    finance_rule = next(rule for rule in result.rules if rule.domain == "Finance")

    assert "order_id" in finance_rule.columns
    assert "a.order_id," in result.sql
    assert "LEFT JOIN invoice_events AS a ON a.order_id = o.order_id" in result.sql
    assert "order_invoice_mismatches AS (" in result.sql
    assert "'ORDER_INVOICE_MISMATCH'" in result.sql
    assert "FROM order_comparison" in result.sql
    assert "final_results AS (" in result.sql
    assert "LEFT JOIN order_invoice_mismatches" in result.sql
    assert "issue_label" in result.sql


def test_commerce_only_triage_emits_only_commerce_evidence_previews():
    result = build_triage_result("Investigate order totals", "Compare commerce order totals.")

    assert result.domains == ("Commerce",)
    assert "FROM commerce.orders" in result.sql
    assert "order_id, customer_id, ordered_at, order_total" in result.sql
    assert "Commerce Data" in result.datahub_steps[0].query_decision
    assert "Order lifecycle" in result.datahub_steps[0].query_decision
    for unexpected in (
        "finance.ar_transactions",
        "payments.settlements",
        "commerce.returns_refunds",
        "fulfillment.shipments",
        "identity.customers",
        "policy.regional_ar_rules",
    ):
        assert unexpected not in result.sql
        assert unexpected not in result.validation_sql
        assert unexpected not in "\n".join(step.query_decision for step in result.datahub_steps)


def test_hosted_steps_identify_bundled_lookups_not_live_retrievals():
    result = build_triage_result("Investigate order totals", "Compare commerce order totals.")

    assert result.datahub_steps[0].operation.startswith("Bundled context lookup #1")
    assert "Bundled catalog discovery" in result.datahub_steps[0].query_decision
    assert "retrieval" not in result.datahub_steps[0].operation.casefold()


def test_triage_text_export_uses_contextiskey_branding_and_project_lineage():
    result = build_triage_result("Investigate order totals", "Compare commerce.")
    export = triage_export_text(result)

    assert export.startswith("contextIsKey TRIAGE COMPOSER")
    assert "DataHub context layer" in export


def test_more_than_twenty_rules_is_rejected():
    requirements = "\n".join(f"Unknown rule {index}" for index in range(21))

    with pytest.raises(ValueError, match="maximum of 20 rules"):
        build_triage_result("Investigate", requirements)
