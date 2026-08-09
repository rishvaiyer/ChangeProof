from changeproof.models import Confidence, SqlMatchKind
from changeproof.sql_impact import SqlModule, analyze_sql_modules, build_discovery_query


def test_discovery_query_is_read_only_and_searches_system_modules() -> None:
    query = build_discovery_query("customer_id")

    assert "sys.sql_modules" in query
    assert "sys.objects" in query
    assert "@column_name" in query
    assert all(token not in query.upper() for token in ("UPDATE ", "DELETE ", "DROP "))


def test_static_convert_generates_a_bigint_fix() -> None:
    findings = analyze_sql_modules("customer_id", "varchar", "bigint")
    match = next(
        item
        for item in findings
        if item.object_name == "usp_reconcile_loyalty_customer"
    )

    assert match.match_kind is SqlMatchKind.CONVERT
    assert match.confidence is Confidence.HIGH
    assert "TRY_CONVERT(BIGINT, customer_id)" in (match.proposed_sql or "")


def test_dynamic_sql_is_flagged_for_manual_review() -> None:
    findings = analyze_sql_modules("customer_id", "varchar", "bigint")
    match = next(
        item for item in findings if item.object_name == "usp_export_customer_segments"
    )

    assert match.match_kind is SqlMatchKind.DYNAMIC_SQL
    assert match.proposed_sql is None
    assert "dynamic SQL" in (match.manual_review_reason or "")


def test_join_without_a_semantic_rewrite_is_manual_review() -> None:
    findings = analyze_sql_modules("customer_id", "varchar", "bigint")
    match = next(
        item for item in findings if item.object_name == "usp_match_regional_returns"
    )

    assert match.match_kind is SqlMatchKind.JOIN
    assert match.proposed_sql is None
    assert "join operands" in (match.manual_review_reason or "")


def test_unrelated_column_has_no_hidden_dependencies() -> None:
    assert analyze_sql_modules("artist_id", "varchar", "bigint") == ()


def test_qualified_convert_is_rewritten_and_reparsed() -> None:
    modules = (
        SqlModule(
            schema_name="loyalty",
            object_name="usp_qualified_customer",
            object_type="SQL_STORED_PROCEDURE",
            definition=(
                "SELECT t.customer_id FROM loyalty.members t "
                "WHERE CONVERT(INT, t.customer_id) = @customer_id;"
            ),
            regions=("WEST",),
        ),
    )

    finding = analyze_sql_modules(
        "customer_id", "varchar", "bigint", modules=modules
    )[0]

    assert finding.proposed_sql is not None
    assert "TRY_CONVERT(BIGINT, t.customer_id)" in finding.proposed_sql
    assert finding.manual_review_reason is None
