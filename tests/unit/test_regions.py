from changeproof.demo import analyze_demo_change
from changeproof.models import (
    Confidence,
    LineageNode,
    MetadataEvidence,
    RegionRisk,
    SqlDependency,
    SqlMatchKind,
)
from changeproof.regions import (
    ASTERVALE_ASSET_REGIONS,
    AssetRegionMetadata,
    assess_regions,
)


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


def test_region_without_critical_customer_data_is_managed_exposure() -> None:
    evidence = analyze_demo_change(
        column="customer_id", old_type="varchar", new_type="bigint"
    ).evidence

    south = next(
        item
        for item in assess_regions(evidence, _dependencies(), ASTERVALE_ASSET_REGIONS)
        if item.region == "SOUTH"
    )

    assert south.risk is RegionRisk.MEDIUM


def test_unknown_is_omitted_when_every_dependency_is_mapped() -> None:
    evidence = analyze_demo_change(
        column="customer_id", old_type="varchar", new_type="bigint"
    ).evidence
    mapped_dependencies = tuple(item for item in _dependencies() if item.regions)

    exposures = assess_regions(evidence, mapped_dependencies, ASTERVALE_ASSET_REGIONS)

    assert "UNKNOWN" not in [item.region for item in exposures]


def test_missing_region_owner_requires_review() -> None:
    evidence = MetadataEvidence(
        source_urn="urn:li:dataset:(urn:li:dataPlatform:dbt,test.source,PROD)",
        source_field="customer_id",
        column_lineage_available=True,
        downstream=[
            LineageNode(
                urn="urn:li:dataset:(urn:li:dataPlatform:dbt,test.asset,PROD)",
                name="unowned_asset",
                entity_type="dataset",
                hop=1,
            )
        ],
        owners=["source-owner@example.com"],
        assertions_passing=True,
        metadata_age_hours=0,
    )

    exposure = assess_regions(
        evidence,
        (),
        {"unowned_asset": AssetRegionMetadata(regions=("NORTHEAST",), owners=())},
    )[0]

    assert exposure.region == "NORTHEAST"
    assert exposure.risk is RegionRisk.REVIEW
    assert "OWNER_METADATA_MISSING" in exposure.policy_flags
