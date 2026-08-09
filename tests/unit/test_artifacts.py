import json
from dataclasses import replace

from changeproof.artifacts import build_artifacts
from changeproof.enterprise import analyze_enterprise_change


def test_artifact_bundle_contains_json_sql_and_sarif() -> None:
    bundle = analyze_enterprise_change(
        column="customer_id", old_type="varchar", new_type="bigint"
    ).artifacts

    assert bundle is not None
    report = json.loads(bundle.impact_report_json)
    sarif = json.loads(bundle.sarif_json)
    assert report["company"] == "AsterVale Living"
    assert report["change"]["column"] == "customer_id"
    assert report["evidence"]["datahub_assets"] == 4
    assert "sys.sql_modules" in bundle.discovery_query_sql
    assert "TRY_CONVERT(BIGINT, customer_id)" in bundle.proposed_fixes_sql
    assert "usp_export_customer_segments" in bundle.proposed_fixes_sql
    assert "MANUAL REVIEW" in bundle.proposed_fixes_sql
    assert "COUNT_BIG" in bundle.validation_queries_sql
    assert "ROLLBACK" in bundle.rollback_sql
    assert sarif["version"] == "2.1.0"
    assert len(sarif["runs"][0]["results"]) == 4


def test_artifacts_are_deterministic() -> None:
    first = analyze_enterprise_change(
        column="customer_id", old_type="varchar", new_type="bigint"
    ).artifacts
    second = analyze_enterprise_change(
        column="customer_id", old_type="varchar", new_type="bigint"
    ).artifacts

    assert first == second


def test_validation_sql_uses_the_validated_proposed_type() -> None:
    analysis = analyze_enterprise_change(
        column="customer_id", old_type="varchar", new_type="bigint"
    )
    request = analysis.request.model_copy(update={"new_type": "decimal(18,4)"})

    bundle = build_artifacts(replace(analysis, request=request))

    assert "TRY_CONVERT(DECIMAL(18,4), customer_id)" in bundle.validation_queries_sql
