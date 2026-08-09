from changeproof.enterprise import analyze_enterprise_change


def test_enterprise_analysis_composes_datahub_sql_and_regions() -> None:
    result = analyze_enterprise_change(
        column="customer_id", old_type="varchar", new_type="bigint"
    )

    assert result.company_name == "AsterVale Living"
    assert result.evidence_source == "Bundled AsterVale Living DataHub metadata"
    assert len(result.impact.impacted_assets) == 4
    assert len(result.sql_dependencies) == 4
    assert len(result.region_exposures) == 5
    assert result.artifacts is not None


def test_enterprise_provider_keeps_legacy_scenario_compatible() -> None:
    result = analyze_enterprise_change(
        column="artist_id", old_type="varchar", new_type="bigint"
    )

    assert result.company_name == "SonicLedger"
    assert result.sql_dependencies == ()
    assert result.region_exposures == ()
    assert result.artifacts is None
