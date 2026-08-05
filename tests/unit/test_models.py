from pathlib import Path

from changeproof.models import ChangeRequest, ChangeType, RemediationPlan


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
