from changeproof.demo import analyze_demo_change
from changeproof.models import Confidence, RegionRisk, SqlDependency, SqlMatchKind
from changeproof.regions import ASTERVALE_ASSET_REGIONS, assess_regions


def _dependencies() -> tuple[SqlDependency, ...]:
    return (
        SqlDependency(
            schema_name="loyalty",
            object_name="usp_reconcile_loyalty_customer",
            object_type="SQL_STORED_PROCEDURE",
            snippet="TRY_CONVERT(INT, customer_id)",
            match_kind=SqlMatchKind.CONVERT,
            confidence=Confidence.HIGH,
            regions=["WEST", "NORTHEAST"],
        ),
        SqlDependency(
            schema_name="exports",
            object_name="usp_export_customer_segments",
            object_type="SQL_STORED_PROCEDURE",
            snippet="EXEC sp_executesql",
            match_kind=SqlMatchKind.DYNAMIC_SQL,
            confidence=Confidence.LOW,
            regions=[],
            manual_review_reason="Contains dynamic SQL.",
        ),
    )


def test_regions_include_national_operating_areas_and_unknown() -> None:
    evidence = analyze_demo_change(
        column="customer_id", old_type="varchar", new_type="bigint"
    ).evidence

    exposures = assess_regions(evidence, _dependencies(), ASTERVALE_ASSET_REGIONS)

    assert [item.region for item in exposures] == [
        "NORTHEAST",
        "SOUTH",
        "MIDWEST",
        "WEST",
        "UNKNOWN",
    ]


def test_west_customer_data_exposure_is_high_risk() -> None:
    evidence = analyze_demo_change(
        column="customer_id", old_type="varchar", new_type="bigint"
    ).evidence

    west = next(
        item
        for item in assess_regions(evidence, _dependencies(), ASTERVALE_ASSET_REGIONS)
        if item.region == "WEST"
    )

    assert west.risk is RegionRisk.HIGH
    assert "CA_PRIVACY_REVIEW" in west.policy_flags
    assert "loyalty-platform@astervale.demo" in west.owners


def test_unknown_dynamic_sql_requires_review() -> None:
    evidence = analyze_demo_change(
        column="customer_id", old_type="varchar", new_type="bigint"
    ).evidence

    unknown = next(
        item
        for item in assess_regions(evidence, _dependencies(), ASTERVALE_ASSET_REGIONS)
        if item.region == "UNKNOWN"
    )

    assert unknown.risk is RegionRisk.REVIEW
    assert "REGION_METADATA_MISSING" in unknown.policy_flags
