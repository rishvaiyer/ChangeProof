from pathlib import Path

from changeproof.models import (
    ChangeRequest,
    ChangeType,
    Confidence,
    RegionExposure,
    RegionRisk,
    RemediationPlan,
    SqlDependency,
    SqlMatchKind,
)


def test_change_request_and_remediation_plan_round_trip() -> None:
    request = ChangeRequest(
        change_type=ChangeType.COLUMN_RENAME,
        old_column="artist_id",
        new_column="rights_holder_id",
        source_file=Path("models/staging/stg_streams.sql"),
    )
    plan = RemediationPlan(
        strategy="compatibility_alias",
        summary="Preserve the old field while dependents migrate.",
        actions=[],
        rollout_steps=["Deploy alias", "Migrate dependents"],
        rollback_steps=["Restore the previous model"],
        unresolved_risks=[],
        requires_approval=False,
        supported_automatically=True,
    )
    assert request.change_type is ChangeType.COLUMN_RENAME
    assert plan.supported_automatically is True


def test_enterprise_evidence_models_preserve_review_state() -> None:
    dependency = SqlDependency(
        schema_name="loyalty",
        object_name="usp_reconcile_customer",
        object_type="SQL_STORED_PROCEDURE",
        snippet="TRY_CONVERT(INT, customer_id)",
        match_kind=SqlMatchKind.CONVERT,
        confidence=Confidence.HIGH,
        regions=["WEST"],
        proposed_sql="TRY_CONVERT(BIGINT, customer_id)",
    )
    exposure = RegionExposure(
        region="WEST",
        asset_names=["loyalty_customer_value"],
        sql_objects=[dependency.object_name],
        owners=["loyalty-platform@astervale.demo"],
        policy_flags=["CA_PRIVACY_REVIEW"],
        risk=RegionRisk.HIGH,
    )

    assert dependency.match_kind is SqlMatchKind.CONVERT
    assert exposure.risk is RegionRisk.HIGH
    assert exposure.policy_flags == ["CA_PRIVACY_REVIEW"]
