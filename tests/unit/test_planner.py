from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from changeproof.models import ChangeRequest, ChangeType, Confidence, ImpactAssessment
from changeproof.planner import plan_remediation


def _type_change_request() -> ChangeRequest:
    return ChangeRequest(
        change_type=ChangeType.COLUMN_TYPE_CHANGE,
        dataset_urn="urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models.staging.stg_streams,PROD)",
        old_column="artist_id",
        new_column="artist_id",
        old_type="varchar",
        new_type="bigint",
        source_file=Path("models/staging/stg_streams.sql"),
    )


def _unsupported_request() -> ChangeRequest:
    return ChangeRequest(
        change_type=ChangeType.UNSUPPORTED,
        dataset_urn="urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models.staging.stg_streams,PROD)",
        source_file=Path("models/staging/stg_streams.sql"),
    )


def test_rename_plan_contains_rollout_rollback_and_actions(
    rename_request: Callable[..., ChangeRequest],
    complete_impact: Callable[[], ImpactAssessment],
) -> None:
    plan = plan_remediation(rename_request(), complete_impact())

    assert plan.strategy == "compatibility_alias"
    assert plan.supported_automatically is True
    assert plan.requires_approval is False
    assert plan.rollout_steps
    assert plan.rollback_steps
    assert len(plan.actions) == 2
    assert plan.actions[0].asset_name == "fct_royalties"
    assert plan.actions[0].owner == "finance@sonicledger.demo"
    assert plan.actions[0].validation_checks


def test_rename_plan_stays_review_required_when_evidence_is_not_high_confidence(
    rename_request: Callable[..., ChangeRequest],
    complete_impact: Callable[[], ImpactAssessment],
) -> None:
    impact = complete_impact().model_copy(
        update={
            "confidence": Confidence.MEDIUM,
            "reasons": ["Only table lineage was observed."],
            "required_reviewers": ["analytics@sonicledger.demo"],
        }
    )

    plan = plan_remediation(rename_request(), impact)

    assert plan.supported_automatically is False
    assert plan.requires_approval is True
    assert "review" in plan.summary.lower()
    assert plan.unresolved_risks


def test_removal_plan_is_specific_but_requires_approval(
    removal_request: Callable[..., ChangeRequest],
    complete_impact: Callable[[], ImpactAssessment],
) -> None:
    plan = plan_remediation(removal_request(), complete_impact())

    assert "deprecation" in plan.strategy
    assert plan.supported_automatically is False
    assert plan.requires_approval is True
    assert plan.unresolved_risks
    assert all(action.validation_checks for action in plan.actions)


def test_type_change_plan_uses_parallel_field_strategy(
    complete_impact: Callable[[], ImpactAssessment],
) -> None:
    plan = plan_remediation(_type_change_request(), complete_impact())

    assert plan.strategy == "parallel_typed_field"
    assert plan.supported_automatically is False
    assert plan.requires_approval is True
    assert any("safe cast" in action.action.lower() for action in plan.actions)
    assert any("backfill" in step.lower() for step in plan.rollout_steps)


def test_unsupported_plan_calls_for_manual_review(
    complete_impact: Callable[[], ImpactAssessment],
) -> None:
    plan = plan_remediation(_unsupported_request(), complete_impact())

    assert plan.strategy == "manual_review_required"
    assert plan.supported_automatically is False
    assert plan.requires_approval is True
    assert "manual review" in plan.summary.lower()
    assert plan.rollback_steps
